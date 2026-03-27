frappe.pages["shop-floor-terminal"].on_page_load = function (wrapper) {
    frappe.ui.make_app_page({
        parent: wrapper,
        title: "Shop Floor Terminal",
        single_column: true,
    });

    // Hide standard navbar/sidebar for full-screen terminal
    $(".page-head, .layout-side-section").hide();
    $(wrapper).find(".layout-main-section").css({
        "max-width": "100%",
        padding: 0,
        margin: 0,
    });

    new ShopFloorTerminal(wrapper);
};

class ShopFloorTerminal {
    constructor(wrapper) {
        this.wrapper = wrapper;
        this.$page = $(wrapper).find(".layout-main-section-wrapper");
        this.entry = null;
        this.machine = null;
        this.timerInterval = null;
        this.refreshInterval = null;
        this.numpadValue = "0";

        this.init();
    }

    init() {
        this.loadMachines();
        this.bindEvents();
        this.startAutoRefresh();

        // Check URL params for pre-selected machine
        let params = frappe.utils.get_url_dict();
        if (params.machine) {
            setTimeout(() => {
                $("#sft-machine-select").val(params.machine).trigger("change");
            }, 500);
        }
    }

    // ==========================================
    // MACHINE LOADING
    // ==========================================
    loadMachines() {
        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Corrugated Machine",
                filters: { enabled: 1 },
                fields: ["machine_id", "machine_name", "department"],
                order_by: "department asc, machine_name asc",
                limit_page_length: 0,
            },
            async: false,
            callback: (r) => {
                if (!r.message) return;
                let $sel = $("#sft-machine-select");
                let lastDept = "";
                r.message.forEach((m) => {
                    let prefix = "";
                    if (m.department && m.department !== lastDept) {
                        prefix = `[${m.department}] `;
                        lastDept = m.department;
                    }
                    $sel.append(
                        `<option value="${m.machine_id}">${prefix}${m.machine_name} (${m.machine_id})</option>`
                    );
                });
            },
        });
    }

    // ==========================================
    // EVENT BINDING
    // ==========================================
    bindEvents() {
        let self = this;

        // Machine select
        $("#sft-machine-select").on("change", function () {
            self.machine = $(this).val();
            if (self.machine) {
                self.loadMachineStatus();
            } else {
                self.resetDisplay();
            }
        });

        // Control buttons
        $("#sft-btn-start").on("click", () => this.startProduction());
        $("#sft-btn-pause").on("click", () => this.pauseProduction());
        $("#sft-btn-resume").on("click", () => this.resumeProduction());
        $("#sft-btn-stop").on("click", () => this.stopProduction());

        // Numpad
        $(".sft-numpad-btn").on("click", function () {
            let val = $(this).data("val").toString();
            self.handleNumpad(val);
        });

        // Downtime buttons
        $(".sft-dt-btn").on("click", function () {
            let reason = $(this).data("reason");
            self.logDowntime(reason);
        });
    }

    // ==========================================
    // MACHINE STATUS
    // ==========================================
    loadMachineStatus() {
        if (!this.machine) return;

        frappe.call({
            method: "plant_operations.api.get_machine_status",
            args: { machine: this.machine },
            callback: (r) => {
                if (!r.message) return;
                let data = r.message;

                $("#sft-machine-name").text(data.machine_name || "");

                if (data.entry) {
                    this.entry = data.entry;
                    this.updateDisplay(data);
                    this.updateButtons(data.status);
                    this.updateStatusBadge(data.status);

                    if (data.status === "Running" && data.start_time) {
                        this.startTimer(data.start_time);
                    } else {
                        this.stopTimer();
                    }
                } else {
                    this.entry = null;
                    this.resetDisplay();
                    this.updateButtons("Idle");
                    this.updateStatusBadge("Idle");
                    this.stopTimer();
                }
            },
        });
    }

    updateDisplay(data) {
        $("#sft-good-count").text(this.formatNumber(data.good_qty || 0));
        $("#sft-waste-count").text(this.formatNumber(data.waste_qty || 0));
        $("#sft-planned-count").text(`/ ${this.formatNumber(data.planned_qty || 0)} planned`);
        $("#sft-reject-count").text(`Reject: ${data.reject_qty || 0}`);
        $("#sft-job-value").text(data.job_card || "--");
        $("#sft-order-value").text(data.sales_order || "--");
        $("#sft-operator-value").text(this.shortUser(data.operator));

        // Speed
        let speed = data.speed_actual || 0;
        $("#sft-speed-value").text(Math.round(speed));
        let ratedSpeed = data.rated_speed || 0;
        $("#sft-rated-speed").text(ratedSpeed ? `Rated: ${ratedSpeed}` : "Rated: --");

        // OEE gauge
        this.updateOEE(data.oee_pct || 0, data.availability_pct || 0, data.performance_pct || 0, data.quality_pct || 0);
    }

    updateOEE(oee, avail, perf, qual) {
        let circumference = 2 * Math.PI * 52; // 326.73
        let pct = Math.min(100, Math.max(0, oee));
        let offset = circumference - (pct / 100) * circumference;

        let $fill = $("#sft-gauge-fill");
        $fill.css("stroke-dashoffset", offset);

        // Color
        let color = "#ef5350"; // red
        if (pct >= 85) color = "#69f0ae"; // green
        else if (pct >= 60) color = "#ffd740"; // yellow

        $fill.css("stroke", color);
        $("#sft-gauge-text").text(Math.round(pct) + "%").css("fill", color);

        // Breakdown
        $("#sft-avail-pct").text(Math.round(avail));
        $("#sft-perf-pct").text(Math.round(perf));
        $("#sft-qual-pct").text(Math.round(qual));
    }

    resetDisplay() {
        $("#sft-good-count").text("0");
        $("#sft-waste-count").text("0");
        $("#sft-planned-count").text("/ 0 planned");
        $("#sft-reject-count").text("Reject: 0");
        $("#sft-job-value").text("--");
        $("#sft-order-value").text("--");
        $("#sft-operator-value").text("--");
        $("#sft-speed-value").text("0");
        $("#sft-rated-speed").text("Rated: --");
        $("#sft-machine-name").text("");
        this.updateOEE(0, 0, 0, 0);
        this.stopTimer();
        $("#sft-timer").text("00:00:00");
    }

    updateButtons(status) {
        let $start = $("#sft-btn-start");
        let $pause = $("#sft-btn-pause");
        let $resume = $("#sft-btn-resume");
        let $stop = $("#sft-btn-stop");

        $start.prop("disabled", true).show();
        $pause.prop("disabled", true).show();
        $resume.prop("disabled", true).hide();
        $stop.prop("disabled", true);

        if (!this.machine) return;

        switch (status) {
            case "Idle":
                $start.prop("disabled", false);
                break;
            case "Running":
                $pause.prop("disabled", false);
                $stop.prop("disabled", false);
                $start.hide();
                break;
            case "Paused":
                $pause.hide();
                $resume.show().prop("disabled", false);
                $stop.prop("disabled", false);
                $start.hide();
                break;
            case "Complete":
                $start.prop("disabled", false);
                break;
        }
    }

    updateStatusBadge(status) {
        let $badge = $("#sft-status-badge");
        $badge
            .text(status.toUpperCase())
            .removeClass("running paused complete")
            .addClass(status.toLowerCase());
    }

    // ==========================================
    // PRODUCTION ACTIONS
    // ==========================================
    startProduction() {
        if (!this.machine) {
            frappe.show_alert({ message: "Select a machine first", indicator: "red" });
            return;
        }

        // Optional: ask for job card / planned qty
        let d = new frappe.ui.Dialog({
            title: "Start Production",
            fields: [
                { fieldname: "job_card", fieldtype: "Link", options: "Job Card", label: "Job Card" },
                { fieldname: "sales_order", fieldtype: "Link", options: "Sales Order", label: "Sales Order" },
                { fieldname: "planned_qty", fieldtype: "Int", label: "Planned Qty", default: 0 },
            ],
            primary_action_label: "Start",
            primary_action: (values) => {
                d.hide();
                frappe.call({
                    method: "plant_operations.api.start_production",
                    args: {
                        machine: this.machine,
                        job_card: values.job_card || "",
                        sales_order: values.sales_order || "",
                        planned_qty: values.planned_qty || 0,
                    },
                    callback: (r) => {
                        if (r.message && r.message.status === "success") {
                            frappe.show_alert({ message: "Production started!", indicator: "green" });
                            this.loadMachineStatus();
                        }
                    },
                });
            },
        });
        d.show();
    }

    pauseProduction() {
        if (!this.entry) return;
        frappe.call({
            method: "plant_operations.api.pause_production",
            args: { entry: this.entry },
            callback: (r) => {
                if (r.message) {
                    frappe.show_alert({ message: "Production paused", indicator: "orange" });
                    this.loadMachineStatus();
                }
            },
        });
    }

    resumeProduction() {
        if (!this.entry) return;
        frappe.call({
            method: "plant_operations.api.resume_production",
            args: { entry: this.entry },
            callback: (r) => {
                if (r.message) {
                    frappe.show_alert({ message: "Production resumed", indicator: "green" });
                    this.loadMachineStatus();
                }
            },
        });
    }

    stopProduction() {
        if (!this.entry) return;

        let d = new frappe.ui.Dialog({
            title: "Stop Production",
            fields: [
                { fieldname: "good_qty", fieldtype: "Int", label: "Good Qty", reqd: 1, default: parseInt($("#sft-good-count").text().replace(/,/g, "")) || 0 },
                { fieldname: "waste_qty", fieldtype: "Int", label: "Waste Qty", default: parseInt($("#sft-waste-count").text().replace(/,/g, "")) || 0 },
                { fieldname: "reject_qty", fieldtype: "Int", label: "Reject Qty", default: 0 },
            ],
            primary_action_label: "Stop & Complete",
            primary_action: (values) => {
                d.hide();
                frappe.call({
                    method: "plant_operations.api.stop_production",
                    args: {
                        entry: this.entry,
                        good_qty: values.good_qty,
                        waste_qty: values.waste_qty,
                        reject_qty: values.reject_qty,
                    },
                    callback: (r) => {
                        if (r.message) {
                            frappe.show_alert({
                                message: `Complete! OEE: ${r.message.oee || 0}%`,
                                indicator: "blue",
                            });
                            this.loadMachineStatus();
                        }
                    },
                });
            },
        });
        d.show();
    }

    // ==========================================
    // DOWNTIME
    // ==========================================
    logDowntime(reason) {
        if (!this.entry) {
            frappe.show_alert({ message: "No active production entry", indicator: "red" });
            return;
        }

        frappe.call({
            method: "plant_operations.api.log_downtime",
            args: {
                entry: this.entry,
                reason: reason,
            },
            callback: (r) => {
                if (r.message) {
                    frappe.show_alert({
                        message: `Downtime logged: ${reason}`,
                        indicator: "orange",
                    });
                    this.loadMachineStatus();
                }
            },
        });
    }

    // ==========================================
    // NUMPAD
    // ==========================================
    handleNumpad(val) {
        if (val === "C") {
            this.numpadValue = "0";
        } else if (val === "Enter") {
            this.submitCount();
            return;
        } else {
            if (this.numpadValue === "0") {
                this.numpadValue = val;
            } else {
                if (this.numpadValue.length < 8) {
                    this.numpadValue += val;
                }
            }
        }
        $("#sft-numpad-display").text(this.formatNumber(parseInt(this.numpadValue) || 0));
    }

    submitCount() {
        if (!this.entry) {
            frappe.show_alert({ message: "No active production entry", indicator: "red" });
            return;
        }

        let target = $("#sft-count-target").val();
        let qty = parseInt(this.numpadValue) || 0;

        frappe.call({
            method: "plant_operations.api.update_count",
            args: {
                entry: this.entry,
                field: target + "_qty",
                value: qty,
            },
            callback: (r) => {
                if (r.message) {
                    frappe.show_alert({
                        message: `${target} qty updated to ${this.formatNumber(qty)}`,
                        indicator: "green",
                    });
                    this.numpadValue = "0";
                    $("#sft-numpad-display").text("0");
                    this.loadMachineStatus();
                }
            },
        });
    }

    // ==========================================
    // TIMER
    // ==========================================
    startTimer(startTimeStr) {
        this.stopTimer();
        let startTime = moment(startTimeStr);

        this.timerInterval = setInterval(() => {
            let now = moment();
            let diff = moment.duration(now.diff(startTime));
            let hrs = String(Math.floor(diff.asHours())).padStart(2, "0");
            let mins = String(diff.minutes()).padStart(2, "0");
            let secs = String(diff.seconds()).padStart(2, "0");
            $("#sft-timer").text(`${hrs}:${mins}:${secs}`);
        }, 1000);
    }

    stopTimer() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
    }

    // ==========================================
    // AUTO REFRESH
    // ==========================================
    startAutoRefresh() {
        this.refreshInterval = setInterval(() => {
            if (this.machine && this.entry) {
                this.loadMachineStatus();
            }
        }, 5000);
    }

    // ==========================================
    // HELPERS
    // ==========================================
    formatNumber(n) {
        return Number(n).toLocaleString();
    }

    shortUser(email) {
        if (!email) return "--";
        return email.split("@")[0];
    }

    destroy() {
        this.stopTimer();
        if (this.refreshInterval) clearInterval(this.refreshInterval);
    }
}
