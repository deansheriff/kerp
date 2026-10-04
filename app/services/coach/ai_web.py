"""Web presentation for AI drafts; all generation is read-only."""

from uuid import UUID

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.services.coach.ai_workflows import (
    AIForbidden,
    AINotFound,
    AIWorkflowService,
    WORKFLOWS,
)
from app.services.coach.insight_engine import LLMError
from app.templates import templates
from app.web.deps import WebAuthContext, base_context


class AIWebService:
    def page(
        self,
        request: Request,
        auth: WebAuthContext,
        db: Session,
        *,
        workflow: str = "knowledge",
        record_id: UUID | None = None,
        brief: str = "",
        generate: bool = False,
    ):
        try:
            service = AIWorkflowService(db, auth)
            service._require(workflow)
            context = base_context(request, auth, "AI Assistant", "ai", db=db)
            context.update(
                workflow=workflow,
                record_id=str(record_id) if record_id else "",
                brief=brief,
                workflows={
                    key: item[0]
                    for key, item in WORKFLOWS.items()
                    if service.allowed(key)
                },
                records=service.record_options(workflow),
                draft=None,
                error=None,
            )
            if generate:
                try:
                    context["draft"] = service.generate(
                        workflow, brief=brief, record_id=record_id
                    )
                except (LLMError, ValueError) as exc:
                    if isinstance(exc, (AIForbidden, AINotFound)):
                        raise
                    context["error"] = (
                        str(exc)
                        if isinstance(exc, LLMError)
                        else "Invalid request. Check the role brief and record reference."
                    )
            response = templates.TemplateResponse(
                request, "coach/assistant.html", context
            )
            response.headers["Cache-Control"] = "no-store"
            return response
        except AIForbidden as exc:
            raise HTTPException(403, str(exc)) from exc
        except AINotFound as exc:
            raise HTTPException(404, str(exc)) from exc

    def source(
        self, request: Request, auth: WebAuthContext, db: Session, document_id: UUID
    ):
        try:
            source = AIWorkflowService(db, auth).document_source(document_id)
        except AIForbidden as exc:
            raise HTTPException(403, str(exc)) from exc
        except AINotFound as exc:
            raise HTTPException(404, str(exc)) from exc
        context = base_context(request, auth, "Knowledge Source", "ai", db=db)
        context["source"] = source
        return templates.TemplateResponse(
            request,
            "coach/knowledge_source.html",
            context,
            headers={"Cache-Control": "no-store"},
        )


ai_web_service = AIWebService()
