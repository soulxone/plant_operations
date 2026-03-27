frappe.pages["production-board"].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Production Board",
        single_column: true,
    });

    // Load CSS
    frappe.require("production_board.bundle.css", function () {});

    $(frappe.render_template("production_board")).appendTo(page.body);

    new ProductionBoard(wrapper, page);
};

/* ═══════════════════════════════════════════════════════════════════════════
   ProductionBoard — Gantt-style production scheduling view
   ═══════════════════════════════════════════════════════════════════════════ */

class ProductionBoard {
    constructor(wrapper, page) {
        this.wrapper = wrapper;
        this.page = page;
        this.date = frappe.datetime.get_today();
        this.shift = "All";
        this.machines = [];
        this.refreshTimer = null;

        // Timeline config: 6 AM to 6 PM (12 hours)
        this.startHour = 6;
        this.endHour = 18;
        this.totalHours = this.endHour - this.startHour;

        this.init();
    }

    init() {
        // Read URL params
        let params = frappe.utils.get_url_dict();
        if (params.date) this.date = params.date;
        if (params.machine) this.filterMachine = params.machine;

        this.bindEvents();
        this.renderTimelineHeader();
        this.setDateDisplay();
        this.loadData();

        // Auto-refresh every 60 seconds
        this.refreshTimer = setInterval(() => this.loadData(), 60000);
    }

    bindEvents() {
        let me = this;

        // Date picker
        $("#pb-date-picker").val(this.date).on("change", function () {
            me.date = $(this).val();
            me.setDateDisplay();
            me.loadData();
        });

        // Previous day
        $("#pb-prev-day").on("click", function () {
            me.date = frappe.datetime.add_days(me.date, -1);
            $("#pb-date-picker").val(me.date);
            me.setDateDisplay();
            me.loadData();
        });

        // Next day
        $("#pb-next-day").on("click", function () {
            me.date = frappe.datetime.add_days(me.date, 1);
            $("#pb-date-picker").val(me.date);
            me.setDateDisplay();
            me.loadData();
        });

        // Today button
        $("#pb-today-btn").on("click", function () {
            me.date = frappe.datetime.get_today();
            $("#pb-date-picker").val(me.date);
            me.setDateDisplay();
            me.loadData();
        });

        // Shift filter
        $("#pb-shift-filter").on("change", function () {
            me.shift = $(this).val();
            me.loadData();
        });

        // Auto Schedule
        $("#pb-auto-schedule").on("click", function () {
            frappe.confirm(
                __("Auto-schedule unassigned Job Cards for {0}?", [me.date]),
                function () {
                    frappe.call({
                        method: "plant_operations.plant_operations.api.auto_schedule_jobs",
                        args: { date: me.date },
                        freeze: true,
                        freeze_message: __("Auto-scheduling..."),
                        callback(r) {
                            if (r.message) {
                                frappe.show_alert({
                                    message: __(
                                        "{0} job(s) scheduled.",
                                        [r.message.scheduled_count || 0]
                                    ),
                                    indicator: "green",
                                });
                                me.loadData();
                            }
                        },
                    });
                }
            );
        });
    }

    setDateDisplay() {
        let d = moment(this.date);
        let display = d.format("dddd, MMMM D, YYYY");
        let isToday = this.date === frappe.datetime.get_today();
        $("#pb-date-display").text(isToday ? display + " (Today)" : display);
    }

    renderTimelineHeader() {
        let $hours = $("#pb-timeline-hours");
        $hours.empty();

        for (let h = this.startHour; h < this.endHour; h++) {
            let label = this.formatHour(h);
            $hours.append(
                `<div class="pb-hour-cell" data-hour="${h}">${label}</div>`
            );
        }
    }

    formatHour(h) {
        if (h === 0) return "12 AM";
        if (h < 12) return h + " AM";
        if (h === 12) return "12 PM";
        return (h - 12) + " PM";
    }

