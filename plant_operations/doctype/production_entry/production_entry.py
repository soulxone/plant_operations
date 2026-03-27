import frappe
from frappe.model.document import Document
from frappe.utils import flt, cint, now_datetime, time_diff_in_seconds


class ProductionEntry(Document):
    def before_save(self):
        self.entry_number = self.name
        self._calc_totals()
        self._calc_oee()
        self._calc_cost_variance()

    def _calc_totals(self):
        self.total_time_min = flt(self.setup_time_min) + flt(self.run_time_min)
        if flt(self.run_time_min) > 0:
            run_hrs = flt(self.run_time_min) / 60.0
            self.speed_actual = round(cint(self.good_qty) / run_hrs, 1) if run_hrs > 0 else 0
        else:
            self.speed_actual = 0

    def _calc_oee(self):
        # Availability = run_time / (run_time + downtime)
        total_downtime = sum(flt(d.duration_min) for d in (self.downtime_events or []))
        available_time = flt(self.run_time_min) + total_downtime
        self.availability_pct = round(
            (flt(self.run_time_min) / available_time * 100) if available_time > 0 else 0, 1
        )

        # Performance = actual_speed / rated_speed
        rated_speed = 0
        if self.machine:
            rated_speed = flt(
                frappe.db.get_value("Corrugated Machine", self.machine, "speed_value")
            )
        self.performance_pct = round(
            (self.speed_actual / rated_speed * 100) if rated_speed > 0 else 0, 1
        )

        # Quality = good_qty / total_produced
        total_produced = cint(self.good_qty) + cint(self.waste_qty) + cint(self.reject_qty)
        self.quality_pct = round(
            (cint(self.good_qty) / total_produced * 100) if total_produced > 0 else 0, 1
        )

        # OEE = A x P x Q / 10000
        self.oee_pct = round(
            self.availability_pct * self.performance_pct * self.quality_pct / 10000, 1
        )

    def _calc_cost_variance(self):
        if self.machine:
            rate_msf = flt(
                frappe.db.get_value("Corrugated Machine", self.machine, "rate_msf")
            )
            setup_cost = flt(
                frappe.db.get_value("Corrugated Machine", self.machine, "setup_cost")
            )
            self.estimated_cost = setup_cost + (rate_msf * flt(self.planned_qty) / 1000)
            self.actual_cost = setup_cost + (rate_msf * cint(self.good_qty) / 1000)
            self.cost_variance = flt(self.estimated_cost) - flt(self.actual_cost)

    def on_submit(self):
        self._update_job_card()

    def _update_job_card(self):
        if not self.job_card:
            return
        try:
            jc = frappe.get_doc("Job Card", self.job_card)
            # Update time logs with actual data
            if jc.time_logs:
                last_log = jc.time_logs[-1]
                last_log.completed_qty = cint(self.good_qty)
                last_log.time_in_mins = flt(self.total_time_min)
            jc.save(ignore_permissions=True)
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(f"MES: Failed to update Job Card {self.job_card}: {e}")
