from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy import select

from app.models.finance.ap.supplier import Supplier
from app.models.finance.ap.supplier_invoice import SupplierInvoice
from app.services.finance.ap.web.invoice_web import InvoiceWebService


def test_list_invoices_context_uses_selected_supplier_without_preloading(monkeypatch):
    org_id = uuid4()
    supplier_id = uuid4()
    db = MagicMock()
    db.execute.return_value.all.return_value = []
    db.scalar.side_effect = [0, Decimal("0"), Decimal("0"), Decimal("0"), 0]

    monkeypatch.setattr(
        "app.services.finance.ap.invoice_query.build_invoice_query",
        lambda **_kwargs: select(SupplierInvoice).join(
            Supplier, SupplierInvoice.supplier_id == Supplier.supplier_id
        ),
    )

    supplier = MagicMock()
    supplier.supplier_id = supplier_id
    supplier.supplier_code = "SUP-001"
    supplier.trading_name = "Acme Supplies"
    supplier.legal_name = "Acme Supplies Ltd"
    supplier.currency_code = "USD"
    supplier.payment_terms_days = 30
    supplier.withholding_tax_code_id = None
    supplier.default_tax_code_id = None

    get_calls: list[str] = []

    def fake_get(_db, _org_id, selected_supplier_id):
        get_calls.append(str(selected_supplier_id))
        return supplier

    def fail_list(*_args, **_kwargs):
        raise AssertionError("supplier list preload should not be used")

    monkeypatch.setattr(
        "app.services.finance.ap.web.invoice_web.supplier_service.get",
        fake_get,
    )
    monkeypatch.setattr(
        "app.services.finance.ap.web.invoice_web.supplier_service.list",
        fail_list,
    )

    context = InvoiceWebService.list_invoices_context(
        db=db,
        organization_id=str(org_id),
        search=None,
        supplier_id=str(supplier_id),
        status=None,
        start_date=None,
        end_date=None,
        page=1,
    )

    assert get_calls == [str(supplier_id)]
    assert context["selected_supplier"]["supplier_id"] == str(supplier_id)
    assert context["active_filters"] == [
        {
            "name": "supplier_id",
            "value": str(supplier_id),
            "display_value": "Acme Supplies",
        }
    ]


def test_ap_invoices_template_uses_remote_supplier_typeahead():
    template_path = "/home/dotmac/projects/dotmac_erp/templates/finance/ap/invoices.html"

    with open(template_path, encoding="utf-8") as template_file:
        template = template_file.read()

    assert 'data-typeahead-url="/finance/ap/suppliers/search"' in template
    assert 'data-typeahead-hidden' in template
    assert 'filter_entity_select_field("supplier_id"' not in template
