"""MES Logic -- OEE calculation, Job Card sync, machine status."""
import frappe
from frappe.utils import now_datetime, flt, cint, time_diff_in_seconds


def start_production(machine, job_card=None, sales_order=None, planned_qty=0):
    """Create a new Production Entry and set it to Running."""
    # Check no other entry is running on this machine
    running = frappe.db.get_value(
        "Production Entry",
        {"machine": machine, "status": "Running", "docstatus": 0},
        "name",
    )
    if running:
        frappe.throw(f"Machine {machine} already has a running entry: {running}")

    entry = frappe.get_doc(
        {
            "doctype": "Production Entry",
            "machine": machine,
            "job_card": job_card,
            "sales_order": sales_order,
            "planned_qty": cint(planned_qty),
            "status": "Running",
            "start_time": now_datetime(),
            "operator": frappe.session.user,
        }
    )
    entry.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "success", "entry": entry.name, "machine": machine}


def pause_production(entry_name):
    """Pause production -- create a downtime event."""
    entry = frappe.get_doc("Production Entry", entry_name)
    if entry.status != "Running":
        frappe.throw(f"Entry {entry_name} is not running.")
    entry.status = "Paused"
    entry.append(
        "downtime_events",
        {
            "start_time": now_datetime(),
            "reason": "Other",
        },
    )
    entry.save(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "paused", "entry": entry_name}


def resume_production(entry_name):
    """Resume from pause -- close the last downtime event."""
    entry = frappe.get_doc("Production Entry", entry_name)
    if entry.status != "Paused":
        frappe.throw(f"Entry {entry_name} is not paused.")
    # Close last downtime
    if entry.downtime_events:
        last = entry.downtime_events[-1]
        if not last.end_time:
            last.end_time = now_datetime()
            start = frappe.utils.get_datetime(last.start_time)
            end = frappe.utils.get_datetime(last.end_time)
            last.duration_min = round((end - start).total_seconds() / 60, 1)
    entry.status = "Running"
    entry.save(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "running", "entry": entry_name}


def stop_production(entry_name, good_qty=0, waste_qty=0, reject_qty=0):
    """Stop production -- finalize counts, calculate OEE."""
    entry = frappe.get_doc("Production Entry", entry_name)
    entry.status = "Complete"
    entry.end_time = now_datetime()
    entry.good_qty = cint(good_qty)
    entry.waste_qty = cint(waste_qty)
    entry.reject_qty = cint(reject_qty)

    # Close any open downtime events
    for dt in entry.downtime_events or []:
        if dt.start_time and not dt.end_time:
            dt.end_time = now_datetime()
            start = frappe.utils.get_datetime(dt.start_time)
            end = frappe.utils.get_datetime(dt.end_time)
            dt.duration_min = round((end - start).total_seconds() / 60, 1)

    # Calculate run time from start/end minus downtime
    if entry.start_time and entry.end_time:
        start = frappe.utils.get_datetime(entry.start_time)
        end = frappe.utils.get_datetime(entry.end_time)
        total_min = (end - start).total_seconds() / 60
        downtime_min = sum(flt(d.duration_min) for d in (entry.downtime_events or []))
        entry.run_time_min = round(max(0, total_min - downtime_min), 1)
        entry.setup_time_min = flt(entry.setup_time_min) or 0

    entry.save(ignore_permissions=True)
    frappe.db.commit()
    return {
        "status": "complete",
        "entry": entry_name,
        "oee": entry.oee_pct,
        "good_qty": entry.good_qty,
        "waste_qty": entry.waste_qty,
    }


def update_count(entry_name, field, value):
    """Update a count field on a running Production Entry."""
    allowed_fields = ("good_qty", "waste_qty", "reject_qty")
    if field not in allowed_fields:
        frappe.throw(f"Invalid field: {field}")

    entry = frappe.get_doc("Production Entry", entry_name)
    if entry.status not in ("Running", "Paused"):
        frappe.throw(f"Cannot update counts on a {entry.status} entry.")

    entry.set(field, cint(value))
    entry.save(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "updated", "entry": entry_name, "field": field, "value": cint(value)}


def log_downtime(entry_name, reason, notes=None):
    """Log a downtime event on a running/paused Production Entry."""
    entry = frappe.get_doc("Production Entry", entry_name)
    if entry.status not in ("Running", "Paused"):
        frappe.throw(f"Cannot log downtime on a {entry.status} entry.")

    # If running, pause it
    was_running = entry.status == "Running"
    if was_running:
        entry.status = "Paused"

    entry.append(
        "downtime_events",
        {
            "start_time": now_datetime(),
            "reason": reason,
            "notes": notes or "",
        },
    )
    entry.save(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "logged", "entry": entry_name, "reason": reason}


def get_machine_status(machine):
    """Get current production status of a machine."""
    running = frappe.db.get_value(
        "Production Entry",
        {
            "machine": machine,
            "status": ["in", ["Running", "Paused"]],
            "docstatus": 0,
        },
        [
            "name",
            "status",
            "start_time",
            "good_qty",
            "waste_qty",
            "reject_qty",
            "job_card",
            "sales_order",
            "operator",
            "planned_qty",
            "oee_pct",
            "availability_pct",
            "performance_pct",
            "quality_pct",
            "speed_actual",
        ],
        as_dict=True,
    )

    if not running:
        return {"machine": machine, "status": "Idle", "entry": None}

    # Also get rated speed for the machine
    rated_speed = flt(
        frappe.db.get_value("Corrugated Machine", machine, "speed_value")
    )

    return {
        "machine": machine,
        "status": running.status,
        "entry": running.name,
        "start_time": str(running.start_time) if running.start_time else None,
        "good_qty": cint(running.good_qty),
        "waste_qty": cint(running.waste_qty),
        "reject_qty": cint(running.reject_qty),
        "planned_qty": cint(running.planned_qty),
        "job_card": running.job_card,
        "sales_order": running.sales_order,
        "operator": running.operator,
        "oee_pct": flt(running.oee_pct),
        "availability_pct": flt(running.availability_pct),
        "performance_pct": flt(running.performance_pct),
        "quality_pct": flt(running.quality_pct),
        "speed_actual": flt(running.speed_actual),
        "rated_speed": rated_speed,
    }


def get_plant_dashboard():
    """Get status of ALL machines for the plant dashboard."""
    machines = frappe.get_all(
        "Corrugated Machine",
        filters={"enabled": 1},
        fields=["machine_id", "machine_name", "department", "speed_value"],
        order_by="department, machine_name",
    )

    result = []
    for m in machines:
        status = get_machine_status(m.machine_id)
        status["machine_name"] = m.machine_name
        status["department"] = m.department
        status["rated_speed"] = flt(m.speed_value)
        result.append(status)

    return result
