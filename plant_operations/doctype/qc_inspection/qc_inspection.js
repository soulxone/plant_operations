frappe.ui.form.on("QC Inspection", {
	refresh(frm) {
		// Color-coded status indicator
		if (frm.doc.overall_result === "Pass") {
			frm.dashboard.set_headline(
				`<span style="color: green; font-weight: bold;">&#10004; PASSED</span>`
			);
		} else if (frm.doc.overall_result === "Fail") {
			frm.dashboard.set_headline(
				`<span style="color: red; font-weight: bold;">&#10008; FAILED</span>`
			);
		} else if (frm.doc.overall_result === "Conditional") {
			frm.dashboard.set_headline(
				`<span style="color: orange; font-weight: bold;">&#9888; CONDITIONAL</span>`
			);
		} else if (frm.doc.status === "Pending") {
			frm.dashboard.set_headline(
				`<span style="color: #f0ad4e; font-weight: bold;">&#9679; PENDING</span>`
			);
		}

		// Color the status indicator on the page
		set_status_indicator(frm);

		// Show pass/fail summary counts
		show_summary_counts(frm);

		// "Create NCR" button if failed and submitted
		if (frm.doc.docstatus === 1 && frm.doc.overall_result === "Fail") {
			frm.add_custom_button(__("Create NCR"), function () {
				frappe.call({
					method: "plant_operations.plant_operations.qc.create_ncr_from_inspection",
					args: { inspection_name: frm.doc.name },
					callback(r) {
						if (r.message) {
							frappe.set_route("Form", "Non-Conformance Report", r.message);
						}
					},
				});
			}, __("Actions"));
		}

		// "View Production Entry" button if linked
		if (frm.doc.production_entry) {
			frm.add_custom_button(__("View Production Entry"), function () {
				frappe.set_route("Form", "Production Entry", frm.doc.production_entry);
			}, __("Links"));
		}

		// "View Job Card" button if linked
		if (frm.doc.job_card) {
			frm.add_custom_button(__("View Job Card"), function () {
				frappe.set_route("Form", "Job Card", frm.doc.job_card);
			}, __("Links"));
		}
	},
});

function set_status_indicator(frm) {
	let color = "blue";
	if (frm.doc.status === "Passed") color = "green";
	else if (frm.doc.status === "Failed") color = "red";
	else if (frm.doc.status === "On Hold") color = "orange";
	else if (frm.doc.status === "Pending") color = "yellow";

	frm.page.set_indicator(frm.doc.status, color);
}

function show_summary_counts(frm) {
	let pass_count = 0;
	let fail_count = 0;
	let na_count = 0;

	(frm.doc.test_results || []).forEach((row) => {
		if (row.pass_fail === "Pass") pass_count++;
		else if (row.pass_fail === "Fail") fail_count++;
		else if (row.pass_fail === "N/A") na_count++;
	});

	(frm.doc.dimension_checks || []).forEach((row) => {
		if (row.pass_fail === "Pass") pass_count++;
		else if (row.pass_fail === "Fail") fail_count++;
	});

	if (pass_count + fail_count + na_count > 0) {
		let html = `
			<div class="row" style="margin-top: 5px;">
				<div class="col-sm-4 text-center">
					<span class="badge" style="background-color: #28a745; color: white; font-size: 13px; padding: 5px 12px;">
						Pass: ${pass_count}
					</span>
				</div>
				<div class="col-sm-4 text-center">
					<span class="badge" style="background-color: #dc3545; color: white; font-size: 13px; padding: 5px 12px;">
						Fail: ${fail_count}
					</span>
				</div>
				<div class="col-sm-4 text-center">
					<span class="badge" style="background-color: #6c757d; color: white; font-size: 13px; padding: 5px 12px;">
						N/A: ${na_count}
					</span>
				</div>
			</div>
		`;
		frm.dashboard.add_comment(html, true);
	}
}
