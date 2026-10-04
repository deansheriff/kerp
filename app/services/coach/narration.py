"""Optional LLM explanations; deterministic facts and workflow decisions stay intact."""

import json
import logging
import re
from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.coach.insight import CoachInsight
from app.models.coach.report import CoachReport
from app.services.coach.ai_workflows import SYSTEM
from app.services.coach.insight_engine import InsightEngine, LLMError

logger = logging.getLogger(__name__)


class Narration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    explanation: str = Field(min_length=1, max_length=3000)
    limitations: str = Field(min_length=1, max_length=1000)


def _generate(
    db: Session, org_id: UUID, context: dict
) -> tuple[Narration, InsightEngine] | None:
    engine = InsightEngine(db, organization_id=org_id)
    if engine._setting("ai_enabled", "coach_ai_enabled").lower() != "true":
        return None
    try:
        result = engine.generate_structured(
            tier="fast",
            output_model=Narration,
            system_prompt=SYSTEM
            + "Explain the supplied deterministic business signals. Never change amounts, severity or conclusions. Suggest questions to investigate, not automatic actions. Do not introduce unsupported numerical claims.",
            user_prompt=json.dumps(context, default=str),
        )
        return result, engine
    except LLMError:
        logger.warning(
            "Coach AI narration unavailable for organization %s; retaining deterministic output",
            org_id,
        )
        return None


def narrate_daily_insights(db: Session, org_id: UUID) -> None:
    engine = InsightEngine(db, organization_id=org_id)
    if engine._setting("ai_enabled", "coach_ai_enabled").lower() != "true":
        return
    rows = db.scalars(
        select(CoachInsight)
        .where(
            CoachInsight.organization_id == org_id,
            func.date(CoachInsight.created_at) == date.today(),
            CoachInsight.detail.is_(None),
        )
        .order_by(CoachInsight.created_at, CoachInsight.insight_id)
        .limit(20)
    ).all()
    for row in rows:
        # Only deterministic headings and numeric aggregates, never raw customer/employee lists.
        metrics = {
            key: value
            for key, value in (row.evidence or {}).items()
            if _safe_metric(value)
        }
        generated = _generate(
            db,
            org_id,
            {
                "title": row.title,
                "category": row.category,
                "severity": row.severity,
                "metrics": metrics,
            },
        )
        if generated:
            result, engine = generated
            row.detail = f"AI explanation ({engine.last_model or 'cached'}):\n{result.explanation}\n\nLimitations: {result.limitations}"
        else:
            break
    db.flush()


def narrate_report(db: Session, report: CoachReport) -> None:
    metrics = [
        m
        for m in (report.key_metrics or [])
        if isinstance(m, dict) and _safe_metric(m.get("value"))
    ]
    generated = _generate(
        db,
        report.organization_id,
        {
            "audience": report.audience,
            "period_start": str(report.period_start),
            "period_end": str(report.period_end),
            "metrics": metrics,
        },
    )
    if generated:
        result, engine = generated
        report.executive_summary += f"\n\nAI explanation (review required): {result.explanation}\nLimitations: {result.limitations}"
        report.model_used = engine.last_model or "cached"
        report.tokens_used = engine.tokens_used


def _safe_metric(value: object) -> bool:
    return not isinstance(value, bool) and (
        isinstance(value, (int, float))
        or isinstance(value, str)
        and bool(re.fullmatch(r"-?\d+(\.\d+)?", value))
    )
