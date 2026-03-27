"""Plant Analytics — OEE, Profitability, Waste, and Quality dashboards."""
import frappe
from frappe.utils import today, add_days, flt, cint, getdate


def get_oee_dashboard(date_from=None, date_to=None, machine=None):
    """OEE analytics data for dashboard charts."""
    if not date_from:
        date_from = add_days(today(), -30)
    if not date_to:
        date_to = today()

    filters = {
        "status": "Complete",
        "docstatus": 1,
        "start_time": [">=", date_from],
        "end_time": ["<=", date_to + " 23:59:59"],
    }
    if machine:
        filters["machine"] = machine

    entries = frappe.get_all("Production Entry",
        filters=filters,
        fields=["name", "machine", "machine_name", "start_time",
                "oee_pct", "availability_pct", "performance_pct", "quality_pct",
                "good_qty", "waste_qty", "reject_qty", "run_time_min",
                "setup_time_min", "shift"],
        order_by="start_time asc")

    # OEE trend by day
    daily_oee = {}
    for e in entries:
        day = str(getdate(e.start_time))
        if day not in daily_oee:
            daily_oee[day] = {"total_oee": 0, "count": 0}
        daily_oee[day]["total_oee"] += flt(e.oee_pct)
        daily_oee[day]["count"] += 1

    oee_trend = []
    for day in sorted(daily_oee.keys()):
        avg = daily_oee[day]["total_oee"] / daily_oee[day]["count"]
        oee_trend.append({"date": day, "oee": round(avg, 1)})

    # Machine comparison
    machine_stats = {}
    for e in entries:
        m = e.machine_name or e.machine
        if m not in machine_stats:
            machine_stats[m] = {"oee_sum": 0, "count": 0, "run_hours": 0, "downtime_hours": 0}
        machine_stats[m]["oee_sum"] += flt(e.oee_pct)
        machine_stats[m]["count"] += 1
        machine_stats[m]["run_hours"] += flt(e.run_time_min) / 60
        machine_stats[m]["downtime_hours"] += flt(e.setup_time_min) / 60

    machine_comparison = []
    for m, stats in sorted(machine_stats.items()):
        machine_comparison.append({
            "machine": m,
            "avg_oee": round(stats["oee_sum"] / stats["count"], 1) if stats["count"] > 0 else 0,
            "run_hours": round(stats["run_hours"], 1),
            "entries": stats["count"],
        })

    # Downtime reasons
    downtime_data = frappe.db.sql("""
        SELECT pd.reason, SUM(pd.duration_min) as total_min
        FROM `tabProduction Downtime` pd
        JOIN `tabProduction Entry` pe ON pd.parent = pe.name
        WHERE pe.start_time >= %s AND pe.start_time <= %s AND pe.docstatus = 1
        GROUP BY pd.reason ORDER BY total_min DESC LIMIT 10
    """, (date_from, date_to + " 23:59:59"), as_dict=True)

    # Overall averages
    total_entries = len(entries)
    avg_oee = round(sum(flt(e.oee_pct) for e in entries) / total_entries, 1) if total_entries else 0
    avg_avail = round(sum(flt(e.availability_pct) for e in entries) / total_entries, 1) if total_entries else 0
    avg_perf = round(sum(flt(e.performance_pct) for e in entries) / total_entries, 1) if total_entries else 0
    avg_qual = round(sum(flt(e.quality_pct) for e in entries) / total_entries, 1) if total_entries else 0

    return {
        "avg_oee": avg_oee,
        "avg_availability": avg_avail,
        "avg_performance": avg_perf,
        "avg_quality": avg_qual,
        "total_entries": total_entries,
        "oee_trend": oee_trend,
        "machine_comparison": machine_comparison,
        "downtime_reasons": [{"reason": d.reason, "hours": round(flt(d.total_min) / 60, 1)} for d in downtime_data],
    }