    loadData() {
        let me = this;

        frappe.call({
            method: "plant_operations.plant_operations.api.get_schedule_board",
            args: { date: me.date },
            callback(r) {
                if (r.message) {
                    me.machines = r.message;
                    me.renderBoard();
                }
            },
            error() {
                $("#pb-machine-rows").html(
                    '<div class="pb-loading" style="color:#e03131;">' +
                    '<i class="fa fa-exclamation-triangle"></i> ' +
                    'Failed to load schedule data.</div>'
                );
            },
        });
    }

    renderBoard() {
        let $rows = $("#pb-machine-rows");
        $rows.empty();

        if (!this.machines || this.machines.length === 0) {
            $rows.html(
                '<div class="pb-loading">' +
                '<i class="fa fa-info-circle"></i> No machines found. ' +
                'Ensure Corrugated Machine records exist and are enabled.</div>'
            );
            this.updateSummary([]);
            return;
        }

        let allItems = [];

        this.machines.forEach((machine) => {
            // Filter by machine if set from URL
            if (this.filterMachine && machine.machine_id !== this.filterMachine) {
                return;
            }

            let items = machine.schedule_items || [];
            allItems = allItems.concat(items);

            let $row = $(`
                <div class="pb-machine-row" data-machine="${machine.machine_id}">
                    <div class="pb-machine-label">
                        <div class="pb-machine-name">${frappe.utils.escape_html(machine.machine_name || machine.machine_id)}</div>
                        <div class="pb-machine-dept">${frappe.utils.escape_html(machine.department || "")}</div>
                        ${this.renderMachineStatus(machine)}
                    </div>
                    <div class="pb-timeline-lane">
                        ${this.renderGridLines()}
                        ${this.renderNowLine()}
                    </div>
                </div>
            `);

            let $lane = $row.find(".pb-timeline-lane");

            if (items.length === 0) {
                $lane.append('<div class="pb-empty-lane">No jobs scheduled</div>');
            } else {
                items.forEach((item) => {
                    let $bar = this.createJobBar(item, machine);
                    if ($bar) $lane.append($bar);
                });
            }

            $rows.append($row);
        });

        this.updateSummary(allItems);
    }

    renderMachineStatus(machine) {
        let entry = machine.current_entry;
        if (entry) {
            let oee = entry.oee_pct ? ` | OEE ${parseFloat(entry.oee_pct).toFixed(0)}%` : "";
            return `<div class="pb-machine-status running">
                <i class="fa fa-circle fa-xs"></i>
                ${entry.status} (${entry.good_qty || 0} pcs${oee})
            </div>`;
        }
        return '<div class="pb-machine-status idle">Idle</div>';
    }

    renderGridLines() {
        let html = "";
        for (let h = 0; h <= this.totalHours; h++) {
            let pct = (h / this.totalHours) * 100;
            html += `<div class="pb-grid-line" style="left:${pct}%"></div>`;
        }
        return html;
    }

    renderNowLine() {
        let now = moment();
        let todayStr = frappe.datetime.get_today();

        if (this.date !== todayStr) return "";

        let hour = now.hours() + now.minutes() / 60;
        if (hour < this.startHour || hour > this.endHour) return "";

        let pct = ((hour - this.startHour) / this.totalHours) * 100;
        return `<div class="pb-now-line" style="left:${pct}%"></div>`;
    }

