# OHCSF Performance Management System — Design Spec

**Date:** 2026-03-28
**Status:** Approved
**Source:** [PMS Guidelines (OHCSF, 2022)](https://ohcsf.gov.ng/wp-content/uploads/2025/09/PMS-Guidelines.pdf)

## Overview

Extend the existing People/HR Performance module to support Nigeria's OHCSF Performance Management System guidelines. Gated by a single feature flag (`pms_ohcsf_enabled`) on the Organization model. When disabled, existing private-sector appraisal flow works unchanged.

### Approach

**Extend existing models + add new ones (Approach A).** ~70% of the data model is shared (employees, KRAs, KPIs, appraisals, departments, reporting lines). The OHCSF workflow adds Performance Contracts, Monthly Reviews, PIPs, Counter-signing, Staff Committee review, Institutional Performance, and a prescriptive competency framework on top of the existing infrastructure.

### Two Performance Levels

1. **Institutional (MDA/Department)** — scored on 8 weighted criteria categories, weights vary by institution type
2. **Employee (Individual)** — KPIs with per-measure criteria thresholds, 70/20/10 weight split (objectives/competencies/processes), quarterly + annual appraisal cycle

---

## 1. Feature Flag & Activation

### Organization Model Extension

```python
pms_ohcsf_enabled = mapped_column(Boolean, default=False)
```

Follows the existing pattern alongside `fund_accounting_enabled` and `commitment_control_enabled`.

### What It Gates

- Performance Contracts UI and workflow
- Monthly Review Forms (PRF)
- Quarterly appraisal sub-cycles within annual cycle
- Counter-signing and Staff Committee workflow steps on appraisals
- PIP management
- Institutional (MDA/Department) performance tracking
- OHCSF 18-competency framework seeding (on first enable)
- OHCSF-specific KRA weight enforcement (70 objectives / 20 competencies / 10 processes)
- Strategic Objectives cascade tracking
- Appraisal Appeals
- OHCSF mandatory reports (11 report types)

### What Stays the Same

- KRA, KPI, Appraisal, AppraisalCycle, Scorecard — all work as today
- Self-assessment → Manager review → Calibration flow (still available)
- 360-degree feedback
- Performance reporting/analytics

### Activation Flow

Admin toggles flag in org settings. On first enable, `PMSConfigService.activate_ohcsf_pms()` runs a one-time setup that seeds 18 OHCSF competencies and creates default KRA weight category templates. Disabling the flag hides PMS-specific UI but does not delete data.

---

## 2. Extended Existing Models

### AppraisalCycle — Quarterly Phase Support

```python
cycle_type       = mapped_column(String(20), default="ANNUAL")   # ANNUAL, QUARTERLY
parent_cycle_id  = mapped_column(UUID, ForeignKey("appraisal_cycle.cycle_id"), nullable=True)
quarter          = mapped_column(Integer, nullable=True)          # 1, 2, 3, 4
```

When `pms_ohcsf_enabled`, creating an annual cycle auto-generates 4 quarterly sub-cycles linked via `parent_cycle_id`. Each quarterly cycle has its own deadlines (self-assessment 1st week of Apr/Jul/Oct/Dec, manager review by 2nd week). The annual cycle aggregates quarterly scores into a final annual rating.

### Appraisal — OHCSF Workflow & Scoring

```python
# Counter-signing & committee
counter_signer_id          = mapped_column(UUID, ForeignKey("employee.employee_id"), nullable=True)
counter_signer_date        = mapped_column(Date, nullable=True)
counter_signer_comments    = mapped_column(Text, nullable=True)
committee_review_date      = mapped_column(Date, nullable=True)
committee_decision         = mapped_column(String(50), nullable=True)  # ENDORSED, ADJUSTED, DISPUTED
committee_notes            = mapped_column(Text, nullable=True)
is_quarterly               = mapped_column(Boolean, default=False)
quarterly_rating           = mapped_column(Numeric(5, 2), nullable=True)

# Process scoring (10% bucket)
process_self_rating        = mapped_column(Integer, nullable=True)
process_manager_rating     = mapped_column(Integer, nullable=True)
process_final_rating       = mapped_column(Integer, nullable=True)
process_comments           = mapped_column(Text, nullable=True)

# Composite breakdown
objective_weighted_score   = mapped_column(Numeric(5, 2), nullable=True)
competency_weighted_score  = mapped_column(Numeric(5, 2), nullable=True)
process_weighted_score     = mapped_column(Numeric(5, 2), nullable=True)

# Approved absence carryover (Section 5.8)
is_prior_year_carryover    = mapped_column(Boolean, default=False)
carryover_source_id        = mapped_column(UUID, ForeignKey("appraisal.appraisal_id"), nullable=True)
absence_months             = mapped_column(Integer, nullable=True)

# Probation (Section 5.6.4)
is_probation_appraisal          = mapped_column(Boolean, default=False)
confirmation_recommendation     = mapped_column(String(20), nullable=True)  # CONFIRM, EXTEND, TERMINATE

# Secondment (Section 5.3.7)
is_secondment_appraisal    = mapped_column(Boolean, default=False)
secondment_org_name        = mapped_column(String(200), nullable=True)
parent_org_notified        = mapped_column(Boolean, default=False)
parent_org_notified_date   = mapped_column(Date, nullable=True)

# Debrief tracking
debrief_date               = mapped_column(Date, nullable=True)
debrief_notes              = mapped_column(Text, nullable=True)
debrief_acknowledged       = mapped_column(Boolean, default=False)

# Reward nomination (Section 5.14)
reward_nominated           = mapped_column(Boolean, default=False)
reward_type                = mapped_column(String(50), nullable=True)
reward_notes               = mapped_column(Text, nullable=True)
```

### Extended AppraisalStatus Enum

OHCSF mode adds 3 new statuses (only reachable when flag is on):

```
DRAFT → SELF_ASSESSMENT → PENDING_REVIEW → UNDER_REVIEW
  → PENDING_COUNTERSIGN → COUNTERSIGNED → PENDING_COMMITTEE
  → COMPLETED
```

Existing private-sector flow (`UNDER_REVIEW → PENDING_CALIBRATION → CALIBRATION → COMPLETED`) remains unchanged.

### AppraisalKRAScore — Per-KPI Criteria Thresholds

```python
target_description       = mapped_column(Text, nullable=True)
achievement_description  = mapped_column(Text, nullable=True)
evidence                 = mapped_column(Text, nullable=True)

# Per-KPI thresholds (set at planning time in PPF)
outstanding_threshold    = mapped_column(Numeric(12, 2), nullable=True)
excellent_threshold      = mapped_column(Numeric(12, 2), nullable=True)
good_threshold           = mapped_column(Numeric(12, 2), nullable=True)
fair_threshold           = mapped_column(Numeric(12, 2), nullable=True)
poor_threshold           = mapped_column(Numeric(12, 2), nullable=True)

# Calculated at appraisal time
actual_achievement       = mapped_column(Numeric(12, 2), nullable=True)
raw_score_percentage     = mapped_column(Numeric(5, 2), nullable=True)
```

### Composite Score Formula (OHCSF mode)

```
final_score = (objective_weighted_score × 0.70)
            + (competency_weighted_score × 0.20)
            + (process_weighted_score × 0.10)
```

---

## 3. New Models

All in `app/models/people/perf/`.

### 3a. PerformanceContract

Formal signed agreement between supervisor and employee (or PS↔Director, Minister↔PS).

```python
contract_id              # UUID PK
organization_id          # UUID FK
cycle_id                 # UUID FK → appraisal_cycle (annual)
employee_id              # UUID FK → employee
supervisor_id            # UUID FK → employee
contract_code            # String(30) — "PC-2026-0042"
contract_type            # Enum: MINISTERIAL, DEPARTMENTAL, INDIVIDUAL
status                   # Enum: DRAFT, PENDING_SIGNATURE, ACTIVE, AMENDED, COMPLETED, CANCELLED

# Content
objectives               # JSON — [{objective, kpi, target, weight, outstanding_threshold,
                         #          excellent_threshold, good_threshold, fair_threshold,
                         #          poor_threshold, parent_dept_goal, parent_mda_objective}]
competency_ids           # JSON — [{competency_id, is_priority, is_development_focus, target_proficiency}]
development_plan         # Text

# Signatures
employee_signed_date     # Date
supervisor_signed_date   # Date
countersigner_id         # UUID FK → employee (HoD)
countersigner_date       # Date

# Amendments
amended_from_id          # UUID FK → self
amendment_reason         # Text
```

**Rules:**
- 3–7 objectives, weights must sum to 70
- Must be signed by 3rd week of January
- If employee refuses to sign, valid when counter-signed by HoD
- New contract required within 30 days of promotion/transfer/secondment
- Changes to signed contract require new version (amendment chain)

### 3b. MonthlyReview

Lightweight Performance Review Form (PRF).

```python
review_id                # UUID PK
organization_id          # UUID FK
employee_id              # UUID FK → employee
reviewer_id              # UUID FK → employee
contract_id              # UUID FK → performance_contract
review_month             # Date (1st of month)
status                   # Enum: DRAFT, SUBMITTED, ACKNOWLEDGED

objective_progress       # JSON — [{objective_index, progress_note, on_track: bool}]
challenges               # Text
support_required         # Text
reviewer_feedback        # Text
agreed_actions           # Text

employee_signed_date     # Date
reviewer_signed_date     # Date
```

**Rules:** Monthly, first week of each month. Progress-focused, not scoring. One per employee per month.

### 3c. PerformanceImprovementPlan (PIP)

```python
pip_id                   # UUID PK
organization_id          # UUID FK
employee_id              # UUID FK → employee
supervisor_id            # UUID FK → employee
hr_officer_id            # UUID FK → employee
appraisal_id             # UUID FK → appraisal (triggering)
pip_code                 # String(30)
status                   # Enum: DRAFT, ACTIVE, UNDER_REVIEW, IMPROVED, EXTENDED, ESCALATED, CLOSED

start_date               # Date
end_date                 # Date (max 6 months from start)
reason                   # Text
cause_category           # Enum: CLARITY, SKILLS, COMMITMENT, HEALTH, PERSONAL

improvement_areas        # JSON — [{area, current_level, expected_level, actions, timeline}]
support_measures         # Text
review_intervals         # JSON — [{date, notes, progress_status}]

# Extension (max one, 3 months)
extension_granted        # Boolean
extension_end_date       # Date
extension_reason         # Text

# Outcome
outcome                  # Enum: SATISFACTORY, UNSATISFACTORY (nullable)
outcome_date             # Date
outcome_notes            # Text
completion_letter_issued # Boolean

# Escalation
escalation_action        # String — DISCIPLINARY, TRANSFER, EXTENDED
committee_referral_date  # Date
committee_decision       # Text
```

**Rules:** Max 6 months, one extension of max 3 months. Triggered when employee rated Fair in ≥50% of KPIs or 3 quarterly assessments below threshold. Escalation links to existing discipline module.

### 3d. AppraisalAppeal

```python
appeal_id                # UUID PK
organization_id          # UUID FK
appraisal_id             # UUID FK → appraisal
employee_id              # UUID FK → employee (appellant)
status                   # Enum: FILED, UNDER_MEDIATION, REFERRED_TO_COMMITTEE, RESOLVED, DISMISSED

filed_date               # Date (within 5 working days of appraisal)
reason                   # Text
requested_outcome        # Text

# Mediation
mediator_id              # UUID FK → employee
mediation_date           # Date
mediation_outcome        # Text
mediation_resolved       # Boolean

# Committee
committee_referral_date  # Date
committee_hearing_date   # Date
committee_decision       # Enum: UPHELD, PARTIALLY_UPHELD, DISMISSED
committee_notes          # Text
adjusted_rating          # Integer (new rating if changed)

# Resolution
resolution_date          # Date (must be by Feb 28)
resolution_notes         # Text
communicated_date        # Date
```

**Timeline:** Filed within 5 working days → Jan 31 collation → Week 1-2 Feb mediation → Week 3 Feb committee → Week 4 Feb communicate. All resolved by Feb 28.

### 3e. InstitutionalPerformance

MDA/Department-level scoring on 8 weighted criteria.

```python
inst_perf_id                   # UUID PK
organization_id                # UUID FK
cycle_id                       # UUID FK → appraisal_cycle (annual)
department_id                  # UUID FK → department (null = org-wide)
institution_type               # Enum: MINISTRY, REGULATORY, GENERAL_SERVICES,
                               #        INFRASTRUCTURE, SECURITY, GOVT_COMPANY
status                         # Enum: DRAFT, UNDER_REVIEW, APPRAISED, RECONCILED, COMPLETED

criteria_scores                # JSON — [{criteria, weight, target, achievement,
                               #          raw_score, weighted_score}]
composite_score                # Numeric(5,2)
rating_label                   # String(50)

reviewed_by_id                 # UUID FK → employee
review_date                    # Date
notes                          # Text

# Reconciliation (Section 5.12)
is_reconciled                  # Boolean
pre_reconciliation_composite   # Numeric(5,2)
reconciled_by_id               # UUID FK → employee
reconciliation_date            # Date
reconciliation_notes           # Text
```

### 3f. InstitutionalCriteriaTemplate

Default weight configurations per institution type.

```python
template_id              # UUID PK
organization_id          # UUID FK
institution_type         # Enum (same as InstitutionalPerformance)
criteria_name            # String(100)
default_weight           # Integer (0-100)
sequence                 # Integer
is_active                # Boolean
```

### 3g. CompetencyAssessment

Links OHCSF competency framework to appraisals.

```python
assessment_id            # UUID PK
organization_id          # UUID FK
appraisal_id             # UUID FK → appraisal
competency_id            # UUID FK → competency
is_priority              # Boolean (one of top 5)
is_development_focus     # Boolean (one of 3 for development)
target_proficiency       # Integer (1-5)
self_rating              # Integer (1-5)
manager_rating           # Integer (1-5)
final_rating             # Integer (1-5)
evidence                 # Text (required if Greatly Exceeds or Exceeds)
```

### 3h. StrategicObjective

Goal cascade: MDA objectives → Department goals → Employee KPIs.

```python
objective_id             # UUID PK
organization_id          # UUID FK
cycle_id                 # UUID FK → appraisal_cycle (annual)
department_id            # UUID FK → department (null = MDA-wide)
parent_objective_id      # UUID FK → self (hierarchy)
objective_code           # String(30) — "SO-2026-001"
description              # Text
source_document          # String(200) — "National Dev Plan", "MDA Strategic Plan"
target_description       # Text
weight                   # Numeric(5,2)
sequence                 # Integer
```

KPI model extended with `institutional_objective_id` FK for traceability.

### 3i. AppraisalOutcomeAction

Audit trail from appraisal → HR decision.

```python
action_id                # UUID PK
organization_id          # UUID FK
appraisal_id             # UUID FK → appraisal
action_type              # Enum: REWARD, PIP, TRAINING, TRANSFER, PROMOTION,
                         #        DEMOTION, REMOVAL, COUNSELING
description              # Text
actioned_by_id           # UUID FK → employee
actioned_date            # Date
reference_id             # UUID (generic FK to PIP, training, lifecycle event)
reference_type           # String — "pip", "training_event", "lifecycle_event"
status                   # Enum: PENDING, COMPLETED, CANCELLED
notes                    # Text
```

---

## 4. Rating Scale

```python
OHCSF_RATING_SCALE = {
    5: {"label": "Outstanding", "percentage": 100},
    4: {"label": "Excellent",   "percentage": 90},
    3: {"label": "Good",        "percentage": 80},
    2: {"label": "Fair",        "percentage": 70},
    1: {"label": "Poor",        "percentage": 60},
}
```

### Competency Rating Labels

```python
OHCSF_COMPETENCY_SCALE = {
    5: "Greatly Exceeds Expectations",
    4: "Exceeds Expectations",
    3: "Meets Expectations",
    2: "Occasionally Meets Expectations",
    1: "Unsatisfactory",
}
```

---

## 5. Business Rules

### Weight Validation
- Objective weights must sum to **70** (MDA distributes freely among 3-7 objectives)
- Competency weight is **20** (fixed by OHCSF, distributed among 3 selected competencies)
- Process weight is **10** (fixed by OHCSF)

### Cascade-Up Rule
A supervisor's appraisal cannot proceed to `SELF_ASSESSMENT` until ALL their direct reports' appraisals for that cycle are `COMPLETED`.

### Sequencing Gate
Individual PerformanceContracts cannot be created until InstitutionalPerformance for that cycle and department has goals defined (status beyond DRAFT).

### 30-Day Contract Requirement
New/transferred/promoted employees must have active PerformanceContract within 30 days of status change.

### Underperformance Detection (Two Triggers)
1. **Annual:** Fair rating on ≥50% of KPIs in year-end appraisal
2. **Quarterly:** 3 quarterly appraisals with composite score below 70%

### 21-Month Probation Flag
Employees approaching 21 months of service flagged for final Progress Report with mandatory `confirmation_recommendation`.

### Approved Absence Rules
- ≤6 months absence → employee is appraised normally
- &gt;6 months absence → prior year rating carried forward (`is_prior_year_carryover`)

### Appeal Deadlines
- Filed within 5 working days of appraisal completion
- All cases resolved by February 28

### PIP Duration
- Maximum 6 months
- One extension of maximum 3 months
- Successful → HR issues completion letter
- Failed → Staff Committee referral, links to discipline module

---

## 6. Scoring Engine

### 3-Step OHCSF Composite Calculation

**Step 1 — Raw achievement score per KPI:** Compare actual achievement against KPI-specific thresholds. Interpolate linearly between threshold bands for precise percentage.

Formula: If actual falls between two adjacent thresholds (e.g., Fair=60, Good=70), the raw score is:
```
lower_pct + ((actual - lower_threshold) / (upper_threshold - lower_threshold)) × (upper_pct - lower_pct)
```

Example: Thresholds `{outstanding: 85, excellent: 80, good: 70, fair: 60, poor: 50}`, actual = 65.
- Falls between Fair(60)→70% and Good(70)→80%.
- Raw score = 70% + ((65-60)/(70-60)) × (80%-70%) = 70% + 5% = 75%.

**Step 2 — Weighted raw score:** `raw_score_percentage × weight`

**Step 3 — Composite score:** Sum all weighted raw scores.

**Final employee score:**
```
(objective_composite × 0.70) + (competency_composite × 0.20) + (process_score × 0.10)
```

---

## 7. Service Layer

### Service Organization

```
app/services/people/perf/
├── perf_service.py                   # existing — extended with OHCSF workflow
├── pms_config_service.py             # Feature flag activation, seeding
├── contract_service.py               # Performance contracts CRUD + signing
├── monthly_review_service.py         # PRF management
├── pip_service.py                    # PIP lifecycle
├── appeal_service.py                 # Appraisal appeals
├── institutional_service.py          # MDA/dept performance scoring
├── strategic_objective_service.py    # Goal cascade management
├── scoring_engine.py                 # OHCSF composite score calculation
├── underperformance_service.py       # Detection + flagging
├── ohcsf_reporting_service.py        # 11 mandatory reports
└── web/
    ├── contract_web.py
    ├── monthly_review_web.py
    ├── pip_web.py
    ├── appeal_web.py
    ├── institutional_web.py
    └── ohcsf_dashboard_web.py
```

### PMSConfigService

- `activate_ohcsf_pms(org_id)` — one-time setup: seeds 18 competencies (5 clusters), seeds 48 criteria templates (8 criteria × 6 institution types), seeds rating scale constants

### ScoringEngine

- `calculate_raw_score(actual, thresholds)` — Step 1: interpolate against per-KPI thresholds
- `calculate_weighted_score(raw_pct, weight)` — Step 2
- `calculate_composite(kpi_scores)` — Step 3: sum weighted raw scores
- `calculate_appraisal_final(obj, comp, proc)` — 70/20/10 formula
- `score_to_rating(composite_pct)` — map to Outstanding/Excellent/Good/Fair/Poor

### PerformanceContractService

- `create_contract()` — validates: flag enabled, dept goals exist (sequencing gate), 3-7 objectives, weights sum to 70, exactly 3 development competencies selected
- `sign_employee()`, `sign_supervisor()`, `countersign()`
- `amend_contract()` — creates new version linked via `amended_from_id`
- `check_30_day_requirement(org_id)` — find employees without active contract within 30 days of joining/transfer/promotion

### MonthlyReviewService

- `create_review()` — validates: active contract exists, one per employee per month, reviewer = reports_to_id
- `submit_review()`, `acknowledge_review()`
- `get_missing_reviews(org_id, cycle_id, month)` — compliance tracking

### Extended Appraisal Workflow (OHCSF mode)

OHCSF status transitions:
```
DRAFT → {SELF_ASSESSMENT, CANCELLED}
SELF_ASSESSMENT → {PENDING_REVIEW, DRAFT}
PENDING_REVIEW → {UNDER_REVIEW}
UNDER_REVIEW → {PENDING_COUNTERSIGN, SELF_ASSESSMENT}
PENDING_COUNTERSIGN → {COUNTERSIGNED}
COUNTERSIGNED → {PENDING_COMMITTEE}
PENDING_COMMITTEE → {COMPLETED}
```

- `submit_self_assessment_ohcsf()` — additional validation: all direct reports must have completed appraisals first (cascade-up rule)
- `submit_manager_review_ohcsf()` — uses ScoringEngine for per-KPI threshold scoring, calculates objective/competency/process composites
- `submit_countersign()`, `submit_committee_review()`
- `create_quarterly_appraisals(org_id, cycle_id, quarter)` — bulk-create for all employees with active contracts
- `calculate_annual_rating(org_id, cycle_id, employee_id)` — aggregates Q1-Q4 scores

### PIPService

- `create_pip()` — validates: end_date - start_date ≤ 6 months, HR officer assigned
- `grant_extension(pip_id, new_end_date, reason)` — max one extension, max 3 months
- `record_review()` — append to review_intervals JSON
- `complete_pip(outcome)` — SATISFACTORY → IMPROVED + completion letter; UNSATISFACTORY → ESCALATED + committee referral
- `escalate_to_committee()` — links to discipline module

### AppraisalAppealService

- `file_appeal()` — validates: within 5 working days, one per appraisal
- `assign_mediator()`, `record_mediation_outcome()`
- `record_committee_decision()` — UPHELD/PARTIALLY_UPHELD/DISMISSED, may adjust rating
- `get_overdue_appeals(org_id)` — not resolved by Feb 28

### InstitutionalPerformanceService

- `create_for_cycle()` — creates records per department from criteria templates
- `score_criteria()` — score 8 criteria, compute composite via ScoringEngine
- `reconcile_with_employee_ratings()` — saves pre-reconciliation score, applies adjustment

### StrategicObjectiveService

- `create_objectives()`, `cascade_to_department()`
- `get_cascade_tree(org_id, cycle_id)` — full hierarchy: MDA → dept → employee KPIs
- `get_alignment_report()` — coverage gaps, which objectives lack employee alignment

### UnderperformanceService

- `detect_annual_trigger()` — employees with Fair on ≥50% of KPIs
- `detect_quarterly_trigger()` — employees with 3 quarters below 70%
- `flag_for_pip()` — create draft PIP, notify HR and supervisor
- `check_probation_milestones()` — employees approaching 21 months

### OHCSFReportingService

11 mandatory reports (Section 5.11):
1. Rating summary (org-wide)
2. Rating by department
3. Rating by grade level
4. Percentage distribution (org-wide)
5. Percentage distribution by department
6. Percentage distribution by grade
7. Top N performers
8. Bottom N performers
9. L&D needs overview
10. L&D needs by department
11. L&D needs by department (granular)

Plus: `cycle_compliance_dashboard()` — contracts signed, reviews completed, appraisals done, appeals pending, PIPs active.

---

## 8. Celery Tasks

```
app/tasks/pms.py
```

| Task | Schedule | Purpose |
|------|----------|---------|
| `pms_monthly_review_reminder` | 1st of each month | Notify supervisors, flag missing reviews |
| `pms_quarterly_appraisal_reminder` | 1st week Apr/Jul/Oct/Dec | Notify for self-assessment and supervisor appraisal |
| `pms_contract_deadline_check` | Daily in January | Flag unsigned contracts past 3rd week deadline |
| `pms_underperformance_detection` | After each quarter closes | Detect both annual and quarterly triggers |
| `pms_probation_check` | Monthly | Flag employees at 18, 20, 21 months |
| `pms_appeal_deadline_check` | Weekly in Jan/Feb | Flag appeals approaching Feb 28 deadline |
| `pms_pip_review_reminder` | Weekly | Check PIP review_intervals for upcoming dates |

---

## 9. Web Routes & Templates

### Route Structure

All under existing `/people/perf/` prefix, gated by `pms_ohcsf_enabled`:

```
/people/perf/pms/dashboard              # Compliance dashboard
/people/perf/pms/contracts              # List, new, detail, edit
/people/perf/pms/reviews                # Monthly reviews
/people/perf/pms/pips                   # PIPs
/people/perf/pms/appeals                # Appeals
/people/perf/pms/institutional          # MDA/dept performance
/people/perf/pms/objectives             # Strategic objectives cascade
/people/perf/pms/reports                # 11 mandatory reports hub
/people/perf/pms/reports/{report_type}  # Individual report views
```

### Sidebar Integration

When enabled, People sidebar (violet, `base_people.html`) adds collapsible "PMS (OHCSF)" section:

```
PMS (OHCSF)
  ├─ Dashboard
  ├─ Contracts
  ├─ Monthly Reviews
  ├─ Institutional Performance
  ├─ Strategic Objectives
  ├─ PIPs
  ├─ Appeals
  └─ Reports
```

### Key Pages

**PMS Dashboard** — 4 stat cards (contracts signed, reviews completed, appraisals status, appeals/PIPs), cycle timeline chart, rating distribution chart, compliance alerts table.

**Performance Contract Detail** — workflow stepper, document card with strategic alignment, objectives table with per-KPI criteria thresholds, competency selections, development plan, signature tracking, linked monthly reviews and quarterly appraisals.

**Quarterly Appraisal (OHCSF)** — extended workflow stepper (7 steps), per-KPI threshold scoring table, competency scoring section, process scoring section, composite score breakdown, counter-signer section, committee review section, debrief record, appeal button (within 5-day window).

**PIP Detail** — status banner, improvement areas from JSON, review timeline, outcome section, links to triggering appraisal and discipline case.

**Strategic Objectives Cascade** — tree view (collapsible, indented like Trial Balance), MDA → department → employee KPIs, alignment summary showing coverage gaps.

### Template Reuse

All pages use existing macros (`topbar`, `live_search`, `status_badge`, `empty_state`, `stats_card`, `bulk_action_bar`, `pagination`). No new components required.

New status badge mappings: PENDING_SIGNATURE (amber), PENDING_COUNTERSIGN (amber), COUNTERSIGNED (blue), PENDING_COMMITTEE (blue), UNDER_MEDIATION (blue), REFERRED_TO_COMMITTEE (amber), IMPROVED (emerald), ESCALATED (rose), EXTENDED (amber), FILED (amber).

---

## 10. Migrations

### Migration 1: Extend Existing Models

`alembic/versions/20260328_pms_extend_existing_models.py`

- Organization: add `pms_ohcsf_enabled`
- AppraisalCycle: add `cycle_type`, `parent_cycle_id`, `quarter`
- Appraisal: add counter-signing, committee, process scoring, composite breakdown, absence carryover, probation, secondment, debrief, reward fields (all nullable)
- AppraisalKRAScore: add per-KPI thresholds, achievement, evidence fields
- AppraisalStatus enum: add `PENDING_COUNTERSIGN`, `COUNTERSIGNED`, `PENDING_COMMITTEE`

### Migration 2: Create New Tables

`alembic/versions/20260328_pms_create_new_tables.py`

9 new tables: `performance_contract`, `monthly_review`, `performance_improvement_plan`, `appraisal_appeal`, `institutional_performance`, `institutional_criteria_template`, `competency_assessment`, `strategic_objective`, `appraisal_outcome_action`.

Plus: add `institutional_objective_id` FK on `kpi` table.

### Migration 3: Seed Data

`alembic/versions/20260328_pms_seed_ohcsf_data.py`

- 48 institutional criteria templates (8 criteria × 6 institution types)
- Weight tables per institution type from OHCSF guidelines

### Rollout Plan

1. Run migrations (all nullable columns, new tables, inserts only — zero risk to existing data)
2. Deploy code with flag defaulting to `false` (no UI visible)
3. Admin enables on test org → `PMSConfigService` seeds competencies and templates
4. Validate full cycle on test org
5. Enable for production orgs (controlled per-org rollout)

---

## 11. Seed Data

### OHCSF Competencies (18)

| Cluster | Competencies |
|---------|-------------|
| Ethics & Values | Commitment, Integrity, Inclusiveness, Courage |
| People | Collaborating & Partnering, Effective Communication, Managing & Developing People |
| Execution | Drive for Results, Transparency & Accountability, Value for Money |
| Vision | Effective Decision Making, Strategic Thinking, Embracing & Managing Change |
| Expertise | Policy Management, Citizen Focus, Information & Records Management, Adoption & Use of Technology, Specialist Competencies |

### Institutional Criteria Weights

| Criteria | Ministry | Regulatory | General Svc | Infrastructure | Security | Govt Company |
|----------|----------|------------|-------------|----------------|----------|--------------|
| Government prioritized objectives | 25 | 25 | 20 | 25 | 20 | 25 |
| MDA Operational Objectives | 25 | 25 | 20 | 20 | 25 | 25 |
| Stakeholder Engagement | 10 | 10 | 5 | 5 | 5 | 5 |
| Service Innovation & Improvement | 10 | 10 | 20 | 15 | 10 | 10 |
| Automated Service Delivery | 10 | 10 | 15 | 15 | 5 | 15 |
| Capacity Building & Talent Mgmt | 5 | 5 | 5 | 5 | 10 | 5 |
| Support for Service Delivery | 10 | 10 | 10 | 10 | 10 | 10 |
| Staff Welfare | 5 | 5 | 5 | 5 | 5 | 5 |

---

## 12. Scope Summary

| Category | Count |
|----------|-------|
| Extended existing models | 3 (Organization, AppraisalCycle, Appraisal + AppraisalKRAScore) |
| New models | 9 |
| New services | 11 |
| New web services | 6 |
| New Celery tasks | 7 |
| New routes | ~20 |
| New template pages | ~15 |
| Alembic migrations | 3 |
| Mandatory reports | 11 |
| New status badge mappings | 10 |
| Seed data sets | 2 (18 competencies, 48 criteria templates) |
