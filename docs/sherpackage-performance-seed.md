# Sherpackage Performance Seed

The Sherpackage startup seed now adds a position hierarchy and private-sector
performance examples. It keeps the existing five employees; unfilled positions
remain vacant. No login accounts, invitations, or notifications are created.

## Included Data

For an unchanged five-employee Sherpackage seed:

| Records | Count |
| --- | ---: |
| Positions (5 occupied, 7 vacant) | 12 |
| Designations (including the original 8) | 12 |
| Role-specific quarterly review templates | 12 |
| Key result areas (3 per template, weights total 100%) | 36 |
| Sample review cycles | 2 |
| Employee KPIs | 30 |
| Appraisals with KRA scores | 8 |
| Peer feedback entries (4 submitted, 4 pending) | 8 |
| Scorecards with metric items | 10 |

Positions cover executive leadership, engineering leadership, product management,
DevOps, people/finance, software engineering, QA, design, frontend, backend, data,
and security. Templates and KRAs link to each role's designation and department.

The fixed sample periods are 2026 Q2 (completed) and 2026 Q3 (active). Sample
cycles, goals, feedback, scorecards, and appraisal summaries are labelled as
examples, not real employee evaluations. Reports calculate their results from
these records; there is no separate report seed. Date filters may need to include
2026. Rerunning does not advance deadlines or create another year's cycles.

Appraisal reviewers come from the position hierarchy. The CEO has no supervisor,
so no CEO appraisal or self-review is fabricated. Staff with changed designations,
inactive status, or no resolvable reviewer may produce fewer sample records.

## Deployment

Redeploy the updated repository in Coolify. With `SEED_SHERPACKAGE_ON_START=true`
(the existing default), the entrypoint runs migrations and the Sherpackage seed.
Restarting an old container does not fetch the updated scripts.

To add just the positions and performance data to an existing Sherpackage
organization, run this inside the deployed app container:

```sh
python scripts/seed_sherpackage_performance.py
```

This command uses the container's existing database configuration. It does not
create an organization, attach the admin, or create/reset employees. It requires
organization code `SHP`, private performance mode, and the existing Sherpackage
departments. It resolves `SHERPACKAGE_ORGANIZATION_ID` or the existing `SHP` code.

Check the printed organization ID and added-record counts, then select Sherpackage
in the app. Positions are under HR; the screenshot's categories are under
Performance (Private). Permissions are unchanged by this seed.

## Repeat Runs

The new records use tenant-scoped lookups and stable seed IDs. PostgreSQL startup
replicas serialize the performance seed with a transaction advisory lock. The
performance seed commits once; a failure rolls back its transaction.

Reruns do not reset ratings, comments, template weights, employee personal details,
pay, status, or existing position assignments. The base Sherpackage seed now also
leaves existing organization details and HR catalog values intact. Existing admin
attachment behavior in the base seed is unchanged; use the standalone performance
command to avoid it.

Back up the database before deployment. Although clearly labelled, completed sample
evaluations contribute to performance reports. They are demonstration data, not
evidence for real staffing or compensation decisions.
