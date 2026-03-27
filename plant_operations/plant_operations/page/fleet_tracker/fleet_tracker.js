frappe.pages["fleet-tracker"].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Fleet Tracker",
        single_column: true,
    });

    $(frappe.render_template("fleet_tracker", {})).appendTo(page.main);

    wrapper.fleet_tracker = new FleetTracker(wrapper, page);
};

frappe.pages["fleet-tracker"].on_page_show = function (wrapper) {
    if (wrapper.fleet_tracker) {
        wrapper.fleet_tracker.refresh();
    }
};

function FleetTracker(wrapper, page) {
    this.wrapper = wrapper;
    this.page = page;
    this.$container = $(wrapper).find(".fleet-container");
    this.map = null;
    this.markers = {};
    this.autoRefreshTimer = null;

    this._loadGoogleMaps();
}

FleetTracker.prototype._loadGoogleMaps = function () {
    var self = this;

    // Get API key
    frappe.call({
        method: "plant_operations.plant_operations.api.get_google_api_key",
        callback: function (r) {
            var key = r.message || "";
            if (!key) {
                self.$container.find("#fleet-map").html(
                    '<div style="padding:40px;text-align:center;color:#999;">Google Maps API key not configured. Set it in Plant Operations Settings.</div>'
                );
                return;
            }

            if (typeof google !== "undefined" && google.maps) {
                self._initMap();
                return;
            }

            var script = document.createElement("script");
            script.src = "https://maps.googleapis.com/maps/api/js?key=" + key + "&callback=__fleetMapReady";
            window.__fleetMapReady = function () {
                self._initMap();
            };
            document.head.appendChild(script);
        },
    });
};

FleetTracker.prototype._initMap = function () {
    var mapEl = this.$container.find("#fleet-map")[0];
    this.map = new google.maps.Map(mapEl, {
        center: { lat: 35.65, lng: -88.39 },  // Lexington, TN
        zoom: 7,
        mapTypeId: "roadmap",
        styles: [
            { featureType: "poi", stylers: [{ visibility: "off" }] },
            { featureType: "transit", stylers: [{ visibility: "off" }] },
        ],
    });

    this._bindEvents();
    this.refresh();

    // Auto-refresh every 30 seconds
    var self = this;
    this.autoRefreshTimer = setInterval(function () {
        self.refresh();
    }, 30000);
};

FleetTracker.prototype._bindEvents = function () {
    var self = this;
    this.$container.find(".fleet-refresh").on("click", function () {
        self.refresh();
    });
};

FleetTracker.prototype.refresh = function () {
    var self = this;
    frappe.call({
        method: "plant_operations.plant_operations.api.get_active_fleet",
        callback: function (r) {
            var loads = r.message || [];
            self._updateMap(loads);
            self._updateSidebar(loads);
            self.$container.find(".fleet-last-update").text(
                "Updated " + frappe.datetime.prettyDate(frappe.datetime.now_datetime())
            );
        },
    });
};

