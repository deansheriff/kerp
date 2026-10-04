"""HTTP, CSRF and template regression coverage for the AI workspace."""

import os
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.coach.ai_workflows import EvidenceDraft, HiringDraft, TicketDraft
from app.web.ai import router
from app.web.csrf import csrf_middleware
from app.web.deps import WebAuthContext, get_db_for_org, require_web_auth


def preview_context(request, auth, *args, **kwargs):
    request.state.csrf_form = (
        f'<input type="hidden" name="csrf_token" value="{request.state.csrf_token}">'
    )
    return dict(
        request=request,
        auth=auth,
        user=auth.user,
        title="AI Assistant",
        page_title="AI Assistant",
        brand={"name": "Sherpackage", "short_name": "SHP"},
        org_branding={},
        accessible_modules=[],
        organization=None,
        app_version="test",
        saved=False,
    )


@pytest.fixture
def client():
    app = FastAPI()
    app.middleware("http")(csrf_middleware)
    app.include_router(router)
    auth = WebAuthContext(
        is_authenticated=True,
        person_id=uuid4(),
        organization_id=uuid4(),
        roles=["admin"],
    )
    db = MagicMock()
    db.info = {"organization_id": auth.organization_id}
    db.scalars.return_value.all.return_value = []
    app.dependency_overrides[require_web_auth] = lambda: auth
    app.dependency_overrides[get_db_for_org] = lambda: db
    with (
        patch("app.services.coach.ai_web.base_context", side_effect=preview_context),
        TestClient(app) as test_client,
    ):
        test_client.cookies.set("access_token", "test-auth")
        yield test_client


def test_get_renders_real_template_with_server_csrf(client):
    response = client.get("/ai?workflow=knowledge")
    assert response.status_code == 200
    assert 'name="csrf_token"' in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.cookies.get("csrf_token")


@pytest.mark.parametrize(
    "data",
    [
        {"workflow": "knowledge", "brief": "leave"},
        {"workflow": "knowledge", "brief": "leave", "csrf_token": "wrong"},
    ],
)
def test_post_rejects_missing_and_wrong_csrf(client, data):
    client.get("/ai?workflow=knowledge")
    with patch(
        "app.services.coach.ai_workflows.AIWorkflowService.generate"
    ) as generate:
        response = client.post("/ai", data=data)
    assert response.status_code == 400
    assert response.json()["code"] == "csrf_error"
    generate.assert_not_called()


def test_post_accepts_csrf_and_escapes_ai_text(client):
    client.get("/ai?workflow=knowledge")
    result = EvidenceDraft(statements=[], gaps=["<script>alert('unsafe')</script>"])
    with patch(
        "app.services.coach.ai_workflows.AIWorkflowService.generate",
        return_value={
            "kind": "knowledge",
            "result": result,
            "sources": [],
            "model": "gemini/test",
        },
    ) as generate:
        response = client.post(
            "/ai",
            data={
                "workflow": "knowledge",
                "brief": "leave",
                "csrf_token": client.cookies.get("csrf_token"),
            },
        )
    assert response.status_code == 200
    assert "&lt;script&gt;" in response.text
    assert "<script>alert('unsafe')</script>" not in response.text
    generate.assert_called_once()


def test_cross_origin_post_rejected(client):
    client.get("/ai?workflow=knowledge")
    response = client.post(
        "/ai",
        data={"workflow": "knowledge", "csrf_token": client.cookies.get("csrf_token")},
        headers={"Origin": "https://attacker.invalid"},
    )
    assert response.status_code == 400


def test_unknown_workflow_is_forbidden(client):
    assert client.get("/ai?workflow=payroll-export").status_code == 403


def test_optional_empty_record_is_accepted(client):
    client.get("/ai?workflow=knowledge")
    draft = {
        "result": EvidenceDraft(statements=[], gaps=["Missing evidence"]),
        "sources": [],
        "model": None,
    }
    with patch(
        "app.services.coach.ai_workflows.AIWorkflowService.generate", return_value=draft
    ) as generate:
        response = client.post(
            "/ai",
            data={
                "workflow": "knowledge",
                "brief": "leave",
                "record_id": "",
                "csrf_token": client.cookies.get("csrf_token"),
            },
        )
    assert response.status_code == 200
    assert generate.call_args.kwargs["record_id"] is None


