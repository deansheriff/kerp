"""Shared AP API router state."""

from fastapi import APIRouter, Depends

from app.api.deps import require_tenant_auth
from app.db import SessionLocal

router = APIRouter(
    prefix="/ap",
    tags=["accounts-payable"],
    dependencies=[Depends(require_tenant_auth)],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
