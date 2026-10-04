# AI Workflows

AI assistance is opt-in per organization. All interactive outputs are drafts;
they never create jobs, change ratings, update tickets or send replies automatically.
The existing forms, permissions and approval workflows remain authoritative.

## Available Workflows

| Location | Assistance | Required permissions, in addition to module access |
| --- | --- | --- |
| Recruitment job forms/details | Job description, requirements, interview questions and weighted proposed KPIs | `recruit:openings:create` or `recruit:openings:update`; existing openings also require `recruit:openings:read` |
| Performance KPI form | Targets, measurement formulas and evidence requirements | `perf:kpis:manage` |
| Appraisal details/manager review | Cited summaries of recorded KPI and KRA evidence; no AI ratings | `perf:appraisals:review` plus `perf:appraisals:read`, or `perf:appraisals:read_team` as the assigned manager |
| Company knowledge, `/ai?workflow=knowledge` | Answers from accessible handbook/policy excerpts, with source links | `selfservice:documents:read` or `hr:employees:read`; non-admin users must be active employees |
| Support ticket details | Suggested category, priority and reply | `support:tickets:read` and `support:tickets:update` |

Review and transfer draft text to the original form before saving. Appraisal
ratings must be assigned and approved by people through the existing review flow.
AI buttons open separately so unsaved work in the original form is preserved.

The same LLM layer also provides optional explanations for all 11 active daily
Coach domains and the weekly finance and HR reports. Deterministic calculations,
severities and recommended actions are preserved. Provider failures leave the
original insights/reports usable. This is not autonomous execution of ERP actions.

## Gemini Setup

Install locked dependencies with `poetry install`. No new schema migration is
required for these features. In **Admin > Settings > Coach / AI**, configure:

1. Allowed providers: `gemini` (add other providers only when failover is intended).
2. Default provider: `gemini`.
3. Base URL: `https://generativelanguage.googleapis.com/v1beta/openai`.
4. Gemini API key and model identifiers available to your Google account.
5. Enable external AI processing after reviewing which data is sent below.

Gemini uses Google's documented [OpenAI-compatible API](https://ai.google.dev/gemini-api/docs/openai).
No fixed model identifier is assumed. The standard tier is used for interactive
drafts; missing tier models fall back to another configured tier on that provider.
Settings require `settings:manage` and the existing admin-area authorization.
Blank API-key fields preserve existing keys; key values are never rendered.
Organization settings override global settings and environment defaults.

Alternatively configure environment defaults for both the web app and workers:

```dotenv
COACH_AI_ENABLED=true
COACH_LLM_BACKENDS=gemini
COACH_LLM_DEFAULT_BACKEND=gemini
COACH_LLM_GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
COACH_LLM_GEMINI_API_KEY=<set securely>
COACH_LLM_GEMINI_MODEL_FAST=<your model>
COACH_LLM_GEMINI_MODEL_STANDARD=<your model>
COACH_LLM_GEMINI_MODEL_DEEP=<your model>
COACH_LLM_MAX_OUTPUT_TOKENS=4096
COACH_MONTHLY_TOKEN_BUDGET=500000
```

Redis is required; interactive requests and external generation fail closed when
their shared limit/budget storage is unavailable. For scheduled explanations also
set `COACH_ENABLED=true` and run the configured Celery worker and Beat scheduler.
If `ENABLED_MODULES` is restricted, include `coach` to register the AI routes.
Build and redeploy the new application image. Restarting an old image will not
install these source changes or the new PDF dependency.

## Data and Safety Boundaries

- Permission and organization filtering happen before provider calls. Knowledge
  documents are additionally filtered by effective dates and department access
  before reading, ranking or sending text. Source links recheck current access.
- External providers receive the user's brief and selected record excerpts.
  Appraisals omit names, private anonymous feedback and existing ratings. Tickets
  include subject, description and the 10 latest active public comments, not
  contact fields or internal notes. Free text can still contain personal data;
  this is data minimization, not guaranteed anonymization.
- Daily/weekly Coach prompts contain numeric aggregates, not raw entity lists.
- Structured schemas reject unknown fields, invalid KPI weights and AI rating
  fields. Citations must reference an accessible source and quote its actual text.
  Quote validation proves provenance, not that every interpretation is correct.
- All outputs remain untrusted text and are HTML-escaped. CSRF is required for
  generation. Documents are treated as untrusted data in prompts. The model has
  no tool execution or record-writing interface.
- Redis caches outputs, isolated by organization and prompt/schema, for the
  configured TTL (24 hours by default). Protect Redis like other sensitive data.
  Application logs record workflow/organization/actor/model, not prompts or keys.
- Interactive allowance: 20 requests per user/organization, reset after a quiet
  minute. Each external attempt reserves input UTF-8 bytes plus maximum output
  tokens and overhead against a shared organization/calendar-month allowance.
  Failed/repair attempts retain reservations. This conservative processing guard
  is not a provider billing meter or guaranteed monetary cap; also configure
  provider-side quotas. Redis counters must survive restarts for durable limits.

## Retrieval Limits

Knowledge search is keyword-based, not a vector index. It scans at most 100 active
documents and sends up to six matching excerpts. PDF extraction supports up to
30 pages, 50,000 characters and 5 MB; plain text/Markdown are supported too.
Unreadable, encrypted, scanned or unsupported documents contribute only their
title/description, explicitly marked in the result. No OCR, DOCX extraction,
external drive connector or evidence-link crawling is included.

Appraisal context is bounded to 20 KPIs fully contained in the review period and
12 KRA evidence records. Missing actual values remain unknown, never zero.
Review the complete appraisal before deciding ratings. Existing KPI progress
forms now persist the submitted evidence and notes used by this summary.

## Verification

Regression tests cover tenant/department isolation, role gates, CSRF, escaped
outputs, provider routing, configuration, source validation, no automatic record
changes and scheduled job integration. Local tests use SQLite and mocked provider
responses. Live PostgreSQL, Redis and a configured Gemini account still require
a staging smoke test; implementation alone does not activate production AI.

To repeat local visual QA with Chromium installed, run PowerShell:

```powershell
$env:AI_BROWSER_QA='1'
poetry run pytest tests/test_ai_web.py -k browser -o addopts='' -q
```

This exercises the real templates/forms with a mocked provider at mobile and
desktop sizes in light/dark themes. Screenshots are under
`.pytest_cache/ai-screenshots/`; it is not a production database smoke test.