def get_profitability_dashboard(date_from=None, date_to=None):
    """Profitability analytics from estimates and sales orders."""
    if not date_from:
        date_from = add_days(today(), -365)
    if not date_to:
        date_to = today()

    # Monthly revenue from Sales Orders
    monthly_revenue = frappe.db.sql("""
        SELECT DATE_FORMAT(transaction_date, '%%Y-%%m') as month,
               SUM(grand_total) as revenue
        FROM `tabSales Order`
        WHERE transaction_date BETWEEN %s AND %s AND docstatus = 1
        GROUP BY month ORDER BY month
    """, (date_from, date_to), as_dict=True)

    # Estimate win rate
    total_estimates = frappe.db.count("Corrugated Estimate",
        {"estimate_date": ["between", [date_from, date_to]]})
    accepted = frappe.db.count("Corrugated Estimate",
        {"estimate_date": ["between", [date_from, date_to]], "status": "Accepted"})
    win_rate = round(accepted / total_estimates * 100, 1) if total_estimates > 0 else 0

    # Top customers by revenue
    top_customers = frappe.db.sql("""
        SELECT customer, customer_name, SUM(grand_total) as total_revenue,
               COUNT(*) as order_count
        FROM `tabSales Order`
        WHERE transaction_date BETWEEN %s AND %s AND docstatus = 1
        GROUP BY customer, customer_name
        ORDER BY total_revenue DESC LIMIT 10
    """, (date_from, date_to), as_dict=True)

    # Estimate margin data
    estimates = frappe.get_all("Corrugated Estimate",
        filters={"estimate_date": ["between", [date_from, date_to]], "status": "Accepted"},
        fields=["name", "customer", "box_style"])

    total_cogs = 0
    total_sell = 0
    for est in estimates:
        qty_rows = frappe.get_all("Corrugated Estimate Quantity",
            filters={"parent": est.name},
            fields=["total_cogs", "extended_total"])
        for row in qty_rows:
            total_cogs += flt(row.total_cogs)
            total_sell += flt(row.extended_total)

    gross_margin = round((total_sell - total_cogs) / total_sell * 100, 1) if total_sell > 0 else 0

    return {
        "monthly_revenue": monthly_revenue,
        "total_revenue": sum(flt(m.revenue) for m in monthly_revenue),
        "total_estimates": total_estimates,
        "accepted_estimates": accepted,
        "win_rate": win_rate,
        "top_customers": top_customers,
        "gross_margin": gross_margin,
        "total_cogs": round(total_cogs, 2),
        "total_sell": round(total_sell, 2),
    }


def get_waste_dashboard(date_from=None, date_to=None, machine=None):
    """Waste analytics from production entries."""
    if not date_from:
        date_from = add_days(today(), -30)
    if not date_to:
        date_to = today()

    filters = {"status": "Complete", "docstatus": 1,
               "start_time": [">=", date_from], "end_time": ["<=", date_to + " 23:59:59"]}
    if machine:
        filters["machine"] = machine

    entries = frappe.get_all("Production Entry",
        filters=filters,
        fields=["name", "machine", "machine_name", "start_time",
                "good_qty", "waste_qty", "reject_qty", "shift", "planned_qty"],
        order_by="start_time asc")

    # Daily waste trend
    daily_waste = {}
    for e in entries:
        day = str(getdate(e.start_time))
        total = cint(e.good_qty) + cint(e.waste_qty) + cint(e.reject_qty)
        if day not in daily_waste:
            daily_waste[day] = {"waste": 0, "total": 0}
        daily_waste[day]["waste"] += cint(e.waste_qty) + cint(e.reject_qty)
        daily_waste[day]["total"] += total

    waste_trend = []
    for day in sorted(daily_waste.keys()):
        d = daily_waste[day]
        pct = round(d["waste"] / d["total"] * 100, 1) if d["total"] > 0 else 0
        waste_trend.append({"date": day, "waste_pct": pct, "waste_qty": d["waste"]})

    # Waste by machine
    machine_waste = {}
    for e in entries:
        m = e.machine_name or e.machine
        if m not in machine_waste:
            machine_waste[m] = {"waste": 0, "total": 0}
        machine_waste[m]["waste"] += cint(e.waste_qty) + cint(e.reject_qty)
        machine_waste[m]["total"] += cint(e.good_qty) + cint(e.waste_qty) + cint(e.reject_qty)

    waste_by_machine = []
    for m, d in sorted(machine_waste.items()):
        waste_by_machine.append({
            "machine": m,
            "waste_pct": round(d["waste"] / d["total"] * 100, 1) if d["total"] > 0 else 0,
            "waste_qty": d["waste"],
        })

    # Waste by shift
    shift_waste = {}
    for e in entries:
        s = e.shift or "Day"
        if s not in shift_waste:
            shift_waste[s] = {"waste": 0, "total": 0}
        shift_waste[s]["waste"] += cint(e.waste_qty) + cint(e.reject_qty)
        shift_waste[s]["total"] += cint(e.good_qty) + cint(e.waste_qty) + cint(e.reject_qty)

    waste_by_shift = []
    for s, d in shift_waste.items():
        waste_by_shift.append({
            "shift": s,
            "waste_pct": round(d["waste"] / d["total"] * 100, 1) if d["total"] > 0 else 0,
        })

    # Overall
    total_good = sum(cint(e.good_qty) for e in entries)
    total_waste = sum(cint(e.waste_qty) + cint(e.reject_qty) for e in entries)
    total_produced = total_good + total_waste
    overall_waste_pct = round(total_waste / total_produced * 100, 1) if total_produced > 0 else 0

    return {
        "overall_waste_pct": overall_waste_pct,
        "total_good": total_good,
        "total_waste": total_waste,
        "total_produced": total_produced,
        "waste_trend": waste_trend,
        "waste_by_machine": waste_by_machine,
        "waste_by_shift": waste_by_shift,
    }


