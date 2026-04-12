"""Project web templates handlers."""

from app.services.pm.web.project_parts.base import (
    Depends,
    Query,
    RedirectResponse,
    Request,
    Session,
    WebAuthContext,
    _resolve_project_template,
    _safe_form_text,
    _template_tasks_payload,
    base_context,
    coerce_uuid,
    get_db,
    require_projects_access,
    templates,
)


def project_template_list(
    request: Request,
    page: int = Query(1, ge=1),
    auth: WebAuthContext = Depends(require_projects_access),
    db: Session = Depends(get_db),
):
    """Project template list page."""
    from sqlalchemy import func, select

    from app.models.pm.project_template import ProjectTemplate

    org_id = coerce_uuid(auth.organization_id)
    per_page = 50
    total_count = (
        db.scalar(
            select(func.count())
            .select_from(ProjectTemplate)
            .where(ProjectTemplate.organization_id == org_id)
        )
        or 0
    )
    total_pages = max(1, (total_count + per_page - 1) // per_page)

    stmt = (
        select(ProjectTemplate)
        .where(ProjectTemplate.organization_id == org_id)
        .order_by(ProjectTemplate.name)
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    templates_list = list(db.scalars(stmt).all())

    context = {
        "request": request,
        **base_context(request, auth, "Project Templates", "templates", db=db),
        "templates": templates_list,
        "page": page,
        "total_pages": total_pages,
        "total_count": total_count,
        "limit": per_page,
    }
    return templates.TemplateResponse(request, "projects/templates/list.html", context)


def new_project_template_form(
    request: Request,
    auth: WebAuthContext = Depends(require_projects_access),
    db: Session = Depends(get_db),
):
    """New project template form page."""
    from app.models.finance.core_org.project import ProjectType

    context = {
        "request": request,
        **base_context(request, auth, "New Project Template", "templates", db=db),
        "template": None,
        "project_types": [t.value for t in ProjectType],
        "tasks_payload_json": "[]",
    }
    return templates.TemplateResponse(request, "projects/templates/form.html", context)


async def create_project_template(
    request: Request,
    auth: WebAuthContext = Depends(require_projects_access),
    db: Session = Depends(get_db),
):
    """Create a new project template with ordered tasks."""
    import json
    import logging

    from app.models.finance.core_org.project import ProjectType
    from app.models.pm.project_template import ProjectTemplate
    from app.models.pm.project_template_task import (
        ProjectTemplateTask,
        ProjectTemplateTaskDependency,
    )
    from app.models.pm.task_dependency import DependencyType

    org_id = coerce_uuid(auth.organization_id)
    form = getattr(request.state, "csrf_form", None)
    if form is None:
        form = await request.form()

    logging.getLogger(__name__).warning(
        "Project template POST form keys: %s",
        list(form.keys()),
    )

    template_name_value = _safe_form_text(
        form.get("template_name") or form.get("name")
    ).strip()
    project_type = _safe_form_text(form.get("project_type") or "INTERNAL").strip()
    tasks_json = _safe_form_text(form.get("tasks_json")) or "[]"
    if not template_name_value:
        context = {
            "request": request,
            **base_context(request, auth, "New Project Template", "templates", db=db),
            "template": None,
            "project_types": [t.value for t in ProjectType],
            "error": "Template name is required.",
            "submitted_name": template_name_value,
        }
        return templates.TemplateResponse(
            "projects/templates/form.html",
            context,
            status_code=400,
        )
    template = ProjectTemplate(
        organization_id=org_id,
        name=template_name_value,
        project_type=ProjectType(project_type)
        if project_type
        else ProjectType.INTERNAL,
    )
    db.add(template)
    db.flush()

    try:
        task_payload = json.loads(tasks_json or "[]")
    except json.JSONDecodeError:
        task_payload = []

    task_map = {}
    order_index = 1
    for task_entry in task_payload:
        task_name = (task_entry.get("task_name") or "").strip()
        if not task_name:
            continue
        task = ProjectTemplateTask(
            template_id=template.template_id,
            task_name=task_name,
            description=(task_entry.get("description") or "").strip() or None,
            order_index=order_index,
        )
        db.add(task)
        db.flush()
        task_map[str(task_entry.get("client_id"))] = task
        order_index += 1

    for task_entry in task_payload:
        client_id = str(task_entry.get("client_id"))
        mapped_task = task_map.get(client_id)
        if not mapped_task:
            continue
        depends_on = task_entry.get("depends_on") or []
        for depends_on_id in depends_on:
            depends_on_task = task_map.get(str(depends_on_id))
            if not depends_on_task:
                continue
            db.add(
                ProjectTemplateTaskDependency(
                    template_task_id=mapped_task.template_task_id,
                    depends_on_template_task_id=depends_on_task.template_task_id,
                    dependency_type=DependencyType.FINISH_TO_START,
                )
            )

    return RedirectResponse(
        url=f"/projects/templates/{template.template_id}?saved=1", status_code=303
    )


def project_template_detail(
    request: Request,
    template_id: str,
    auth: WebAuthContext = Depends(require_projects_access),
    db: Session = Depends(get_db),
):
    """Project template detail page."""
    from sqlalchemy import select

    from app.models.pm.project_template_task import (
        ProjectTemplateTask,
        ProjectTemplateTaskDependency,
    )

    org_id = coerce_uuid(auth.organization_id)
    template = _resolve_project_template(db, org_id, template_id)
    if not template:
        return templates.TemplateResponse(
            "errors/404.html",
            {"request": request, "message": "Project template not found"},
            status_code=404,
        )

    tasks = list(
        db.scalars(
            select(ProjectTemplateTask)
            .where(ProjectTemplateTask.template_id == template.template_id)
            .order_by(
                ProjectTemplateTask.order_index, ProjectTemplateTask.template_task_id
            )
        ).all()
    )
    dependencies = list(
        db.scalars(
            select(ProjectTemplateTaskDependency).where(
                ProjectTemplateTaskDependency.template_task_id.in_(
                    [t.template_task_id for t in tasks]
                )
            )
        ).all()
    )

    context = {
        "request": request,
        **base_context(request, auth, template.name, "templates", db=db),
        "template": template,
        "tasks": tasks,
        "dependencies": dependencies,
    }
    return templates.TemplateResponse(
        request, "projects/templates/detail.html", context
    )


def edit_project_template_form(
    request: Request,
    template_id: str,
    auth: WebAuthContext = Depends(require_projects_access),
    db: Session = Depends(get_db),
):
    """Edit project template form page."""
    import json

    from app.models.finance.core_org.project import ProjectType

    org_id = coerce_uuid(auth.organization_id)
    template = _resolve_project_template(db, org_id, template_id)
    if not template:
        return templates.TemplateResponse(
            "errors/404.html",
            {"request": request, "message": "Project template not found"},
            status_code=404,
        )

    tasks_payload = _template_tasks_payload(db, template.template_id)
    context = {
        "request": request,
        **base_context(request, auth, f"Edit {template.name}", "templates", db=db),
        "template": template,
        "project_types": [t.value for t in ProjectType],
        "tasks_payload_json": json.dumps(tasks_payload),
    }
    return templates.TemplateResponse(request, "projects/templates/form.html", context)


async def update_project_template(
    request: Request,
    template_id: str,
    auth: WebAuthContext = Depends(require_projects_access),
    db: Session = Depends(get_db),
):
    """Update a project template and its tasks."""
    import json

    from sqlalchemy import delete, select

    from app.models.finance.core_org.project import ProjectType
    from app.models.pm.project_template_task import (
        ProjectTemplateTask,
        ProjectTemplateTaskDependency,
    )
    from app.models.pm.task_dependency import DependencyType

    org_id = coerce_uuid(auth.organization_id)
    template = _resolve_project_template(db, org_id, template_id)
    if not template:
        return templates.TemplateResponse(
            "errors/404.html",
            {"request": request, "message": "Project template not found"},
            status_code=404,
        )

    form = getattr(request.state, "csrf_form", None)
    if form is None:
        form = await request.form()

    template_name_value = _safe_form_text(
        form.get("template_name") or form.get("name")
    ).strip()
    project_type = _safe_form_text(form.get("project_type") or "INTERNAL").strip()
    tasks_json = _safe_form_text(form.get("tasks_json")) or "[]"

    if not template_name_value:
        context = {
            "request": request,
            **base_context(request, auth, f"Edit {template.name}", "templates", db=db),
            "template": template,
            "project_types": [t.value for t in ProjectType],
            "error": "Template name is required.",
            "submitted_name": template_name_value,
            "tasks_payload_json": tasks_json,
        }
        return templates.TemplateResponse(
            "projects/templates/form.html",
            context,
            status_code=400,
        )

    template.name = template_name_value
    template.project_type = (
        ProjectType(project_type) if project_type else ProjectType.INTERNAL
    )

    try:
        task_payload = json.loads(tasks_json or "[]")
    except json.JSONDecodeError:
        task_payload = []

    existing_tasks = list(
        db.scalars(
            select(ProjectTemplateTask).where(
                ProjectTemplateTask.template_id == template.template_id
            )
        ).all()
    )
    if existing_tasks:
        task_ids = [t.template_task_id for t in existing_tasks]
        db.execute(
            delete(ProjectTemplateTaskDependency).where(
                ProjectTemplateTaskDependency.template_task_id.in_(task_ids)
            )
        )
        db.execute(
            delete(ProjectTemplateTask).where(
                ProjectTemplateTask.template_id == template.template_id
            )
        )

    task_map = {}
    order_index = 1
    for task_entry in task_payload:
        task_name = (task_entry.get("task_name") or "").strip()
        if not task_name:
            continue
        task = ProjectTemplateTask(
            template_id=template.template_id,
            task_name=task_name,
            description=(task_entry.get("description") or "").strip() or None,
            order_index=order_index,
        )
        db.add(task)
        db.flush()
        task_map[str(task_entry.get("client_id"))] = task
        order_index += 1

    for task_entry in task_payload:
        client_id = str(task_entry.get("client_id"))
        mapped_task = task_map.get(client_id)
        if not mapped_task:
            continue
        depends_on = task_entry.get("depends_on") or []
        for depends_on_id in depends_on:
            depends_on_task = task_map.get(str(depends_on_id))
            if not depends_on_task:
                continue
            db.add(
                ProjectTemplateTaskDependency(
                    template_task_id=mapped_task.template_task_id,
                    depends_on_template_task_id=depends_on_task.template_task_id,
                    dependency_type=DependencyType.FINISH_TO_START,
                )
            )

    return RedirectResponse(
        url=f"/projects/templates/{template.template_id}?saved=1", status_code=303
    )


__all__ = [
    "project_template_list",
    "new_project_template_form",
    "create_project_template",
    "project_template_detail",
    "edit_project_template_form",
    "update_project_template",
]
