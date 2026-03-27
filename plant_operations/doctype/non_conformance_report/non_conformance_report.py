import frappe
from frappe.model.document import Document
from frappe.utils import nowdate


class NonConformanceReport(Document):
	def before_save(self):
		self.ncr_number = self.name

	def on_submit(self):
		"""If status is Closed at time of submit, set actual_close_date."""
		if self.status == "Closed" and not self.actual_close_date:
			self.actual_close_date = nowdate()

	def start_review(self):
		"""Transition status to Under Review."""
		self.status = "Under Review"
		self.save(ignore_permissions=True)

	def assign_corrective_action(self):
		"""Transition status to Corrective Action."""
		self.status = "Corrective Action"
		self.save(ignore_permissions=True)

	def close_ncr(self):
		"""Transition status to Closed and set actual close date."""
		self.status = "Closed"
		self.actual_close_date = nowdate()
		self.save(ignore_permissions=True)
