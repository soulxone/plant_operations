import frappe
from frappe.model.document import Document
from frappe.utils import flt


class ProductionDowntime(Document):
    def before_save(self):
        self._calc_duration()

    def _calc_duration(self):
        if self.start_time and self.end_time:
            start = frappe.utils.get_datetime(self.start_time)
            end = frappe.utils.get_datetime(self.end_time)
            diff_seconds = (end - start).total_seconds()
            self.duration_min = round(max(0, diff_seconds / 60), 1)
        elif not self.end_time:
            self.duration_min = 0
