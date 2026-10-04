# Sherpackage: Digital Marketer Hiring Pack

Prepared 4 October 2026. User-confirmed terms: **full-time, Abuja**.

## Opening

- Title: Digital Marketer
- Company: Sherpackage
- Location: Abuja, Nigeria; remote/hybrid arrangements are not promised
- Department: Marketing & Growth (proposed)
- Reports to: Chief Executive Officer through the position hierarchy (proposed)
- Vacancies: one
- Salary: undisclosed; no invented range or benefits
- Closing date: not set
- Job code: `SHP-DM-2026-001`
- Position: `SHP-DIGITAL-MKT`
- Appraisal template: `SHP-DM-90DAY`

The full candidate-facing advertisement is in
`scripts/data/sherpackage_digital_marketer.txt`. It includes responsibilities,
essential and preferred skills, education alternatives, application materials,
selection stages, and first-90-day expectations. The file ships with the seed;
it is not under the Docker-excluded `docs` directory.

## Requirements

Two years of practical campaign experience or comparable demonstrable campaign
ownership; strong English copywriting; SEO and content planning; social and email
marketing; paid-campaign and budget management; GA4 and conversion tracking;
spreadsheet reporting; CRM lead handover; clear stakeholder communication.

Software/SaaS experience, campaign-platform experience, Tag Manager, Search
Console, marketing automation, design/video skills, and responsible AI use are
preferred. A relevant qualification is welcome, but equivalent experience and
a strong portfolio are accepted. Salary and working arrangements still need
confirmation with candidates; the pack does not invent contractual commitments.

## Proposed KPI Plan

These are **proposed targets for a 90-day measurement period**, not employee
results or market benchmarks. Confirm audience, baseline, available budget,
sales capacity, attribution rules, and resourcing before assigning them. Do not
retroactively change an agreed target just to produce a desired rating.

| KRA | KPI | Proposed target | Weight |
| --- | --- | ---: | ---: |
| Qualified demand generation | Sales-accepted marketing leads | 30 | 30% |
| Pipeline contribution | Completed marketing-sourced product demos | 12 | 20% |
| Content and organic discovery | Approved original content assets published | 12 | 15% |
| Campaign delivery | Approved milestones delivered on time | 90% | 15% |
| Measurement and attribution | Live campaigns passing tracking checks | 100% | 10% |
| Experimentation and learning | Documented experiments completed | 3 | 10% |

Definitions and evidence requirements are stored on the six KRAs and on employee
KPIs when assigned. Leads must be distinct and accepted by sales against agreed
fit/need criteria. Demos must actually occur. Content excludes duplicate
cross-posts. Experiments need a hypothesis, observations, and a documented
decision, not necessarily a positive result.

For delivery, calculate on-time completed milestones / milestones due x 100.
For tracking, calculate passing campaigns / campaigns audited x 100. A zero
denominator is **not applicable**, not 100%; leave the actual unset and discuss
it with the manager. For counts, enter the cumulative total. For percentages,
enter `90`, not `0.90`.

All six seeded metrics are higher-is-better, matching the current scoring logic.
Cost per lead, acquisition cost, spend, and return on ad spend should still be
reviewed in marketing reports, but are not forced into an incompatible KPI
formula. Paid spend always requires an agreed budget.

## 30/60/90-Day Plan

| Period | Deliverables | Evidence |
| --- | --- | --- |
| Days 1-30 | Product/audience research; channel and tracking audit; baseline report; agreed lead definition; content plan; approved campaign budget | Audit, baseline dashboard, manager-approved plan |
| Days 31-60 | Approved campaigns launched; content published; landing-page/message tests; working CRM handover; weekly reports | Live URLs, campaign/tag checks, CRM records, reports |
| Days 61-90 | Optimisation based on results; completed experiments; verified pipeline contribution; next-quarter plan | Experiment summaries, demo records, reconciliation to source data |

