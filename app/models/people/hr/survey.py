"""
Employee Survey Models - HR Schema.

Models for the employee survey system: surveys, questions, responses, and answers.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.people.base import AuditMixin


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SurveyType(str, enum.Enum):
    """Type of survey."""

    ENGAGEMENT = "ENGAGEMENT"
    PULSE = "PULSE"
    EXIT = "EXIT"
    ONBOARDING = "ONBOARDING"
    CUSTOM = "CUSTOM"


class SurveyStatus(str, enum.Enum):
    """Lifecycle status of a survey."""

    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class TargetAudience(str, enum.Enum):
    """Who the survey targets."""

    ALL = "ALL"
    DEPARTMENT = "DEPARTMENT"
    DESIGNATION = "DESIGNATION"
    CUSTOM = "CUSTOM"


class QuestionType(str, enum.Enum):
    """Type of survey question."""

    RATING = "RATING"
    TEXT = "TEXT"
    SINGLE_CHOICE = "SINGLE_CHOICE"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    SCALE = "SCALE"
    YES_NO = "YES_NO"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Survey(Base, AuditMixin):
    """
    Employee survey definition.

    Surveys can target all employees or specific departments/designations.
    Responses may be anonymous depending on ``is_anonymous``.
    """

    __tablename__ = "survey"
    __table_args__ = (
        Index("ix_survey_org_status", "organization_id", "status"),
        {"schema": "hr"},
    )

    survey_id: Mapped[uuid.UUID] = mapped_column(
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
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    survey_type: Mapped[SurveyType] = mapped_column(
        Enum(SurveyType, name="survey_type", create_type=False),
        nullable=False,
    )
    status: Mapped[SurveyStatus] = mapped_column(
        Enum(SurveyStatus, name="survey_status", create_type=False),
        nullable=False,
        default=SurveyStatus.DRAFT,
        server_default="DRAFT",
    )
    is_anonymous: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    target_audience: Mapped[TargetAudience] = mapped_column(
        Enum(TargetAudience, name="target_audience", create_type=False),
        nullable=False,
        default=TargetAudience.ALL,
    )
    target_filter: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=func.now()
    )

    # Relationships
    questions: Mapped[list[SurveyQuestion]] = relationship(
        "SurveyQuestion",
        back_populates="survey",
        cascade="all, delete-orphan",
        order_by="SurveyQuestion.sort_order",
    )
    responses: Mapped[list[SurveyResponse]] = relationship(
        "SurveyResponse",
        back_populates="survey",
        cascade="all, delete-orphan",
    )


class SurveyQuestion(Base):
    """
    A single question within a survey.

    Choice-based questions store options in the ``options`` JSONB column.
    """

    __tablename__ = "survey_question"
    __table_args__ = (
        Index("ix_survey_question_survey", "survey_id", "sort_order"),
        {"schema": "hr"},
    )

    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    survey_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr.survey.survey_id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core_org.organization.organization_id"),
        nullable=False,
        index=True,
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[QuestionType] = mapped_column(
        Enum(QuestionType, name="question_type", create_type=False),
        nullable=False,
    )
    options: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    survey: Mapped[Survey] = relationship("Survey", back_populates="questions")
    answers: Mapped[list[SurveyAnswer]] = relationship(
        "SurveyAnswer",
        back_populates="question",
        cascade="all, delete-orphan",
    )


class SurveyResponse(Base):
    """
    A single employee's response session to a survey.

    ``employee_id`` is nullable to support anonymous surveys.
    """

    __tablename__ = "survey_response"
    __table_args__ = (
        Index("ix_survey_response_survey", "survey_id"),
        {"schema": "hr"},
    )

    response_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    survey_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr.survey.survey_id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core_org.organization.organization_id"),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr.employee.employee_id"),
        nullable=True,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_complete: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # Relationships
    survey: Mapped[Survey] = relationship("Survey", back_populates="responses")
    answers: Mapped[list[SurveyAnswer]] = relationship(
        "SurveyAnswer",
        back_populates="response",
        cascade="all, delete-orphan",
    )


class SurveyAnswer(Base):
    """
    A single answer to a survey question within a response.

    Stores the answer value in the appropriate typed column based on
    the parent question's type.
    """

    __tablename__ = "survey_answer"
    __table_args__ = (
        Index("ix_survey_answer_response", "response_id"),
        Index("ix_survey_answer_question", "question_id"),
        {"schema": "hr"},
    )

    answer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    response_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr.survey_response.response_id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr.survey_question.question_id", ondelete="CASCADE"),
        nullable=False,
    )
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    answer_choices: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    response: Mapped[SurveyResponse] = relationship(
        "SurveyResponse", back_populates="answers"
    )
    question: Mapped[SurveyQuestion] = relationship(
        "SurveyQuestion", back_populates="answers"
    )
