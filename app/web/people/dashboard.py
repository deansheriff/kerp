"""
People Dashboard Web Routes.

Dashboard page for the People/HR module.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.services.people.hr.web import people_dashboard_service
from app.web.deps import WebAuthContext, get_db_for_org, require_web_auth

router = APIRouter(tags=["people-dashboard-web"])


@router.get("/", response_class=HTMLResponse)
@router.get("/dashboard", response_class=HTMLResponse)
def people_dashboard(
    request: Request,
    auth: WebAuthContext = Depends(require_web_auth),
    db: Session = Depends(get_db_for_org),
) -> HTMLResponse | RedirectResponse:
    """People module dashboard page."""
    if not auth.has_permission("hr:dashboard"):
        if auth.has_any_permission(
            ["hr:employees:directory", "hr:employees:read"]
        ):
            return RedirectResponse(url="/people/hr/employees", status_code=302)
        if auth.has_permission("self:access"):
            return RedirectResponse(url="/people/self", status_code=302)
        raise HTTPException(status_code=403, detail="People access required")

    return people_dashboard_service.dashboard_response(request, auth, db)
