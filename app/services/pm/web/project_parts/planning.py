"""Project web planning handlers."""

from app.services.pm.web.project_parts.base import (
    Decimal,
    Depends,
    Form,
    NotFoundError,
    RedirectResponse,
    Request,
    Session,
    WebAuthContext,
    _get_employees,
    _get_projects,
    _get_services,
    _resolve_project_ref,
    _safe_date,
    _safe_decimal,
    base_context,
    coerce_uuid,
    date,
    get_db,
    logger,
    require_projects_access,
    templates,
)


def project_gantt(
    request: Request,
    project_id: str,
    auth: WebAuthContext = Depends(require_projects_access),
    db: Session = Depends(get_db),
):
    """Project Gantt chart page."""

    org_id = coerce_uuid(auth.organization_id)
    project = _resolve_project_ref(db, org_id, project_id)

    if not project:
        return templates.TemplateResponse(
            "errors/404.html",
            {"request": request, "message": "Project not found"},
            status_code=404,
        )

    services = _get_services(db, org_id)

    try:
        gantt_data = services["gantt"].get_gantt_data(project.project_id)
    except NotFoundError:
        gantt_data = None

    context = {
        "request": request,
        **base_context(request, auth, "Gantt Chart", "gantt", db=db),
        "project": project,
        "gantt_data": gantt_data,
    }

    return templates.TemplateResponse(request, "projects/gantt.html", context)


def project_team(
    request: Request,
    project_id: str,
    auth: WebAuthContext = Depends(require_projects_access),
    db: Session = Depends(get_db),
):
    """Project team management page."""

    org_id = coerce_uuid(auth.organization_id)
    project = _resolve_project_ref(db, org_id, project_id)

    if not project:
        return templates.TemplateResponse(
            "errors/404.html",
            {"request": request, "message": "Project not found"},
            status_code=404,
        )

    services = _get_services(db, org_id)

    allocations = services["resource"].get_project_team(project.project_id)
    employees = _get_employees(db, org_id)

    context = {
        "request": request,
        **base_context(request, auth, "Project Team", "team", db=db),
        "project": project,
        "allocations": allocations,
        "employees": employees,
    }

    return templates.TemplateResponse(request, "projects/team.html", context)


def create_resource_allocation(
    request: Request,
    project_id: str,
    auth: WebAuthContext = Depends(require_projects_access),
    employee_id: str = Form(...),
    role_on_project: str = Form(default=""),
    allocation_percent: str = Form(default="100"),
    start_date: str = Form(...),
    end_date: str = Form(default=""),
    cost_rate_per_hour: str = Form(default=""),
    billing_rate_per_hour: str = Form(default=""),
    db: Session = Depends(get_db),
):
    """Add a team member to the project."""
    org_id = coerce_uuid(auth.organization_id)
    project = _resolve_project_ref(db, org_id, project_id)
    if not project:
        return RedirectResponse(
            url="/projects?success=Record+created+successfully", status_code=303
        )
    services = _get_services(db, org_id)

    parsed_start = _safe_date(start_date)
    if not parsed_start:
        return RedirectResponse(
            url=f"/projects/{project.project_code}/team?saved=1",
            status_code=303,
        )

    services["resource"].allocate_resource(
        {
            "project_id": project.project_id,
            "employee_id": coerce_uuid(employee_id),
            "role_on_project": role_on_project.strip() if role_on_project else None,
            "allocation_percent": _safe_decimal(allocation_percent, Decimal("100")),
            "start_date": parsed_start,
            "end_date": _safe_date(end_date),
            "cost_rate_per_hour": _safe_decimal(cost_rate_per_hour),
            "billing_rate_per_hour": _safe_decimal(billing_rate_per_hour),
        }
    )

    return RedirectResponse(
        url=f"/projects/{project.project_code}/team?saved=1",
        status_code=303,
    )


