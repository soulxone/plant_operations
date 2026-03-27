# Copyright (c) 2026, Plant Operations and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LoadTag(Document):
	def before_save(self):
		"""Calculate totals from load_pallets child table."""
		self.total_pallets = len(self.load_pallets) if self.load_pallets else 0
		self.total_weight = sum(
			(row.weight_lbs or 0) for row in (self.load_pallets or [])
		)
		self.total_pieces = sum(
			(row.quantity or 0) for row in (self.load_pallets or [])
		)

	def on_submit(self):
		"""Set load_number and update all linked pallets to Loaded status."""
		self.db_set("load_number", self.name)

		for row in self.load_pallets or []:
			if row.pallet:
				frappe.db.set_value("Pallet", row.pallet, "status", "Loaded")
