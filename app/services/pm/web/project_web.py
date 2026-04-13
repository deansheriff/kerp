"""Project web service facade.

Implementation lives in ``project_parts`` so route handlers stay thin while
project web behavior remains grouped by functional area.
"""

from __future__ import annotations

from app.services.pm.web.project_parts import (
    MANUAL_PROJECT_CREATION_ENABLED,
    _apply_project_template,
    _build_pm_comment_attachment_map,
    _ensure_task_code,
    _format_project_error,
    _get_employees,
    _get_project_templates,
    _get_projects,
    _get_services,
    _get_tickets,
    _manual_project_creation_disabled_response,
    _normalize_uploads,
    _project_type_duration_days,
    _project_url,
    _resolve_project_ref,
    _resolve_project_template,
    _resolve_task_ref,
    _safe_date,
    _safe_decimal,
    _safe_form_text,
    _task_url,
    _template_tasks_payload,
    projects_index,
    list_projects,
    new_project_form,
    edit_project_form,
    project_dashboard,
    add_project_comment,
    delete_project_comment,
    create_project,
    update_project,
    delete_project,
    project_template_list,
    new_project_template_form,
    create_project_template,
    project_template_detail,
    edit_project_template_form,
    update_project_template,
    global_task_list,
    global_task_new_form,
    create_global_task,
    project_tasks,
    task_detail,
    add_task_comment,
    delete_task_comment,
    download_task_attachment,
    upload_task_attachment,
    delete_task_attachment,
    new_task_form,
    create_task,
    edit_task_form,
    update_task,
    delete_task,
    start_task,
    complete_task,
    add_task_dependency,
    remove_task_dependency,
    bulk_update_task_status,
    bulk_delete_tasks,
    project_gantt,
    project_team,
    create_resource_allocation,
    update_resource_allocation,
    end_resource_allocation,
    delete_resource_allocation,
    resource_utilization_report,
    project_milestones,
    create_milestone,
    update_milestone,
    achieve_milestone,
    delete_milestone,
    project_time_entries,
    new_time_entry_form,
    create_time_entry,
    edit_time_entry_form,
    update_time_entry,
    delete_time_entry,
    bill_time_entry,
    bulk_bill_time_entries,
    employee_timesheet,
    log_timesheet_entry,
    project_expenses,
    project_attachments,
    upload_project_attachment,
    download_project_attachment,
    delete_project_attachment,
    project_import_dashboard,
    project_import_form,
    project_import_preview,
    project_execute_import,
)


class ProjectWebService:
    """Facade for project-management web route behavior."""

    projects_index = staticmethod(projects_index)
    list_projects = staticmethod(list_projects)
    new_project_form = staticmethod(new_project_form)
    edit_project_form = staticmethod(edit_project_form)
    project_template_list = staticmethod(project_template_list)
    new_project_template_form = staticmethod(new_project_template_form)
    create_project_template = staticmethod(create_project_template)
    project_template_detail = staticmethod(project_template_detail)
    edit_project_template_form = staticmethod(edit_project_template_form)
    update_project_template = staticmethod(update_project_template)
    global_task_list = staticmethod(global_task_list)
    global_task_new_form = staticmethod(global_task_new_form)
    create_global_task = staticmethod(create_global_task)
    project_dashboard = staticmethod(project_dashboard)
    add_project_comment = staticmethod(add_project_comment)
    delete_project_comment = staticmethod(delete_project_comment)
    create_project = staticmethod(create_project)
    update_project = staticmethod(update_project)
    delete_project = staticmethod(delete_project)
    project_tasks = staticmethod(project_tasks)
    task_detail = staticmethod(task_detail)
    add_task_comment = staticmethod(add_task_comment)
    delete_task_comment = staticmethod(delete_task_comment)
    download_task_attachment = staticmethod(download_task_attachment)
    upload_task_attachment = staticmethod(upload_task_attachment)
    delete_task_attachment = staticmethod(delete_task_attachment)
    new_task_form = staticmethod(new_task_form)
    create_task = staticmethod(create_task)
    edit_task_form = staticmethod(edit_task_form)
    update_task = staticmethod(update_task)
    delete_task = staticmethod(delete_task)
    start_task = staticmethod(start_task)
    complete_task = staticmethod(complete_task)
    add_task_dependency = staticmethod(add_task_dependency)
    remove_task_dependency = staticmethod(remove_task_dependency)
    bulk_update_task_status = staticmethod(bulk_update_task_status)
    bulk_delete_tasks = staticmethod(bulk_delete_tasks)
    project_gantt = staticmethod(project_gantt)
    project_team = staticmethod(project_team)
    create_resource_allocation = staticmethod(create_resource_allocation)
    update_resource_allocation = staticmethod(update_resource_allocation)
    end_resource_allocation = staticmethod(end_resource_allocation)
    delete_resource_allocation = staticmethod(delete_resource_allocation)
    resource_utilization_report = staticmethod(resource_utilization_report)
    project_milestones = staticmethod(project_milestones)
    create_milestone = staticmethod(create_milestone)
    update_milestone = staticmethod(update_milestone)
    achieve_milestone = staticmethod(achieve_milestone)
    delete_milestone = staticmethod(delete_milestone)
    project_time_entries = staticmethod(project_time_entries)
    new_time_entry_form = staticmethod(new_time_entry_form)
    create_time_entry = staticmethod(create_time_entry)
    edit_time_entry_form = staticmethod(edit_time_entry_form)
    update_time_entry = staticmethod(update_time_entry)
    delete_time_entry = staticmethod(delete_time_entry)
    bill_time_entry = staticmethod(bill_time_entry)
    bulk_bill_time_entries = staticmethod(bulk_bill_time_entries)
    employee_timesheet = staticmethod(employee_timesheet)
    log_timesheet_entry = staticmethod(log_timesheet_entry)
    project_expenses = staticmethod(project_expenses)
    project_attachments = staticmethod(project_attachments)
    upload_project_attachment = staticmethod(upload_project_attachment)
    download_project_attachment = staticmethod(download_project_attachment)
    delete_project_attachment = staticmethod(delete_project_attachment)
    project_import_dashboard = staticmethod(project_import_dashboard)
    project_import_form = staticmethod(project_import_form)
    project_import_preview = staticmethod(project_import_preview)
    project_execute_import = staticmethod(project_execute_import)


project_web_service = ProjectWebService()

__all__ = [
    "ProjectWebService",
    "project_web_service",
    "MANUAL_PROJECT_CREATION_ENABLED",
    "_apply_project_template",
    "_build_pm_comment_attachment_map",
    "_ensure_task_code",
    "_format_project_error",
    "_get_employees",
    "_get_project_templates",
    "_get_projects",
    "_get_services",
    "_get_tickets",
    "_manual_project_creation_disabled_response",
    "_normalize_uploads",
    "_project_type_duration_days",
    "_project_url",
    "_resolve_project_ref",
    "_resolve_project_template",
    "_resolve_task_ref",
    "_safe_date",
    "_safe_decimal",
    "_safe_form_text",
    "_task_url",
    "_template_tasks_payload",
]