def update_resource_allocation(
    request: Request,
    project_id: str,
    allocation_id: str,
    auth: WebAuthContext = Depends(require_projects_access),
    role_on_project: str = Form(default=""),
    allocation_percent: str = Form(default="100"),
    start_date: str = Form(...),
    end_date: str = Form(default=""),
    cost_rate_per_hour: str = Form(default=""),
    billing_rate_per_hour: str = Form(default=""),
    is_active: str = Form(default="on"),
    db: Session = Depends(get_db),
):
    """Update a resource allocation."""
    org_id = coerce_uuid(auth.organization_id)
    project = _resolve_project_ref(db, org_id, project_id)
    if not project:
        return RedirectResponse(
            url="/projects?success=Record+updated+successfully", status_code=303
        )
    allocation_uuid = coerce_uuid(allocation_id)
    services = _get_services(db, org_id)

    try:
        services["resource"].update_allocation(
            allocation_uuid,
            {
                "role_on_project": role_on_project.strip() if role_on_project else None,
                "allocation_percent": _safe_decimal(allocation_percent, Decimal("100")),
                "end_date": _safe_date(end_date),
                "cost_rate_per_hour": _safe_decimal(cost_rate_per_hour),
                "billing_rate_per_hour": _safe_decimal(billing_rate_per_hour),
                "is_active": is_active == "on",
            },
        )
    except NotFoundError:
        pass

    return RedirectResponse(
        url=f"/projects/{project.project_code}/team?saved=1",
        status_code=303,
    )


def end_resource_allocation(
    request: Request,
    project_id: str,
    allocation_id: str,
    auth: WebAuthContext = Depends(require_projects_access),
    end_date: str = Form(default=""),
    db: Session = Depends(get_db),
):
    """End a resource allocation."""
    org_id = coerce_uuid(auth.organization_id)
    project = _resolve_project_ref(db, org_id, project_id)
    if not project:
        return RedirectResponse(
            url="/projects?success=Record+saved+successfully", status_code=303
        )
    allocation_uuid = coerce_uuid(allocation_id)
    services = _get_services(db, org_id)

    try:
        end_dt = date.fromisoformat(end_date) if end_date else date.today()
        services["resource"].end_allocation(allocation_uuid, end_dt)
    except NotFoundError:
        pass

    return RedirectResponse(
        url=f"/projects/{project.project_code}/team?saved=1",
        status_code=303,
    )


def delete_resource_allocation(
    request: Request,
    project_id: str,
    allocation_id: str,
    auth: WebAuthContext = Depends(require_projects_access),
    db: Session = Depends(get_db),
):
    """Delete a resource allocation."""
    org_id = coerce_uuid(auth.organization_id)
    project = _resolve_project_ref(db, org_id, project_id)
    if not project:
        return RedirectResponse(
            url="/projects?success=Record+deleted+successfully", status_code=303
        )
    allocation_uuid = coerce_uuid(allocation_id)
    services = _get_services(db, org_id)

    try:
        services["resource"].delete_allocation(allocation_uuid)
    except NotFoundError:
        pass

    return RedirectResponse(
        url=f"/projects/{project.project_code}/team?saved=1",
        status_code=303,
    )


