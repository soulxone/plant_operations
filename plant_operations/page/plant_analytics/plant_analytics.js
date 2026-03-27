/* ═══════════════════════════════════════════════════════════════════════════
   Plant Analytics Dashboard — OEE, Profitability, Waste, Quality
   Uses built-in frappe.Chart for all visualizations
   ═══════════════════════════════════════════════════════════════════════════ */

frappe.pages["plant-analytics"].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Plant Analytics",
        single_column: true,
    });

    $(frappe.render_template("plant_analytics", {})).appendTo(page.main);
    wrapper.analytics = new PlantAnalytics(wrapper, page);
};

frappe.pages["plant-analytics"].on_page_show = function (wrapper) {
    if (wrapper.analytics) {
        wrapper.analytics.refresh();
    }
};


class PlantAnalytics {
    constructor(wrapper, page) {
        this.wrapper = wrapper;
        this.page = page;
        this.$container = $(wrapper).find(".analytics-container");
        this.charts = {};
        this.currentTab = "oee";
        this.dateFrom = null;
        this.dateTo = null;
        this.machine = null;

        this._setDefaultDates(30);
        this._bindTabs();
        this._bindDatePicker();
        this._bindRefresh();
        this._loadMachines();
        this.loadTab("oee");
    }

    // ── Date Helpers ───────────────────────────────────────────────────────
    _setDefaultDates(days) {
        let to = frappe.datetime.get_today();
        let from = frappe.datetime.add_days(to, -days);
        this.dateFrom = from;
        this.dateTo = to;
        this.$container.find(".filter-date-from").val(from);
        this.$container.find(".filter-date-to").val(to);
    }

    _bindDatePicker() {
        let me = this;

        this.$container.on("click", ".range-btn", function () {
            me.$container.find(".range-btn").removeClass("active");
            $(this).addClass("active");
            let days = parseInt($(this).data("days"));
            me._setDefaultDates(days);
            me.refresh();
        });

        this.$container.find(".filter-date-from, .filter-date-to").on("change", function () {
            me.$container.find(".range-btn").removeClass("active");
            me.dateFrom = me.$container.find(".filter-date-from").val();
            me.dateTo = me.$container.find(".filter-date-to").val();
        });
    }

    _bindRefresh() {
        this.$container.find(".btn-refresh").on("click", () => this.refresh());
    }

    _bindTabs() {
        let me = this;
        this.$container.on("click", ".analytics-tab", function () {
            me.$container.find(".analytics-tab").removeClass("active");
            $(this).addClass("active");
            let tab = $(this).data("tab");
            me.loadTab(tab);
        });
    }

    _loadMachines() {
        frappe.call({
            method: "frappe.client.get_list",
            args: { doctype: "Machine", fields: ["name", "machine_name"], limit_page_length: 0 },
            async: true,
            callback: (r) => {
                if (r.message) {
                    let $sel = this.$container.find(".filter-machine");
                    r.message.forEach((m) => {
                        $sel.append(
                            `<option value="${m.name}">${m.machine_name || m.name}</option>`
                        );
                    });
                }
            },
        });
    }

    refresh() {
        this.loadTab(this.currentTab);
    }

    // ── Tab Router ─────────────────────────────────────────────────────────
    loadTab(tab) {
        this.currentTab = tab;
        this._destroyCharts();
        this._showLoading(true);

        // Show/hide machine filter for relevant tabs
        let showMachine = tab === "oee" || tab === "waste";
        this.$container.find(".filter-machine-group").toggle(showMachine);
        this.machine = showMachine
            ? this.$container.find(".filter-machine").val()
            : null;

        let methodMap = {
            oee: "plant_operations.plant_operations.api.get_oee_dashboard",
            profitability: "plant_operations.plant_operations.api.get_profitability_dashboard",
            waste: "plant_operations.plant_operations.api.get_waste_dashboard",
            quality: "plant_operations.plant_operations.api.get_quality_dashboard",
        };

        let args = { date_from: this.dateFrom, date_to: this.dateTo };
        if (this.machine) args.machine = this.machine;

        frappe.call({
            method: methodMap[tab],
            args: args,
            callback: (r) => {
                this._showLoading(false);
                if (r.message) {
                    switch (tab) {
                        case "oee":           this.renderOEE(r.message); break;
                        case "profitability":  this.renderProfitability(r.message); break;
                        case "waste":          this.renderWaste(r.message); break;
                        case "quality":        this.renderQuality(r.message); break;
                    }
                }
            },
            error: () => {
                this._showLoading(false);
                this._showEmpty("Failed to load analytics data.");
            },
        });
    }

