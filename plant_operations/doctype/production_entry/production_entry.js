frappe.ui.form.on("Production Entry", {
    refresh(frm) {
        // --- OEE colored indicator ---
        if (frm.doc.oee_pct) {
            let color = "red";
            if (frm.doc.oee_pct >= 85) color = "green";
            else if (frm.doc.oee_pct >= 60) color = "orange";

            frm.dashboard.add_indicator(
                __("OEE: {0}%", [frm.doc.oee_pct]),
                color
            );
        }

        // --- Dashboard headline: total pieces & waste ---
        let total_produced =
            (frm.doc.good_qty || 0) +
            (frm.doc.waste_qty || 0) +
            (frm.doc.reject_qty || 0);
        if (total_produced > 0) {
            frm.dashboard.add_comment(
                __("Total: {0} pcs | Good: {1} | Waste: {2} | Reject: {3}", [
                    total_produced,
                    frm.doc.good_qty || 0,
                    frm.doc.waste_qty || 0,
                    frm.doc.reject_qty || 0,
                ]),
                "blue",
                true
            );
        }

        // --- Status indicator ---
        if (frm.doc.status === "Running") {
            frm.dashboard.add_indicator(__("Running"), "green");
        } else if (frm.doc.status === "Paused") {
            frm.dashboard.add_indicator(__("Paused"), "orange");
        } else if (frm.doc.status === "Complete") {
            frm.dashboard.add_indicator(__("Complete"), "blue");
        }

        // --- Timer buttons (only for draft docs) ---
        if (frm.doc.docstatus === 0) {
            if (frm.doc.status === "Running" && !frm.doc.__timer_running) {
                frm.add_custom_button(__("Start Timer"), function () {
                    frm.doc.__timer_start = frappe.datetime.now_datetime();
                    frm.doc.__timer_running = true;
                    frappe.show_alert({
                        message: __("Timer started"),
                        indicator: "green",
                    });
                    frm.dirty();
                });
            }

            if (frm.doc.__timer_running) {
                frm.add_custom_button(
                    __("Stop Timer"),
                    function () {
                        if (!frm.doc.__timer_start) {
                            frappe.msgprint(__("No timer running."));
                            return;
                        }
                        let start = moment(frm.doc.__timer_start);
                        let end = moment(frappe.datetime.now_datetime());
                        let diff_min = end.diff(start, "minutes", true);
                        diff_min = Math.round(diff_min * 10) / 10;

                        frm.set_value(
                            "run_time_min",
                            (frm.doc.run_time_min || 0) + diff_min
                        );
                        frm.doc.__timer_running = false;
                        frm.doc.__timer_start = null;

                        frappe.show_alert({
                            message: __("Timer stopped. Added {0} min", [diff_min]),
                            indicator: "blue",
                        });
                        frm.dirty();
                    },
                    __("Timer")
                );
            }

            // --- Quick actions ---
            if (frm.doc.status === "Running") {
                frm.add_custom_button(
                    __("Pause"),
                    function () {
                        frappe.call({
                            method: "plant_operations.api.pause_production",
                            args: { entry: frm.doc.name },
                            callback(r) {
                                if (r.message) frm.reload_doc();
                            },
                        });
                    },
                    __("Actions")
                );
            }

            if (frm.doc.status === "Paused") {
                frm.add_custom_button(
                    __("Resume"),
                    function () {
                        frappe.call({
                            method: "plant_operations.api.resume_production",
                            args: { entry: frm.doc.name },
                            callback(r) {
                                if (r.message) frm.reload_doc();
                            },
                        });
                    },
                    __("Actions")
                );
            }

            if (
                frm.doc.status === "Running" ||
                frm.doc.status === "Paused"
            ) {
                frm.add_custom_button(
                    __("Stop & Complete"),
                    function () {
                        let d = new frappe.ui.Dialog({
                            title: __("Stop Production"),
                            fields: [
                                {
                                    fieldname: "good_qty",
                                    fieldtype: "Int",
                                    label: "Good Qty",
                                    default: frm.doc.good_qty || 0,
                                },
                                {
                                    fieldname: "waste_qty",
                                    fieldtype: "Int",
                                    label: "Waste Qty",
                                    default: frm.doc.waste_qty || 0,
                                },
                                {
                                    fieldname: "reject_qty",
                                    fieldtype: "Int",
                                    label: "Reject Qty",
                                    default: frm.doc.reject_qty || 0,
                                },
                            ],
                            primary_action_label: __("Stop"),
                            primary_action(values) {
                                frappe.call({
                                    method: "plant_operations.api.stop_production",
                                    args: {
                                        entry: frm.doc.name,
                                        good_qty: values.good_qty,
                                        waste_qty: values.waste_qty,
                                        reject_qty: values.reject_qty,
                                    },
                                    callback(r) {
                                        d.hide();
                                        if (r.message) frm.reload_doc();
                                    },
                                });
                            },
                        });
                        d.show();
                    },
                    __("Actions")
                );
            }
        }

        // --- Link to Shop Floor Terminal ---
        if (frm.doc.machine) {
            frm.add_custom_button(__("Shop Floor Terminal"), function () {
                frappe.set_route("shop-floor-terminal", {
                    machine: frm.doc.machine,
                });
            });
        }
    },

    machine(frm) {
        // Auto-fetch machine name
        if (frm.doc.machine) {
            frappe.db.get_value(
                "Corrugated Machine",
                frm.doc.machine,
                "machine_name",
                (r) => {
                    if (r) frm.set_value("machine_name", r.machine_name);
                }
            );
        }
    },
});
