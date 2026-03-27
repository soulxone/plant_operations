# Copyright (c) 2026, Plant Operations and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Pallet(Document):
	def before_save(self):
		"""Calculate weight if blank based on item and quantity."""
		if not self.weight_lbs and self.item_code and self.quantity:
			item_weight = frappe.db.get_value("Item", self.item_code, "weight_per_unit")
			if item_weight:
				self.weight_lbs = float(item_weight) * float(self.quantity)

	def on_submit(self):
		"""Set pallet_id and generate GS1-128 barcode."""
		self.db_set("pallet_id", self.name)
		self._generate_barcode()

	def _generate_barcode(self):
		"""Generate GS1-128 SSCC barcode.

		Format: AI '00' + Extension '0' + Company Prefix '0123456789' + Serial + Check Digit
		"""
		# Extract numeric sequence from name (e.g., PLT-2026-00001 -> 00001)
		serial_part = self.name.split("-")[-1] if "-" in self.name else "00001"
		serial_num = serial_part.zfill(6)

		# Build SSCC: extension digit + company prefix + serial
		sscc_body = "0" + "0123456789" + serial_num

		# Calculate mod-10 check digit
		check_digit = self._calculate_check_digit(sscc_body)
		sscc = sscc_body + str(check_digit)

		# GS1-128 with AI 00
		barcode_value = "00" + sscc
		self.db_set("barcode", barcode_value)

	@staticmethod
	def _calculate_check_digit(digits):
		"""Calculate GS1 mod-10 check digit."""
		total = 0
		for i, d in enumerate(digits):
			weight = 3 if i % 2 == 0 else 1
			total += int(d) * weight
		return (10 - (total % 10)) % 10
