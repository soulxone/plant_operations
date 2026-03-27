import frappe
from frappe.utils import nowdate, getdate


@frappe.whitelist()
def auto_evaluate_inspection(inspection_name):
	"""Calculate overall_result from test results and dimension checks.

	Args:
		inspection_name: Name of the QC Inspection document

	Returns:
		dict with overall_result and status
	"""
	doc = frappe.get_doc("QC Inspection", inspection_name)
	all_results = []

	for row in doc.test_results or []:
		if row.pass_fail:
			all_results.append(row.pass_fail)

	for row in doc.dimension_checks or []:
		if row.actual_value is not None and row.target_value is not None:
			row.deviation = abs(float(row.actual_value) - float(row.target_value))
			tolerance = float(row.tolerance or 0.0625)
			row.pass_fail = "Pass" if row.deviation <= tolerance else "Fail"
		if row.pass_fail:
			all_results.append(row.pass_fail)

	if not all_results:
		return {"overall_result": "", "status": "Pending"}

	has_fail = any(r == "Fail" for r in all_results)
	all_pass_or_na = all(r in ("Pass", "N/A") for r in all_results)

	if has_fail:
		overall_result = "Fail"
		status = "Failed"
	elif all_pass_or_na:
		overall_result = "Pass"
		status = "Passed"
	else:
		overall_result = "Conditional"
		status = "On Hold"

	doc.overall_result = overall_result
	doc.status = status
	doc.save(ignore_permissions=True)

	return {"overall_result": overall_result, "status": status}


@frappe.whitelist()
def create_ncr_from_inspection(inspection_name):
	"""Create a Non-Conformance Report from a failed QC Inspection.

	Args:
		inspection_name: Name of the QC Inspection document

	Returns:
		Name of the created NCR document
	"""
	doc = frappe.get_doc("QC Inspection", inspection_name)

	# Check if NCR already exists for this inspection
	existing = frappe.db.exists("Non-Conformance Report", {"qc_inspection": inspection_name})
	if existing:
		frappe.msgprint(f"NCR already exists: {existing}")
		return existing

	ncr = frappe.new_doc("Non-Conformance Report")
	ncr.qc_inspection = inspection_name
	ncr.severity = "Major"
	ncr.machine = doc.machine
	ncr.sales_order = doc.sales_order
	ncr.job_card = doc.job_card

	# Build defect description from failed tests and dimensions
	defects = []
	for row in doc.test_results or []:
		if row.pass_fail == "Fail":
			defects.append(
				f"Test '{row.test_name}': spec {row.specification or 'N/A'}, "
				f"actual {row.actual_value}"
			)

	for row in doc.dimension_checks or []:
		if row.pass_fail == "Fail":
			defects.append(
				f"Dimension '{row.measurement}': target {row.target_value}, "
				f"actual {row.actual_value}, deviation {row.deviation}"
			)

	ncr.defect_description = (
		f"Generated from QC Inspection {inspection_name}.\n\n"
		f"Failed items:\n" + "\n".join(f"- {d}" for d in defects)
	) if defects else f"Generated from failed QC Inspection {inspection_name}."

	ncr.insert(ignore_permissions=True)

	return ncr.name


@frappe.whitelist()
def get_qc_summary(date_from=None, date_to=None):
	"""Get quality control summary statistics for a date range.

	Args:
		date_from: Start date (defaults to first day of current month)
		date_to: End date (defaults to today)

	Returns:
		dict with summary counts and pass rate
	"""
	if not date_from:
		today = getdate(nowdate())
		date_from = today.replace(day=1).isoformat()
	if not date_to:
		date_to = nowdate()

	# Total inspections in period
	total_inspections = frappe.db.count("QC Inspection", filters={
		"inspection_date": ["between", [date_from, date_to]],
		"docstatus": ["!=", 2],
	})

	# Passed inspections
	passed = frappe.db.count("QC Inspection", filters={
		"inspection_date": ["between", [date_from, date_to]],
		"overall_result": "Pass",
		"docstatus": ["!=", 2],
	})

	# Failed inspections
	failed = frappe.db.count("QC Inspection", filters={
		"inspection_date": ["between", [date_from, date_to]],
		"overall_result": "Fail",
		"docstatus": ["!=", 2],
	})

	# Conditional inspections
	conditional = frappe.db.count("QC Inspection", filters={
		"inspection_date": ["between", [date_from, date_to]],
		"overall_result": "Conditional",
		"docstatus": ["!=", 2],
	})

	# Pass rate
	pass_rate = (passed / total_inspections * 100) if total_inspections > 0 else 0

	# Open NCRs
	open_ncrs = frappe.db.count("Non-Conformance Report", filters={
		"status": ["in", ["Open", "Under Review", "Corrective Action"]],
		"docstatus": ["!=", 2],
	})

	# Open complaints
	open_complaints = frappe.db.count("Customer Complaint", filters={
		"status": ["in", ["Open", "Investigating"]],
		"docstatus": ["!=", 2],
	})

	return {
		"date_from": date_from,
		"date_to": date_to,
		"total_inspections": total_inspections,
		"passed": passed,
		"failed": failed,
		"conditional": conditional,
		"pass_rate": round(pass_rate, 1),
		"open_ncrs": open_ncrs,
		"open_complaints": open_complaints,
	}
