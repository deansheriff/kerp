"""Employee collaboration web routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.services.collaboration_web import collaboration_web_service
from app.web.deps import WebAuthContext, get_db_for_org, require_web_auth

router = APIRouter(prefix="/collaboration", tags=["collaboration-web"])


@router.get("", response_class=HTMLResponse)
def inbox(
    request: Request,
    conversation_id: str | None = Query(default=None),
    search: str | None = Query(default=None),
    people_search: str | None = Query(default=None),
    auth: WebAuthContext = Depends(require_web_auth),
    db: Session = Depends(get_db_for_org),
):
    """Collaboration inbox."""
    return collaboration_web_service.inbox_response(
        request,
        auth,
        db,
        conversation_id=conversation_id,
        search=search,
        people_search=people_search,
    )


@router.post("/direct", response_class=RedirectResponse)
def create_direct(
    request: Request,
    other_person_id: str = Form(...),
    auth: WebAuthContext = Depends(require_web_auth),
    db: Session = Depends(get_db_for_org),
):
    """Create or open a direct conversation."""
    return collaboration_web_service.create_direct_response(
        request,
        auth,
        db,
        other_person_id=other_person_id,
    )


@router.post("/groups", response_class=RedirectResponse)
def create_group(
    request: Request,
    title: str = Form(...),
    participant_ids: list[str] = Form(default=[]),
    description: str | None = Form(default=None),
    auth: WebAuthContext = Depends(require_web_auth),
    db: Session = Depends(get_db_for_org),
):
    """Create a group conversation."""
    return collaboration_web_service.create_group_response(
        request,
        auth,
        db,
        title=title,
        participant_ids=participant_ids,
        description=description,
    )


@router.post("/{conversation_id}/messages", response_class=RedirectResponse)
async def add_message(
    request: Request,
    conversation_id: str,
    body: str = Form(default=""),
    files: list[UploadFile] = File(default=None),
    auth: WebAuthContext = Depends(require_web_auth),
    db: Session = Depends(get_db_for_org),
):
    """Post a message to a conversation."""
    return await collaboration_web_service.add_message_response(
        request,
        auth,
        db,
        conversation_id=conversation_id,
        body=body,
        files=files,
    )


@router.get("/attachments/{attachment_id}")
def download_attachment(
    request: Request,
    attachment_id: str,
    auth: WebAuthContext = Depends(require_web_auth),
    db: Session = Depends(get_db_for_org),
):
    """Download a collaboration attachment."""
    return collaboration_web_service.download_attachment_response(
        request,
        auth,
        db,
        attachment_id=attachment_id,
    )
