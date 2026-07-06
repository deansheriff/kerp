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
