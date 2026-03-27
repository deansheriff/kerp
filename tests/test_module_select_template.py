from types import SimpleNamespace

from app.templates import templates


def test_module_select_renders_self_service_tile_when_accessible():
    html = templates.env.get_template("module_select.html").render(
        title="Dotmac | Select Module",
        brand={"name": "Dotmac"},
        user=SimpleNamespace(is_admin=False),
        accessible_modules=["people", "self_service"],
        csrf_token="test-csrf-token",
    )

    assert "Self Service" in html
    assert 'href="/people/self/attendance"' in html
    assert "Open Self Service" in html