    _showLoading(show) {
        this.$container.find(".analytics-loading").toggle(show);
        this.$container.find(".kpi-cards-row, .charts-grid, .analytics-table-wrap").toggle(!show);
    }

    _showEmpty(message) {
        $("#kpi-cards").html("");
        $("#chart-primary").html(
            `<div class="analytics-empty"><i class="fa fa-bar-chart"></i><p>${message}</p></div>`
        );
        $("#chart-secondary").html("");
        $("#chart-tertiary").html("");
        $("#analytics-table-wrap").hide();
    }

    _destroyCharts() {
        Object.values(this.charts).forEach((c) => {
            if (c && c.destroy) c.destroy();
        });
        this.charts = {};
    }

    // ════════════════════════════════════════════════════════════════════════
    //  OEE TAB
    // ════════════════════════════════════════════════════════════════════════
    renderOEE(data) {
        // KPI cards
        this._renderKPIs([
            { label: "Avg OEE", value: data.avg_oee, suffix: "%", color: this._oeeColor(data.avg_oee) },
            { label: "Availability", value: data.avg_availability, suffix: "%", color: "blue" },
            { label: "Performance", value: data.avg_performance, suffix: "%", color: "teal" },
            { label: "Quality", value: data.avg_quality, suffix: "%", color: "purple" },
            { label: "Production Runs", value: data.total_entries, suffix: "", color: "orange" },
        ]);

        // OEE Trend line chart
        $("#chart-primary-title").text("OEE Trend (Daily Average)");
        if (data.oee_trend.length > 0) {
            this.charts.primary = new frappe.Chart("#chart-primary", {
                data: {
                    labels: data.oee_trend.map((d) => d.date),
                    datasets: [{ name: "OEE %", values: data.oee_trend.map((d) => d.oee) }],
                },
                type: "line",
                height: 260,
                colors: ["#2E7D32"],
                lineOptions: { regionFill: 1 },
                axisOptions: { xIsSeries: true },
            });
        } else {
            this._chartEmpty("#chart-primary", "No OEE data for this period.");
        }

        // Machine comparison bar chart
        $("#chart-secondary-title").text("OEE by Machine");
        if (data.machine_comparison.length > 0) {
            this.charts.secondary = new frappe.Chart("#chart-secondary", {
                data: {
                    labels: data.machine_comparison.map((m) => m.machine),
                    datasets: [
                        { name: "Avg OEE %", values: data.machine_comparison.map((m) => m.avg_oee) },
                    ],
                },
                type: "bar",
                height: 260,
                colors: ["#1565C0"],
                barOptions: { spaceRatio: 0.4 },
            });
        } else {
            this._chartEmpty("#chart-secondary", "No machine data.");
        }

        // Downtime reasons pie chart
        $("#chart-tertiary-title").text("Top Downtime Reasons (hours)");
        if (data.downtime_reasons.length > 0) {
            this.charts.tertiary = new frappe.Chart("#chart-tertiary", {
                data: {
                    labels: data.downtime_reasons.map((d) => d.reason),
                    datasets: [{ values: data.downtime_reasons.map((d) => d.hours) }],
                },
                type: "pie",
                height: 260,
                colors: ["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF",
                         "#FF9F40", "#C9CBCF", "#7BC225", "#E74C3C", "#3498DB"],
            });
        } else {
            this._chartEmpty("#chart-tertiary", "No downtime data.");
        }

        // Machine data table
        this._renderTable(
            "Machine Performance Summary",
            ["Machine", "Avg OEE %", "Run Hours", "Runs"],
            data.machine_comparison.map((m) => [
                m.machine,
                { value: m.avg_oee + "%", class: "number-cell" },
                { value: m.run_hours.toLocaleString(), class: "number-cell" },
                { value: m.entries, class: "number-cell" },
            ])
        );
    }

