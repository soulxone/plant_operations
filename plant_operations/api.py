"""Plant Operations API — Whitelisted endpoints for receiving, shipping, GPS, labels."""
import frappe
from frappe.utils import now_datetime, today, flt, cint


# ═══════════════════════════════════════════════════════════════════════════
#  PALLET & LOAD TAG OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════

@frappe.whitelist()
def scan_pallet(pallet_name, action="locate", zone=None, warehouse=None):
    """Scan a pallet barcode — update location, timestamp, user.

    Actions: locate (update zone), stage, load, ship, deliver
    """
    pallet = frappe.get_doc("Pallet", pallet_name)
    pallet.last_scan_time = now_datetime()
    pallet.last_scan_by = frappe.session.user

    if zone:
        pallet.zone = zone
    if warehouse:
        pallet.warehouse = warehouse

    status_map = {
        "locate": None,  # just update location
        "stage": "Staged",
        "load": "Loaded",
        "ship": "Shipped",
        "deliver": "Delivered",
    }
    new_status = status_map.get(action)
    if new_status:
        pallet.status = new_status

    pallet.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "pallet": pallet.name,
        "pallet_status": pallet.status,
        "zone": pallet.zone,
        "scan_time": str(pallet.last_scan_time),
    }


@frappe.whitelist()
def add_pallet_to_load(load_tag_name, pallet_name):
    """Add a pallet to a load tag by scanning."""
    load = frappe.get_doc("Load Tag", load_tag_name)
    if load.status not in ("Building",):
        frappe.throw(f"Load {load_tag_name} is {load.status} — can only add pallets to Building loads.")

    # Check pallet isn't already on another load
    existing = frappe.db.get_value("Load Pallet", {"pallet": pallet_name, "parent": ["!=", ""]}, "parent")
    if existing and existing != load_tag_name:
        frappe.throw(f"Pallet {pallet_name} is already on load {existing}.")

    # Check not already on this load
    for row in load.load_pallets:
        if row.pallet == pallet_name:
            return {"status": "already_on_load", "message": f"Pallet {pallet_name} already on this load."}

    load.append("load_pallets", {"pallet": pallet_name})
    load.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "load": load_tag_name,
        "pallet": pallet_name,
        "total_pallets": load.total_pallets,
        "total_pieces": load.total_pieces,
        "total_weight": load.total_weight,
    }


