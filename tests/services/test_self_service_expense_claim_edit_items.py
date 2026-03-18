from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

from app.models.people.exp import ExpenseClaimStatus
from app.services.people.self_service_web import SelfServiceWebService


def _make_auth():
    auth = MagicMock()
    auth.organization_id = "00000000-0000-0000-0000-000000000001"
    auth.person_id = "00000000-0000-0000-0000-000000000002"
    return auth


def test_expense_claim_update_supports_existing_new_and_removed_items():
    svc = SelfServiceWebService()
    auth = _make_auth()
    db = MagicMock()
    org_id = UUID("00000000-0000-0000-0000-000000000001")
    claim_id = uuid4()
    existing_item_id = uuid4()
    removed_item_id = uuid4()
    requested_approver_id = uuid4()
    category_id = uuid4()

    claim = MagicMock()
    claim.employee_id = "00000000-0000-0000-0000-000000000003"
    claim.status = ExpenseClaimStatus.DRAFT

    with (
        patch.object(
            svc, "_get_employee_id", return_value="00000000-0000-0000-0000-000000000003"
        ),
        patch("app.services.people.self_service_web.ExpenseService") as expense_service,
    ):
        expense_service.return_value.get_claim.return_value = claim

        response = svc.expense_claim_update_response(
            auth,
            db,
            claim_id=claim_id,
            requested_approver_id=requested_approver_id,
            items=[
                {
                    "item_id": str(existing_item_id),
                    "expense_date": date(2026, 3, 1),
                    "category_id": str(category_id),
                    "description": "Updated hotel",
                    "claimed_amount": Decimal("120.00"),
                    "receipt_number": "R-1",
                    "receipt_url": "https://example.com/r1",
                },
                {
                    "expense_date": date(2026, 3, 2),
                    "category_id": str(category_id),
                    "description": "New taxi",
                    "claimed_amount": Decimal("45.50"),
                    "receipt_number": "R-2",
                    "receipt_url": "https://example.com/r2",
                },
                {
                    "item_id": str(removed_item_id),
                    "remove": True,
                },
            ],
        )

    assert response.status_code == 302
    expense_service.return_value.update_claim.assert_called_once()
    expense_service.return_value.update_claim_item.assert_called_once_with(
        org_id,
        claim_id=claim_id,
        item_id=existing_item_id,
        expense_date=date(2026, 3, 1),
        category_id=category_id,
        description="Updated hotel",
        claimed_amount=Decimal("120.00"),
        receipt_number="R-1",
        receipt_url="https://example.com/r1",
    )
    expense_service.return_value.add_claim_item.assert_called_once_with(
        org_id,
        claim_id=claim_id,
        expense_date=date(2026, 3, 2),
        category_id=category_id,
        description="New taxi",
        claimed_amount=Decimal("45.50"),
        receipt_number="R-2",
        receipt_url="https://example.com/r2",
    )
    expense_service.return_value.remove_claim_item.assert_called_once_with(
        org_id,
        claim_id=claim_id,
        item_id=removed_item_id,
    )
    db.commit.assert_called_once()
