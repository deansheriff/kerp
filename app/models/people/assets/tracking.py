"""Asset tracking event models for QR/RFID/GPS updates."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.people.base import AuditMixin, ERPNextSyncMixin


class AssetTrackingMethod(str, enum.Enum):
    """Tracking capture method."""

    QR_BARCODE = "QR_BARCODE"
    RFID = "RFID"
    GPS = "GPS"


class AssetTrackingEvent(Base, AuditMixin, ERPNextSyncMixin):
    """Recorded asset tracking event with optional geolocation."""

    __tablename__ = "asset_tracking_event"
    __table_args__ = (
        Index("idx_asset_tracking_event_asset", "organization_id", "asset_id"),
        Index("idx_asset_tracking_event_method", "organization_id", "tracking_method"),
        Index("idx_asset_tracking_event_time", "organization_id", "tracked_at"),
        {"schema": "hr"},
    )

    tracking_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core_org.organization.organization_id"),
        nullable=False,
        index=True,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fa.asset.asset_id"),
        nullable=False,
        index=True,
    )
    tracking_method: Mapped[AssetTrackingMethod] = mapped_column(
        Enum(AssetTrackingMethod, name="asset_tracking_method", schema="hr"),
        nullable=False,
    )
    tracking_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tracked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core_org.location.location_id"),
        nullable=True,
    )
    previous_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core_org.location.location_id"),
        nullable=True,
    )
    latitude: Mapped[float | None] = mapped_column(Numeric(11, 8), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(11, 8), nullable=True)
    accuracy_meters: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    movement_logged: Mapped[bool] = mapped_column(nullable=False, default=False)
    scanned_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        onupdate=func.now(),
    )
