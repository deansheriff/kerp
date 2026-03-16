from __future__ import annotations


def test_ap_payment_detail_template_exposes_workflow_actions():
    from pathlib import Path

    template_path = (
        Path(__file__).resolve().parent.parent
        / "templates"
        / "finance"
        / "ap"
        / "payment_detail.html"
    )

    with open(template_path, encoding="utf-8") as template_file:
        template = template_file.read()

    assert "payment.status_raw == 'DRAFT'" in template
    assert "/finance/ap/payments/{{ payment.payment_id }}/approve" in template
    assert "payment.status_raw == 'APPROVED'" in template
    assert "/finance/ap/payments/{{ payment.payment_id }}/post" in template
    assert "payment.status_raw in ['APPROVED', 'SENT']" in template
    assert "/finance/ap/payments/{{ payment.payment_id }}/void" in template
