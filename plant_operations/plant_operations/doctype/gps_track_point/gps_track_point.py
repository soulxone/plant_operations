# Copyright (c) 2026, Plant Operations and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class GPSTrackPoint(Document):
	def after_insert(self):
		"""Update the linked Load Tag with latest GPS coordinates."""
		if self.load_tag:
			frappe.db.set_value("Load Tag", self.load_tag, {
				"last_gps_lat": self.latitude,
				"last_gps_lng": self.longitude,
				"last_gps_time": self.timestamp
			})
