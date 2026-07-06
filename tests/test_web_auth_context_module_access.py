from pathlib import Path
from uuid import UUID

from app.web.deps import WebAuthContext


def test_hr_manager_has_people_module_access():
    auth = WebAuthContext(
        is_authenticated=True,
        person_id=UUID("00000000-0000-0000-0000-000000000002"),
        organization_id=UUID("00000000-0000-0000-0000-000000000001"),
        roles=["hr_manager"],
        scopes=[],
    )
    assert auth.has_module_access("people") is True
    assert auth.has_module_access("hr") is True  # alias


def test_finance_manager_role_exposes_finance_modules_without_scopes():
    auth = WebAuthContext(
        is_authenticated=True,
        person_id=UUID("00000000-0000-0000-0000-000000000002"),
        organization_id=UUID("00000000-0000-0000-0000-000000000001"),
        roles=["finance_manager"],
        scopes=[],
    )

    assert auth.has_module_access("finance") is True
    assert auth.has_module_access("fixed_assets") is True


def test_operations_manager_role_exposes_operations_modules_without_scopes():
    auth = WebAuthContext(
        is_authenticated=True,
        person_id=UUID("00000000-0000-0000-0000-000000000002"),
        organization_id=UUID("00000000-0000-0000-0000-000000000001"),
        roles=["operations_manager"],
        scopes=[],
    )

    for module in [
        "fleet",
        "inventory",
        "procurement",
        "projects",
        "settings",
        "support",
    ]:
        assert auth.has_module_access(module) is True


def test_fleet_manager_role_exposes_fleet_module_without_scopes():
    auth = WebAuthContext(
        is_authenticated=True,
        person_id=UUID("00000000-0000-0000-0000-000000000002"),
        organization_id=UUID("00000000-0000-0000-0000-000000000001"),
        roles=["fleet_manager"],
        scopes=[],
    )

    assert auth.has_module_access("fleet") is True


def test_support_manager_role_exposes_support_module_without_scopes():
    auth = WebAuthContext(
        is_authenticated=True,
        person_id=UUID("00000000-0000-0000-0000-000000000002"),
        organization_id=UUID("00000000-0000-0000-0000-000000000001"),
        roles=["support_manager"],
        scopes=[],
    )

    assert auth.has_module_access("support") is True
    assert auth.has_module_access("projects") is True


def test_module_access_infers_from_permission_scope_prefixes():
    auth = WebAuthContext(
        is_authenticated=True,
        person_id=UUID("00000000-0000-0000-0000-000000000002"),
        organization_id=UUID("00000000-0000-0000-0000-000000000001"),
        roles=[],
        scopes=["gl:journals:read", "fleet:vehicles:create", "settings:read"],
    )

    assert auth.has_module_access("finance") is True
    assert auth.has_module_access("fleet") is True
    assert auth.has_module_access("settings") is True


def test_granular_fleet_permissions_expose_fleet_module():
    auth = WebAuthContext(
        is_authenticated=True,
        person_id=UUID("00000000-0000-0000-0000-000000000002"),
        organization_id=UUID("00000000-0000-0000-0000-000000000001"),
        roles=[],
        scopes=["fleet:maintenance:create", "fleet:fuel:create"],
    )

    assert auth.has_module_access("fleet") is True


def test_seed_rbac_contains_fleet_fuel_and_maintenance_permissions():
    seed = (Path(__file__).resolve().parents[1] / "scripts" / "seed_rbac.py").read_text()

    assert '"fleet:maintenance:create"' in seed
    assert '"fleet:fuel:create"' in seed
    assert '"fleet_manager"' in seed


def test_collaboration_panel_does_not_eager_load_null_conversation():
    template = (
        Path(__file__).resolve().parents[1]
        / "templates"
        / "partials"
        / "_collab_panel.html"
    ).read_text()

    assert "conversation/null" not in template
    assert ":hx-get=\"'/collaboration/panel/conversation/' + activeConvId\"" not in template
    assert "if (activeConvId && collabView === 'conversation')" in template


def test_collaboration_panel_posts_csrf_form_token_for_direct_messages():
    template = (
        Path(__file__).resolve().parents[1]
        / "templates"
        / "partials"
        / "_collab_panel.html"
    ).read_text()

    assert "body.append('csrf_token', csrf)" in template
    assert "'X-CSRF-Token': csrf" in template


def test_authenticated_admin_without_org_has_no_module_navigation():
    auth = WebAuthContext(
        is_authenticated=True,
        person_id=UUID("00000000-0000-0000-0000-000000000002"),
        organization_id=None,
        roles=["admin"],
        scopes=["finance:access", "settings:access"],
    )

    assert auth.accessible_modules == []
    assert auth.has_module_access("finance") is False
    assert auth.default_redirect == "/no-access"
