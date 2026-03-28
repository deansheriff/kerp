"""
PMS (Performance Management System) Web Routes.

OHCSF-compliant PMS routes: dashboard, contracts, monthly reviews,
PIPs, appeals, institutional performance, strategic objectives,
and reports.

All routes are accessible at /people/perf/pms/*.
"""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.web.deps import WebAuthContext, get_db, require_hr_access

router = APIRouter(prefix="/pms", tags=["people-pms-web"])


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────────────────────


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
@router.get("/dashboard", response_class=HTMLResponse)
def pms_dashboard(
    request: Request,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """OHCSF PMS compliance dashboard."""
    from app.services.people.perf.web.ohcsf_dashboard_web import (
        OHCSFDashboardWebService,
    )

    return OHCSFDashboardWebService().dashboard_response(request, auth, db)


# ─────────────────────────────────────────────────────────────────────────────
# Performance Contracts
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/contracts", response_class=HTMLResponse)
def list_contracts(
    request: Request,
    status: str | None = None,
    cycle_id: str | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Performance contracts list page."""
    from app.services.people.perf.web.contract_web import ContractWebService

    return ContractWebService().list_contracts_response(
        request, auth, db, status=status, cycle_id=cycle_id, search=search, page=page
    )


@router.get("/contracts/new", response_class=HTMLResponse)
def new_contract_form(
    request: Request,
    cycle_id: str | None = None,
    employee_id: str | None = None,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """New performance contract form."""
    from app.services.people.perf.web.contract_web import ContractWebService

    return ContractWebService().contract_form_response(
        request, auth, db, cycle_id=cycle_id, employee_id=employee_id
    )


@router.post("/contracts/new", response_class=HTMLResponse)
async def create_contract(
    request: Request,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Create a new performance contract."""
    from app.services.people.perf.web.contract_web import ContractWebService

    return await ContractWebService().create_contract_response(request, auth, db)


@router.get("/contracts/{contract_id}", response_class=HTMLResponse)
def contract_detail(
    request: Request,
    contract_id: str,
    success: str | None = None,
    error: str | None = None,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Performance contract detail page."""
    from app.services.people.perf.web.contract_web import ContractWebService

    return ContractWebService().contract_detail_response(
        request, auth, db, contract_id, success=success, error=error
    )


@router.post("/contracts/{contract_id}/sign-employee", response_class=HTMLResponse)
async def sign_contract_employee(
    request: Request,
    contract_id: str,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Employee signs the performance contract."""
    from app.services.people.perf.web.contract_web import ContractWebService

    return ContractWebService().sign_employee_response(auth, db, contract_id)


@router.post("/contracts/{contract_id}/sign-supervisor", response_class=HTMLResponse)
async def sign_contract_supervisor(
    request: Request,
    contract_id: str,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Supervisor signs the performance contract."""
    from app.services.people.perf.web.contract_web import ContractWebService

    return ContractWebService().sign_supervisor_response(auth, db, contract_id)


# ─────────────────────────────────────────────────────────────────────────────
# Monthly Reviews
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/reviews", response_class=HTMLResponse)
def list_reviews(
    request: Request,
    status: str | None = None,
    employee_id: str | None = None,
    contract_id: str | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Monthly reviews list page."""
    from app.services.people.perf.web.monthly_review_web import MonthlyReviewWebService

    return MonthlyReviewWebService().list_reviews_response(
        request,
        auth,
        db,
        status=status,
        employee_id=employee_id,
        contract_id=contract_id,
        search=search,
        page=page,
    )


@router.get("/reviews/new", response_class=HTMLResponse)
def new_review_form(
    request: Request,
    employee_id: str | None = None,
    contract_id: str | None = None,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """New monthly review form."""
    from app.services.people.perf.web.monthly_review_web import MonthlyReviewWebService

    return MonthlyReviewWebService().review_form_response(
        request, auth, db, employee_id=employee_id, contract_id=contract_id
    )


@router.post("/reviews/new", response_class=HTMLResponse)
async def create_review(
    request: Request,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Create a new monthly review."""
    from app.services.people.perf.web.monthly_review_web import MonthlyReviewWebService

    return await MonthlyReviewWebService().create_review_response(request, auth, db)


@router.get("/reviews/{review_id}", response_class=HTMLResponse)
def review_detail(
    request: Request,
    review_id: str,
    success: str | None = None,
    error: str | None = None,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Monthly review detail page."""
    from app.services.people.perf.web.monthly_review_web import MonthlyReviewWebService

    return MonthlyReviewWebService().review_detail_response(
        request, auth, db, review_id, success=success, error=error
    )


@router.post("/reviews/{review_id}/submit", response_class=HTMLResponse)
async def submit_review(
    request: Request,
    review_id: str,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Submit a monthly review."""
    from app.services.people.perf.web.monthly_review_web import MonthlyReviewWebService

    return await MonthlyReviewWebService().submit_review_response(
        request, auth, db, review_id
    )


@router.post("/reviews/{review_id}/acknowledge", response_class=HTMLResponse)
async def acknowledge_review(
    request: Request,
    review_id: str,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Acknowledge a monthly review."""
    from app.services.people.perf.web.monthly_review_web import MonthlyReviewWebService

    return MonthlyReviewWebService().acknowledge_review_response(auth, db, review_id)


# ─────────────────────────────────────────────────────────────────────────────
# Performance Improvement Plans (PIPs)
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/pips", response_class=HTMLResponse)
def list_pips(
    request: Request,
    status: str | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """PIPs list page."""
    from app.services.people.perf.web.pip_web import PIPWebService

    return PIPWebService().list_pips_response(
        request,
        auth,
        db,
        status=status,
        search=search,
        page=page,
    )


@router.get("/pips/new", response_class=HTMLResponse)
def new_pip_form(
    request: Request,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """New PIP form."""
    from app.services.people.perf.web.pip_web import PIPWebService

    return PIPWebService().pip_new_form_response(request, auth, db)


@router.post("/pips/new", response_class=HTMLResponse)
async def create_pip(
    request: Request,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Create a new PIP."""
    from app.services.people.perf.web.pip_web import PIPWebService

    return await PIPWebService().create_pip_response(request, auth, db)


@router.get("/pips/{pip_id}", response_class=HTMLResponse)
def pip_detail(
    request: Request,
    pip_id: str,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """PIP detail page."""
    from app.services.people.perf.web.pip_web import PIPWebService

    return PIPWebService().pip_detail_response(request, auth, db, pip_id)


@router.post("/pips/{pip_id}/activate", response_class=HTMLResponse)
async def activate_pip(
    request: Request,
    pip_id: str,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Activate a PIP."""
    from fastapi.responses import RedirectResponse

    from app.services.common import coerce_uuid
    from app.services.people.perf.pip_service import PIPService

    org_id = coerce_uuid(auth.organization_id)
    svc = PIPService(db)
    try:
        svc.activate_pip(org_id, coerce_uuid(pip_id))
        db.commit()
        return RedirectResponse(
            url=f"/people/perf/pms/pips/{pip_id}?saved=1", status_code=303
        )
    except Exception as e:
        db.rollback()
        return RedirectResponse(
            url=f"/people/perf/pms/pips/{pip_id}?error={e}", status_code=303
        )


@router.post("/pips/{pip_id}/extend", response_class=HTMLResponse)
async def extend_pip(
    request: Request,
    pip_id: str,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Extend a PIP end date."""
    from fastapi.responses import RedirectResponse

    from app.services.common import coerce_uuid
    from app.services.people.perf.pip_service import PIPService
    from app.services.people.perf.web.base import parse_date

    form_data = await request.form()
    org_id = coerce_uuid(auth.organization_id)
    svc = PIPService(db)
    try:
        new_end_str = str(form_data.get("new_end_date", "")).strip()
        new_end = parse_date(new_end_str)
        if not new_end:
            raise ValueError("New end date is required")
        reason = str(form_data.get("reason", "")).strip()
        if not reason:
            raise ValueError("Reason is required")
        svc.grant_extension(org_id, coerce_uuid(pip_id), new_end_date=new_end, reason=reason)
        db.commit()
        return RedirectResponse(
            url=f"/people/perf/pms/pips/{pip_id}?saved=1", status_code=303
        )
    except Exception as e:
        db.rollback()
        return RedirectResponse(
            url=f"/people/perf/pms/pips/{pip_id}?error={e}", status_code=303
        )


@router.post("/pips/{pip_id}/record-review", response_class=HTMLResponse)
async def pip_record_review(
    request: Request,
    pip_id: str,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Record a PIP interval review."""
    from fastapi.responses import RedirectResponse

    from app.services.common import coerce_uuid
    from app.services.people.perf.pip_service import PIPService
    from app.services.people.perf.web.base import parse_date

    form_data = await request.form()
    org_id = coerce_uuid(auth.organization_id)
    svc = PIPService(db)
    try:
        review_date_str = str(form_data.get("review_date", "")).strip()
        review_date = parse_date(review_date_str)
        if not review_date:
            raise ValueError("Review date is required")
        notes = str(form_data.get("notes", "")).strip()
        if not notes:
            raise ValueError("Notes are required")
        progress_status = str(form_data.get("progress_status", "")).strip()
        if not progress_status:
            raise ValueError("Progress status is required")
        svc.record_review(
            org_id,
            coerce_uuid(pip_id),
            review_date=review_date,
            notes=notes,
            progress_status=progress_status,
        )
        db.commit()
        return RedirectResponse(
            url=f"/people/perf/pms/pips/{pip_id}?saved=1", status_code=303
        )
    except Exception as e:
        db.rollback()
        return RedirectResponse(
            url=f"/people/perf/pms/pips/{pip_id}?error={e}", status_code=303
        )


@router.post("/pips/{pip_id}/complete", response_class=HTMLResponse)
async def complete_pip(
    request: Request,
    pip_id: str,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Complete a PIP with an outcome."""
    from fastapi.responses import RedirectResponse

    from app.services.common import coerce_uuid
    from app.services.people.perf.pip_service import PIPService
    from app.models.people.perf.pms_enums import PIPOutcome

    form_data = await request.form()
    org_id = coerce_uuid(auth.organization_id)
    svc = PIPService(db)
    try:
        outcome_str = str(form_data.get("outcome", "")).strip()
        if not outcome_str:
            raise ValueError("Outcome is required")
        try:
            outcome = PIPOutcome(outcome_str)
        except ValueError as exc:
            raise ValueError(f"Invalid outcome value: {outcome_str}") from exc
        notes = str(form_data.get("notes", "")).strip()
        if not notes:
            raise ValueError("Notes are required")
        svc.complete_pip(
            org_id,
            coerce_uuid(pip_id),
            outcome=outcome,
            notes=notes,
        )
        db.commit()
        return RedirectResponse(
            url=f"/people/perf/pms/pips/{pip_id}?saved=1", status_code=303
        )
    except Exception as e:
        db.rollback()
        return RedirectResponse(
            url=f"/people/perf/pms/pips/{pip_id}?error={e}", status_code=303
        )


# ─────────────────────────────────────────────────────────────────────────────
# Appeals
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/appeals", response_class=HTMLResponse)
def list_appeals(
    request: Request,
    status: str | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Appeals list page."""
    from app.services.people.perf.web.appeal_web import AppealWebService

    return AppealWebService().list_appeals_response(
        request,
        auth,
        db,
        status=status,
        search=search,
        page=page,
    )


@router.get("/appeals/new", response_class=HTMLResponse)
def new_appeal_form(
    request: Request,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """New appeal form."""
    from app.services.people.perf.web.appeal_web import AppealWebService

    return AppealWebService().appeal_new_form_response(request, auth, db)


@router.post("/appeals/new", response_class=HTMLResponse)
async def create_appeal(
    request: Request,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Create a new appeal."""
    from app.services.people.perf.web.appeal_web import AppealWebService

    return await AppealWebService().create_appeal_response(request, auth, db)


@router.get("/appeals/{appeal_id}", response_class=HTMLResponse)
def appeal_detail(
    request: Request,
    appeal_id: str,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Appeal detail page."""
    from app.services.people.perf.web.appeal_web import AppealWebService

    return AppealWebService().appeal_detail_response(request, auth, db, appeal_id)


@router.post("/appeals/{appeal_id}/assign-mediator", response_class=HTMLResponse)
async def assign_mediator(
    request: Request,
    appeal_id: str,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Assign a mediator to an appeal."""
    from fastapi.responses import RedirectResponse

    from app.services.common import coerce_uuid
    from app.services.people.perf.appeal_service import AppraisalAppealService

    form_data = await request.form()
    org_id = coerce_uuid(auth.organization_id)
    svc = AppraisalAppealService(db)
    try:
        mediator_id_str = str(form_data.get("mediator_id", "")).strip()
        if not mediator_id_str:
            raise ValueError("Mediator is required")
        svc.assign_mediator(
            org_id,
            coerce_uuid(appeal_id),
            mediator_id=coerce_uuid(mediator_id_str),
        )
        db.commit()
        return RedirectResponse(
            url=f"/people/perf/pms/appeals/{appeal_id}?saved=1", status_code=303
        )
    except Exception as e:
        db.rollback()
        return RedirectResponse(
            url=f"/people/perf/pms/appeals/{appeal_id}?error={e}", status_code=303
        )


@router.post("/appeals/{appeal_id}/mediation-outcome", response_class=HTMLResponse)
async def record_mediation_outcome(
    request: Request,
    appeal_id: str,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Record the outcome of mediation for an appeal."""
    from fastapi.responses import RedirectResponse

    from app.services.common import coerce_uuid
    from app.services.people.perf.appeal_service import AppraisalAppealService

    form_data = await request.form()
    org_id = coerce_uuid(auth.organization_id)
    svc = AppraisalAppealService(db)
    try:
        outcome = str(form_data.get("outcome", "")).strip()
        if not outcome:
            raise ValueError("Outcome is required")
        resolved_str = str(form_data.get("resolved", "")).strip().lower()
        resolved = resolved_str in ("true", "1", "yes")
        svc.record_mediation_outcome(
            org_id,
            coerce_uuid(appeal_id),
            outcome=outcome,
            resolved=resolved,
        )
        db.commit()
        return RedirectResponse(
            url=f"/people/perf/pms/appeals/{appeal_id}?saved=1", status_code=303
        )
    except Exception as e:
        db.rollback()
        return RedirectResponse(
            url=f"/people/perf/pms/appeals/{appeal_id}?error={e}", status_code=303
        )


@router.post("/appeals/{appeal_id}/committee-decision", response_class=HTMLResponse)
async def record_committee_decision(
    request: Request,
    appeal_id: str,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Record an appeal committee decision."""
    from fastapi.responses import RedirectResponse

    from app.services.common import coerce_uuid
    from app.models.people.perf.pms_enums import AppealDecision
    from app.services.people.perf.appeal_service import AppraisalAppealService

    form_data = await request.form()
    org_id = coerce_uuid(auth.organization_id)
    svc = AppraisalAppealService(db)
    try:
        decision_str = str(form_data.get("decision", "")).strip()
        if not decision_str:
            raise ValueError("Decision is required")
        try:
            decision = AppealDecision(decision_str)
        except ValueError as exc:
            raise ValueError(f"Invalid decision value: {decision_str}") from exc
        notes = str(form_data.get("notes", "")).strip()
        if not notes:
            raise ValueError("Notes are required")
        adjusted_rating_str = str(form_data.get("adjusted_rating", "")).strip()
        adjusted_rating = int(adjusted_rating_str) if adjusted_rating_str else None
        svc.record_committee_decision(
            org_id,
            coerce_uuid(appeal_id),
            decision=decision,
            notes=notes,
            adjusted_rating=adjusted_rating,
        )
        db.commit()
        return RedirectResponse(
            url=f"/people/perf/pms/appeals/{appeal_id}?saved=1", status_code=303
        )
    except Exception as e:
        db.rollback()
        return RedirectResponse(
            url=f"/people/perf/pms/appeals/{appeal_id}?error={e}", status_code=303
        )


@router.post("/appeals/{appeal_id}/communicate", response_class=HTMLResponse)
async def communicate_appeal_decision(
    request: Request,
    appeal_id: str,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Communicate the final decision on an appeal to the appellant."""
    from fastapi.responses import RedirectResponse

    from app.services.common import coerce_uuid
    from app.services.people.perf.appeal_service import AppraisalAppealService

    org_id = coerce_uuid(auth.organization_id)
    svc = AppraisalAppealService(db)
    try:
        svc.communicate_decision(org_id, coerce_uuid(appeal_id))
        db.commit()
        return RedirectResponse(
            url=f"/people/perf/pms/appeals/{appeal_id}?saved=1", status_code=303
        )
    except Exception as e:
        db.rollback()
        return RedirectResponse(
            url=f"/people/perf/pms/appeals/{appeal_id}?error={e}", status_code=303
        )


# ─────────────────────────────────────────────────────────────────────────────
# Institutional Performance
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/institutional", response_class=HTMLResponse)
def list_institutional(
    request: Request,
    status: str | None = None,
    cycle_id: str | None = None,
    page: int = Query(default=1, ge=1),
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Institutional performance list page."""
    from app.services.people.perf.web.institutional_web import InstitutionalWebService

    return InstitutionalWebService().list_institutional_response(
        request,
        auth,
        db,
        status=status,
        cycle_id=cycle_id,
        page=page,
    )


@router.get("/institutional/new", response_class=HTMLResponse)
def new_institutional_form(
    request: Request,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """New institutional performance form."""
    from app.services.people.perf.web.institutional_web import InstitutionalWebService

    return InstitutionalWebService().institutional_new_form_response(request, auth, db)


@router.post("/institutional/new", response_class=HTMLResponse)
async def create_institutional(
    request: Request,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Create a new institutional performance record."""
    from app.services.people.perf.web.institutional_web import InstitutionalWebService

    return await InstitutionalWebService().create_institutional_response(
        request, auth, db
    )


@router.get("/institutional/{inst_perf_id}", response_class=HTMLResponse)
def institutional_detail(
    request: Request,
    inst_perf_id: str,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Institutional performance detail page."""
    from app.services.people.perf.web.institutional_web import InstitutionalWebService

    return InstitutionalWebService().institutional_detail_response(
        request, auth, db, inst_perf_id
    )


@router.post("/institutional/{inst_perf_id}/score", response_class=HTMLResponse)
async def score_institutional(
    request: Request,
    inst_perf_id: str,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Score criteria for an institutional performance record."""
    import json

    from fastapi.responses import RedirectResponse

    from app.services.common import coerce_uuid
    from app.services.people.perf.institutional_service import (
        InstitutionalPerformanceService,
    )

    form_data = await request.form()
    org_id = coerce_uuid(auth.organization_id)
    svc = InstitutionalPerformanceService(db)
    try:
        scores_raw = str(form_data.get("criteria_scores_json", "{}")).strip()
        try:
            criteria_scores = json.loads(scores_raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Criteria scores data is not valid JSON") from exc
        svc.score_criteria(org_id, coerce_uuid(inst_perf_id), criteria_scores=criteria_scores)
        db.commit()
        return RedirectResponse(
            url=f"/people/perf/pms/institutional/{inst_perf_id}?saved=1", status_code=303
        )
    except Exception as e:
        db.rollback()
        return RedirectResponse(
            url=f"/people/perf/pms/institutional/{inst_perf_id}?error={e}",
            status_code=303,
        )


@router.post("/institutional/{inst_perf_id}/reconcile", response_class=HTMLResponse)
async def reconcile_institutional(
    request: Request,
    inst_perf_id: str,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Reconcile institutional performance with employee ratings."""
    from decimal import Decimal

    from fastapi.responses import RedirectResponse

    from app.services.common import coerce_uuid
    from app.services.people.perf.institutional_service import (
        InstitutionalPerformanceService,
    )

    form_data = await request.form()
    org_id = coerce_uuid(auth.organization_id)
    svc = InstitutionalPerformanceService(db)
    try:
        notes = str(form_data.get("notes", "")).strip()
        if not notes:
            raise ValueError("Notes are required")
        adjusted_str = str(form_data.get("adjusted_composite", "")).strip()
        adjusted_composite = Decimal(adjusted_str) if adjusted_str else None
        svc.reconcile_with_employee_ratings(
            org_id,
            coerce_uuid(inst_perf_id),
            reconciled_by_id=coerce_uuid(auth.person_id),
            notes=notes,
            adjusted_composite=adjusted_composite,
        )
        db.commit()
        return RedirectResponse(
            url=f"/people/perf/pms/institutional/{inst_perf_id}?saved=1", status_code=303
        )
    except Exception as e:
        db.rollback()
        return RedirectResponse(
            url=f"/people/perf/pms/institutional/{inst_perf_id}?error={e}",
            status_code=303,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Strategic Objectives
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/objectives", response_class=HTMLResponse)
def list_objectives(
    request: Request,
    cycle_id: str | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Strategic objectives list page."""
    from app.services.people.perf.web.strategic_objective_web import (
        StrategicObjectiveWebService,
    )

    return StrategicObjectiveWebService().list_objectives_response(
        request,
        auth,
        db,
        cycle_id=cycle_id,
        search=search,
        page=page,
    )


@router.get("/objectives/new", response_class=HTMLResponse)
def new_objective_form(
    request: Request,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """New strategic objective form."""
    from app.services.people.perf.web.strategic_objective_web import (
        StrategicObjectiveWebService,
    )

    return StrategicObjectiveWebService().objective_new_form_response(
        request, auth, db
    )


@router.post("/objectives/new", response_class=HTMLResponse)
async def create_objective(
    request: Request,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Create a new strategic objective."""
    from app.services.people.perf.web.strategic_objective_web import (
        StrategicObjectiveWebService,
    )

    return await StrategicObjectiveWebService().create_objective_response(
        request, auth, db
    )


# ─────────────────────────────────────────────────────────────────────────────
# Reports
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/reports", response_class=HTMLResponse)
def pms_reports_hub(
    request: Request,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """PMS reports hub."""
    from app.services.people.perf.web.pms_reports_web import PMSReportsWebService

    return PMSReportsWebService().reports_hub_response(request, auth, db)


@router.get("/reports/{report_type}", response_class=HTMLResponse)
def pms_report(
    request: Request,
    report_type: str,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Individual PMS report page."""
    from app.services.people.perf.web.pms_reports_web import PMSReportsWebService

    return PMSReportsWebService().report_response(
        request,
        auth,
        db,
        report_type=report_type,
    )
