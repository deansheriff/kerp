"""Employee survey service — business logic for survey management.

Handles survey CRUD, question management, response submission,
and aggregated results computation.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.people.hr.survey import (
    QuestionType,
    Survey,
    SurveyAnswer,
    SurveyQuestion,
    SurveyResponse,
    SurveyStatus,
)
from app.services.common import PaginatedResult, PaginationParams, paginate

logger = logging.getLogger(__name__)

__all__ = ["SurveyService"]


# ---------------------------------------------------------------------------
# Input data classes
# ---------------------------------------------------------------------------


@dataclass
class SurveyCreateInput:
    """Input for creating a survey."""

    title: str
    description: str | None = None
    survey_type: str = "CUSTOM"
    is_anonymous: bool = True
    start_date: date | None = None
    end_date: date | None = None
    target_audience: str = "ALL"
    target_filter: dict[str, Any] | None = None


@dataclass
class QuestionInput:
    """Input for adding a question to a survey."""

    question_text: str
    question_type: str
    options: dict[str, Any] | None = None
    is_required: bool = True
    sort_order: int = 0


@dataclass
class AnswerInput:
    """Input for a single answer."""

    question_id: UUID
    answer_text: str | None = None
    answer_rating: int | None = None
    answer_choices: dict[str, Any] | None = None


@dataclass
class SurveyResults:
    """Aggregated results for a survey."""

    survey_id: UUID
    total_responses: int = 0
    complete_responses: int = 0
    question_results: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class SurveyService:
    """Service for employee survey operations."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # -- helpers --------------------------------------------------------------

    def _get_survey(self, org_id: UUID, survey_id: UUID) -> Survey:
        """Fetch a survey or raise ``ValueError``."""
        survey = self.db.scalar(
            select(Survey).where(
                Survey.survey_id == survey_id,
                Survey.organization_id == org_id,
            )
        )
        if not survey:
            raise ValueError(f"Survey {survey_id} not found")
        return survey

    # -- CRUD -----------------------------------------------------------------

    def create_survey(
        self,
        org_id: UUID,
        data: SurveyCreateInput,
        *,
        created_by_id: UUID | None = None,
    ) -> Survey:
        """Create a new survey in DRAFT status."""
        survey = Survey(
            organization_id=org_id,
            title=data.title,
            description=data.description,
            survey_type=data.survey_type,
            status=SurveyStatus.DRAFT,
            is_anonymous=data.is_anonymous,
            start_date=data.start_date or date.today(),
            end_date=data.end_date or date.today(),
            target_audience=data.target_audience,
            target_filter=data.target_filter,
            created_by_id=created_by_id,
        )
        self.db.add(survey)
        self.db.flush()
        logger.info("Created survey %s: %s", survey.survey_id, survey.title)
        return survey

    def activate_survey(self, org_id: UUID, survey_id: UUID) -> Survey:
        """Transition a survey from DRAFT to ACTIVE."""
        survey = self._get_survey(org_id, survey_id)
        if survey.status != SurveyStatus.DRAFT:
            raise ValueError(f"Cannot activate survey in status {survey.status.value}")
        survey.status = SurveyStatus.ACTIVE
        self.db.flush()
        logger.info("Activated survey %s", survey_id)
        return survey

    def close_survey(self, org_id: UUID, survey_id: UUID) -> Survey:
        """Transition a survey from ACTIVE to CLOSED."""
        survey = self._get_survey(org_id, survey_id)
        if survey.status != SurveyStatus.ACTIVE:
            raise ValueError(f"Cannot close survey in status {survey.status.value}")
        survey.status = SurveyStatus.CLOSED
        self.db.flush()
        logger.info("Closed survey %s", survey_id)
        return survey

    # -- Questions ------------------------------------------------------------

    def add_question(
        self, org_id: UUID, survey_id: UUID, data: QuestionInput
    ) -> SurveyQuestion:
        """Add a question to a DRAFT survey."""
        survey = self._get_survey(org_id, survey_id)
        if survey.status != SurveyStatus.DRAFT:
            raise ValueError("Questions can only be added to DRAFT surveys")

        question = SurveyQuestion(
            survey_id=survey_id,
            organization_id=org_id,
            question_text=data.question_text,
            question_type=data.question_type,
            options=data.options,
            is_required=data.is_required,
            sort_order=data.sort_order,
        )
        self.db.add(question)
        self.db.flush()
        logger.info("Added question %s to survey %s", question.question_id, survey_id)
        return question

    # -- Responses ------------------------------------------------------------

    def submit_response(
        self,
        org_id: UUID,
        survey_id: UUID,
        employee_id: UUID | None,
        answers: list[AnswerInput],
    ) -> SurveyResponse:
        """Submit a complete response to an ACTIVE survey."""
        survey = self._get_survey(org_id, survey_id)
        if survey.status != SurveyStatus.ACTIVE:
            raise ValueError("Responses can only be submitted to ACTIVE surveys")

        # For anonymous surveys, strip the employee_id
        resp_employee_id = None if survey.is_anonymous else employee_id

        response = SurveyResponse(
            survey_id=survey_id,
            organization_id=org_id,
            employee_id=resp_employee_id,
            submitted_at=datetime.now(timezone.utc),
            is_complete=True,
        )
        self.db.add(response)
        self.db.flush()

        for ans in answers:
            answer = SurveyAnswer(
                response_id=response.response_id,
                question_id=ans.question_id,
                answer_text=ans.answer_text,
                answer_rating=ans.answer_rating,
                answer_choices=ans.answer_choices,
            )
            self.db.add(answer)

        # Bump response count
        survey.response_count = (survey.response_count or 0) + 1
        self.db.flush()
        logger.info(
            "Submitted response %s to survey %s", response.response_id, survey_id
        )
        return response

    # -- Results --------------------------------------------------------------

    def get_results(self, org_id: UUID, survey_id: UUID) -> SurveyResults:
        """Aggregate results for a survey.

        Returns average ratings per question, text responses,
        and choice distributions.
        """
        self._get_survey(org_id, survey_id)  # validates existence + org ownership

        # Load questions
        questions = list(
            self.db.scalars(
                select(SurveyQuestion)
                .where(SurveyQuestion.survey_id == survey_id)
                .order_by(SurveyQuestion.sort_order)
            ).all()
        )

        total_responses = (
            self.db.scalar(
                select(func.count(SurveyResponse.response_id)).where(
                    SurveyResponse.survey_id == survey_id,
                    SurveyResponse.organization_id == org_id,
                )
            )
            or 0
        )

        complete_responses = (
            self.db.scalar(
                select(func.count(SurveyResponse.response_id)).where(
                    SurveyResponse.survey_id == survey_id,
                    SurveyResponse.organization_id == org_id,
                    SurveyResponse.is_complete.is_(True),
                )
            )
            or 0
        )

        question_results: list[dict[str, Any]] = []
        for q in questions:
            answers_stmt = select(SurveyAnswer).where(
                SurveyAnswer.question_id == q.question_id
            )
            answers = list(self.db.scalars(answers_stmt).all())
            result: dict[str, Any] = {
                "question_id": str(q.question_id),
                "question_text": q.question_text,
                "question_type": q.question_type.value
                if isinstance(q.question_type, QuestionType)
                else q.question_type,
                "total_answers": len(answers),
            }

            q_type = q.question_type
            if q_type in (QuestionType.RATING, QuestionType.SCALE):
                ratings = [
                    a.answer_rating for a in answers if a.answer_rating is not None
                ]
                result["avg_rating"] = (
                    round(sum(ratings) / len(ratings), 2) if ratings else None
                )
                result["min_rating"] = min(ratings) if ratings else None
                result["max_rating"] = max(ratings) if ratings else None
            elif q_type == QuestionType.TEXT:
                result["text_responses"] = [
                    a.answer_text for a in answers if a.answer_text
                ]
            elif q_type in (
                QuestionType.SINGLE_CHOICE,
                QuestionType.MULTIPLE_CHOICE,
            ):
                counter: Counter[str] = Counter()
                for a in answers:
                    if a.answer_choices and isinstance(a.answer_choices, dict):
                        for choice in a.answer_choices.get("selected", []):
                            counter[str(choice)] += 1
                result["choice_distribution"] = dict(counter)
            elif q_type == QuestionType.YES_NO:
                yes_count = sum(
                    1
                    for a in answers
                    if a.answer_text and a.answer_text.upper() == "YES"
                )
                no_count = sum(
                    1
                    for a in answers
                    if a.answer_text and a.answer_text.upper() == "NO"
                )
                result["yes_count"] = yes_count
                result["no_count"] = no_count

            question_results.append(result)

        return SurveyResults(
            survey_id=survey_id,
            total_responses=total_responses,
            complete_responses=complete_responses,
            question_results=question_results,
        )

    # -- Listing --------------------------------------------------------------

    def list_surveys(
        self,
        org_id: UUID,
        *,
        status: SurveyStatus | None = None,
        pagination: PaginationParams | None = None,
    ) -> PaginatedResult[Survey]:
        """List surveys for an organization with optional status filter."""
        stmt = (
            select(Survey)
            .where(Survey.organization_id == org_id)
            .order_by(Survey.created_at.desc())
        )
        if status is not None:
            stmt = stmt.where(Survey.status == status)

        return paginate(self.db, stmt, pagination)