    _oeeColor(val) {
        if (val >= 85) return "green";
        if (val >= 65) return "orange";
        return "red";
    }

    // ════════════════════════════════════════════════════════════════════════
    //  PROFITABILITY TAB
    // ════════════════════════════════════════════════════════════════════════
    renderProfitability(data) {
        this._renderKPIs([
            {
                label: "Total Revenue",
                value: this._fmtCurrency(data.total_revenue),
                suffix: "",
                color: "green",
            },
            { label: "Gross Margin", value: data.gross_margin, suffix: "%", color: "blue" },
            { label: "Win Rate", value: data.win_rate, suffix: "%", color: "teal" },
            {
                label: "Estimates",
                value: data.total_estimates,
                suffix: "",
                color: "orange",
                sub: `${data.accepted_estimates} accepted`,
            },
        ]);

        // Monthly revenue bar chart
        $("#chart-primary-title").text("Monthly Revenue");
        if (data.monthly_revenue.length > 0) {
            this.charts.primary = new frappe.Chart("#chart-primary", {
                data: {
                    labels: data.monthly_revenue.map((m) => m.month),
                    datasets: [
                        {
                            name: "Revenue",
                            values: data.monthly_revenue.map((m) => parseFloat(m.revenue) || 0),
                        },
                    ],
                },
                type: "bar",
                height: 260,
                colors: ["#2E7D32"],
                barOptions: { spaceRatio: 0.3 },
                tooltipOptions: {
                    formatTooltipY: (d) => "$" + (d || 0).toLocaleString(),
                },
            });
        } else {
            this._chartEmpty("#chart-primary", "No revenue data for this period.");
        }

        // Top customers bar chart
        $("#chart-secondary-title").text("Top 10 Customers by Revenue");
        if (data.top_customers.length > 0) {
            this.charts.secondary = new frappe.Chart("#chart-secondary", {
                data: {
                    labels: data.top_customers.map(
                        (c) => (c.customer_name || c.customer).substring(0, 20)
                    ),
                    datasets: [
                        {
                            name: "Revenue",
                            values: data.top_customers.map((c) => parseFloat(c.total_revenue) || 0),
                        },
                    ],
                },
                type: "bar",
                height: 260,
                colors: ["#1565C0"],
                barOptions: { spaceRatio: 0.4 },
                tooltipOptions: {
                    formatTooltipY: (d) => "$" + (d || 0).toLocaleString(),
                },
            });
        } else {
            this._chartEmpty("#chart-secondary", "No customer data.");
        }

        // Margin breakdown (COGS vs Sell as pie)
        $("#chart-tertiary-title").text("Cost vs Selling Price");
        if (data.total_sell > 0) {
            let profit = Math.max(0, data.total_sell - data.total_cogs);
            this.charts.tertiary = new frappe.Chart("#chart-tertiary", {
                data: {
                    labels: ["COGS", "Gross Profit"],
                    datasets: [{ values: [data.total_cogs, profit] }],
                },
                type: "pie",
                height: 260,
                colors: ["#c62828", "#2E7D32"],
            });
        } else {
            this._chartEmpty("#chart-tertiary", "No estimate margin data.");
        }

        // Top customers table
        this._renderTable(
            "Top Customers",
            ["Customer", "Revenue", "Orders"],
            data.top_customers.map((c) => [
                c.customer_name || c.customer,
                { value: "$" + parseFloat(c.total_revenue || 0).toLocaleString(), class: "number-cell" },
                { value: c.order_count, class: "number-cell" },
            ])
        );
    }