    createJobBar(item, machine) {
        // Calculate bar position based on planned_start / planned_end
        let startPos, endPos;
        let schedDate = this.date;

        if (item.planned_start && item.planned_end) {
            let startM = moment(item.planned_start);
            let endM = moment(item.planned_end);
            let startHr = startM.hours() + startM.minutes() / 60;
            let endHr = endM.hours() + endM.minutes() / 60;

            startPos = ((startHr - this.startHour) / this.totalHours) * 100;
            endPos = ((endHr - this.startHour) / this.totalHours) * 100;
        } else {
            // No times set — distribute evenly by sequence
            let seq = (item.sequence || 1) - 1;
            let totalItems = (machine.schedule_items || []).length || 1;
            let totalMin = flt(item.estimated_run_min) + flt(item.estimated_setup_min);
            let barWidthHrs = Math.max(totalMin / 60, 0.5); // minimum 30 min display
            let barWidthPct = (barWidthHrs / this.totalHours) * 100;

            // Stack sequentially
            let prevEnd = 0;
            for (let i = 0; i < seq; i++) {
                let prev = (machine.schedule_items || [])[i];
                if (prev) {
                    let prevMin = flt(prev.estimated_run_min) + flt(prev.estimated_setup_min);
                    prevEnd += Math.max(prevMin / 60, 0.5);
                }
            }
            startPos = (prevEnd / this.totalHours) * 100;
            endPos = startPos + barWidthPct;
        }

        // Clamp
        startPos = Math.max(0, Math.min(startPos, 100));
        endPos = Math.max(startPos + 1, Math.min(endPos, 100));
        let widthPct = endPos - startPos;

        // Determine color class
        let colorClass = this.getBarColorClass(item);

        // Setup stripe width
        let totalMin = flt(item.estimated_run_min) + flt(item.estimated_setup_min);
        let setupPct = totalMin > 0
            ? (flt(item.estimated_setup_min) / totalMin) * 100
            : 0;

        // Label
        let label = item.customer || item.item_description || item.job_card || "Job";
        let qty = item.planned_qty ? ` (${item.planned_qty})` : "";

        let $bar = $(`
            <div class="pb-job-bar ${colorClass}"
                 style="left:${startPos}%; width:${widthPct}%"
                 data-item-name="${item.name}"
                 data-parent="${item.parent}"
                 title="${frappe.utils.escape_html(label)}${qty} — ${item.status}">
                <div class="pb-setup-stripe" style="width:${setupPct}%"></div>
                <span class="pb-bar-label">${frappe.utils.escape_html(label)}</span>
                <span class="pb-bar-qty">${item.planned_qty || ""}</span>
            </div>
        `);

        let me = this;
        $bar.on("click", function () {
            me.showJobDetail(item);
        });

        return $bar;
    }

    getBarColorClass(item) {
        // Hot priority overrides
        if (item.priority === "Hot") return "pb-bar-hot";

        // Check overdue: status is Pending and planned_end is in the past
        if (item.status === "Pending" && item.planned_end) {
            if (moment(item.planned_end).isBefore(moment())) {
                return "pb-bar-overdue";
            }
        }

        switch (item.status) {
            case "Running": return "pb-bar-running";
            case "Complete": return "pb-bar-complete";
            case "Skipped": return "pb-bar-skipped";
            default: return "pb-bar-pending";
        }
    }

