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

    return ContractWebService().list_response(
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

    return ContractWebService().form_response(
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

    return await ContractWebService().create_response(request, auth, db)


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

    return ContractWebService().detail_response(
        request, auth, db, contract_id, success=success, error=error
    )


@router.get("/contracts/{contract_id}/edit", response_class=HTMLResponse)
def edit_contract_form(
    request: Request,
    contract_id: str,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Edit performance contract form."""
    from app.services.people.perf.web.contract_web import ContractWebService

    return ContractWebService().edit_form_response(request, auth, db, contract_id)


@router.post("/contracts/{contract_id}/edit", response_class=HTMLResponse)
async def update_contract(
    request: Request,
    contract_id: str,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Update a performance contract."""
    from app.services.people.perf.web.contract_web import ContractWebService

    return await ContractWebService().update_response(request, auth, db, contract_id)


@router.post("/contracts/{contract_id}/sign-employee", response_class=HTMLResponse)
async def sign_contract_employee(
    request: Request,
    contract_id: str,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Employee signs the performance contract."""
    from app.services.people.perf.web.contract_web import ContractWebService

    return await ContractWebService().sign_employee_response(
        request, auth, db, contract_id
    )


@router.post("/contracts/{contract_id}/sign-supervisor", response_class=HTMLResponse)
async def sign_contract_supervisor(
    request: Request,
    contract_id: str,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Supervisor signs the performance contract."""
    from app.services.people.perf.web.contract_web import ContractWebService

    return await ContractWebService().sign_supervisor_response(
        request, auth, db, contract_id
    )


# ─────────────────────────────────────────────────────────────────────────────
# Monthly Reviews
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/reviews", response_class=HTMLResponse)
def list_reviews(
    request: Request,
    status: str | None = None,
    employee_id: str | None = None,
    cycle_id: str | None = None,
    month: int | None = None,
    page: int = Query(default=1, ge=1),
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Monthly reviews list page."""
    from app.services.people.perf.web.monthly_review_web import MonthlyReviewWebService

    return MonthlyReviewWebService().list_response(
        request,
        auth,
        db,
        status=status,
        employee_id=employee_id,
        cycle_id=cycle_id,
        month=month,
        page=page,
    )


@router.get("/reviews/new", response_class=HTMLResponse)
def new_review_form(
    request: Request,
    employee_id: str | None = None,
    cycle_id: str | None = None,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """New monthly review form."""
    from app.services.people.perf.web.monthly_review_web import MonthlyReviewWebService

    return MonthlyReviewWebService().form_response(
        request, auth, db, employee_id=employee_id, cycle_id=cycle_id
    )


@router.post("/reviews/new", response_class=HTMLResponse)
async def create_review(
    request: Request,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Create a new monthly review."""
    from app.services.people.perf.web.monthly_review_web import MonthlyReviewWebService

    return await MonthlyReviewWebService().create_response(request, auth, db)


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

    return MonthlyReviewWebService().detail_response(
        request, auth, db, review_id, success=success, error=error
    )


# ─────────────────────────────────────────────────────────────────────────────
# Performance Improvement Plans (PIPs)
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/pips", response_class=HTMLResponse)
def list_pips(
    request: Request,
    status: str | None = None,
    employee_id: str | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """PIPs list page."""
    from app.services.people.perf.web.pip_web import PIPWebService

    return PIPWebService().list_response(
        request,
        auth,
        db,
        status=status,
        employee_id=employee_id,
        search=search,
        page=page,
    )


@router.get("/pips/new", response_class=HTMLResponse)
def new_pip_form(
    request: Request,
    employee_id: str | None = None,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """New PIP form."""
    from app.services.people.perf.web.pip_web import PIPWebService

    return PIPWebService().form_response(request, auth, db, employee_id=employee_id)


@router.post("/pips/new", response_class=HTMLResponse)
async def create_pip(
    request: Request,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Create a new PIP."""
    from app.services.people.perf.web.pip_web import PIPWebService

    return await PIPWebService().create_response(request, auth, db)


@router.get("/pips/{pip_id}", response_class=HTMLResponse)
def pip_detail(
    request: Request,
    pip_id: str,
    success: str | None = None,
    error: str | None = None,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """PIP detail page."""
    from app.services.people.perf.web.pip_web import PIPWebService

    return PIPWebService().detail_response(
        request, auth, db, pip_id, success=success, error=error
    )


# ─────────────────────────────────────────────────────────────────────────────
# Appeals
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/appeals", response_class=HTMLResponse)
def list_appeals(
    request: Request,
    status: str | None = None,
    employee_id: str | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Appeals list page."""
    from app.services.people.perf.web.appeal_web import AppealWebService

    return AppealWebService().list_response(
        request,
        auth,
        db,
        status=status,
        employee_id=employee_id,
        search=search,
        page=page,
    )


@router.get("/appeals/new", response_class=HTMLResponse)
def new_appeal_form(
    request: Request,
    appraisal_id: str | None = None,
    employee_id: str | None = None,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """New appeal form."""
    from app.services.people.perf.web.appeal_web import AppealWebService

    return AppealWebService().form_response(
        request, auth, db, appraisal_id=appraisal_id, employee_id=employee_id
    )


@router.post("/appeals/new", response_class=HTMLResponse)
async def create_appeal(
    request: Request,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Create a new appeal."""
    from app.services.people.perf.web.appeal_web import AppealWebService

    return await AppealWebService().create_response(request, auth, db)


@router.get("/appeals/{appeal_id}", response_class=HTMLResponse)
def appeal_detail(
    request: Request,
    appeal_id: str,
    success: str | None = None,
    error: str | None = None,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Appeal detail page."""
    from app.services.people.perf.web.appeal_web import AppealWebService

    return AppealWebService().detail_response(
        request, auth, db, appeal_id, success=success, error=error
    )


# ─────────────────────────────────────────────────────────────────────────────
# Institutional Performance
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/institutional", response_class=HTMLResponse)
def list_institutional(
    request: Request,
    status: str | None = None,
    cycle_id: str | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Institutional performance list page."""
    from app.services.people.perf.web.institutional_web import InstitutionalWebService

    return InstitutionalWebService().list_response(
        request,
        auth,
        db,
        status=status,
        cycle_id=cycle_id,
        search=search,
        page=page,
    )


@router.get("/institutional/new", response_class=HTMLResponse)
def new_institutional_form(
    request: Request,
    cycle_id: str | None = None,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """New institutional performance form."""
    from app.services.people.perf.web.institutional_web import InstitutionalWebService

    return InstitutionalWebService().form_response(
        request, auth, db, cycle_id=cycle_id
    )


@router.post("/institutional/new", response_class=HTMLResponse)
async def create_institutional(
    request: Request,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Create a new institutional performance record."""
    from app.services.people.perf.web.institutional_web import InstitutionalWebService

    return await InstitutionalWebService().create_response(request, auth, db)


@router.get("/institutional/{record_id}", response_class=HTMLResponse)
def institutional_detail(
    request: Request,
    record_id: str,
    success: str | None = None,
    error: str | None = None,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """Institutional performance detail page."""
    from app.services.people.perf.web.institutional_web import InstitutionalWebService

    return InstitutionalWebService().detail_response(
        request, auth, db, record_id, success=success, error=error
    )


# ─────────────────────────────────────────────────────────────────────────────
# Strategic Objectives
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/objectives", response_class=HTMLResponse)
def list_objectives(
    request: Request,
    status: str | None = None,
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

    return StrategicObjectiveWebService().list_response(
        request,
        auth,
        db,
        status=status,
        cycle_id=cycle_id,
        search=search,
        page=page,
    )


@router.get("/objectives/new", response_class=HTMLResponse)
def new_objective_form(
    request: Request,
    cycle_id: str | None = None,
    auth: WebAuthContext = Depends(require_hr_access),
    db: Session = Depends(get_db),
):
    """New strategic objective form."""
    from app.services.people.perf.web.strategic_objective_web import (
        StrategicObjectiveWebService,
    )

    return StrategicObjectiveWebService().form_response(
        request, auth, db, cycle_id=cycle_id
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

    return await StrategicObjectiveWebService().create_response(request, auth, db)


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

    return PMSReportsWebService().hub_response(request, auth, db)


@router.get("/reports/{report_type}", response_class=HTMLResponse)
def pms_report(
    request: Request,
    report_type: str,
    cycle_id: str | None = None,
    department_id: str | None = None,
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
        cycle_id=cycle_id,
        department_id=department_id,
    )
