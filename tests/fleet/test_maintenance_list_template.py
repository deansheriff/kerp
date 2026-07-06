from pathlib import Path


def test_maintenance_template_uses_context_records_and_primary_key():
    template = (
        Path(__file__).resolve().parents[2] / "templates" / "fleet" / "maintenance.html"
    ).read_text()

    assert "{% for record in maintenance_records %}" in template
    assert "record.maintenance_id" in template
    assert "record.record_id" not in template
    assert "equalto', 'SCHEDULED'" in template


def test_maintenance_template_exposes_edit_for_authorized_users():
    template = (
        Path(__file__).resolve().parents[2] / "templates" / "fleet" / "maintenance.html"
    ).read_text()

    assert "can_update_maintenance" in template
    assert "~ record.maintenance_id ~ \"/edit\"" in template


def test_maintenance_form_supports_edit_mode():
    template = (
        Path(__file__).resolve().parents[2]
        / "templates"
        / "fleet"
        / "maintenance_form.html"
    ).read_text()

    assert 'action="{{ form_action }}"' in template
    assert "Save Maintenance" in template
    assert "record.description if record else" in template


def test_maintenance_detail_exposes_edit_for_authorized_users():
    template = (
        Path(__file__).resolve().parents[2]
        / "templates"
        / "fleet"
        / "maintenance_detail.html"
    ).read_text()

    assert "{% if can_update_maintenance %}" in template
    assert "/fleet/maintenance/{{ record.maintenance_id }}/edit" in template


def test_fuel_templates_support_permission_gated_edit_mode():
    root = Path(__file__).resolve().parents[2]
    list_template = (root / "templates" / "fleet" / "fuel.html").read_text()
    form_template = (root / "templates" / "fleet" / "fuel_form.html").read_text()

    assert "can_update_fuel" in list_template
    assert "{% for log in fuel_logs %}" in list_template
    assert "~ log.fuel_log_id ~ \"/edit\"" in list_template
    assert "log.log_date" in list_template
    assert "log.station_name" in list_template
    assert "fuel_station" not in list_template
    assert "current_vehicle_id|string" in list_template
    assert 'action="{{ form_action }}"' in form_template
    assert "Save Fuel Log" in form_template
    assert "selected_fuel_type == ft" in form_template


def test_document_templates_support_permission_gated_edit_mode():
    root = Path(__file__).resolve().parents[2]
    list_template = (root / "templates" / "fleet" / "documents.html").read_text()
    detail_template = (
        root / "templates" / "fleet" / "document_detail.html"
    ).read_text()
    form_template = (
        root / "templates" / "fleet" / "document_form.html"
    ).read_text()

    assert "can_update_document" in list_template
    assert "~ doc.document_id ~ \"/edit\"" in list_template
    assert "{% if can_update_document %}" in detail_template
    assert "/fleet/documents/{{ document.document_id }}/edit" in detail_template
    assert 'action="{{ form_action }}"' in form_template
    assert "Save Document" in form_template
    assert "selected_document_type == dt" in form_template


def test_fleet_filter_templates_use_current_context_values():
    root = Path(__file__).resolve().parents[2]
    document_template = (root / "templates" / "fleet" / "documents.html").read_text()
    incident_template = (root / "templates" / "fleet" / "incidents.html").read_text()
    reservation_template = (
        root / "templates" / "fleet" / "reservations.html"
    ).read_text()

    assert "current_type == dt" in document_template
    assert "current_vehicle_id|string" in document_template
    assert "current_status == s" in incident_template
    assert "current_severity == sev" in incident_template
    assert "current_vehicle_id|string" in incident_template
    assert "current_status == s" in reservation_template
    assert "current_vehicle_id|string" in reservation_template


def test_fleet_routes_include_edit_handlers_for_action_links():
    route_source = (
        Path(__file__).resolve().parents[2] / "app" / "web" / "fleet.py"
    ).read_text()

    assert '@router.get("/maintenance/{record_id}/edit"' in route_source
    assert '@router.post("/maintenance/{record_id}/edit")' in route_source
    assert '@router.get("/fuel/{log_id}/edit"' in route_source
    assert '@router.post("/fuel/{log_id}/edit")' in route_source
    assert '@router.get("/documents/{document_id}/edit"' in route_source
    assert '@router.post("/documents/{document_id}/edit")' in route_source
