"""Atomic tenant-specific AI configuration, without changing global defaults."""

from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import null, select
from sqlalchemy.orm import Session

from app.models.domain_settings import (
    DomainSetting,
    SettingChangeAction,
    SettingDomain,
    SettingScope,
)
from app.services.domain_settings import _record_setting_history
from app.services.settings_spec import coerce_value, get_spec


def save_configuration(
    db: Session, organization_id: UUID, data: dict
) -> tuple[bool, str | None]:
    if db.info.get("organization_id") != organization_id or db.info.get(
        "allow_cross_org"
    ):
        return False, "A matching tenant-scoped session is required"
    values = {}
    for key, raw in data.items():
        spec = get_spec(SettingDomain.coach, key)
        if spec is None or (spec.is_secret and raw == ""):
            continue
        value, error = coerce_value(spec, raw)
        if error:
            return False, f"{spec.label or key}: {error}"
        if key.endswith("base_url") and value:
            url = urlsplit(str(value))
            if (
                url.scheme != "https"
                or not url.hostname
                or url.username
                or url.password
                or url.query
                or url.fragment
            ):
                return (
                    False,
                    "Provider URLs must use HTTPS without credentials or query parameters",
                )
            if key == "gemini_base_url" and (
                url.hostname != "generativelanguage.googleapis.com"
                or url.path.rstrip("/") != "/v1beta/openai"
            ):
                return False, "Use the official Gemini compatibility endpoint"
        if key == "backends" and (
            not str(value).strip()
            or any(
                p.strip() not in {"gemini", "deepseek", "llama"}
                for p in str(value).split(",")
            )
        ):
            return False, "Allowed providers must contain gemini, deepseek or llama"
        if key == "default_backend" and value not in {"gemini", "deepseek", "llama"}:
            return False, "Select a supported default provider"
        values[key] = (spec, value)
    if "backends" in values and "default_backend" in values:
        if values["default_backend"][1] not in str(values["backends"][1]).replace(
            " ", ""
        ).split(","):
            return False, "The default provider must be in the allowed providers list"
    for key, (spec, value) in values.items():
        row = db.scalar(
            select(DomainSetting).where(
                DomainSetting.organization_id == organization_id,
                DomainSetting.domain == SettingDomain.coach,
                DomainSetting.key == key,
            )
        )
        old = {}
        action = SettingChangeAction.CREATE
        if row:
            action = SettingChangeAction.UPDATE
            old = dict(
                old_value_type=row.value_type.value,
                old_value_text=row.value_text,
                old_value_json=row.value_json,
                old_is_secret=row.is_secret,
                old_is_active=row.is_active,
            )
        else:
            row = DomainSetting(
                organization_id=organization_id,
                scope=SettingScope.ORG_SPECIFIC,
                domain=SettingDomain.coach,
                key=key,
            )
            db.add(row)
        row.value_type = spec.value_type
        row.value_text = str(value) if value is not None else None
        # SQL NULL, not JSON null: the storage constraint distinguishes them.
        row.value_json = null()  # type: ignore[assignment]
        row.is_secret = spec.is_secret
        row.is_active = True
        db.flush()
        _record_setting_history(db, row, action, **old)
    db.flush()
    return True, None
