"""
WebSocket connection manager for real-time messaging.

In-memory broadcast hub. For multi-worker deployments, messages are
still delivered via database (unread counts + polling fallback).
Redis pub/sub can be added later as a scaling optimization.
"""

import asyncio
import json
import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections per person."""

    def __init__(self) -> None:
        # person_id (str) → set of active WebSocket connections
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, person_id: str, ws: WebSocket) -> None:
        """Accept and register a WebSocket connection."""
        await ws.accept()
        self._connections[person_id].add(ws)
        logger.debug("WS connected: %s (total: %d)", person_id, len(self._connections[person_id]))

    def disconnect(self, person_id: str, ws: WebSocket) -> None:
        """Remove a WebSocket connection."""
        self._connections[person_id].discard(ws)
        if not self._connections[person_id]:
            del self._connections[person_id]
        logger.debug("WS disconnected: %s", person_id)

    @property
    def online_count(self) -> int:
        """Number of unique connected users."""
        return len(self._connections)

    def is_online(self, person_id: str) -> bool:
        """Check if a person has any active connections."""
        return bool(self._connections.get(person_id))

    async def broadcast_to_participants(
        self,
        participant_person_ids: list[str],
        event: dict,
    ) -> None:
        """Send a JSON event to all connected participants."""
        data = json.dumps(event, default=str)
        for pid in participant_person_ids:
            for ws in list(self._connections.get(pid, [])):
                try:
                    await ws.send_text(data)
                except Exception:
                    self._connections[pid].discard(ws)

    async def send_to_person(self, person_id: str, event: dict) -> None:
        """Send a JSON event to a specific person (all their connections)."""
        data = json.dumps(event, default=str)
        for ws in list(self._connections.get(person_id, [])):
            try:
                await ws.send_text(data)
            except Exception:
                self._connections[person_id].discard(ws)


# Module-level singleton
ws_manager = ConnectionManager()
