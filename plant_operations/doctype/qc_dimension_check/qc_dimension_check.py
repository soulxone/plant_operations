import frappe
from frappe.model.document import Document


class QCDimensionCheck(Document):
	def before_save(self):
		"""Auto-calculate deviation and pass/fail based on target, actual, and tolerance."""
		if self.actual_value is not None and self.target_value is not None:
			self.deviation = abs(float(self.actual_value) - float(self.target_value))
			tolerance = float(self.tolerance or 0.0625)
			self.pass_fail = "Pass" if self.deviation <= tolerance else "Fail"