The manager should agree whether formal KPI measurement starts on joining or
after the setup period. The script requires explicit dates and does not assume
today is the employee's start date. Review progress weekly, discuss it monthly,
and complete the appraisal at the end of the agreed period.

## Interview Rubric

Use the same job-related questions and a 1-5 evidence-based rating for candidates.
Keep this interview rubric separate from the employee performance template.

| Assessment area | Weight | Evidence to request |
| --- | ---: | --- |
| B2B strategy and audience understanding | 20% | Audience, proposition, funnel, channel rationale |
| Campaign execution and commercial results | 25% | Candidate's actual role, spend context, qualified outcomes |
| Analytics, attribution, and experimentation | 20% | Tracking validation, interpretation, experiment decisions |
| Content and communication | 20% | Two relevant writing/creative examples with rationale |
| Planning, collaboration, and responsible practice | 15% | Prioritisation, handovers, privacy, accurate claims |

Suggested questions:
1. Walk through a campaign: audience, objective, your work, measurement, result,
   and what you would change. How did you distinguish activity from business value?
2. How would you market a software product to a clearly defined business audience?
3. How would you check whether a lead source and conversion event are reliable?
4. What would you do if clicks increased but sales rejected most leads?
5. Describe an experiment that did not work and what you learned.
6. How do you use AI tools without leaking customer data or publishing false claims?

Exercise: a 45-minute hypothetical brief for a software demo campaign. Request
a short audience/message/channel plan, one ad or social post, a landing-page
outline, and measurement suggestions. Do not request unpaid live campaigns or
confidential previous-client data. Humans make shortlisting and hiring decisions.

## Database Application

No live database is connected to this workspace. Preparing and testing these
files does **not** mean the job is posted. Nothing was added to automatic startup
seeding, so an ordinary restart will not publish this vacancy.

Run from an app environment with its normal database configuration and the new
script plus its `scripts/data` text file present:

```sh
# Preview the full package and publication, with all writes rolled back:
python scripts/seed_sherpackage_digital_marketer.py --dry-run --publish

# Save a draft for HR review:
python scripts/seed_sherpackage_digital_marketer.py

# Publish the draft when ready:
python scripts/seed_sherpackage_digital_marketer.py --publish
```

Use `--organization-id UUID` to select an exact Sherpackage organization. The
script refuses a different organization code or non-private performance mode,
requires the existing `SHP-CEO` position, and uses tenant-scoped transactions.
It adds a department, designation, vacant position, six KRAs, a weighted template,
and one opening. It creates no employees, applicants, fake reviews, or notifications.

Publication changes the opening to OPEN using the existing recruitment service.
The app's careers route, when enabled and the org slug is `sherpackage`, is
`/careers/sherpackage/jobs/SHP-DM-2026-001`. It does not post to LinkedIn, Indeed,
or other external job boards. Existing edited records are retained; closed,
cancelled, held, or filled jobs are not reopened by rerunning the command.

After hiring and assigning the employee to the Digital Marketer position in HR,
create six draft KPIs using an explicitly agreed 90-day period. Example dates
only; replace them with the employee's actual agreed period:

```sh
python scripts/seed_sherpackage_digital_marketer.py --employee-code SHP-0006 --period-start 2026-11-01 --period-end 2027-01-29
```

No actual values, achievement percentages, or ratings are fabricated. Review
targets under Goals & KPIs before activation. Create the employee's appraisal
in the appropriate real review cycle using `SHP-DM-90DAY`; no dummy cycle or
appraisal is created. The interview rubric and onboarding plan above are a guide,
not fabricated interviews or completed onboarding tasks in the database.

Existing KPI screen limitations still apply: progress Notes/Evidence have a known
save-handler mismatch; achieved KPIs hide editing; scoring does not understand
lower-is-better metrics or elapsed-time pacing. These require a separate fix.
Keep evidence in the team's existing records until those issues are addressed.
