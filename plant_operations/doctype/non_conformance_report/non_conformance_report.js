frappe.ui.form.on("Non-Conformance Report", {
	refresh(frm) {
		// Color-coded severity indicator
		if (frm.doc.severity === "Critical") {
			frm.dashboard.set_headline(
				`<span style="color: red; font-weight: bold;">&#9888; CRITICAL NCR</span>`
			);
		} else if (frm.doc.severity === "Major") {
			frm.dashboard.set_headline(
				`<span style="color: orange; font-weight: bold;">&#9888; MAJOR NCR</span>`
			);
		}

		// Workflow buttons (only for saved, non-submitted docs)
		if (frm.doc.docstatus === 0 && !frm.is_new()) {
			if (frm.doc.status === "Open") {
				frm.add_custom_button(__("Start Review"), function () {
					frappe.call({
						method: "start_review",
						doc: frm.doc,
						callback() {
							frm.reload_doc();
						},
					});
				}, __("Actions"));
			}

			if (frm.doc.status === "Under Review") {
				frm.add_custom_button(__("Assign Corrective Action"), function () {
					frappe.call({
						method: "assign_corrective_action",
						doc: frm.doc,
						callback() {
							frm.reload_doc();
						},
					});
				}, __("Actions"));
			}

			if (["Under Review", "Corrective Action"].includes(frm.doc.status)) {
				frm.add_custom_button(__("Close NCR"), function () {
					frappe.confirm(
						__("Are you sure you want to close this NCR?"),
						function () {
							frappe.call({
								method: "close_ncr",
								doc: frm.doc,
								callback() {
									frm.reload_doc();
								},
							});
						}
					);
				}, __("Actions"));
			}
		}

		// Link to QC Inspection
		if (frm.doc.qc_inspection) {
			frm.add_custom_button(__("View QC Inspection"), function () {
				frappe.set_route("Form", "QC Inspection", frm.doc.qc_inspection);
			}, __("Links"));
		}
	},
});
