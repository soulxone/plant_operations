"""Hook implementations for ERPNext doc_events."""
import frappe
from frappe.utils import cint


def on_sales_order_submit(doc, method):
    """When a Sales Order is submitted, auto-create Pallet records.

    Only creates if the SO has items linked to corrugated estimates
    or if items are in the 'Corrugated Boxes' item group.
    """
    try:
        settings = frappe.get_single("Plant Operations Settings")
        bpp = cint(settings.default_pallet_max_weight) or 40  # boxes per pallet default

        for item in doc.items:
            # Check if item is a corrugated box (item group check)
            item_group = frappe.db.get_value("Item", item.item_code, "item_group")
            if item_group and "Corrugated" in (item_group or ""):
                qty = cint(item.qty)
                num_pallets = max(1, -(-qty // bpp))

                for i in range(num_pallets):
                    pallet_qty = min(bpp, qty - i * bpp)
                    if pallet_qty <= 0:
                        break

                    frappe.get_doc({
                        "doctype": "Pallet",
                        "sales_order": doc.name,
                        "customer": doc.customer,
                        "item_code": item.item_code,
                        "item_name": item.item_name,
                        "quantity": pallet_qty,
                        "warehouse": settings.default_warehouse,
                        "status": "Created",
                    }).insert(ignore_permissions=True)

        frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"Plant Operations: Failed to create pallets for {doc.name}: {e}")


def on_job_card_update(doc, method):
    """When a Job Card is updated, sync status to any linked Production Entry."""
    try:
        entries = frappe.get_all("Production Entry",
            filters={"job_card": doc.name, "docstatus": 0},
            pluck="name",
        )
        if doc.status == "Completed":
            for entry_name in entries:
                entry = frappe.get_doc("Production Entry", entry_name)
                if entry.status in ("Running", "Paused"):
                    entry.status = "Complete"
                    entry.end_time = frappe.utils.now_datetime()
                    entry.save(ignore_permissions=True)
            frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"Plant Operations: Job Card sync failed for {doc.name}: {e}")


def on_delivery_note_submit(doc, method):
    """When a Delivery Note is submitted, update linked Load Tag status."""
    try:
        # Find Load Tags linked to this DN
        load_tags = frappe.get_all("Load Tag",
            filters={"delivery_note": doc.name, "status": ["in", ["Building", "Sealed"]]},
            pluck="name",
        )
        for lt_name in load_tags:
            frappe.db.set_value("Load Tag", lt_name, "status", "In Transit")

        frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"Plant Operations: Failed to update load tags for DN {doc.name}: {e}")
