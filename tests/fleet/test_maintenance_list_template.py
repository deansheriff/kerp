from pathlib import Path


def test_maintenance_template_uses_context_records_and_primary_key():
    template = (
        Path(__file__).resolve().parents[2] / "templates" / "fleet" / "maintenance.html"
    ).read_text()

    assert "{% for record in maintenance_records %}" in template
    assert "record.maintenance_id" in template
    assert "record.record_id" not in template
    assert "equalto', 'SCHEDULED'" in template
