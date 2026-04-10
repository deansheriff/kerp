"""AP API router compatibility module."""

from app.api.finance.ap_routes import get_db, router

__all__ = ["get_db", "router"]
