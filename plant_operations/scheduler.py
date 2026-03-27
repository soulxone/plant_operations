"""Production Scheduler — auto-scheduling, capacity planning."""
import frappe
from frappe.utils import today, add_days, flt, cint, get_datetime, now_datetime, date_diff


def get_schedule_board(date=None):
    """Get all machines with their schedule items for a given date."""
    if not date:
        date = today()

    machines = frappe.get_all("Corrugated Machine",
        filters={"enabled": 1},
        fields=["machine_id", "machine_name", "department", "speed_value",
                "rate_msf", "setup_time_min"],
        order_by="department, machine_name")

    for machine in machines:
        # Get schedule items for this machine on this date
        schedules = frappe.get_all("Production Schedule",
            filters={
                "machine": machine.machine_id,
                "schedule_date": date,
                "docstatus": ["<", 2],
            },
            pluck="name")

        items = []
        for sched_name in schedules:
            sched = frappe.get_doc("Production Schedule", sched_name)
            for item in sched.schedule_items:
                items.append({
                    "name": item.name,
                    "parent": sched_name,
                    "sequence": item.sequence,
                    "job_card": item.job_card,
                    "sales_order": item.sales_order,
                    "item_description": item.item_description,
                    "customer": item.customer,
                    "planned_qty": item.planned_qty,
                    "planned_start": str(item.planned_start) if item.planned_start else None,
                    "planned_end": str(item.planned_end) if item.planned_end else None,
                    "estimated_run_min": flt(item.estimated_run_min),
                    "estimated_setup_min": flt(item.estimated_setup_min),
                    "priority": item.priority,
                    "status": item.status,
                    "actual_start": str(item.actual_start) if item.actual_start else None,
                    "actual_end": str(item.actual_end) if item.actual_end else None,
                })

        machine["schedule_items"] = sorted(items, key=lambda x: x.get("sequence", 0))

        # Get current MES status (Production Entry running on this machine)
        running = frappe.db.get_value("Production Entry",
            {
                "machine": machine.machine_id,
                "status": ["in", ["Running", "Paused"]],
                "docstatus": 0,
            },
            ["name", "status", "good_qty", "oee_pct"],
            as_dict=True)
        machine["current_entry"] = running

    return machines


def auto_schedule(date=None, strategy="earliest_due"):
    """Auto-assign unscheduled Job Cards to machines for a date.

    Strategies: earliest_due, shortest_setup, best_fit
    """
    if not date:
        date = today()

    # Find unscheduled Job Cards that are not yet on any schedule
    job_cards = frappe.get_all("Job Card",
        filters={
            "status": ["in", ["Open", "Work In Progress"]],
            "posting_date": ["<=", date],
        },
        fields=["name", "operation", "workstation", "for_quantity",
                "time_logs", "remarks", "sales_order"],
        order_by="posting_date asc")

    if not job_cards:
        return {"status": "no_jobs", "message": "No unscheduled jobs found.", "scheduled_count": 0}

    # Filter out already-scheduled Job Cards
    already_scheduled = set()
    existing_items = frappe.get_all("Schedule Item",
        filters={"job_card": ["in", [jc.name for jc in job_cards]]},
        pluck="job_card")
    already_scheduled = set(existing_items)

    unscheduled = [jc for jc in job_cards if jc.name not in already_scheduled]
    if not unscheduled:
        return {"status": "no_jobs", "message": "All jobs already scheduled.", "scheduled_count": 0}

    # Get available machines
    machines = frappe.get_all("Corrugated Machine",
        filters={"enabled": 1},
        fields=["machine_id", "machine_name", "department", "speed_value", "setup_time_min"],
        order_by="department, machine_name")

    if not machines:
        return {"status": "error", "message": "No enabled machines found.", "scheduled_count": 0}

    scheduled = []
    for jc in unscheduled:
        # Find best machine (match workstation name to machine)
        best_machine = None
        for m in machines:
            if m.machine_name == jc.workstation or m.machine_id == jc.workstation:
                best_machine = m
                break
        if not best_machine:
            best_machine = machines[0]  # fallback to first available

        # Find or create schedule for this machine+date
        existing = frappe.db.get_value("Production Schedule",
            {"machine": best_machine.machine_id, "schedule_date": date, "docstatus": 0},
            "name")

        if existing:
            sched = frappe.get_doc("Production Schedule", existing)
        else:
            sched = frappe.get_doc({
                "doctype": "Production Schedule",
                "machine": best_machine.machine_id,
                "schedule_date": date,
                "status": "Draft",
            })
            sched.insert(ignore_permissions=True)

        # Calculate timing
        speed = max(1, flt(best_machine.speed_value))
        run_min = flt(jc.for_quantity) / (speed / 60) if speed > 0 else 30
        setup_min = flt(best_machine.setup_time_min) or 15

        # Extract customer from SO
        customer = ""
        if jc.sales_order:
            customer = frappe.db.get_value("Sales Order", jc.sales_order, "customer") or ""

        seq = len(sched.schedule_items) + 1
        sched.append("schedule_items", {
            "sequence": seq,
            "job_card": jc.name,
            "sales_order": jc.sales_order,
            "item_description": jc.operation or "Production",
            "customer": customer,
            "planned_qty": cint(jc.for_quantity),
            "estimated_run_min": round(run_min, 1),
            "estimated_setup_min": round(setup_min, 1),
            "priority": "Normal",
            "status": "Pending",
        })
        sched.save(ignore_permissions=True)
        scheduled.append({
            "job_card": jc.name,
            "machine": best_machine.machine_id,
            "schedule": sched.name,
        })

    frappe.db.commit()
    return {
        "status": "success",
        "scheduled_count": len(scheduled),
        "jobs": scheduled,
    }


