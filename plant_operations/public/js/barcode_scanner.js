/**
 * barcode_scanner.js — HTML5 Barcode Scanner for Plant Operations
 *
 * Uses BarcodeDetector API (Chrome 83+) or falls back to manual entry.
 * Scans pallet tags and load tags from phone camera.
 */
frappe.provide("plant_operations");

plant_operations.BarcodeScanner = class {
    constructor(opts) {
        this.callback = opts.callback || function () {};
        this.title = opts.title || "Scan Barcode";
        this.supported = "BarcodeDetector" in window;
    }

    show() {
        if (this.supported) {
            this._showCameraScanner();
        } else {
            this._showManualEntry();
        }
    }

    _showCameraScanner() {
        var self = this;

        var d = new frappe.ui.Dialog({
            title: this.title,
            fields: [
                {
                    fieldtype: "HTML",
                    fieldname: "video_container",
                    options: '<div style="text-align:center;">' +
                        '<video id="barcode-video" style="width:100%;max-width:400px;border-radius:8px;border:2px solid #2490EF;" autoplay playsinline></video>' +
                        '<div id="barcode-result" style="margin-top:10px;font-size:16px;font-weight:700;color:#2E7D32;"></div>' +
                        '</div>',
                },
                {
                    fieldtype: "Data",
                    fieldname: "manual_code",
                    label: "Or enter code manually",
                },
            ],
            primary_action_label: "Use Manual Code",
            primary_action: function (values) {
                if (values.manual_code) {
                    self._stopCamera();
                    d.hide();
                    self.callback(values.manual_code);
                }
            },
        });

        d.show();

        // Start camera after dialog renders
        setTimeout(function () {
            self._startCamera(d);
        }, 300);

        d.on_hide = function () {
            self._stopCamera();
        };
    }

    _startCamera(dialog) {
        var self = this;
        var video = document.getElementById("barcode-video");
        if (!video) return;

        navigator.mediaDevices
            .getUserMedia({ video: { facingMode: "environment" } })
            .then(function (stream) {
                self._stream = stream;
                video.srcObject = stream;

                var detector = new BarcodeDetector({
                    formats: ["code_128", "code_39", "ean_13", "qr_code"],
                });

                self._scanInterval = setInterval(function () {
                    if (video.readyState >= 2) {
                        detector.detect(video).then(function (barcodes) {
                            if (barcodes.length > 0) {
                                var code = barcodes[0].rawValue;
                                document.getElementById("barcode-result").textContent = code;

                                clearInterval(self._scanInterval);
                                self._stopCamera();
                                dialog.hide();
                                self.callback(code);
                            }
                        }).catch(function () {});
                    }
                }, 250);
            })
            .catch(function (err) {
                frappe.show_alert({
                    message: "Camera not available. Use manual entry.",
                    indicator: "orange",
                });
            });
    }

    _stopCamera() {
        if (this._scanInterval) {
            clearInterval(this._scanInterval);
            this._scanInterval = null;
        }
        if (this._stream) {
            this._stream.getTracks().forEach(function (track) {
                track.stop();
            });
            this._stream = null;
        }
    }

    _showManualEntry() {
        var self = this;
        frappe.prompt(
            [{ fieldname: "code", fieldtype: "Data", label: "Enter Barcode / ID", reqd: 1 }],
            function (values) {
                self.callback(values.code);
            },
            this.title,
            "Scan"
        );
    }
};