    showJobDetail(item) {
        let me = this;

        let setupMin = flt(item.estimated_setup_min);
        let runMin = flt(item.estimated_run_min);
        let totalMin = setupMin + runMin;

        let fields = [
            { label: "Job Card", value: item.job_card || "-" },
            { label: "Sales Order", value: item.sales_order || "-" },
            { label: "Customer", value: item.customer || "-" },
            { label: "Description", value: item.item_description || "-" },
            { label: "Planned Qty", value: item.planned_qty || 0 },
            { label: "Priority", value: item.priority || "Normal" },
            { label: "Status", value: item.status || "Pending" },
            { label: "Setup Time", value: setupMin + " min" },
            { label: "Run Time", value: runMin + " min" },
            { label: "Total Time", value: totalMin.toFixed(1) + " min (" + (totalMin / 60).toFixed(1) + " hrs)" },
            { label: "Planned Start", value: item.planned_start || "Not set" },
            { label: "Planned End", value: item.planned_end || "Not set" },
            { label: "Actual Start", value: item.actual_start || "-" },
            { label: "Actual End", value: item.actual_end || "-" },
        ];

        let html = '<table class="table table-bordered table-sm" style="margin:0">';
        fields.forEach((f) => {
            html += `<tr><th style="width:35%;font-size:12px">${f.label}</th>
                     <td style="font-size:12px">${frappe.utils.escape_html(String(f.value))}</td></tr>`;
        });
        html += "</table>";

        let buttons = [];

        // Start Job button (only if Pending)
        if (item.status === "Pending") {
            buttons.push({
                label: __("Start Job"),
                class: "btn-primary",
                handler() {
                    me.startJob(item, dlg);
                },
            });
        }

        // Mark Complete (if Running)
        if (item.status === "Running") {
            buttons.push({
                label: __("Mark Complete"),
                class: "btn-success",
                handler() {
                    me.completeJob(item, dlg);
                },
            });
        }

        // Open Schedule link
        buttons.push({
            label: __("Open Schedule"),
            class: "btn-default",
            handler() {
                frappe.set_route("Form", "Production Schedule", item.parent);
                dlg.hide();
            },
        });

        let dlg = new frappe.ui.Dialog({
            title: __("Job Detail — {0}", [item.customer || item.job_card || "Job"]),
            size: "large",
        });

        dlg.$body.html(html);

        // Add custom buttons
        buttons.forEach((btn) => {
            dlg.add_custom_action(btn.label, btn.handler, btn.class);
        });

        dlg.show();
    }

    startJob(item, dlg) {
        frappe.call({
            method: "plant_operations.plant_operations.api.start_schedule_job",
            args: {
                schedule_name: item.parent,
                item_name: item.name,
            },
            freeze: true,
            freeze_message: __("Starting job..."),
            callback: (r) => {
                if (r.message) {
                    frappe.show_alert({
                        message: __("Job started. Production Entry: {0}", [r.message.production_entry || ""]),
                        indicator: "green",
                    });
                    dlg.hide();
                    this.loadData();
                }
            },
        });
    }

    completeJob(item, dlg) {
        frappe.call({
            method: "plant_operations.plant_operations.api.complete_schedule_job",
            args: {
                schedule_name: item.parent,
                item_name: item.name,
            },
            freeze: true,
            freeze_message: __("Completing job..."),
            callback: (r) => {
                if (r.message) {
                    frappe.show_alert({
                        message: __("Job marked complete."),
                        indicator: "green",
                    });
                    dlg.hide();
                    this.loadData();
                }
            },
        });
    }

    updateSummary(allItems) {
        let totalJobs = allItems.length;
        let totalPlannedMin = 0;
        let complete = 0;
        let pending = 0;
        let running = 0;
        let overdue = 0;
        let now = moment();

        allItems.forEach((item) => {
            totalPlannedMin += flt(item.estimated_run_min) + flt(item.estimated_setup_min);

            switch (item.status) {
                case "Complete": complete++; break;
                case "Running": running++; break;
                case "Skipped": break;
                default:
                    if (item.planned_end && moment(item.planned_end).isBefore(now)) {
                        overdue++;
                    } else {
                        pending++;
                    }
            }
        });

        let plannedHrs = (totalPlannedMin / 60).toFixed(1);
        let availableHrs = this.machines.length * (this.endHour - this.startHour);
        let capacityPct = availableHrs > 0
            ? ((totalPlannedMin / 60 / availableHrs) * 100).toFixed(0)
            : 0;

        $("#pb-total-jobs").text(totalJobs);
        $("#pb-planned-hours").text(plannedHrs + " hrs");
        $("#pb-capacity-pct").text(capacityPct + "%");
        $("#pb-jobs-complete").text(complete);
        $("#pb-jobs-pending").text(pending);
        $("#pb-jobs-running").text(running);
        $("#pb-jobs-overdue").text(overdue);
        $("#pb-capacity-stat").text(
            `${this.machines.length} machines | ${availableHrs} hrs available`
        );
    }

    destroy() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
        }
    }
}