def resource_utilization_report(
    request: Request,
    auth: WebAuthContext = Depends(require_projects_access),
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
):
    """Resource utilization report across all projects."""
    from datetime import timedelta

    org_id = coerce_uuid(auth.organization_id)
    services = _get_services(db, org_id)

    # Default to current month
    today = date.today()
    if start_date:
        try:
            period_start = date.fromisoformat(start_date)
        except ValueError:
            period_start = today.replace(day=1)
    else:
        period_start = today.replace(day=1)

    if end_date:
        try:
            period_end = date.fromisoformat(end_date)
        except ValueError:
            # End of month
            next_month = period_start.replace(day=28) + timedelta(days=4)
            period_end = next_month.replace(day=1) - timedelta(days=1)
    else:
        next_month = period_start.replace(day=28) + timedelta(days=4)
        period_end = next_month.replace(day=1) - timedelta(days=1)

    # Get all employees with active allocations
    employees = _get_employees(db, org_id)

    utilization_data = []
    total_utilization = Decimal("0")

    for emp in employees:
        try:
            util = services["resource"].get_utilization(
                emp.employee_id, period_start, period_end
            )
            if util["total_allocation_percent"] > 0 or util["hours_logged"] > 0:
                utilization_data.append(
                    {
                        "employee_id": emp.employee_id,
                        "employee_name": emp.full_name,
                        "hours_logged": util["hours_logged"],
                        "expected_hours": util["expected_hours"],
                        "utilization_percent": util["utilization_percent"],
                        "total_allocation_percent": util["total_allocation_percent"],
                        "allocations": util["project_allocations"],
                    }
                )
                total_utilization += util["utilization_percent"]
        except Exception:
            logger.exception(
                "utilization_by_employee: failed for employee_id=%s",
                emp.employee_id,
            )
            continue

    # Calculate averages and flags
    avg_utilization = (
        total_utilization / len(utilization_data) if utilization_data else Decimal("0")
    )
    over_allocated = [
        d for d in utilization_data if d["total_allocation_percent"] > 100
    ]
    under_utilized = [d for d in utilization_data if d["utilization_percent"] < 50]

    # Sort by utilization descending
    utilization_data.sort(key=lambda x: x["utilization_percent"], reverse=True)

    # Get project-level utilization
    projects = _get_projects(db, org_id)
    project_utilization = []
    for proj in projects:
        if proj.status and proj.status.value in ("ACTIVE", "IN_PROGRESS"):
            try:
                proj_util = services["resource"].get_project_utilization(
                    proj.project_id
                )
                if proj_util["total_team_members"] > 0:
                    project_utilization.append(
                        {
                            "project_id": proj.project_id,
                            "project_code": proj.project_code,
                            "project_name": proj.project_name,
                            "team_size": proj_util["total_team_members"],
                            "avg_allocation": proj_util["average_allocation"],
                            "total_hours": proj_util["total_hours_logged"],
                            "billable_percent": proj_util["billable_percent"],
                        }
                    )
            except Exception:
                logger.exception(
                    "utilization_by_project: failed for project_id=%s",
                    proj.project_id,
                )
                continue

    context = {
        "request": request,
        **base_context(request, auth, "Resource Utilization", "utilization", db=db),
        "period_start": period_start,
        "period_end": period_end,
        "utilization_data": utilization_data,
        "avg_utilization": avg_utilization,
        "over_allocated": over_allocated,
        "under_utilized": under_utilized,
        "team_members": employees,
        "project_utilization": project_utilization,
    }

    return templates.TemplateResponse(request, "projects/utilization.html", context)


def project_milestones(
    request: Request,
    project_id: str,
    auth: WebAuthContext = Depends(require_projects_access),
    db: Session = Depends(get_db),
):
    """Project milestones page."""

    org_id = coerce_uuid(auth.organization_id)
    project = _resolve_project_ref(db, org_id, project_id)

    if not project:
        return templates.TemplateResponse(
            "errors/404.html",
            {"request": request, "message": "Project not found"},
            status_code=404,
        )

    services = _get_services(db, org_id)

    milestones = services["milestone"].get_project_milestones(project.project_id)

    context = {
        "request": request,
        **base_context(request, auth, "Milestones", "milestones", db=db),
        "project": project,
        "milestones": milestones,
    }

    return templates.TemplateResponse(request, "projects/milestones.html", context)


