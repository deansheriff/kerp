"""AI workflow endpoints. Global CSRF middleware protects every POST."""

from uuid import UUID

from fastapi import APIRouter, Depends, Form, Query, Request
from sqlalchemy.orm import Session

from app.services.coach.ai_web import ai_web_service
from app.web.deps import WebAuthContext, get_db_for_org, require_web_auth

router = APIRouter(prefix="/ai", tags=["ai-web"])


@router.get("")
def assistant(
    request: Request,
    workflow: str = "knowledge",
    record_id: UUID | None = None,
    brief: str = Query("", max_length=8000),
    auth: WebAuthContext = Depends(require_web_auth),
    db: Session = Depends(get_db_for_org),
):
    return ai_web_service.page(
        request, auth, db, workflow=workflow, record_id=record_id, brief=brief
    )


@router.post("")
def generate(
    request: Request,
    workflow: str = Form(...),
    brief: str = Form("", max_length=8000),
    record_id: UUID | None = Form(None),
    auth: WebAuthContext = Depends(require_web_auth),
    db: Session = Depends(get_db_for_org),
):
    return ai_web_service.page(
        request,
        auth,
        db,
        workflow=workflow,
        record_id=record_id,
        brief=brief,
        generate=True,
    )


@router.get("/knowledge/{document_id}")
def knowledge_source(
    request: Request,
    document_id: UUID,
    auth: WebAuthContext = Depends(require_web_auth),
    db: Session = Depends(get_db_for_org),
):
    return ai_web_service.source(request, auth, db, document_id)