FleetTracker.prototype._updateMap = function (loads) {
    if (!this.map) return;

    // Clear old markers
    for (var key in this.markers) {
        this.markers[key].setMap(null);
    }
    this.markers = {};

    var bounds = new google.maps.LatLngBounds();
    var hasPoints = false;

    for (var i = 0; i < loads.length; i++) {
        var load = loads[i];
        if (!load.last_gps_lat || !load.last_gps_lng) continue;

        var pos = { lat: load.last_gps_lat, lng: load.last_gps_lng };
        hasPoints = true;
        bounds.extend(pos);

        var marker = new google.maps.Marker({
            position: pos,
            map: this.map,
            title: load.name + " — " + (load.destination_customer || "Unknown"),
            icon: {
                path: google.maps.SymbolPath.FORWARD_CLOSED_ARROW,
                scale: 6,
                fillColor: "#1565C0",
                fillOpacity: 1,
                strokeWeight: 2,
                strokeColor: "#fff",
                rotation: 0,
            },
        });

        // Info window
        var infoContent = [
            '<div style="font-size:12px;min-width:200px;">',
            '<div style="font-weight:700;font-size:14px;">' + load.name + '</div>',
            '<div>Trailer: ' + (load.trailer_number || '—') + '</div>',
            '<div>Driver: ' + (load.driver_name || '—') + '</div>',
            '<div style="margin-top:6px;font-weight:600;">→ ' + (load.destination_customer || '—') + '</div>',
            '<div style="font-size:11px;color:#666;">' + (load.destination_address || '') + '</div>',
            '<div style="margin-top:6px;">',
            '<b>' + (load.total_pallets || 0) + '</b> pallets | ',
            '<b>' + (load.total_pieces || 0) + '</b> pcs | ',
            '<b>' + (load.total_weight || 0) + '</b> lbs',
            '</div>',
            '<div style="font-size:10px;color:#999;margin-top:4px;">Last update: ' + (load.last_gps_time || '—') + '</div>',
            '<div style="margin-top:6px;"><a href="/app/load-tag/' + load.name + '">View Load Tag</a></div>',
            '</div>',
        ].join("");

        var infoWindow = new google.maps.InfoWindow({ content: infoContent });
        (function (m, iw) {
            m.addListener("click", function () { iw.open(this.map, m); }.bind(this));
        }).call(this, marker, infoWindow);

        this.markers[load.name] = marker;
    }

    if (hasPoints) {
        this.map.fitBounds(bounds);
        if (loads.length === 1) {
            this.map.setZoom(12);
        }
    }
};

FleetTracker.prototype._updateSidebar = function (loads) {
    this.$container.find(".fleet-count").text(loads.length);

    var totalPallets = 0;
    loads.forEach(function (l) { totalPallets += (l.total_pallets || 0); });
    this.$container.find(".fleet-pallets").text(totalPallets);

    var html = "";
    if (loads.length === 0) {
        html = '<div style="text-align:center;padding:20px;color:#999;">No loads currently in transit.</div>';
    }

    for (var i = 0; i < loads.length; i++) {
        var l = loads[i];
        var hasGps = l.last_gps_lat && l.last_gps_lng;
        html += '<div class="fleet-card" data-load="' + l.name + '" style="background:#fff;border:1px solid #e0e0e0;border-radius:6px;padding:10px;margin-bottom:8px;cursor:pointer;">';
        html += '<div style="display:flex;justify-content:space-between;align-items:center;">';
        html += '<div style="font-weight:700;font-size:13px;">' + l.name + '</div>';
        html += '<span style="font-size:9px;padding:2px 6px;border-radius:3px;background:' + (hasGps ? '#e8f5e9' : '#fff3e0') + ';color:' + (hasGps ? '#2E7D32' : '#E65100') + ';">' + (hasGps ? 'GPS' : 'No GPS') + '</span>';
        html += '</div>';
        html += '<div style="font-size:11px;color:#333;margin-top:2px;">→ ' + (l.destination_customer || '—') + '</div>';
        html += '<div style="font-size:10px;color:#888;margin-top:2px;">';
        html += 'Trailer: ' + (l.trailer_number || '—') + ' | Driver: ' + (l.driver_name || '—');
        html += '</div>';
        html += '<div style="font-size:10px;color:#666;margin-top:4px;">';
        html += '<b>' + (l.total_pallets || 0) + '</b> pallets · <b>' + (l.total_pieces || 0) + '</b> pcs · <b>' + Math.round(l.total_weight || 0) + '</b> lbs';
        html += '</div>';
        html += '</div>';
    }

    this.$container.find(".fleet-list").html(html);

    // Click card to zoom on map
    var self = this;
    this.$container.find(".fleet-card").on("click", function () {
        var loadName = $(this).data("load");
        var marker = self.markers[loadName];
        if (marker && self.map) {
            self.map.panTo(marker.getPosition());
            self.map.setZoom(14);
            google.maps.event.trigger(marker, "click");
        }
    });
};
