// Copyright (c) 2026, Plant Operations and contributors
// For license information, please see license.txt

frappe.ui.form.on("Receiving Log", {
	refresh(frm) {
		// Status indicator colors
		const status_colors = {
			"Draft": "red",
			"Received": "blue",
			"Inspected": "orange",
			"Put Away": "green",
			"Rejected": "darkgrey"
		};
		if (frm.doc.status) {
			frm.page.set_indicator(frm.doc.status, status_colors[frm.doc.status] || "grey");
		}

		// Pull from PO button (before submit)
		if (frm.doc.docstatus === 0 && frm.doc.purchase_order) {
			frm.add_custom_button(__("Pull from PO"), function () {
				frappe.call({
					method: "frappe.client.get",
					args: {
						doctype: "Purchase Order",
						name: frm.doc.purchase_order
					},
					callback: function (r) {
						if (r.message && r.message.items) {
							frm.clear_table("receiving_items");
							r.message.items.forEach(function (item) {
								let row = frm.add_child("receiving_items");
								row.item_code = item.item_code;
								row.item_name = item.item_name;
								row.ordered_qty = item.qty;
								row.received_qty = item.qty;
								row.uom = item.uom;
								row.warehouse = item.warehouse;
							});
							frm.refresh_field("receiving_items");
							frappe.msgprint(__("Items pulled from Purchase Order."));
						}
					}
				});
			});
		}

		// Create Purchase Receipt button (after submit)
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Create Purchase Receipt"), function () {
				frappe.call({
					method: "plant_operations.api.create_purchase_receipt_from_receiving",
					args: { receiving_log_name: frm.doc.name },
					callback: function (r) {
						if (r.message) {
							frappe.msgprint(__("Purchase Receipt {0} created.", [r.message]));
							frm.reload_doc();
						}
					}
				});
			});
		}
	}
});
