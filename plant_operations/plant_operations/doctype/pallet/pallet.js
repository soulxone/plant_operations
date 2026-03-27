// Copyright (c) 2026, Plant Operations and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pallet", {
	refresh(frm) {
		// Status indicator colors
		const status_colors = {
			"Created": "blue",
			"In Production": "orange",
			"Staged": "yellow",
			"Loaded": "purple",
			"Shipped": "cyan",
			"Delivered": "green"
		};
		if (frm.doc.status) {
			frm.page.set_indicator(frm.doc.status, status_colors[frm.doc.status] || "grey");
		}

		// Print Pallet Tag button
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Print Pallet Tag"), function () {
				frappe.call({
					method: "plant_operations.api.print_pallet_label",
					args: { pallet_name: frm.doc.name },
					callback: function (r) {
						if (r.message) {
							frappe.msgprint(__("Pallet tag sent to printer."));
							frm.reload_doc();
						}
					}
				});
			});
		}
	}
});