def get_quality_dashboard(date_from=None, date_to=None):
    """Quality analytics from QC inspections and NCRs."""
    if not date_from:
        date_from = add_days(today(), -30)
    if not date_to:
        date_to = today()

    # Inspection stats
    total_inspections = frappe.db.count("QC Inspection",
        {"inspection_date": ["between", [date_from, date_to + " 23:59:59"]], "docstatus": 1})
    passed = frappe.db.count("QC Inspection",
        {"inspection_date": ["between", [date_from, date_to + " 23:59:59"]], "docstatus": 1, "overall_result": "Pass"})
    failed = frappe.db.count("QC Inspection",
        {"inspection_date": ["between", [date_from, date_to + " 23:59:59"]], "docstatus": 1, "overall_result": "Fail"})
    first_pass_yield = round(passed / total_inspections * 100, 1) if total_inspections > 0 else 0

    # Open NCRs by severity
    ncr_by_severity = frappe.db.sql("""
        SELECT severity, COUNT(*) as count
        FROM `tabNon Conformance Report`
        WHERE status != 'Closed' AND docstatus = 1
        GROUP BY severity
    """, as_dict=True)

    # Total COPQ
    copq = frappe.db.sql("""
        SELECT COALESCE(SUM(cost_of_quality), 0) as total
        FROM `tabNon Conformance Report`
        WHERE creation BETWEEN %s AND %s AND docstatus = 1
    """, (date_from, date_to + " 23:59:59"), as_dict=True)
    total_copq = flt(copq[0].total) if copq else 0

    # Open complaints
    open_complaints = frappe.db.count("Customer Complaint",
        {"status": ["in", ["Open", "Investigating"]], "docstatus": 1})

    # Defect types from test results
    defect_types = frappe.db.sql("""
        SELECT qtr.test_name, COUNT(*) as count
        FROM `tabQC Test Result` qtr
        JOIN `tabQC Inspection` qi ON qtr.parent = qi.name
        WHERE qtr.pass_fail = 'Fail' AND qi.docstatus = 1
          AND qi.inspection_date BETWEEN %s AND %s
        GROUP BY qtr.test_name ORDER BY count DESC LIMIT 10
    """, (date_from, date_to + " 23:59:59"), as_dict=True)

    return {
        "total_inspections": total_inspections,
        "passed": passed,
        "failed": failed,
        "first_pass_yield": first_pass_yield,
        "ncr_by_severity": ncr_by_severity,
        "total_copq": total_copq,
        "open_complaints": open_complaints,
        "defect_types": defect_types,
    }