@pytest.mark.skipif(
    os.environ.get("AI_BROWSER_QA") != "1", reason="Opt-in Chromium visual QA"
)
@pytest.mark.parametrize("width", [390, 1440])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_browser_draft_forms_and_responsive_layout(client, width, theme):
    from playwright.sync_api import sync_playwright

    root = Path(__file__).resolve().parents[1]
    screenshots = root / ".pytest_cache" / "ai-screenshots"
    screenshots.mkdir(parents=True, exist_ok=True)
    hiring = HiringDraft(
        description="Digital Marketer\nFull-time, Abuja. Build measurable software-product campaigns.",
        requirements=["Campaign analytics experience", "Clear written communication"],
        interview_questions=["How would you validate campaign attribution?"],
        assumptions=["Targets require manager approval."],
        kpis=[
            dict(
                name="Qualified product leads",
                kra="Demand generation",
                target=30,
                unit="leads per quarter",
                weight_percent=100,
                measurement="Deduplicated qualified CRM leads in the review quarter.",
                evidence_required="CRM export and attribution report",
            )
        ],
    )
    evidence = EvidenceDraft(
        statements=[
            dict(
                text="The policy states 20 days of annual leave.",
                source_id="document:test",
                quote="Annual leave is 20 days.",
            )
        ],
        gaps=[],
    )
    ticket = TicketDraft(
        category_code="LOGIN",
        priority="MEDIUM",
        rationale="Access issue requires investigation.",
        suggested_reply="Please share the error message and the time it occurred. Do not send passwords.",
        missing_information=[],
    )

    def serve(route):
        request = route.request
        url = urlsplit(request.url)
        if url.path.startswith("/static/"):
            path = (root / url.path.lstrip("/")).resolve()
            if path.is_relative_to(root / "static") and path.is_file():
                route.fulfill(path=str(path))
            else:
                route.fulfill(status=404, body="")
        elif url.path == "/ai":
            target = url.path + ("?" + url.query if url.query else "")
            response = client.request(
                request.method, target, data=dict(parse_qsl(request.post_data or ""))
            )
            route.fulfill(
                status=response.status_code,
                content_type="text/html",
                body=response.text,
            )
        else:
            route.fulfill(status=200, content_type="application/json", body="{}")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(
            viewport={"width": width, "height": 900}, color_scheme=theme
        )
        page.add_init_script(
            "localStorage.setItem('darkMode', '" + str(theme == "dark").lower() + "')"
        )
        page.route("**/*", serve)
        for workflow in ["hiring", "kpi", "appraisal", "knowledge", "support"]:
            result = (
                hiring
                if workflow in {"hiring", "kpi"}
                else ticket
                if workflow == "support"
                else evidence
            )
            draft = {
                "kind": workflow,
                "result": result,
                "sources": [
                    {
                        "id": "document:test",
                        "title": "Annual leave policy (v1)",
                        "url": "/ai/knowledge/" + str(uuid4()),
                        "coverage": "Title and description only; document text unavailable",
                    }
                ],
                "model": "gemini/test",
            }
            record = (
                f"&record_id={uuid4()}" if workflow in {"support", "appraisal"} else ""
            )
            with patch(
                "app.services.coach.ai_workflows.AIWorkflowService.generate",
                return_value=draft,
            ) as generate:
                page.goto(f"http://ai.test/ai?workflow={workflow}{record}")
                page.locator("#ai-brief").fill(
                    "Draft for the quarterly review, using confirmed facts."
                )
                page.get_by_role("button", name="Generate draft", exact=True).click()
                page.get_by_role(
                    "heading",
                    name="Source-grounded answer"
                    if workflow == "knowledge"
                    else "Draft for human review",
                ).wait_for()
                generate.assert_called_once()
                assert page.locator(".app-page").evaluate(
                    "e => e.scrollWidth <= e.clientWidth + 1"
                )
                if workflow == "support":
                    page.locator("#ai-reply").fill("Reviewed reply")
                    assert page.locator("#ai-reply").input_value() == "Reviewed reply"
                page.screenshot(
                    path=str(screenshots / f"{workflow}-{width}-{theme}.png"),
                    full_page=True,
                )
        browser.close()