def create_milestone(
    request: Request,
    project_id: str,
    auth: WebAuthContext = Depends(require_projects_access),
    name: str = Form(...),
    description: str = Form(default=""),
    target_date: str = Form(...),
    linked_task_id: str = Form(default=""),
    db: Session = Depends(get_db),
):
    """Create a new milestone."""
    import uuid as uuid_mod

    org_id = coerce_uuid(auth.organization_id)
    project = _resolve_project_ref(db, org_id, project_id)
    if not project:
        return RedirectResponse(
            url="/projects?success=Record+created+successfully", status_code=303
        )
    services = _get_services(db, org_id)

    # Generate milestone code
    milestone_code = f"MS-{str(uuid_mod.uuid4())[:8].upper()}"

    services["milestone"].create_milestone(
        {
            "project_id": project.project_id,
            "milestone_code": milestone_code,
            "milestone_name": name.strip(),
            "description": description.strip() if description else None,
            "target_date": date.fromisoformat(target_date),
            "linked_task_id": coerce_uuid(linked_task_id) if linked_task_id else None,
        }
    )

    return RedirectResponse(
        url=f"/projects/{project.project_code}/milestones?saved=1",
        status_code=303,
    )


def update_milestone(
    request: Request,
    project_id: str,
    milestone_id: str,
    auth: WebAuthContext = Depends(require_projects_access),
    name: str = Form(...),
    description: str = Form(default=""),
    target_date: str = Form(...),
    status: str = Form(...),
    actual_date: str = Form(default=""),
    db: Session = Depends(get_db),
):
    """Update a milestone."""

    org_id = coerce_uuid(auth.organization_id)
    project = _resolve_project_ref(db, org_id, project_id)
    if not project:
        return RedirectResponse(
            url="/projects?success=Record+updated+successfully", status_code=303
        )
    milestone_uuid = coerce_uuid(milestone_id)
    services = _get_services(db, org_id)

    try:
        # Note: update_milestone doesn't accept status change - only the fields defined
        # If status changes needed, use achieve_milestone for ACHIEVED
        services["milestone"].update_milestone(
            milestone_uuid,
            {
                "milestone_name": name.strip(),
                "description": description.strip() if description else None,
                "target_date": date.fromisoformat(target_date),
            },
        )
    except NotFoundError:
        pass

    return RedirectResponse(
        url=f"/projects/{project.project_code}/milestones?saved=1",
        status_code=303,
    )


def achieve_milestone(
    request: Request,
    project_id: str,
    milestone_id: str,
    auth: WebAuthContext = Depends(require_projects_access),
    db: Session = Depends(get_db),
):
    """Mark a milestone as achieved."""
    org_id = coerce_uuid(auth.organization_id)
    project = _resolve_project_ref(db, org_id, project_id)
    if not project:
        return RedirectResponse(
            url="/projects?success=Record+saved+successfully", status_code=303
        )
    milestone_uuid = coerce_uuid(milestone_id)
    services = _get_services(db, org_id)

    try:
        services["milestone"].achieve_milestone(milestone_uuid)
    except NotFoundError:
        pass

    return RedirectResponse(
        url=f"/projects/{project.project_code}/milestones?saved=1",
        status_code=303,
    )


def delete_milestone(
    request: Request,
    project_id: str,
    milestone_id: str,
    auth: WebAuthContext = Depends(require_projects_access),
    db: Session = Depends(get_db),
):
    """Delete a milestone."""
    org_id = coerce_uuid(auth.organization_id)
    project = _resolve_project_ref(db, org_id, project_id)
    if not project:
        return RedirectResponse(
            url="/projects?success=Record+deleted+successfully", status_code=303
        )
    milestone_uuid = coerce_uuid(milestone_id)
    services = _get_services(db, org_id)

    try:
        services["milestone"].delete_milestone(milestone_uuid)
    except NotFoundError:
        pass

    return RedirectResponse(
        url=f"/projects/{project.project_code}/milestones?saved=1",
        status_code=303,
    )


__all__ = [
    "project_gantt",
    "project_team",
    "create_resource_allocation",
    "update_resource_allocation",
    "end_resource_allocation",
    "delete_resource_allocation",
    "resource_utilization_report",
    "project_milestones",
    "create_milestone",
    "update_milestone",
    "achieve_milestone",
    "delete_milestone",
]
