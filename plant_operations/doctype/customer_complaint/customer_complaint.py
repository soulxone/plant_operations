import frappe
from frappe.model.document import Document
from frappe.utils import nowdate


class CustomerComplaint(Document):
	def before_save(self):
		self.complaint_number = self.name

		# Auto-set resolved_date when status changes to Resolved or Closed
		if self.status in ("Resolved", "Closed") and not self.resolved_date:
			self.resolved_date = nowdate()

	def create_ncr(self):
		"""Create a Non-Conformance Report from this complaint."""
		ncr = frappe.new_doc("Non-Conformance Report")
		ncr.customer = self.customer
		ncr.sales_order = self.sales_order
		ncr.severity = "Major"
		ncr.defect_description = (
			f"Customer Complaint {self.name}\n"
			f"Type: {self.complaint_type}\n\n"
			f"{self.description}"
		)
		ncr.insert(ignore_permissions=True)

		self.ncr_ref = ncr.name
		self.status = "Investigating"
		self.save(ignore_permissions=True)

		return ncr.name

	def mark_resolved(self):
		"""Mark this complaint as resolved."""
		self.status = "Resolved"
		self.resolved_date = nowdate()
		self.save(ignore_permissions=True)
