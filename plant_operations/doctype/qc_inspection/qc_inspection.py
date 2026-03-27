import frappe
from frappe.model.document import Document
from frappe.utils import nowdate


class QCInspection(Document):
	def before_save(self):
		"""Auto-calculate overall_result from test_results and dimension_checks."""
		self.evaluate_overall_result()
		self.inspection_number = self.name

	def evaluate_overall_result(self):
		"""Determine overall result based on all test results and dimension checks.

		- If any test or dimension check is 'Fail' -> overall_result = 'Fail'
		- If all are 'Pass' or 'N/A' -> overall_result = 'Pass'
		- Otherwise -> 'Conditional'
		"""
		all_results = []

		# Collect pass/fail from test results
		for row in self.test_results or []:
			if row.pass_fail:
				all_results.append(row.pass_fail)

		# Calculate dimension checks deviation/pass_fail and collect results
		for row in self.dimension_checks or []:
			if row.actual_value is not None and row.target_value is not None:
				row.deviation = abs(float(row.actual_value) - float(row.target_value))
				tolerance = float(row.tolerance or 0.0625)
				row.pass_fail = "Pass" if row.deviation <= tolerance else "Fail"
			if row.pass_fail:
				all_results.append(row.pass_fail)

		if not all_results:
			self.overall_result = ""
			return

		has_fail = any(r == "Fail" for r in all_results)
		all_pass_or_na = all(r in ("Pass", "N/A") for r in all_results)

		if has_fail:
			self.overall_result = "Fail"
			self.status = "Failed"
		elif all_pass_or_na:
			self.overall_result = "Pass"
			self.status = "Passed"
		else:
			self.overall_result = "Conditional"
			self.status = "On Hold"

	def on_submit(self):
		"""If overall_result is Fail, auto-create a Non-Conformance Report."""
		if self.overall_result == "Fail":
			self.create_ncr()

	def create_ncr(self):
		"""Create a Non-Conformance Report linked to this inspection."""
		ncr = frappe.new_doc("Non-Conformance Report")
		ncr.qc_inspection = self.name
		ncr.severity = "Major"
		ncr.machine = self.machine
		ncr.sales_order = self.sales_order
		ncr.job_card = self.job_card

		# Build defect description from failed tests and dimensions
		defects = []
		for row in self.test_results or []:
			if row.pass_fail == "Fail":
				defects.append(f"Test '{row.test_name}': spec {row.specification or 'N/A'}, actual {row.actual_value}")
		for row in self.dimension_checks or []:
			if row.pass_fail == "Fail":
				defects.append(
					f"Dimension '{row.measurement}': target {row.target_value}, "
					f"actual {row.actual_value}, deviation {row.deviation}"
				)

		ncr.defect_description = (
			f"Auto-generated from QC Inspection {self.name}.\n\n"
			f"Failed items:\n" + "\n".join(f"- {d}" for d in defects)
		)
		ncr.insert(ignore_permissions=True)
		frappe.msgprint(
			f"Non-Conformance Report <b>{ncr.name}</b> created.",
			title="NCR Created",
			indicator="red",
		)
