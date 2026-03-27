app_name = "plant_operations"
app_title = "Plant Operations"
app_publisher = "Welchwyse"
app_description = "Corrugated plant receiving, shipping, GPS tracking, and load tag system"
app_email = "admin@welchwyse.com"
app_license = "MIT"
app_version = "0.1.0"

required_apps = ["frappe", "erpnext"]

# ── Fixtures ──────────────────────────────────────────────────────────────
fixtures = [
    "Plant Operations Settings",
    {"dt": "Custom Field", "filters": [["module", "=", "Plant Operations"]]},
    {"dt": "Workspace", "filters": [["module", "=", "Plant Operations"]]},
]

# ── Custom Fields on ERPNext DocTypes ─────────────────────────────────────
# These are created by bench migrate
override_doctype_class = {}

# ── Doc Events ────────────────────────────────────────────────────────────
doc_events = {
    "Sales Order": {
        "on_submit": "plant_operations.plant_operations.hooks_impl.on_sales_order_submit",
    },
    "Delivery Note": {
        "on_submit": "plant_operations.plant_operations.hooks_impl.on_delivery_note_submit",
    },
    "Job Card": {
        "on_update": "plant_operations.plant_operations.hooks_impl.on_job_card_update",
    },
}

# ── Website ───────────────────────────────────────────────────────────────
website_route_rules = [
    {"from_route": "/driver", "to_route": "driver_app"},
]