    // ════════════════════════════════════════════════════════════════════════
    //  WASTE TAB
    // ════════════════════════════════════════════════════════════════════════
    renderWaste(data) {
        this._renderKPIs([
            {
                label: "Waste Rate",
                value: data.overall_waste_pct,
                suffix: "%",
                color: data.overall_waste_pct > 5 ? "red" : data.overall_waste_pct > 3 ? "orange" : "green",
            },
            { label: "Total Waste", value: data.total_waste.toLocaleString(), suffix: "", color: "red" },
            { label: "Good Units", value: data.total_good.toLocaleString(), suffix: "", color: "green" },
            { label: "Total Produced", value: data.total_produced.toLocaleString(), suffix: "", color: "blue" },
        ]);

        // Waste trend line chart
        $("#chart-primary-title").text("Daily Waste Rate Trend");
        if (data.waste_trend.length > 0) {
            this.charts.primary = new frappe.Chart("#chart-primary", {
                data: {
                    labels: data.waste_trend.map((d) => d.date),
                    datasets: [
                        { name: "Waste %", values: data.waste_trend.map((d) => d.waste_pct) },
                    ],
                },
                type: "line",
                height: 260,
                colors: ["#c62828"],
                lineOptions: { regionFill: 1 },
                axisOptions: { xIsSeries: true },
            });
        } else {
            this._chartEmpty("#chart-primary", "No waste data for this period.");
        }

        // Waste by machine bar chart
        $("#chart-secondary-title").text("Waste % by Machine");
        if (data.waste_by_machine.length > 0) {
            this.charts.secondary = new frappe.Chart("#chart-secondary", {
                data: {
                    labels: data.waste_by_machine.map((m) => m.machine),
                    datasets: [
                        { name: "Waste %", values: data.waste_by_machine.map((m) => m.waste_pct) },
                    ],
                },
                type: "bar",
                height: 260,
                colors: ["#E65100"],
                barOptions: { spaceRatio: 0.4 },
            });
        } else {
            this._chartEmpty("#chart-secondary", "No machine waste data.");
        }

        // Waste by shift pie chart
        $("#chart-tertiary-title").text("Waste % by Shift");
        if (data.waste_by_shift.length > 0) {
            this.charts.tertiary = new frappe.Chart("#chart-tertiary", {
                data: {
                    labels: data.waste_by_shift.map((s) => s.shift),
                    datasets: [{ values: data.waste_by_shift.map((s) => s.waste_pct) }],
                },
                type: "pie",
                height: 260,
                colors: ["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0"],
            });
        } else {
            this._chartEmpty("#chart-tertiary", "No shift waste data.");
        }

        // Machine waste table
        this._renderTable(
            "Waste by Machine",
            ["Machine", "Waste %", "Waste Qty"],
            data.waste_by_machine.map((m) => [
                m.machine,
                { value: m.waste_pct + "%", class: "number-cell" },
                { value: m.waste_qty.toLocaleString(), class: "number-cell" },
            ])
        );
    }

