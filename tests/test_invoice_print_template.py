from types import SimpleNamespace

from app.templates import templates


def _render_invoice_print_logo_snippet(**context) -> str:
    snippet = """
{% set brand_name_value = brand.name if brand is defined and brand and brand.name else title %}
{% set document_logo_fallback_url = (org_branding.report_logo_url if org_branding is defined and org_branding and org_branding.report_logo_url else (brand.logo_url if brand is defined and brand and brand.logo_url else "")) %}
{% set org_display_name = organization.legal_name if organization and organization.legal_name else (organization.name if organization and organization.name else brand_name_value) %}
{% set invoice_logo_url = print_logo_url or document_logo_fallback_url %}
{% if invoice_logo_url %}
<img src="{{ invoice_logo_url }}" alt="{{ org_display_name }} logo" class="print-company-logo">
{% else %}
<div class="print-company-name">{{ org_display_name }}</div>
{% endif %}
"""
    wrapped = "{% autoescape true %}" + snippet + "{% endautoescape %}"
    return templates.env.from_string(wrapped).render(**context)


def test_invoice_print_logo_falls_back_to_document_logo_url():
    html = _render_invoice_print_logo_snippet(
        print_logo_url=None,
        brand=SimpleNamespace(name="Dotmac", logo_url="/static/brand-logo.svg"),
        org_branding=SimpleNamespace(report_logo_url="/files/branding/report-logo.png"),
        organization=SimpleNamespace(legal_name="Dotmac Technologies Ltd"),
        title="AR Invoice",
    )

    assert 'src="/files/branding/report-logo.png"' in html
    assert "Dotmac Technologies Ltd logo" in html
    assert "print-company-name" not in html


def test_invoice_print_logo_uses_print_logo_url_when_present():
    html = _render_invoice_print_logo_snippet(
        print_logo_url="/files/branding/invoice-print-logo.png",
        brand=SimpleNamespace(name="Dotmac", logo_url="/static/brand-logo.svg"),
        org_branding=SimpleNamespace(report_logo_url="/files/branding/report-logo.png"),
        organization=SimpleNamespace(legal_name="Dotmac Technologies Ltd"),
        title="AR Invoice",
    )

    assert 'src="/files/branding/invoice-print-logo.png"' in html
    assert 'src="/files/branding/report-logo.png"' not in html
