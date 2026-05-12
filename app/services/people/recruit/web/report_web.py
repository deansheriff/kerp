"""
Recruit Web Service - Report methods.

Provides view-focused data and operations for recruitment report web routes.
"""

from __future__ import annotations

import csv
import re
from datetime import datetime
from io import StringIO
from uuid import UUID

from fastapi import Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.models.people.recruit import ApplicantStatus
from app.services.common import PaginationParams, coerce_uuid
from app.services.common_filters import build_active_filters
from app.services.forms import FormEngineService
from app.services.people.recruit import RecruitmentService
from app.templates import templates
from app.web.deps import WebAuthContext, base_context

from .base import parse_date_only, parse_status, parse_uuid


class ReportWebService:
    """Web service methods for recruitment reports."""

    JOB_APPLICANT_EXPORT_FIELDS = {
        "application_number": "Application #",
        "applicant_name": "Applicant Name",
        "email": "Email",
        "phone": "Phone",
        "applied_on": "Applied Date",
        "status": "Status",
        "source": "Source",
    }

    # ─────────────────────────────────────────────────────────────────────────
    # Context Builders
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def pipeline_report_context(
        db: Session,
        organization_id: UUID,
        job_opening_id: str | None = None,
    ) -> dict:
        """Build context for pipeline report page."""
        svc = RecruitmentService(db)

        report = svc.get_recruitment_pipeline_report(
            organization_id,
            job_opening_id=parse_uuid(job_opening_id),
        )

        active_filters = build_active_filters(
            params={"job_opening_id": job_opening_id},
        )
        return {
            "report": report,
            "job_opening_id": job_opening_id,
            "active_filters": active_filters,
        }

    @staticmethod
    def time_to_hire_report_context(
        db: Session,
        organization_id: UUID,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        """Build context for time to hire report page."""
        svc = RecruitmentService(db)

        report = svc.get_time_to_hire_report(
            organization_id,
            start_date=parse_date_only(start_date),
            end_date=parse_date_only(end_date),
        )

        return {
            "report": report,
            "start_date": start_date or "",
            "end_date": end_date or "",
        }

    @staticmethod
    def source_analysis_report_context(
        db: Session,
        organization_id: UUID,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        """Build context for source analysis report page."""
        svc = RecruitmentService(db)

        report = svc.get_source_analysis_report(
            organization_id,
            start_date=parse_date_only(start_date),
            end_date=parse_date_only(end_date),
        )

        return {
            "report": report,
            "start_date": start_date or "",
            "end_date": end_date or "",
        }

    @staticmethod
    def overview_report_context(
        db: Session,
        organization_id: UUID,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        """Build context for recruitment overview report page."""
        svc = RecruitmentService(db)

        report = svc.get_recruitment_overview_report(
            organization_id,
            start_date=parse_date_only(start_date),
            end_date=parse_date_only(end_date),
        )

        return {
            "report": report,
            "start_date": start_date or "",
            "end_date": end_date or "",
        }

    @staticmethod
    def job_applicant_report_context(
        db: Session,
        organization_id: UUID,
        job_opening_id: str,
        request: Request,
        page: int = 1,
    ) -> dict:
        """Build context for a job-scoped applicant report."""
        svc = RecruitmentService(db)
        opening = svc.get_job_opening(organization_id, coerce_uuid(job_opening_id))
        export_fields = svc.list_job_applicant_form_fields(
            organization_id, opening.job_opening_id
        )
        report_fields = svc.list_job_applicant_report_fields(
            organization_id, opening.job_opening_id
        )
        field_by_key = {field.field_key: field for field in report_fields}

        params = request.query_params
        status = params.get("status") or None
        search = params.get("search") or None
        source = params.get("source") or None
        sort_by = params.get("sort") or "applied_on"
        sort_dir = params.get("direction") or "desc"

        allowed_sorts = {
            "application_number",
            "applicant",
            "applied_on",
            "source",
            "status",
        }
        dynamic_sort_key = sort_by.removeprefix("field:") if sort_by else ""
        if sort_by not in allowed_sorts and dynamic_sort_key not in field_by_key:
            sort_by = "applied_on"
        if sort_dir not in {"asc", "desc"}:
            sort_dir = "desc"

        dynamic_filters: list[dict] = []
        pagination_filters = {
            "status": status or "",
            "source": source or "",
            "sort": sort_by,
            "direction": sort_dir,
        }
        active_params = {
            "search": search,
            "status": status,
            "source": source,
        }
        active_labels = {
            "search": "Search",
            "status": "Status",
            "source": "Source",
        }
        for field in report_fields:
            if not field.is_filterable:
                continue
            param_name = f"df_{field.field_key}"
            value = params.get(param_name) or ""
            operator = params.get(f"op_{field.field_key}") or "contains"
            if value or operator in {"has_value", "is_empty"}:
                dynamic_filters.append(
                    {
                        "field_key": field.field_key,
                        "field_type": field.field_type,
                        "operator": operator,
                        "value": value,
                    }
                )
                active_params[param_name] = value or operator
                active_labels[param_name] = field.label
                pagination_filters[param_name] = value
                pagination_filters[f"op_{field.field_key}"] = operator

        pagination = PaginationParams.from_page(page, per_page=20)
        result = svc.list_job_applicant_report(
            organization_id,
            opening.job_opening_id,
            status=parse_status(status, ApplicantStatus),
            search=search,
            source=source,
            dynamic_filters=dynamic_filters,
            sort_by=sort_by,
            sort_dir=sort_dir,
            pagination=pagination,
        )
        dynamic_columns, dynamic_values = FormEngineService(db).list_column_answers(
            organization_id, [applicant.applicant_id for applicant in result.items]
        )
        configured_columns = [field for field in report_fields if field.show_in_list][
            :8
        ]

        return {
            "opening": opening,
            "applicants": result.items,
            "dynamic_columns": configured_columns or dynamic_columns,
            "dynamic_values": dynamic_values,
            "filterable_fields": [
                field for field in report_fields if field.is_filterable
            ],
            "export_system_fields": ReportWebService.JOB_APPLICANT_EXPORT_FIELDS,
            "export_fields": export_fields,
            "pipeline": svc.get_pipeline_summary(
                organization_id, job_opening_id=opening.job_opening_id
            ),
            "search": search or "",
            "status": status or "",
            "source": source or "",
            "statuses": [item.value for item in ApplicantStatus],
            "sort": sort_by,
            "direction": sort_dir,
            "page": result.page,
            "total_pages": result.total_pages,
            "total_count": result.total,
            "total": result.total,
            "limit": result.limit,
            "has_prev": result.has_prev,
            "has_next": result.has_next,
            "active_filters": build_active_filters(
                params=active_params, labels=active_labels
            ),
            "pagination_filters": pagination_filters,
            "request_params": params,
        }

    def export_job_applicant_report_csv_response(
        self,
        request: Request,
        auth: WebAuthContext,
        db: Session,
        job_opening_id: str,
        fields: list[str] | None = None,
    ) -> Response:
        """Export a job-scoped applicant report to CSV."""
        org_id = coerce_uuid(auth.organization_id)
        svc = RecruitmentService(db)
        opening = svc.get_job_opening(org_id, coerce_uuid(job_opening_id))
        form_fields = svc.list_job_applicant_form_fields(org_id, opening.job_opening_id)
        form_field_by_key = {field.field_key: field for field in form_fields}
        report_fields = svc.list_job_applicant_report_fields(
            org_id, opening.job_opening_id
        )
        filterable_field_by_key = {
            field.field_key: field for field in report_fields if field.is_filterable
        }

        params = request.query_params
        status = params.get("status") or None
        search = params.get("search") or None
        source = params.get("source") or None
        sort_by = params.get("sort") or "applied_on"
        sort_dir = params.get("direction") or "desc"
        allowed_sorts = {
            "application_number",
            "applicant",
            "applied_on",
            "source",
            "status",
        }
        dynamic_sort_key = sort_by.removeprefix("field:") if sort_by else ""
        if sort_by not in allowed_sorts and dynamic_sort_key not in form_field_by_key:
            sort_by = "applied_on"
        if sort_dir not in {"asc", "desc"}:
            sort_dir = "desc"

        dynamic_filters: list[dict] = []
        for field_key, field in filterable_field_by_key.items():
            value = params.get(f"df_{field_key}") or ""
            operator = params.get(f"op_{field_key}") or "contains"
            if value or operator in {"has_value", "is_empty"}:
                dynamic_filters.append(
                    {
                        "field_key": field.field_key,
                        "field_type": field.field_type,
                        "operator": operator,
                        "value": value,
                    }
                )

        requested_fields = fields or params.getlist("fields")
        columns = self._job_applicant_export_columns(
            requested_fields=requested_fields,
            form_field_by_key=form_field_by_key,
        )
        result = svc.list_job_applicant_report(
            org_id,
            opening.job_opening_id,
            status=parse_status(status, ApplicantStatus),
            search=search,
            source=source,
            dynamic_filters=dynamic_filters,
            sort_by=sort_by,
            sort_dir=sort_dir,
            pagination=None,
        )
        dynamic_values = FormEngineService(db).list_subject_answer_values(
            org_id,
            "JOB_APPLICANT",
            [applicant.applicant_id for applicant in result.items],
        )

        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow([label for _, label in columns])
        for applicant in result.items:
            writer.writerow(
                [
                    self._csv_safe_cell(
                        self._job_applicant_export_value(
                            applicant, column_key, dynamic_values
                        )
                    )
                    for column_key, _ in columns
                ]
            )

        safe_code = re.sub(r"[^A-Za-z0-9_-]+", "_", opening.job_code or "job")
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"job_applicants_{safe_code}_{timestamp}.csv"
        return Response(
            buffer.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    def _job_applicant_export_columns(
        self,
        *,
        requested_fields: list[str],
        form_field_by_key: dict,
    ) -> list[tuple[str, str]]:
        columns: list[tuple[str, str]] = []
        if not requested_fields:
            requested_fields = [
                "system:application_number",
                "system:applicant_name",
                "system:email",
                "system:applied_on",
                "system:status",
                *[f"field:{field_key}" for field_key in form_field_by_key],
            ]

        seen: set[str] = set()
        for requested in requested_fields:
            if requested in seen:
                continue
            seen.add(requested)
            if requested.startswith("system:"):
                field_key = requested.removeprefix("system:")
                label = self.JOB_APPLICANT_EXPORT_FIELDS.get(field_key)
                if label:
                    columns.append((requested, label))
            elif requested.startswith("field:"):
                field_key = requested.removeprefix("field:")
                field = form_field_by_key.get(field_key)
                if field:
                    columns.append((requested, field.label))

        if columns:
            return columns
        return [
            ("system:application_number", "Application #"),
            ("system:applicant_name", "Applicant Name"),
            ("system:email", "Email"),
        ]

    @staticmethod
    def _job_applicant_export_value(applicant, column_key: str, dynamic_values: dict):
        if column_key.startswith("field:"):
            field_key = column_key.removeprefix("field:")
            return dynamic_values.get(applicant.applicant_id, {}).get(field_key, "")

        field_key = column_key.removeprefix("system:")
        if field_key == "application_number":
            return applicant.application_number
        if field_key == "applicant_name":
            return applicant.full_name
        if field_key == "email":
            return applicant.email
        if field_key == "phone":
            return applicant.phone
        if field_key == "applied_on":
            return applicant.applied_on.isoformat() if applicant.applied_on else ""
        if field_key == "status":
            return applicant.status.value if applicant.status else ""
        if field_key == "source":
            return applicant.source
        return ""

    @staticmethod
    def _csv_safe_cell(value) -> str:
        text = "" if value is None else str(value)
        if text.startswith(("=", "+", "-", "@", "\t", "\r")):
            return f"'{text}"
        return text

    # ─────────────────────────────────────────────────────────────────────────
    # Response Methods
    # ─────────────────────────────────────────────────────────────────────────

    def pipeline_report_response(
        self,
        request: Request,
        auth: WebAuthContext,
        db: Session,
        job_opening_id: str | None = None,
    ) -> HTMLResponse:
        """Render pipeline report page."""
        context = base_context(request, auth, "Pipeline Report", "recruit", db=db)
        context["request"] = request
        context.update(
            self.pipeline_report_context(
                db,
                coerce_uuid(auth.organization_id),
                job_opening_id=job_opening_id,
            )
        )
        return templates.TemplateResponse(
            request, "people/recruit/reports/pipeline.html", context
        )

    def time_to_hire_report_response(
        self,
        request: Request,
        auth: WebAuthContext,
        db: Session,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> HTMLResponse:
        """Render time to hire report page."""
        context = base_context(request, auth, "Time to Hire", "recruit", db=db)
        context["request"] = request
        context.update(
            self.time_to_hire_report_context(
                db,
                coerce_uuid(auth.organization_id),
                start_date=start_date,
                end_date=end_date,
            )
        )
        return templates.TemplateResponse(
            request, "people/recruit/reports/time_to_hire.html", context
        )

    def source_analysis_report_response(
        self,
        request: Request,
        auth: WebAuthContext,
        db: Session,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> HTMLResponse:
        """Render source analysis report page."""
        context = base_context(request, auth, "Source Analysis", "recruit", db=db)
        context["request"] = request
        context.update(
            self.source_analysis_report_context(
                db,
                coerce_uuid(auth.organization_id),
                start_date=start_date,
                end_date=end_date,
            )
        )
        return templates.TemplateResponse(
            request, "people/recruit/reports/sources.html", context
        )

    def overview_report_response(
        self,
        request: Request,
        auth: WebAuthContext,
        db: Session,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> HTMLResponse:
        """Render recruitment overview report page."""
        context = base_context(request, auth, "Recruitment Overview", "recruit", db=db)
        context["request"] = request
        context.update(
            self.overview_report_context(
                db,
                coerce_uuid(auth.organization_id),
                start_date=start_date,
                end_date=end_date,
            )
        )
        return templates.TemplateResponse(
            request, "people/recruit/reports/overview.html", context
        )

    def job_applicant_report_response(
        self,
        request: Request,
        auth: WebAuthContext,
        db: Session,
        job_opening_id: str,
        page: int = 1,
    ) -> HTMLResponse:
        """Render a job-scoped applicant report page."""
        context = base_context(request, auth, "Job Applicant Report", "recruit", db=db)
        context["request"] = request
        context.update(
            self.job_applicant_report_context(
                db,
                coerce_uuid(auth.organization_id),
                job_opening_id,
                request,
                page=page,
            )
        )
        return templates.TemplateResponse(
            request, "people/recruit/reports/job_applicants.html", context
        )