    // ════════════════════════════════════════════════════════════════════════
    //  QUALITY TAB
    // ════════════════════════════════════════════════════════════════════════
    renderQuality(data) {
        let openNCRs = (data.ncr_by_severity || []).reduce((a, b) => a + (b.count || 0), 0);

        this._renderKPIs([
            {
                label: "First Pass Yield",
                value: data.first_pass_yield,
                suffix: "%",
                color: data.first_pass_yield >= 95 ? "green" : data.first_pass_yield >= 85 ? "orange" : "red",
            },
            { label: "Open NCRs", value: openNCRs, suffix: "", color: openNCRs > 0 ? "red" : "green" },
            {
                label: "Cost of Poor Quality",
                value: this._fmtCurrency(data.total_copq),
                suffix: "",
                color: data.total_copq > 0 ? "red" : "green",
            },
            {
                label: "Open Complaints",
                value: data.open_complaints,
                suffix: "",
                color: data.open_complaints > 0 ? "orange" : "green",
            },
            {
                label: "Inspections",
                value: data.total_inspections,
                suffix: "",
                color: "blue",
                sub: `${data.passed} passed / ${data.failed} failed`,
            },
        ]);

        // NCR by severity bar chart
        $("#chart-primary-title").text("Inspection Results");
        if (data.total_inspections > 0) {
            this.charts.primary = new frappe.Chart("#chart-primary", {
                data: {
                    labels: ["Passed", "Failed"],
                    datasets: [{ name: "Count", values: [data.passed, data.failed] }],
                },
                type: "bar",
                height: 260,
                colors: ["#2E7D32"],
                barOptions: { spaceRatio: 0.5 },
            });
        } else {
            this._chartEmpty("#chart-primary", "No inspection data for this period.");
        }

        // NCR by severity
        $("#chart-secondary-title").text("Open NCRs by Severity");
        if (data.ncr_by_severity && data.ncr_by_severity.length > 0) {
            this.charts.secondary = new frappe.Chart("#chart-secondary", {
                data: {
                    labels: data.ncr_by_severity.map((n) => n.severity),
                    datasets: [{ values: data.ncr_by_severity.map((n) => n.count) }],
                },
                type: "pie",
                height: 260,
                colors: ["#c62828", "#E65100", "#FFCE56", "#4BC0C0"],
            });
        } else {
            this._chartEmpty("#chart-secondary", "No open NCRs.");
        }

        // Defect types bar chart
        $("#chart-tertiary-title").text("Top Defect Types");
        if (data.defect_types && data.defect_types.length > 0) {
            this.charts.tertiary = new frappe.Chart("#chart-tertiary", {
                data: {
                    labels: data.defect_types.map((d) => d.test_name),
                    datasets: [
                        { name: "Failures", values: data.defect_types.map((d) => d.count) },
                    ],
                },
                type: "bar",
                height: 260,
                colors: ["#6A1B9A"],
                barOptions: { spaceRatio: 0.4 },
            });
        } else {
            this._chartEmpty("#chart-tertiary", "No defect data.");
        }

        // Defect types table
        if (data.defect_types && data.defect_types.length > 0) {
            this._renderTable(
                "Top Defect Types",
                ["Test / Defect", "Failure Count"],
                data.defect_types.map((d) => [
                    d.test_name,
                    { value: d.count, class: "number-cell" },
                ])
            );
        } else {
            $("#analytics-table-wrap").hide();
        }
    }

    // ════════════════════════════════════════════════════════════════════════
    //  RENDER HELPERS
    // ════════════════════════════════════════════════════════════════════════
    _renderKPIs(cards) {
        let html = cards
            .map((c) => {
                let subHtml = c.sub ? `<div class="kpi-card-sub">${c.sub}</div>` : "";
                return `
                <div class="kpi-card ${c.color}">
                    <div class="kpi-card-value">${c.value}${c.suffix}</div>
                    <div class="kpi-card-label">${c.label}</div>
                    ${subHtml}
                </div>`;
            })
            .join("");
        $("#kpi-cards").html(html);
    }

    _chartEmpty(selector, message) {
        $(selector).html(
            `<div class="analytics-empty"><i class="fa fa-bar-chart"></i><p>${message}</p></div>`
        );
    }

    _renderTable(title, headers, rows) {
        if (!rows || rows.length === 0) {
            $("#analytics-table-wrap").hide();
            return;
        }

        let ths = headers.map((h) => `<th>${h}</th>`).join("");
        let trs = rows
            .map((row) => {
                let tds = row
                    .map((cell) => {
                        if (typeof cell === "object" && cell !== null) {
                            return `<td class="${cell.class || ""}">${cell.value}</td>`;
                        }
                        return `<td>${cell}</td>`;
                    })
                    .join("");
                return `<tr>${tds}</tr>`;
            })
            .join("");

        $("#table-title").text(title);
        $("#analytics-table").html(
            `<table><thead><tr>${ths}</tr></thead><tbody>${trs}</tbody></table>`
        );
        $("#analytics-table-wrap").show();
    }

    _fmtCurrency(val) {
        let n = parseFloat(val) || 0;
        if (n >= 1000000) return "$" + (n / 1000000).toFixed(1) + "M";
        if (n >= 1000) return "$" + (n / 1000).toFixed(1) + "K";
        return "$" + n.toFixed(0);
    }
}
