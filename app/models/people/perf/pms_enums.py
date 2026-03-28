"""
OHCSF Performance Management System (PMS) Enumerations.

Defines all status, type, category, and decision enums for the PMS module.
Covers contracts, monthly reviews, performance improvement plans, appeals,
institutional performance, and outcome management.
"""

import enum


class ContractStatus(str, enum.Enum):
    """Performance contract lifecycle status."""

    DRAFT = "DRAFT"
    PENDING_SIGNATURE = "PENDING_SIGNATURE"
    ACTIVE = "ACTIVE"
    AMENDED = "AMENDED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ContractType(str, enum.Enum):
    """Type of performance contract."""

    MINISTERIAL = "MINISTERIAL"
    DEPARTMENTAL = "DEPARTMENTAL"
    INDIVIDUAL = "INDIVIDUAL"


class MonthlyReviewStatus(str, enum.Enum):
    """Monthly performance review status."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"


class PIPStatus(str, enum.Enum):
    """Performance Improvement Plan lifecycle status."""

    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    UNDER_REVIEW = "UNDER_REVIEW"
    IMPROVED = "IMPROVED"
    EXTENDED = "EXTENDED"
    ESCALATED = "ESCALATED"
    CLOSED = "CLOSED"


class PIPCauseCategory(str, enum.Enum):
    """Root cause category for performance improvement needs."""

    CLARITY = "CLARITY"
    SKILLS = "SKILLS"
    COMMITMENT = "COMMITMENT"
    HEALTH = "HEALTH"
    PERSONAL = "PERSONAL"


class PIPOutcome(str, enum.Enum):
    """Outcome of performance improvement plan."""

    SATISFACTORY = "SATISFACTORY"
    UNSATISFACTORY = "UNSATISFACTORY"


class AppealStatus(str, enum.Enum):
    """Appeal lifecycle status."""

    FILED = "FILED"
    UNDER_MEDIATION = "UNDER_MEDIATION"
    REFERRED_TO_COMMITTEE = "REFERRED_TO_COMMITTEE"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class AppealDecision(str, enum.Enum):
    """Appeal decision outcome."""

    UPHELD = "UPHELD"
    PARTIALLY_UPHELD = "PARTIALLY_UPHELD"
    DISMISSED = "DISMISSED"


class InstitutionType(str, enum.Enum):
    """Type of public institution for institutional performance."""

    MINISTRY = "MINISTRY"
    REGULATORY = "REGULATORY"
    GENERAL_SERVICES = "GENERAL_SERVICES"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    SECURITY = "SECURITY"
    GOVT_COMPANY = "GOVT_COMPANY"


class InstitutionalPerfStatus(str, enum.Enum):
    """Institutional performance appraisal lifecycle status."""

    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPRAISED = "APPRAISED"
    RECONCILED = "RECONCILED"
    COMPLETED = "COMPLETED"


class OutcomeActionType(str, enum.Enum):
    """Type of action resulting from performance appraisal."""

    REWARD = "REWARD"
    PIP = "PIP"
    TRAINING = "TRAINING"
    TRANSFER = "TRANSFER"
    PROMOTION = "PROMOTION"
    DEMOTION = "DEMOTION"
    REMOVAL = "REMOVAL"
    COUNSELING = "COUNSELING"


class OutcomeActionStatus(str, enum.Enum):
    """Status of outcome action implementation."""

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ConfirmationRecommendation(str, enum.Enum):
    """Recommendation for probationary officer confirmation."""

    CONFIRM = "CONFIRM"
    EXTEND = "EXTEND"
    TERMINATE = "TERMINATE"


class CommitteeDecision(str, enum.Enum):
    """Decision made by performance committee."""

    ENDORSED = "ENDORSED"
    ADJUSTED = "ADJUSTED"
    DISPUTED = "DISPUTED"