@frappe.whitelist()
def create_pallets_from_so(sales_order_name, boxes_per_pallet=40):
    """Auto-create Pallet records from a Sales Order's items."""
    so = frappe.get_doc("Sales Order", sales_order_name)
    bpp = cint(boxes_per_pallet) or 40
    created = []

    for item in so.items:
        qty = cint(item.qty)
        num_pallets = max(1, -(-qty // bpp))  # ceiling division

        for i in range(num_pallets):
            pallet_qty = min(bpp, qty - i * bpp)
            if pallet_qty <= 0:
                break

            pallet = frappe.get_doc({
                "doctype": "Pallet",
                "sales_order": so.name,
                "customer": so.customer,
                "item_code": item.item_code,
                "item_name": item.item_name,
                "quantity": pallet_qty,
                "status": "Created",
            })
            pallet.insert(ignore_permissions=True)
            created.append(pallet.name)

    frappe.db.commit()
    return {
        "status": "success",
        "pallets_created": len(created),
        "pallet_names": created,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  LABEL PRINTING
# ═══════════════════════════════════════════════════════════════════════════

@frappe.whitelist()
def print_pallet_label(pallet_name, mode="pdf"):
    """Generate pallet tag label (ZPL or PDF).

    mode: 'zpl' for Zebra direct, 'pdf' for browser PDF
    """
    from plant_operations.plant_operations.label_printer import generate_pallet_label
    return generate_pallet_label(pallet_name, mode)


@frappe.whitelist()
def print_load_label(load_tag_name, mode="pdf"):
    """Generate load tag label (ZPL or PDF)."""
    from plant_operations.plant_operations.label_printer import generate_load_label
    return generate_load_label(load_tag_name, mode)


# ═══════════════════════════════════════════════════════════════════════════
#  RECEIVING
# ═══════════════════════════════════════════════════════════════════════════

@frappe.whitelist()
def pull_po_items(purchase_order_name):
    """Fetch items from a Purchase Order for receiving."""
    po = frappe.get_doc("Purchase Order", purchase_order_name)
    items = []
    for row in po.items:
        items.append({
            "item_code": row.item_code,
            "item_name": row.item_name,
            "ordered_qty": row.qty,
            "received_qty": row.qty,  # default to full receipt
            "uom": row.uom,
            "warehouse": row.warehouse,
        })
    return items


@frappe.whitelist()
def create_purchase_receipt_from_receiving(receiving_log_name):
    """Create ERPNext Purchase Receipt from a Receiving Log."""
    rl = frappe.get_doc("Receiving Log", receiving_log_name)

    if not rl.purchase_order:
        frappe.throw("Receiving Log must be linked to a Purchase Order.")

    pr = frappe.new_doc("Purchase Receipt")
    pr.supplier = rl.supplier
    pr.company = frappe.defaults.get_global_default("company")

    for item in rl.receiving_items:
        if flt(item.received_qty) <= 0:
            continue
        pr.append("items", {
            "item_code": item.item_code,
            "qty": item.received_qty,
            "rejected_qty": flt(item.rejected_qty),
            "uom": item.uom,
            "warehouse": item.warehouse,
            "purchase_order": rl.purchase_order,
            "batch_no": item.batch_no,
        })

    if not pr.items:
        frappe.throw("No items with received quantity > 0.")

    pr.insert(ignore_permissions=True)
    pr.submit()

    # Link back
    frappe.db.set_value("Receiving Log", receiving_log_name, "status", "Put Away")
    frappe.db.commit()

    return {
        "status": "success",
        "purchase_receipt": pr.name,
        "message": f"Purchase Receipt {pr.name} created.",
    }


# ═══════════════════════════════════════════════════════════════════════════
#  SHIPPING
# ═══════════════════════════════════════════════════════════════════════════

@frappe.whitelist()
def create_delivery_note_from_shipment(shipment_name):
    """Create ERPNext Delivery Note from a Shipment."""
    ship = frappe.get_doc("Shipment", shipment_name)

    if not ship.customer:
        frappe.throw("Shipment must have a customer.")

    dn = frappe.new_doc("Delivery Note")
    dn.customer = ship.customer
    dn.company = frappe.defaults.get_global_default("company")

    if ship.sales_order:
        so = frappe.get_doc("Sales Order", ship.sales_order)
        for item in so.items:
            dn.append("items", {
                "item_code": item.item_code,
                "qty": item.qty,
                "uom": item.uom,
                "against_sales_order": ship.sales_order,
                "so_detail": item.name,
                "warehouse": item.warehouse,
            })

    dn.insert(ignore_permissions=True)

    # Link back
    frappe.db.set_value("Shipment", shipment_name, {
        "delivery_note": dn.name,
        "status": "Shipped",
    })
    frappe.db.commit()

    return {
        "status": "success",
        "delivery_note": dn.name,
        "message": f"Delivery Note {dn.name} created.",
    }


# ═══════════════════════════════════════════════════════════════════════════
#  GPS TRACKING
# ═══════════════════════════════════════════════════════════════════════════

@frappe.whitelist(allow_guest=True)
def log_gps_position(load_tag, latitude, longitude,
                      speed_mph=0, heading=0, accuracy_meters=0,
                      source="Driver App"):
    """Log a GPS position for a load tag (called from driver app)."""
    from plant_operations.plant_operations.gps_tracker import log_position
    return log_position(load_tag, latitude, longitude,
                         speed_mph, heading, accuracy_meters, source)


@frappe.whitelist()
def get_active_fleet():
    """Get all In Transit loads with latest GPS position for fleet map."""
    from plant_operations.plant_operations.gps_tracker import get_fleet_positions
    return get_fleet_positions()


@frappe.whitelist()
def get_load_track_history(load_tag_name):
    """Get full GPS track history for a load."""
    points = frappe.get_all("GPS Track Point",
        filters={"load_tag": load_tag_name},
        fields=["timestamp", "latitude", "longitude", "speed_mph", "heading"],
        order_by="timestamp asc",
        limit_page_length=1000,
    )
    return points


@frappe.whitelist()
def get_google_api_key():
    """Get Google Maps API key from Plant Operations Settings or Delivery Settings."""
    key = frappe.db.get_single_value("Plant Operations Settings", "google_api_key")
    if key:
        return key
    # Fallback to customer_map's Delivery Settings
    try:
        key = frappe.db.get_single_value("Delivery Settings", "google_api_key")
    except Exception:
        pass
    if key:
        return key
    return frappe.conf.get("google_api_key", "")
