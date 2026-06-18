"""Collaboration module web routes.

Full-page views, JSON API endpoints, HTMX panel partials, and WebSocket.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.services.collaboration.conversation_service import ConversationService
from app.services.collaboration.message_service import MessageService
from app.services.collaboration.web.collab_web import collab_web_service
from app.services.collaboration.websocket_manager import ws_manager
from app.services.common import coerce_uuid
from app.web.deps import WebAuthContext, base_context, get_db_for_org, require_web_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collaboration", tags=["collaboration-web"])


# ---------------------------------------------------------------------------
# Full-page views
# ---------------------------------------------------------------------------


@router.get("", response_class=HTMLResponse)
def collaboration_inbox(
    request: Request,
    auth: WebAuthContext = Depends(require_web_auth),
    db: Session = Depends(get_db_for_org),
):
    """Collaboration inbox page."""
    return collab_web_service.inbox_page(request, auth, db)


@router.get("/c/{conversation_id}", response_class=HTMLResponse)
def collaboration_conversation(
    request: Request,
    conversation_id: str,
    auth: WebAuthContext = Depends(require_web_auth),
    db: Session = Depends(get_db_for_org),
):
    """Conversation detail page."""
    return collab_web_service.conversation_page(request, conversation_id, auth, db)


@router.get("/new-group", response_class=HTMLResponse)
def collaboration_new_group(
    request: Request,
    auth: WebAuthContext = Depends(require_web_auth),
    db: Session = Depends(get_db_for_org),
):
    """New group creation form."""
    return collab_web_service.new_group_form(request, auth, db)


@router.get("/search", response_class=HTMLResponse)
def collaboration_search(
    request: Request,
    q: str = Query(""),
    auth: WebAuthContext = Depends(require_web_auth),
    db: Session = Depends(get_db_for_org),
):
    """Message search page."""
    return collab_web_service.search_page(request, auth, db, query=q)


# ---------------------------------------------------------------------------
# Panel HTMX partials (loaded into the slide-over)
# ---------------------------------------------------------------------------


@router.get("/panel/inbox", response_class=HTMLResponse)
@router.get("/panel/conversations", response_class=HTMLResponse)
def panel_conversations(
    request: Request,
    auth: WebAuthContext = Depends(require_web_auth),
    db: Session = Depends(get_db_for_org),
):
    """HTMX partial: conversation list for the slide-over panel."""
    return collab_web_service.panel_inbox(request, auth, db)


@router.get("/panel/conversation/{conversation_id}", response_class=HTMLResponse)
def panel_messages(
    request: Request,
    conversation_id: str,
    auth: WebAuthContext = Depends(require_web_auth),
    db: Session = Depends(get_db_for_org),
):
    """HTMX partial: messages pane for the slide-over panel."""
    return collab_web_service.panel_conversation(request, conversation_id, auth, db)


# ---------------------------------------------------------------------------
# JSON API endpoints
# ---------------------------------------------------------------------------


@router.post("/api/conversations/direct", response_class=JSONResponse)
def api_create_direct(
    request: Request,
    person_id: str = Form(...),
    auth: WebAuthContext = Depends(require_web_auth),
    db: Session = Depends(get_db_for_org),
):
    """Create or fetch an existing DM conversation."""
    try:
        org_id = coerce_uuid(auth.organization_id)
        conv = ConversationService.create_direct(
            db, org_id, coerce_uuid(auth.person_id), coerce_uuid(person_id)
        )
        db.commit()
        return JSONResponse(
            {"conversation_id": str(conv.conversation_id), "name": conv.name or "DM"}
        )
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to create DM")
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.post("/groups", response_class=RedirectResponse)
def create_group(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    member_ids: str = Form(""),
    auth: WebAuthContext = Depends(require_web_auth),
    db: Session = Depends(get_db_for_org),
):
    """Create a group conversation."""
    try:
        org_id = coerce_uuid(auth.organization_id)
        ids = [coerce_uuid(mid.strip()) for mid in member_ids.split(",") if mid.strip()]
        conv = ConversationService.create_group(
            db, org_id, name, description, coerce_uuid(auth.person_id), ids
        )
        db.commit()
        return RedirectResponse(
            url=f"/collaboration/c/{conv.conversation_id}", status_code=303
        )
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to create group")
        return RedirectResponse(url="/collaboration?error=creation_failed", status_code=303)


@router.post(
    "/api/conversations/{conversation_id}/messages", response_class=JSONResponse
)
async def api_send_message(
    request: Request,
    conversation_id: str,
    content: str = Form(""),
    quoted_message_id: str = Form(None),
    files: list[UploadFile] = File(default=[]),
    auth: WebAuthContext = Depends(require_web_auth),
    db: Session = Depends(get_db_for_org),
):
    """Send a message to a conversation."""
    try:
        org_id = coerce_uuid(auth.organization_id)
        person_id = coerce_uuid(auth.person_id)
        conv_id = coerce_uuid(conversation_id)
        quoted = coerce_uuid(quoted_message_id) if quoted_message_id else None

        msg = MessageService.send_message(
            db,
            org_id,
            conv_id,
            person_id,
            content=content or None,
            quoted_message_id=quoted,
        )

        # Handle file attachments
        if files and files[0].filename:
            from app.services.collaboration.attachment_service import (
                CollabAttachmentService,
            )

            await CollabAttachmentService.save_attachments(
                db, org_id, conv_id, msg.message_id, files
            )

        db.commit()

        # Broadcast via WebSocket
        try:
            from app.models.collaboration.participant import ConversationParticipant

            participant_ids = [
                str(p.person_id)
                for p in db.query(ConversationParticipant)
                .filter(
                    ConversationParticipant.conversation_id == conv_id,
                    ConversationParticipant.left_at.is_(None),
                )
                .all()
            ]
            await ws_manager.broadcast_to_participants(
                participant_ids,
                {
                    "type": "new_message",
                    "conversation_id": str(conv_id),
                    "message_id": str(msg.message_id),
                    "sender_id": str(person_id),
                    "content": content[:100] if content else "",
                },
            )
        except Exception:
            pass  # Non-critical

        return JSONResponse({"message_id": str(msg.message_id)})
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to send message")
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.post("/api/messages/{message_id}/react", response_class=JSONResponse)
def api_toggle_reaction(
    request: Request,
    message_id: str,
    auth: WebAuthContext = Depends(require_web_auth),
    db: Session = Depends(get_db_for_org),
):
    """Toggle emoji reaction on a message."""
    try:
        import json

        body = {}
        # Try to parse JSON body
        try:
            body = json.loads(request._body.decode() if hasattr(request, "_body") else "{}")
        except Exception:
            pass
        emoji = body.get("emoji", "👍")
        org_id = coerce_uuid(auth.organization_id)
        MessageService.toggle_reaction(
            db, org_id, coerce_uuid(message_id), coerce_uuid(auth.person_id), emoji
        )
        db.commit()
        return JSONResponse({"ok": True})
    except Exception as exc:
        db.rollback()
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.post("/api/messages/{message_id}/pin", response_class=JSONResponse)
def api_pin_message(
    request: Request,
    message_id: str,
    auth: WebAuthContext = Depends(require_web_auth),
    db: Session = Depends(get_db_for_org),
):
    """Toggle pin on a message."""
    try:
        org_id = coerce_uuid(auth.organization_id)
        MessageService.pin_message(
            db, org_id, coerce_uuid(message_id), coerce_uuid(auth.person_id)
        )
        db.commit()
        return JSONResponse({"ok": True})
    except Exception as exc:
        db.rollback()
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.delete("/api/messages/{message_id}", response_class=JSONResponse)
def api_delete_message(
    request: Request,
    message_id: str,
    auth: WebAuthContext = Depends(require_web_auth),
    db: Session = Depends(get_db_for_org),
):
    """Soft-delete a message."""
    try:
        org_id = coerce_uuid(auth.organization_id)
        MessageService.delete_message(
            db, org_id, coerce_uuid(message_id), coerce_uuid(auth.person_id)
        )
        db.commit()
        return JSONResponse({"ok": True})
    except Exception as exc:
        db.rollback()
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.get("/api/employees", response_class=JSONResponse)
def api_search_employees(
    request: Request,
    q: str = Query(""),
    auth: WebAuthContext = Depends(require_web_auth),
    db: Session = Depends(get_db_for_org),
):
    """Search employees for member picker."""
    from app.models.person import Person

    org_id = coerce_uuid(auth.organization_id)
    query = (
        db.query(Person)
        .filter(Person.organization_id == org_id)
    )
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Person.first_name.ilike(like))
            | (Person.last_name.ilike(like))
            | (Person.email.ilike(like))
        )
    people = query.limit(20).all()
    return JSONResponse(
        {
            "employees": [
                {
                    "person_id": str(p.id),
                    "name": f"{p.first_name} {p.last_name}",
                    "email": p.email,
                }
                for p in people
            ]
        }
    )


@router.get("/api/unread-count", response_class=JSONResponse)
def api_unread_count(
    request: Request,
    auth: WebAuthContext = Depends(require_web_auth),
    db: Session = Depends(get_db_for_org),
):
    """Return total unread collaboration messages for the current person."""
    org_id = coerce_uuid(auth.organization_id)
    person_id = coerce_uuid(auth.person_id)
    unread = ConversationService.get_total_unread(db, org_id, person_id)
    return JSONResponse({"unread": unread})


# ---------------------------------------------------------------------------
# WebSocket for real-time updates
# ---------------------------------------------------------------------------


@router.websocket("/ws")
async def collab_websocket(websocket: WebSocket, token: str = Query("")):
    """WebSocket endpoint for real-time collaboration updates."""
    if not token:
        await websocket.close(code=4001)
        return

    # Validate the session token
    try:
        from app.db import SessionLocal
        from app.services.auth_flow import decode_access_token

        ws_db = SessionLocal()
        try:
            payload = decode_access_token(ws_db, token)
        finally:
            ws_db.close()
        person_id = payload.get("person_id") or payload.get("sub")
        if not person_id:
            await websocket.close(code=4001)
            return
    except Exception:
        await websocket.close(code=4001)
        return

    person_id_str = str(person_id)
    await ws_manager.connect(person_id_str, websocket)
    try:
        while True:
            # Keep connection alive, receive pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(person_id_str, websocket)
    except Exception:
        ws_manager.disconnect(person_id_str, websocket)
