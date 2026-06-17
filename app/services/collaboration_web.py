"""Template response helpers for employee collaboration."""

from __future__ import annotations

import logging
from urllib.parse import quote

from fastapi import Request, UploadFile
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.services.collaboration import CollaborationService
from app.services.common import coerce_uuid
from app.services.storage import get_storage
from app.templates import templates
from app.web.deps import WebAuthContext, base_context

logger = logging.getLogger(__name__)


class CollaborationWebService:
    """Build responses for collaboration routes."""

    def inbox_response(
        self,
        request: Request,
        auth: WebAuthContext,
        db: Session,
        *,
        conversation_id: str | None = None,
        search: str | None = None,
        people_search: str | None = None,
    ):
        """Render the collaboration inbox."""
        service = CollaborationService(db)
        org_id = coerce_uuid(auth.organization_id)
        person_id = coerce_uuid(auth.person_id)
        conversations = service.list_conversations(
            org_id,
            person_id,
            search=search,
        )
        selected_id = conversation_id or (
            conversations[0].conversation_id if conversations else None
        )
        selected = (
            service.get_conversation_for_member(org_id, selected_id, person_id)
            if selected_id
            else None
        )
        messages = (
            service.list_messages(org_id, selected.conversation_id, person_id)
            if selected
            else []
        )
        if selected:
            service.mark_read(org_id, selected.conversation_id, person_id)
        people = service.list_people(
            org_id,
            current_person_id=person_id,
            search=people_search,
            limit=60,
        )
        context = base_context(
            request,
            auth,
            "Collaboration",
            "collaboration",
            db=db,
        )
        context.update(
            {
                "conversations": conversations,
                "selected_conversation": selected,
                "selected_conversation_id": str(selected.conversation_id)
                if selected
                else "",
                "messages": messages,
                "people": people,
                "search": search or "",
                "people_search": people_search or "",
            }
        )
        return templates.TemplateResponse(request, "collaboration/index.html", context)

    def create_direct_response(
        self,
        request: Request,
        auth: WebAuthContext,
        db: Session,
        *,
        other_person_id: str,
    ) -> RedirectResponse:
        """Create or open a direct conversation."""
        service = CollaborationService(db)
        try:
            conversation = service.create_direct_conversation(
                coerce_uuid(auth.organization_id),
                coerce_uuid(auth.person_id),
                other_person_id,
            )
            return RedirectResponse(
                url=f"/collaboration?conversation_id={conversation.conversation_id}",
                status_code=303,
            )
        except Exception as exc:
            db.rollback()
            logger.exception("Failed to create direct conversation")
            return self._error_redirect(str(exc))

    def create_group_response(
        self,
        request: Request,
        auth: WebAuthContext,
        db: Session,
        *,
        title: str,
        participant_ids: list[str],
        description: str | None = None,
    ) -> RedirectResponse:
        """Create a group conversation."""
        service = CollaborationService(db)
        try:
            conversation = service.create_group_conversation(
                coerce_uuid(auth.organization_id),
                coerce_uuid(auth.person_id),
                title=title,
                participant_ids=participant_ids,
                description=description,
            )
            return RedirectResponse(
                url=f"/collaboration?conversation_id={conversation.conversation_id}",
                status_code=303,
            )
        except Exception as exc:
            db.rollback()
            logger.exception("Failed to create group conversation")
            return self._error_redirect(str(exc))

    async def add_message_response(
        self,
        request: Request,
        auth: WebAuthContext,
        db: Session,
        *,
        conversation_id: str,
        body: str,
        files: list[UploadFile] | None = None,
    ) -> RedirectResponse:
        """Post a message to a conversation."""
        service = CollaborationService(db)
        try:
            await service.add_message(
                coerce_uuid(auth.organization_id),
                conversation_id,
                coerce_uuid(auth.person_id),
                body=body,
                files=files,
            )
            return RedirectResponse(
                url=f"/collaboration?conversation_id={conversation_id}",
                status_code=303,
            )
        except Exception as exc:
            db.rollback()
            logger.exception("Failed to add collaboration message")
            return self._error_redirect(str(exc), conversation_id=conversation_id)

    def download_attachment_response(
        self,
        request: Request,
        auth: WebAuthContext,
        db: Session,
        *,
        attachment_id: str,
    ) -> StreamingResponse | RedirectResponse:
        """Download a chat attachment if the user can see it."""
        service = CollaborationService(db)
        attachment = service.get_attachment_for_member(
            coerce_uuid(auth.organization_id),
            attachment_id,
            coerce_uuid(auth.person_id),
        )
        if not attachment:
            return self._error_redirect("Attachment not found.")

        storage = get_storage()
        s3_key = attachment.storage_path
        if not s3_key.startswith("collaboration/"):
            s3_key = f"collaboration/{s3_key}"
        if not storage.exists(s3_key):
            return self._error_redirect("File not found.")

        chunks, content_type, content_length = storage.stream(s3_key)
        headers = {
            "Content-Disposition": f'attachment; filename="{attachment.filename}"',
        }
        if content_length is not None:
            headers["Content-Length"] = str(content_length)
        return StreamingResponse(
            chunks,
            media_type=content_type or attachment.content_type,
            headers=headers,
        )

    def _error_redirect(
        self,
        message: str,
        *,
        conversation_id: str | None = None,
    ) -> RedirectResponse:
        url = f"/collaboration?error={quote(message)}"
        if conversation_id:
            url = (
                f"/collaboration?conversation_id={conversation_id}"
                f"&error={quote(message)}"
            )
        return RedirectResponse(url=url, status_code=303)


collaboration_web_service = CollaborationWebService()
