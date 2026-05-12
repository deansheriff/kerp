from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_admin_user_update_redirects_after_success():
    source = (ROOT / "app" / "services" / "admin" / "web.py").read_text()

    success_redirect = (
        'return RedirectResponse(url="/admin/users?updated=1", status_code=303)'
    )
    assert success_redirect in source
    assert source.index("if error:") < source.index(success_redirect)


def test_admin_users_template_has_updated_success_message():
    template = (ROOT / "templates" / "admin" / "users.html").read_text()

    assert "request.query_params.get('updated')" in template
    assert "User updated successfully." in template
