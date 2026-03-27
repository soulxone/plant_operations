frappe.ui.form.on("Customer Complaint", {
	refresh(frm) {
		// Status indicator colors
		let color = "blue";
		if (frm.doc.status === "Open") color = "red";
		else if (frm.doc.status === "Investigating") color = "orange";
		else if (frm.doc.status === "Resolved") color = "green";
		else if (frm.doc.status === "Closed") color = "darkgrey";

		frm.page.set_indicator(frm.doc.status, color);

		// "Create NCR" button when Open or Investigating and no NCR linked yet
		if (!frm.is_new() && !frm.doc.ncr_ref && frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Create NCR"), function () {
				frappe.call({
					method: "create_ncr",
					doc: frm.doc,
					callback(r) {
						if (r.message) {
							frm.reload_doc();
							frappe.set_route("Form", "Non-Conformance Report", r.message);
						}
					},
				});
			}, __("Actions"));
		}

		// "Mark Resolved" button
		if (!frm.is_new() && frm.doc.status !== "Resolved" && frm.doc.status !== "Closed" && frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Mark Resolved"), function () {
				frappe.confirm(
					__("Mark this complaint as resolved?"),
					function () {
						frappe.call({
							method: "mark_resolved",
							doc: frm.doc,
							callback() {
								frm.reload_doc();
							},
						});
					}
				);
			}, __("Actions"));
		}

		// Link to NCR if exists
		if (frm.doc.ncr_ref) {
			frm.add_custom_button(__("View NCR"), function () {
				frappe.set_route("Form", "Non-Conformance Report", frm.doc.ncr_ref);
			}, __("Links"));
		}
	},
});
