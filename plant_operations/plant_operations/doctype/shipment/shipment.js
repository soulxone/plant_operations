// Copyright (c) 2026, Plant Operations and contributors
// For license information, please see license.txt

frappe.ui.form.on("Shipment", {
	refresh(frm) {
		// Status indicator colors
		const status_colors = {
			"Planning": "blue",
			"Picking": "orange",
			"Staging": "yellow",
			"Loading": "purple",
			"Shipped": "cyan",
			"Delivered": "green"
		};
		if (frm.doc.status) {
			frm.page.set_indicator(frm.doc.status, status_colors[frm.doc.status] || "grey");
		}

		if (frm.doc.docstatus === 1) {
			// Create Delivery Note button
			if (!frm.doc.delivery_note) {
				frm.add_custom_button(__("Create Delivery Note"), function () {
					frappe.call({
						method: "plant_operations.api.create_delivery_note_from_shipment",
						args: { shipment_name: frm.doc.name },
						callback: function (r) {
							if (r.message) {
								frappe.msgprint(__("Delivery Note {0} created.", [r.message]));
								frm.reload_doc();
							}
						}
					});
				});
			}

			// Mark Delivered button
			if (frm.doc.status !== "Delivered") {
				frm.add_custom_button(__("Mark Delivered"), function () {
					frappe.confirm(
						__("Mark this shipment as delivered?"),
						function () {
							frappe.call({
								method: "frappe.client.set_value",
								args: {
									doctype: "Shipment",
									name: frm.doc.name,
									fieldname: {
										status: "Delivered",
										delivered_date: frappe.datetime.now_datetime()
									}
								},
								callback: function () {
									frm.reload_doc();
								}
							});
						}
					);
				}, __("Actions"));
			}
		}
	}
});
