# Copyright (c) 2026, Plant Operations and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Shipment(Document):
	def before_save(self):
		"""Calculate totals from shipment_loads child table."""
		self.total_pallets = sum(
			(row.pallet_count or 0) for row in (self.shipment_loads or [])
		)
		self.total_weight = sum(
			(row.total_weight or 0) for row in (self.shipment_loads or [])
		)
		self.total_pieces = sum(
			(row.total_pieces or 0) for row in (self.shipment_loads or [])
		)

	def on_submit(self):
		"""Set shipment_number and create Delivery Note from loads."""
		self.db_set("shipment_number", self.name)
		self._create_delivery_note()

	def _create_delivery_note(self):
		"""Create a Delivery Note from the shipment loads."""
		if not self.shipment_loads or not self.customer:
			return

		# Collect all pallet items across all loads
		items = []
		for load_row in self.shipment_loads:
			if not load_row.load_tag:
				continue
			load_doc = frappe.get_doc("Load Tag", load_row.load_tag)
			for pallet_row in load_doc.load_pallets or []:
				if pallet_row.pallet:
					pallet = frappe.get_doc("Pallet", pallet_row.pallet)
					if pallet.item_code:
						items.append({
							"item_code": pallet.item_code,
							"item_name": pallet.item_name,
							"qty": pallet.quantity or 0,
							"warehouse": pallet.warehouse,
						})

		if not items:
			return

		dn = frappe.new_doc("Delivery Note")
		dn.customer = self.customer
		dn.posting_date = self.ship_date or frappe.utils.today()
		dn.company = frappe.defaults.get_defaults().get("company")

		if self.sales_order:
			dn.against_sales_order = self.sales_order

		for item in items:
			dn.append("items", item)

		dn.flags.ignore_permissions = True
		dn.insert()

		self.db_set("delivery_note", dn.name)

		frappe.msgprint(
			f"Delivery Note {dn.name} created.",
			alert=True,
			indicator="green"
		)
