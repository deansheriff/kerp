from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from starlette.requests import Request


def _request(path: str = "/collaboration/direct") -> Request:
    return Request({"type": "http", "method": "POST", "path": path})


def test_direct_message_form_route_accepts_existing_person_field_names(monkeypatch):
    from app.web import collaboration

    org_id = uuid4()
    actor_id = uuid4()
    target_id = uuid4()
    conversation_id = uuid4()
    calls = {}

    def fake_create_direct(db, seen_org_id, seen_actor_id, seen_target_id):
        calls["args"] = (db, seen_org_id, seen_actor_id, seen_target_id)
        return SimpleNamespace(conversation_id=conversation_id)

    monkeypatch.setattr(
        collaboration.ConversationService,
        "create_direct",
        staticmethod(fake_create_direct),
    )
    db = SimpleNamespace(commit=lambda: calls.setdefault("committed", True))
    auth = SimpleNamespace(organization_id=org_id, person_id=actor_id)

    response = collaboration.create_direct(
        request=_request(),
        person_id=None,
        other_person_id=str(target_id),
        target_person_id=None,
        compact=False,
        auth=auth,
        db=db,
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"/collaboration/c/{conversation_id}"
    assert calls["args"] == (db, org_id, actor_id, target_id)
    assert calls["committed"] is True


def test_collaboration_panel_has_direct_message_employee_picker():
    template = (
        Path(__file__).resolve().parents[1]
        / "templates"
        / "partials"
        / "_collab_panel.html"
    ).read_text()

    assert "New DM" in template
    assert "/collaboration/api/employees" in template
    assert "/collaboration/api/conversations/direct" in template
