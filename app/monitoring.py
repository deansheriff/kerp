"""
External monitoring integrations — Loki log shipping and GlitchTip error tracking.

Wires up:
- python-logging-loki: pushes structured logs to a Grafana Loki instance
- sentry-sdk: captures exceptions and sends them to GlitchTip (Sentry-compatible)

Both are optional — if the relevant env vars are empty the integration is silently skipped.
"""

from __future__ import annotations

import logging
import os
from queue import Queue

logger = logging.getLogger(__name__)


def _setup_loki(app_name: str, server: str, environment: str, url: str) -> None:
    """Add a Loki push handler to the root logger."""
    if not url:
        return

    try:
        import logging_loki
    except ImportError:
        logger.warning("python-logging-loki not installed — skipping Loki handler")
        return

    handler = logging_loki.LokiQueueHandler(
        Queue(-1),
        url=url,
        tags={"app": app_name, "server": server, "environment": environment},
        version="1",
    )
    logging.getLogger().addHandler(handler)
    logger.info("Loki handler enabled → %s", url)


def _setup_sentry(app_name: str, environment: str, dsn: str) -> None:
    """Initialise Sentry SDK pointing at GlitchTip."""
    if not dsn:
        return

    try:
        import sentry_sdk
    except ImportError:
        logger.warning("sentry-sdk not installed — skipping GlitchTip integration")
        return

    traces_sample_rate = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        traces_sample_rate=traces_sample_rate,
        release=os.getenv("APP_VERSION", ""),
        server_name=app_name,
    )
    logger.info("Sentry/GlitchTip enabled for %s (%s)", app_name, environment)


def setup_monitoring(
    app_name: str = "dotmac_erp",
    server: str = "",
    environment: str = "",
    loki_url: str = "",
    glitchtip_dsn: str = "",
) -> None:
    """One-call setup for Loki logging and GlitchTip error tracking.

    Values can be passed directly or read from environment variables.
    Direct arguments take precedence over env vars.

    Args:
        app_name: Label used in Loki tags and Sentry server_name.
        server: Host identifier for Loki tags (e.g. ``"remote-1"``).
            Falls back to ``MONITORING_SERVER`` env var.
        environment: ``"production"`` / ``"staging"`` — falls back to
            ``APP_ENV`` env var then ``"production"``.
        loki_url: Loki push endpoint. Falls back to ``LOKI_URL`` env var.
        glitchtip_dsn: Sentry/GlitchTip DSN. Falls back to ``SENTRY_DSN`` env var.
    """
    if not server:
        server = os.getenv("MONITORING_SERVER", "")
    if not environment:
        environment = os.getenv("APP_ENV", "production")
    if not loki_url:
        loki_url = os.getenv("LOKI_URL", "")
    if not glitchtip_dsn:
        glitchtip_dsn = os.getenv("SENTRY_DSN", "")

    _setup_loki(app_name, server, environment, loki_url)
    _setup_sentry(app_name, environment, glitchtip_dsn)
