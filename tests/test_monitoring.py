"""Tests for app.monitoring — resilient Loki handler and monitoring status."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import app.monitoring as _monitoring_mod
from app.logging import JsonLogFormatter
from app.monitoring import (
    ResilientLokiHandler,
    _loki_stats,
    _loki_stats_lock,
    get_monitoring_status,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reset_loki_stats() -> None:
    """Reset module-level stats between tests."""
    with _loki_stats_lock:
        _loki_stats.update(
            {
                "enabled": False,
                "url": "",
                "sent": 0,
                "dropped": 0,
                "last_error": "",
                "last_success_ts": 0.0,
                "consecutive_failures": 0,
            }
        )


@pytest.fixture(autouse=True)
def _clean_stats():
    _reset_loki_stats()
    prev_sentry = _monitoring_mod._sentry_enabled
    _monitoring_mod._sentry_enabled = False
    yield
    _reset_loki_stats()
    _monitoring_mod._sentry_enabled = prev_sentry


def _make_handler(
    url: str = "http://localhost:3100/loki/api/v1/push",
) -> ResilientLokiHandler:
    return ResilientLokiHandler(
        url=url,
        tags={"app": "test", "server": "test-server", "environment": "test"},
        connect_timeout=1,
        read_timeout=1,
    )


def _make_record(msg: str = "test message") -> logging.LogRecord:
    return logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=msg,
        args=(),
        exc_info=None,
    )


# ---------------------------------------------------------------------------
# ResilientLokiHandler tests
# ---------------------------------------------------------------------------


class TestResilientLokiHandler:
    """Tests for the resilient Loki log handler."""

    @patch("app.monitoring.ResilientLokiHandler._new_session")
    def test_successful_emit_updates_stats(self, mock_new_session: MagicMock) -> None:
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_session.post.return_value = mock_resp
        mock_new_session.return_value = mock_session

        handler = _make_handler()
        handler.emit(_make_record())

        mock_session.post.assert_called_once()
        with _loki_stats_lock:
            assert _loki_stats["sent"] == 1
            assert _loki_stats["dropped"] == 0
            assert _loki_stats["consecutive_failures"] == 0

    @patch("app.monitoring.ResilientLokiHandler._new_session")
    def test_failed_emit_increments_failures(self, mock_new_session: MagicMock) -> None:
        mock_session = MagicMock()
        mock_session.post.side_effect = ConnectionError("refused")
        mock_new_session.return_value = mock_session

        handler = _make_handler()
        handler.emit(_make_record())

        with _loki_stats_lock:
            assert _loki_stats["sent"] == 0
            assert _loki_stats["dropped"] == 1
            assert _loki_stats["consecutive_failures"] == 1
            assert "refused" in _loki_stats["last_error"]

    @patch("app.monitoring.ResilientLokiHandler._new_session")
    def test_backoff_drops_logs_during_cooldown(
        self, mock_new_session: MagicMock
    ) -> None:
        mock_session = MagicMock()
        mock_session.post.side_effect = ConnectionError("down")
        mock_new_session.return_value = mock_session

        handler = _make_handler()

        # First emit triggers the failure and sets backoff
        handler.emit(_make_record("first"))

        # Second emit within backoff window should be dropped without calling post
        call_count_after_first = mock_session.post.call_count
        handler.emit(_make_record("second"))

        # post should NOT have been called again (backoff active)
        assert mock_session.post.call_count == call_count_after_first

        with _loki_stats_lock:
            assert _loki_stats["dropped"] == 2  # one from failure, one from backoff

    @patch("app.monitoring.ResilientLokiHandler._new_session")
    def test_session_recreated_on_failure(self, mock_new_session: MagicMock) -> None:
        mock_session = MagicMock()
        mock_session.post.side_effect = ConnectionError("broken pipe")
        mock_new_session.return_value = mock_session

        handler = _make_handler()
        handler.emit(_make_record())

        # Session should have been closed and recreated
        mock_session.close.assert_called_once()
        # _new_session called twice: once in __init__, once in _reset_session
        assert mock_new_session.call_count == 2

    @patch("app.monitoring.ResilientLokiHandler._new_session")
    def test_recovery_after_backoff(self, mock_new_session: MagicMock) -> None:
        mock_session = MagicMock()
        mock_session.post.side_effect = ConnectionError("temporary")
        mock_new_session.return_value = mock_session

        handler = _make_handler()
        handler.emit(_make_record())

        # Manually expire the backoff window
        handler._next_retry_at = 0.0

        # Now make the next call succeed
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_session.post.side_effect = None
        mock_session.post.return_value = mock_resp

        handler.emit(_make_record("recovered"))

        with _loki_stats_lock:
            assert _loki_stats["sent"] == 1
            assert _loki_stats["consecutive_failures"] == 0

    @patch("app.monitoring.ResilientLokiHandler._new_session")
    def test_http_error_response_handled(self, mock_new_session: MagicMock) -> None:
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_session.post.return_value = mock_resp
        mock_new_session.return_value = mock_session

        handler = _make_handler()
        handler.emit(_make_record())

        with _loki_stats_lock:
            assert _loki_stats["dropped"] == 1
            assert "HTTP 500" in _loki_stats["last_error"]

    @patch("app.monitoring.ResilientLokiHandler._new_session")
    def test_payload_structure(self, mock_new_session: MagicMock) -> None:
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_session.post.return_value = mock_resp
        mock_new_session.return_value = mock_session

        handler = _make_handler()
        record = _make_record("hello from test")
        record.request_id = "req-123"
        record.invoice_id = "inv-123"
        handler.emit(record)

        call_args = mock_session.post.call_args
        import json

        body = json.loads(call_args.kwargs.get("data", call_args[1].get("data", "")))
        assert "streams" in body
        stream = body["streams"][0]
        assert stream["stream"]["app"] == "test"
        assert stream["stream"]["logger"] == "test.logger"
        assert stream["stream"]["severity"] == "info"
        payload = json.loads(stream["values"][0][1])
        assert payload["message"] == "hello from test"
        assert payload["logger"] == "test.logger"
        assert payload["request_id"] == "req-123"
        assert payload["invoice_id"] == "inv-123"
        assert isinstance(handler.formatter, JsonLogFormatter)


# ---------------------------------------------------------------------------
# get_monitoring_status tests
# ---------------------------------------------------------------------------


class TestGetMonitoringStatus:
    """Tests for the monitoring status endpoint helper."""

    def test_default_state(self) -> None:
        status = get_monitoring_status()
        assert status["loki"]["enabled"] is False
        assert status["sentry"]["enabled"] is False

    def test_loki_enabled_with_stats(self) -> None:
        with _loki_stats_lock:
            _loki_stats["enabled"] = True
            _loki_stats["url"] = "http://loki:3100/loki/api/v1/push"
            _loki_stats["sent"] = 42
            _loki_stats["dropped"] = 3

        status = get_monitoring_status()
        assert status["loki"]["enabled"] is True
        assert status["loki"]["sent"] == 42
        assert status["loki"]["dropped"] == 3
        assert status["loki"]["url"] == "http://loki:3100/loki/api/v1/push"

    def test_monitoring_status_redacts_sensitive_details(self) -> None:
        with _loki_stats_lock:
            _loki_stats["enabled"] = True
            _loki_stats["url"] = (
                "https://user:secret@loki.internal:3100/loki/api/v1/push?token=abc"
            )
            _loki_stats["last_error"] = (
                "HTTPSConnectionPool(host='loki.internal', port=3100): Max retries exceeded"
            )

        status = get_monitoring_status()

        assert status["loki"]["url"] == "https://loki.internal:3100/loki/api/v1/push"
        assert status["loki"]["last_error"] == (
            "delivery failure; inspect application logs for details"
        )

    @patch("sentry_sdk.get_client")
    def test_sentry_transport_health_calls_callable(
        self, mock_get_client: MagicMock
    ) -> None:
        _monitoring_mod._sentry_enabled = True
        mock_transport = SimpleNamespace(is_healthy=lambda: False)
        mock_get_client.return_value = SimpleNamespace(
            dsn="https://public@example.com/1",
            transport=mock_transport,
        )

        status = get_monitoring_status()

        assert status["sentry"]["enabled"] is True
        assert status["sentry"]["dsn_configured"] is True
        assert status["sentry"]["transport_healthy"] is False
