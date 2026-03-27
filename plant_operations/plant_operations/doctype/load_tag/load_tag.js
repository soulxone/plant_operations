// Copyright (c) 2026, Plant Operations and contributors
// For license information, please see license.txt

frappe.ui.form.on("Load Tag", {
	refresh(frm) {
		// Status indicator colors
		const status_colors = {
			"Building": "blue",
			"Sealed": "orange",
			"In Transit": "purple",
			"Delivered": "green"
		};
		if (frm.doc.status) {
			frm.page.set_indicator(frm.doc.status, status_colors[frm.doc.status] || "grey");
		}

		// Show totals in dashboard
		if (frm.doc.total_pallets) {
			frm.dashboard.add_indicator(
				__("Pallets: {0} | Weight: {1} lbs | Pieces: {2}",
					[frm.doc.total_pallets, frm.doc.total_weight, frm.doc.total_pieces]),
				"blue"
			);
		}

		if (frm.doc.docstatus === 1) {
			// Print Load Tag button
			frm.add_custom_button(__("Print Load Tag"), function () {
				frappe.call({
					method: "plant_operations.api.print_load_tag_label",
					args: { load_tag_name: frm.doc.name },
					callback: function (r) {
						if (r.message) {
							frappe.msgprint(__("Load tag sent to printer."));
							frm.reload_doc();
						}
					}
				});
			});

			// Seal Load button (only if Building)
			if (frm.doc.status === "Building") {
				frm.add_custom_button(__("Seal Load"), function () {
					frappe.confirm(
						__("Are you sure you want to seal this load?"),
						function () {
							frappe.call({
								method: "frappe.client.set_value",
								args: {
									doctype: "Load Tag",
									name: frm.doc.name,
									fieldname: "status",
									value: "Sealed"
								},
								callback: function () {
									frm.reload_doc();
								}
							});
						}
					);
				}, __("Actions"));
			}

			// Start Transit button (only if Sealed)
			if (frm.doc.status === "Sealed") {
				frm.add_custom_button(__("Start Transit"), function () {
					frappe.call({
						method: "frappe.client.set_value",
						args: {
							doctype: "Load Tag",
							name: frm.doc.name,
							fieldname: "status",
							value: "In Transit"
						},
						callback: function () {
							frm.reload_doc();
						}
					});
				}, __("Actions"));
			}
		}
	}
});
