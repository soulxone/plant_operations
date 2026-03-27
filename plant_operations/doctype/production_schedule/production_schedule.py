# Copyright (c) 2026, Plant Operations and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, cint


class ProductionSchedule(Document):
    def before_save(self):
        self.calculate_totals()

    def on_submit(self):
        self.db_set("status", "Published")

    def calculate_totals(self):
        """Recalculate summary fields from schedule_items."""
        total_planned_min = 0
        total_actual_min = 0

        for item in self.schedule_items:
            total_planned_min += flt(item.estimated_run_min) + flt(item.estimated_setup_min)

            if item.actual_start and item.actual_end:
                from frappe.utils import time_diff_in_seconds
                diff_sec = time_diff_in_seconds(item.actual_end, item.actual_start)
                total_actual_min += max(0, flt(diff_sec) / 60)

        self.total_planned_hours = round(total_planned_min / 60, 2)
        self.total_actual_hours = round(total_actual_min / 60, 2)
        self.total_jobs = len(self.schedule_items)

        shift_hrs = flt(self.shift_hours) or 8
        self.utilization_pct = round(
            (self.total_planned_hours / shift_hrs) * 100, 1
        ) if shift_hrs > 0 else 0

    def set_schedule_name(self):
        if not self.schedule_name:
            self.schedule_name = self.name
