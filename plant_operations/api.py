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


# ═══════════════════════════════════════════════════════════════════════════
#  MES — SHOP FLOOR MANUFACTURING EXECUTION
# ═══════════════════════════════════════════════════════════════════════════

@frappe.whitelist()
def start_production(machine, job_card=None, sales_order=None, planned_qty=0):
    """Start a production run on a machine."""
    from plant_operations.plant_operations.mes import start_production as _start
    return _start(machine, job_card, sales_order, planned_qty)


@frappe.whitelist()
def pause_production(entry):
    """Pause a running production entry (creates downtime event)."""
    from plant_operations.plant_operations.mes import pause_production as _pause
    return _pause(entry)


@frappe.whitelist()
def resume_production(entry):
    """Resume a paused production entry."""
    from plant_operations.plant_operations.mes import resume_production as _resume
    return _resume(entry)


@frappe.whitelist()
def stop_production(entry, good_qty=0, waste_qty=0, reject_qty=0):
    """Stop production — finalize counts, calculate OEE."""
    from plant_operations.plant_operations.mes import stop_production as _stop
    return _stop(entry, good_qty, waste_qty, reject_qty)


@frappe.whitelist()
def get_machine_status(machine):
    """Get current production status of a machine."""
    from plant_operations.plant_operations.mes import get_machine_status as _status
    return _status(machine)


@frappe.whitelist()
def get_plant_dashboard():
    """Get status of ALL machines for plant overview."""
    from plant_operations.plant_operations.mes import get_plant_dashboard as _dash
    return _dash()


@frappe.whitelist()
def update_production_count(entry, good_qty=0, waste_qty=0):
    """Live count update from shop floor terminal (no stop)."""
    doc = frappe.get_doc("Production Entry", entry)
    doc.good_qty = cint(good_qty)
    doc.waste_qty = cint(waste_qty)
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "updated", "good_qty": doc.good_qty, "waste_qty": doc.waste_qty, "oee_pct": doc.oee_pct}


@frappe.whitelist()
def update_count(entry, field, value):
    """Update a single count field from the shop floor numpad."""
    from plant_operations.plant_operations.mes import update_count as _update
    return _update(entry, field, cint(value))


@frappe.whitelist()
def log_downtime(entry, reason, notes=None):
    """Log a downtime event from the shop floor terminal."""
    from plant_operations.plant_operations.mes import log_downtime as _log
    return _log(entry, reason, notes)


# ═══════════════════════════════════════════════════════════════════════════
#  QUALITY CONTROL
# ═══════════════════════════════════════════════════════════════════════════

@frappe.whitelist()
def create_ncr_from_inspection(inspection_name):
    """Create a Non-Conformance Report from a failed QC Inspection."""
    from plant_operations.plant_operations.qc import create_ncr_from_inspection as _ncr
    return _ncr(inspection_name)


@frappe.whitelist()
def get_qc_summary(date_from=None, date_to=None):
    """Get QC summary stats for dashboard."""
    from plant_operations.plant_operations.qc import get_qc_summary as _qc
    return _qc(date_from, date_to)


# ═══════════════════════════════════════════════════════════════════════════
#  PRODUCTION SCHEDULING
# ═══════════════════════════════════════════════════════════════════════════

@frappe.whitelist()
def get_schedule_board(date=None):
    """Get all machines with schedule items for the Production Board."""
    from plant_operations.plant_operations.scheduler import get_schedule_board as _board
    return _board(date)


@frappe.whitelist()
def auto_schedule(date=None, strategy="earliest_due"):
    """Auto-assign unscheduled Job Cards to machines."""
    from plant_operations.plant_operations.scheduler import auto_schedule as _auto
    return _auto(date, strategy)


@frappe.whitelist()
def get_capacity_summary(date_from=None, date_to=None):
    """Get planned vs available capacity per machine."""
    from plant_operations.plant_operations.scheduler import get_capacity_summary as _cap
    return _cap(date_from, date_to)


@frappe.whitelist()
def reorder_schedule(schedule_name, new_order):
    """Reorder schedule items (drag-and-drop from Production Board)."""
    import json
    order = json.loads(new_order) if isinstance(new_order, str) else new_order
    sched = frappe.get_doc("Production Schedule", schedule_name)
    for item in sched.schedule_items:
        if item.name in order:
            item.sequence = order[item.name]
    sched.schedule_items.sort(key=lambda x: x.sequence)
    sched.save(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "reordered", "schedule": schedule_name}


@frappe.whitelist()
def auto_fill_schedule(schedule_name, machine, date=None):
    """Auto-fill a Production Schedule with unscheduled Job Cards for its machine."""
    from plant_operations.plant_operations.scheduler import auto_fill_for_schedule as _fill
    return _fill(schedule_name, machine, date)


@frappe.whitelist()
def auto_schedule_jobs(date=None, strategy="earliest_due"):
    """Auto-schedule unassigned Job Cards (alias for Production Board button)."""
    from plant_operations.plant_operations.scheduler import auto_schedule as _auto
    return _auto(date, strategy)


@frappe.whitelist()
def start_schedule_job(schedule_name, item_name):
    """Start a schedule item — mark Running, create Production Entry."""
    from plant_operations.plant_operations.scheduler import start_schedule_job as _start
    return _start(schedule_name, item_name)


@frappe.whitelist()
def complete_schedule_job(schedule_name, item_name):
    """Complete a schedule item — mark Complete, update schedule status."""
    from plant_operations.plant_operations.scheduler import complete_schedule_job as _complete
    return _complete(schedule_name, item_name)


# ═══════════════════════════════════════════════════════════════════════════
#  ANALYTICS DASHBOARDS
# ═══════════════════════════════════════════════════════════════════════════

@frappe.whitelist()
def get_oee_dashboard(date_from=None, date_to=None, machine=None):
    from plant_operations.plant_operations.analytics import get_oee_dashboard as _oee
    return _oee(date_from, date_to, machine)


@frappe.whitelist()
def get_profitability_dashboard(date_from=None, date_to=None):
    from plant_operations.plant_operations.analytics import get_profitability_dashboard as _prof
    return _prof(date_from, date_to)


@frappe.whitelist()
def get_waste_dashboard(date_from=None, date_to=None, machine=None):
    from plant_operations.plant_operations.analytics import get_waste_dashboard as _waste
    return _waste(date_from, date_to, machine)


@frappe.whitelist()
def get_quality_dashboard(date_from=None, date_to=None):
    from plant_operations.plant_operations.analytics import get_quality_dashboard as _qual
    return _qual(date_from, date_to)
