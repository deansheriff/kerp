from app.middleware.csp import add_unsafe_eval_to_csp


def test_csp_allows_alpine_eval_by_default(monkeypatch):
    monkeypatch.delenv("CSP_ALLOW_UNSAFE", raising=False)

    policy = add_unsafe_eval_to_csp("script-src 'self' https://cdn.jsdelivr.net")

    assert "'unsafe-eval'" in policy
    assert "'unsafe-inline'" in policy


def test_csp_can_disable_unsafe_script_tokens(monkeypatch):
    monkeypatch.setenv("CSP_ALLOW_UNSAFE", "false")

    policy = add_unsafe_eval_to_csp("script-src 'self' https://cdn.jsdelivr.net")

    assert policy == "script-src 'self' https://cdn.jsdelivr.net"