def auto_fill_for_schedule(schedule_name, machine, date):
    """Auto-fill a specific Production Schedule with unscheduled Job Cards
    matched to its machine.
    """
    if not schedule_name or not machine:
        return {"status": "error", "message": "Schedule and machine required.", "added_count": 0}

    sched = frappe.get_doc("Production Schedule", schedule_name)

    # Already-scheduled JC names on this schedule
    existing_jcs = set(item.job_card for item in sched.schedule_items if item.job_card)

    # Find Job Cards for this workstation
    job_cards = frappe.get_all("Job Card",
        filters={
            "status": ["in", ["Open", "Work In Progress"]],
            "posting_date": ["<=", date or today()],
        },
        fields=["name", "operation", "workstation", "for_quantity", "sales_order"],
        order_by="posting_date asc")

    # Filter: match machine and not already on this schedule
    machine_doc = frappe.get_doc("Corrugated Machine", machine)
    matched = []
    for jc in job_cards:
        if jc.name in existing_jcs:
            continue
        # Check if already on ANY schedule
        if frappe.db.exists("Schedule Item", {"job_card": jc.name}):
            continue
        if jc.workstation in (machine, machine_doc.machine_name):
            matched.append(jc)

    added = 0
    for jc in matched:
        speed = max(1, flt(machine_doc.speed_value))
        run_min = flt(jc.for_quantity) / (speed / 60) if speed > 0 else 30
        setup_min = flt(machine_doc.setup_time_min) or 15

        customer = ""
        if jc.sales_order:
            customer = frappe.db.get_value("Sales Order", jc.sales_order, "customer") or ""

        seq = len(sched.schedule_items) + 1
        sched.append("schedule_items", {
            "sequence": seq,
            "job_card": jc.name,
            "sales_order": jc.sales_order,
            "item_description": jc.operation or "Production",
            "customer": customer,
            "planned_qty": cint(jc.for_quantity),
            "estimated_run_min": round(run_min, 1),
            "estimated_setup_min": round(setup_min, 1),
            "priority": "Normal",
            "status": "Pending",
        })
        added += 1

    if added > 0:
        sched.save(ignore_permissions=True)
        frappe.db.commit()

    return {"status": "success", "added_count": added}


def start_schedule_job(schedule_name, item_name):
    """Mark a schedule item as Running and optionally create a Production Entry."""
    sched = frappe.get_doc("Production Schedule", schedule_name)

    target = None
    for item in sched.schedule_items:
        if item.name == item_name:
            target = item
            break

    if not target:
        frappe.throw(f"Schedule item {item_name} not found in {schedule_name}")

    target.status = "Running"
    target.actual_start = now_datetime()
    sched.status = "In Progress"
    sched.save(ignore_permissions=True)

    # Try to create a Production Entry if the doctype exists
    production_entry = None
    try:
        if frappe.db.exists("DocType", "Production Entry"):
            pe = frappe.get_doc({
                "doctype": "Production Entry",
                "machine": sched.machine,
                "job_card": target.job_card,
                "sales_order": target.sales_order,
                "planned_qty": target.planned_qty,
                "status": "Running",
                "start_time": now_datetime(),
            })
            pe.insert(ignore_permissions=True)
            production_entry = pe.name
    except Exception:
        pass  # Production Entry creation is optional

    frappe.db.commit()
    return {
        "status": "success",
        "item_status": "Running",
        "production_entry": production_entry,
    }


def complete_schedule_job(schedule_name, item_name):
    """Mark a schedule item as Complete."""
    sched = frappe.get_doc("Production Schedule", schedule_name)

    target = None
    for item in sched.schedule_items:
        if item.name == item_name:
            target = item
            break

    if not target:
        frappe.throw(f"Schedule item {item_name} not found in {schedule_name}")

    target.status = "Complete"
    target.actual_end = now_datetime()

    # Check if all items are complete
    all_complete = all(
        i.status in ("Complete", "Skipped") for i in sched.schedule_items
    )
    if all_complete:
        sched.status = "Complete"

    sched.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "item_status": "Complete",
        "schedule_status": sched.status,
    }


def get_capacity_summary(date_from=None, date_to=None):
    """Get planned vs available hours per machine for a date range."""
    if not date_from:
        date_from = today()
    if not date_to:
        date_to = add_days(date_from, 7)

    machines = frappe.get_all("Corrugated Machine",
        filters={"enabled": 1},
        fields=["machine_id", "machine_name", "department"],
        order_by="department, machine_name")

    result = []
    for m in machines:
        schedules = frappe.get_all("Production Schedule",
            filters={
                "machine": m.machine_id,
                "schedule_date": ["between", [date_from, date_to]],
                "docstatus": ["<", 2],
            },
            fields=["total_planned_hours", "total_actual_hours", "schedule_date"])

        planned = sum(flt(s.total_planned_hours) for s in schedules)
        actual = sum(flt(s.total_actual_hours) for s in schedules)
        days = max(1, date_diff(date_to, date_from) + 1)
        available = days * 8  # 8 hours per day

        result.append({
            "machine_id": m.machine_id,
            "machine_name": m.machine_name,
            "department": m.department,
            "planned_hours": round(planned, 1),
            "actual_hours": round(actual, 1),
            "available_hours": available,
            "utilization_pct": round(planned / available * 100, 1) if available > 0 else 0,
        })

    return result
