from __future__ import annotations

import os
from collections.abc import Iterable


def _split_directives(policy: str) -> list[str]:
    return [part.strip() for part in policy.split(";") if part.strip()]


def _join_directives(directives: Iterable[str]) -> str:
    return "; ".join(directives)


def _ensure_token(directive: str, token: str) -> str:
    parts = directive.split()
    if token in parts:
        return directive
    return f"{directive} {token}"


def _update_script_src(policy: str) -> str:
    directives = _split_directives(policy)
    updated = []
    seen_script = False
    seen_script_elem = False
    for directive in directives:
        if directive.startswith("script-src "):
            seen_script = True
            directive = _ensure_token(directive, "'unsafe-eval'")
            directive = _ensure_token(directive, "'unsafe-inline'")
        elif directive.startswith("script-src-elem "):
            seen_script_elem = True
            directive = _ensure_token(directive, "'unsafe-eval'")
            directive = _ensure_token(directive, "'unsafe-inline'")
        updated.append(directive)

    if not seen_script and not seen_script_elem:
        updated.append(
            "script-src 'self' 'unsafe-eval' 'unsafe-inline' https://cdn.jsdelivr.net https://static.cloudflareinsights.com"
        )

    return _join_directives(updated)


def _allow_unsafe_script() -> bool:
    """Allow Alpine-compatible script directives unless explicitly disabled."""
    value = os.getenv("CSP_ALLOW_UNSAFE", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def add_unsafe_eval_to_csp(policy: str | None) -> str:
    """Relax CSP for the server-rendered Alpine UI unless disabled via env."""
    if not _allow_unsafe_script():
        # Return policy unchanged (or a safe default if missing).
        return policy or "script-src 'self' https://cdn.jsdelivr.net https://static.cloudflareinsights.com"
    if not policy:
        return (
            "script-src 'self' 'unsafe-eval' 'unsafe-inline' https://cdn.jsdelivr.net https://static.cloudflareinsights.com"
        )
    if "'unsafe-eval'" in policy and "'unsafe-inline'" in policy:
        return policy
    return _update_script_src(policy)
