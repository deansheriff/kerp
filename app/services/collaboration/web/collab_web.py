"""
Collaboration web service facade.

Renders full-page views and HTMX partials for the collaboration UI.
"""

import logging
import uuid

from fastapi import Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.collaboration.conversation_service import ConversationService
from app.services.collaboration.message_service import MessageService
from app.services.common import coerce_uuid
from app.templates import templates
from app.web.deps import WebAuthContext, base_context

logger = logging.getLogger(__name__)


def _person_id(auth: WebAuthContext) -> uuid.UUID:
    return coerce_uuid(
        str(auth.person_id) if hasattr(auth, "person_id") else str(auth.user_id)
    )


class CollabWebService:
    """Web facade for collaboration module template rendering."""

    @staticmethod
    def inbox_page(
        request: Request,
        auth: WebAuthContext,
        db: Session,
    ):
        """Full-page inbox view."""
        org_id = coerce_uuid(auth.organization_id)
        person_id = _person_id(auth)

        conversations = ConversationService.list_conversations(
            db, org_id, person_id, page=1,
        )

        ctx = base_context(
            request, auth,
            page_title="Collaboration",
            active_module="collaboration",
            db=db,
        )
        ctx["conversations"] = conversations.get("conversations", [])
        ctx["total_conversations"] = conversations.get("total", 0)

        return templates.TemplateResponse(
            "collaboration/inbox.html", ctx,
        )

    @staticmethod
    def conversation_page(
        request: Request,
        conversation_id: str,
        auth: WebAuthContext,
        db: Session,
    ):
        """Full-page conversation view."""
        org_id = coerce_uuid(auth.organization_id)
        person_id = _person_id(auth)
        conv_id = coerce_uuid(conversation_id)

        conversation = ConversationService.get_conversation(
            db, org_id, conv_id, person_id,
        )
        if not conversation:
            ctx = base_context(
                request, auth,
                page_title="Conversation Not Found",
                active_module="collaboration",
                db=db,
            )
            return templates.TemplateResponse(
                "collaboration/inbox.html",
                {**ctx, "conversations": [], "error": "Conversation not found or access denied."},
                status_code=404,
            )

        messages = MessageService.list_messages(
            db, org_id, conv_id, person_id, limit=50,
        )

        # Mark as read
        msg_list = messages.get("messages", [])
        if msg_list:
            last_msg_id = msg_list[-1]["message_id"]
            MessageService.mark_read(db, org_id, conv_id, person_id, coerce_uuid(last_msg_id))
            db.commit()

        # Get conversation display name for DMs
        from app.models.collaboration.conversation import ConversationType

        display_name = conversation.name
        if conversation.conversation_type == ConversationType.DIRECT:
            for p in (conversation.participants or []):
                if p.person_id != person_id and p.left_at is None:
                    person = p.person
                    if person:
                        first = getattr(person, "first_name", "") or ""
                        last = getattr(person, "last_name", "") or ""
                        display_name = f"{first} {last}".strip() or "Direct Message"
                    break

        # Get all conversations for sidebar
        all_convs = ConversationService.list_conversations(db, org_id, person_id, page=1)

        # Get members for sidebar
        members = []
        for p in (conversation.participants or []):
            if p.left_at is None and p.person:
                person = p.person
                first = getattr(person, "first_name", "") or ""
                last = getattr(person, "last_name", "") or ""
                members.append({
                    "person_id": str(p.person_id),
                    "name": f"{first} {last}".strip() or "Unknown",
                    "role": p.role.value if p.role else "MEMBER",
                    "is_self": p.person_id == person_id,
                })

        ctx = base_context(
            request, auth,
            page_title=display_name or "Conversation",
            active_module="collaboration",
            db=db,
        )
        ctx["conversation"] = conversation
        ctx["conversation_id"] = str(conv_id)
        ctx["conversation_name"] = display_name or "Conversation"
        ctx["conversation_type"] = conversation.conversation_type.value
        ctx["messages"] = msg_list
        ctx["has_more"] = messages.get("has_more", False)
        ctx["members"] = members
        ctx["conversations"] = all_convs.get("conversations", [])
        ctx["current_person_id"] = str(person_id)

        return templates.TemplateResponse(
            "collaboration/conversation.html", ctx,
        )

    @staticmethod
    def new_group_form(
        request: Request,
        auth: WebAuthContext,
        db: Session,
    ):
        """New group chat creation form."""
        ctx = base_context(
            request, auth,
            page_title="New Group Chat",
            active_module="collaboration",
            db=db,
        )
        return templates.TemplateResponse(
            "collaboration/new_group.html", ctx,
        )

    @staticmethod
    def search_page(
        request: Request,
        auth: WebAuthContext,
        db: Session,
        query: str | None = None,
    ):
        """Search messages page."""
        org_id = coerce_uuid(auth.organization_id)
        person_id = _person_id(auth)

        results = {}
        if query and query.strip():
            results = MessageService.search_messages(
                db, org_id, person_id, query.strip(),
            )

        ctx = base_context(
            request, auth,
            page_title="Search Messages",
            active_module="collaboration",
            db=db,
        )
        ctx["query"] = query or ""
        ctx["results"] = results.get("results", [])

        return templates.TemplateResponse(
            "collaboration/search.html", ctx,
        )

    # ------------------------------------------------------------------
    # Panel partials (HTMX fragments for slide-over)
    # ------------------------------------------------------------------

    @staticmethod
    def panel_inbox(
        request: Request,
        auth: WebAuthContext,
        db: Session,
    ):
        """Conversation list partial for panel."""
        org_id = coerce_uuid(auth.organization_id)
        person_id = _person_id(auth)

        conversations = ConversationService.list_conversations(
            db, org_id, person_id, page=1,
        )

        return templates.TemplateResponse(
            "collaboration/partials/_conversation_list.html",
            {
                "request": request,
                "conversations": conversations.get("conversations", []),
                "current_person_id": str(person_id),
            },
        )

    @staticmethod
    def panel_conversation(
        request: Request,
        conversation_id: str,
        auth: WebAuthContext,
        db: Session,
    ):
        """Message pane partial for panel."""
        org_id = coerce_uuid(auth.organization_id)
        person_id = _person_id(auth)
        conv_id = coerce_uuid(conversation_id)

        conversation = ConversationService.get_conversation(
            db, org_id, conv_id, person_id,
        )
        if not conversation:
            return HTMLResponse('<div class="p-4 text-center text-slate-400">Conversation not found.</div>')

        messages = MessageService.list_messages(
            db, org_id, conv_id, person_id, limit=50,
        )

        # Mark as read
        msg_list = messages.get("messages", [])
        if msg_list:
            last_msg_id = msg_list[-1]["message_id"]
            MessageService.mark_read(db, org_id, conv_id, person_id, coerce_uuid(last_msg_id))
            db.commit()

        from app.models.collaboration.conversation import ConversationType

        display_name = conversation.name
        if conversation.conversation_type == ConversationType.DIRECT:
            for p in (conversation.participants or []):
                if p.person_id != person_id and p.left_at is None:
                    person = p.person
                    if person:
                        first = getattr(person, "first_name", "") or ""
                        last = getattr(person, "last_name", "") or ""
                        display_name = f"{first} {last}".strip() or "DM"
                    break

        return templates.TemplateResponse(
            "collaboration/partials/_message_pane.html",
            {
                "request": request,
                "conversation_id": str(conv_id),
                "conversation_name": display_name or "Conversation",
                "conversation_type": conversation.conversation_type.value,
                "messages": msg_list,
                "has_more": messages.get("has_more", False),
                "current_person_id": str(person_id),
            },
        )


collab_web_service = CollabWebService()
