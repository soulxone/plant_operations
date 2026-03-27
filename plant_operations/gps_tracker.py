"""GPS Tracker — Real-time fleet tracking and position logging."""
import frappe
from frappe.utils import now_datetime, flt


def log_position(load_tag, latitude, longitude,
                  speed_mph=0, heading=0, accuracy_meters=0,
                  source="Driver App"):
    """Log a GPS position for a load tag.

    Creates a GPS Track Point record and updates the Load Tag's last position.
    """
    lat = flt(latitude)
    lng = flt(longitude)

    if not lat or not lng:
        return {"status": "error", "message": "Invalid coordinates"}

    # Create track point
    point = frappe.get_doc({
        "doctype": "GPS Track Point",
        "load_tag": load_tag,
        "timestamp": now_datetime(),
        "latitude": lat,
        "longitude": lng,
        "speed_mph": flt(speed_mph),
        "heading": flt(heading),
        "accuracy_meters": flt(accuracy_meters),
        "source": source or "Driver App",
    })
    point.insert(ignore_permissions=True)

    # Update Load Tag last position
    frappe.db.set_value("Load Tag", load_tag, {
        "last_gps_lat": lat,
        "last_gps_lng": lng,
        "last_gps_time": now_datetime(),
    })

    frappe.db.commit()

    return {
        "status": "success",
        "point": point.name,
        "load_tag": load_tag,
        "lat": lat,
        "lng": lng,
    }


def get_fleet_positions():
    """Get all active loads (In Transit) with their latest GPS position.

    Returns list of dicts for the fleet tracker map.
    """
    loads = frappe.get_all("Load Tag",
        filters={"status": "In Transit"},
        fields=[
            "name", "load_number", "trailer_number", "driver_name",
            "destination_customer", "destination_address",
            "total_pallets", "total_pieces", "total_weight",
            "last_gps_lat", "last_gps_lng", "last_gps_time",
            "ship_date", "expected_delivery_date",
            "seal_number", "carrier", "bol_number",
        ],
        order_by="ship_date desc",
    )

    # Filter to only loads with GPS data
    active = []
    for load in loads:
        if load.last_gps_lat and load.last_gps_lng:
            active.append(load)
        else:
            # Include even without GPS for awareness
            load["last_gps_lat"] = 0
            load["last_gps_lng"] = 0
            active.append(load)

    return active
