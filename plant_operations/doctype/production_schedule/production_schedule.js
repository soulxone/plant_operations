// Copyright (c) 2026, Plant Operations and contributors
// For license information, please see license.txt

frappe.ui.form.on("Production Schedule", {
    refresh(frm) {
        // Set schedule_name from name after save
        if (frm.doc.name && !frm.doc.schedule_name) {
            frm.set_value("schedule_name", frm.doc.name);
        }

        // Open Production Board button
        if (!frm.is_new()) {
            frm.add_custom_button(__("Open Production Board"), function () {
                let date = frm.doc.schedule_date || frappe.datetime.get_today();
                let machine = frm.doc.machine || "";
                frappe.set_route("production-board", {
                    date: date,
                    machine: machine,
                });
            }, __("View"));
        }

        // Auto-Fill from Job Cards button (only in Draft)
        if (frm.doc.docstatus === 0 && frm.doc.machine) {
            frm.add_custom_button(__("Auto-Fill from Job Cards"), function () {
                frappe.call({
                    method: "plant_operations.plant_operations.api.auto_fill_schedule",
                    args: {
                        schedule_name: frm.doc.name,
                        machine: frm.doc.machine,
                        date: frm.doc.schedule_date,
                    },
                    freeze: true,
                    freeze_message: __("Finding unscheduled Job Cards..."),
                    callback(r) {
                        if (r.message) {
                            frappe.show_alert({
                                message: __("{0} job(s) added to schedule.", [r.message.added_count || 0]),
                                indicator: r.message.added_count > 0 ? "green" : "orange",
                            });
                            frm.reload_doc();
                        }
                    },
                });
            }, __("Actions"));
        }

        // Color the status indicator
        if (frm.doc.status) {
            let indicator_map = {
                "Draft": "orange",
                "Published": "blue",
                "In Progress": "yellow",
                "Complete": "green",
            };
            frm.page.set_indicator(frm.doc.status, indicator_map[frm.doc.status] || "gray");
        }
    },

    schedule_items_on_form_rendered(frm) {
        // Recalculate totals when items table is modified
        frm.trigger("calculate_totals");
    },

    calculate_totals(frm) {
        let total_planned_min = 0;
        let total_actual_min = 0;

        (frm.doc.schedule_items || []).forEach(function (item) {
            total_planned_min += flt(item.estimated_run_min) + flt(item.estimated_setup_min);
            if (item.actual_start && item.actual_end) {
                let diff = moment(item.actual_end).diff(moment(item.actual_start), "minutes", true);
                total_actual_min += Math.max(0, diff);
            }
        });

        let shift_hrs = flt(frm.doc.shift_hours) || 8;
        frm.set_value("total_planned_hours", (total_planned_min / 60).toFixed(2));
        frm.set_value("total_actual_hours", (total_actual_min / 60).toFixed(2));
        frm.set_value("total_jobs", (frm.doc.schedule_items || []).length);
        frm.set_value(
            "utilization_pct",
            shift_hrs > 0 ? ((total_planned_min / 60 / shift_hrs) * 100).toFixed(1) : 0
        );
    },
});

frappe.ui.form.on("Schedule Item", {
    estimated_run_min(frm) { frm.trigger("calculate_totals"); },
    estimated_setup_min(frm) { frm.trigger("calculate_totals"); },
    actual_start(frm) { frm.trigger("calculate_totals"); },
    actual_end(frm) { frm.trigger("calculate_totals"); },
    schedule_items_remove(frm) { frm.trigger("calculate_totals"); },
});
