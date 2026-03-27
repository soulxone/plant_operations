# Copyright (c) 2026, Plant Operations and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ReceivingLog(Document):
	def on_submit(self):
		"""Set receiving_number and create Purchase Receipt from items."""
		self.db_set("receiving_number", self.name)
		self._create_purchase_receipt()

	def _create_purchase_receipt(self):
		"""Create a Purchase Receipt in ERPNext from receiving items."""
		if not self.receiving_items:
			return

		pr = frappe.new_doc("Purchase Receipt")
		pr.supplier = self.supplier
		pr.posting_date = self.received_date or frappe.utils.today()
		pr.company = frappe.defaults.get_defaults().get("company")

		if self.purchase_order:
			pr.purchase_order = self.purchase_order

		for item in self.receiving_items:
			pr.append("items", {
				"item_code": item.item_code,
				"item_name": item.item_name,
				"qty": item.received_qty,
				"rejected_qty": item.rejected_qty or 0,
				"uom": item.uom,
				"stock_uom": item.uom,
				"warehouse": item.warehouse,
				"batch_no": item.batch_no,
				"purchase_order": self.purchase_order,
			})

		pr.flags.ignore_permissions = True
		pr.insert()
		pr.submit()

		frappe.msgprint(
			f"Purchase Receipt {pr.name} created and submitted.",
			alert=True,
			indicator="green"
		)
