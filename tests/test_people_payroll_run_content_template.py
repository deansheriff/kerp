from pathlib import Path


def test_payroll_run_content_uses_supported_run_actions_only():
    template = Path("templates/people/payroll/_run_content.html").read_text()

    assert '/people/payroll/runs/{{ entry.entry_id }}/copy' in template
    assert "clone_from={{ entry.entry_id }}" not in template
    assert "/people/payroll/runs/{{ entry.entry_id }}/variance" not in template
    assert "/people/payroll/runs/{{ entry.entry_id }}/adjustments" not in template
    assert "/people/payroll/runs/{{ entry.entry_id }}/submit-and-approve" not in template
