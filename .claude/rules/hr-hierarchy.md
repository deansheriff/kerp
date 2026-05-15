# HR Hierarchy — Source of Truth

The HR reporting hierarchy lives in **positions and position assignments**, not on `Employee`. Resolve it through `OrgResolver`.

## Use `OrgResolver` for every "who is X's manager / who reports to X / approval chain" question

```python
from app.services.people.hr.org_resolver import OrgResolver

resolver = OrgResolver(db)
manager = resolver.get_manager(employee_id, organization_id)
reports = resolver.get_direct_reports(manager_id, organization_id)
chain = resolver.get_approval_chain(employee_id, organization_id)
```

`OrgResolver` walks the position tree, applies the documented vacancy policy
(PRIMARY > ACTING > INTERIM, rolls up past empty seats), supports historical
`as_of` resolution, and protects against cycles.

## Do NOT read `Employee.reports_to_id` for hierarchy decisions

`Employee.reports_to_id` is a legacy column kept for ERPNext sync compatibility:
- **ERPNext sync writes it** (`app/services/erpnext/sync/hr.py`) as inbound
  HR data lands.
- **`PositionService.reconcile_from_reports_to_id()`** bridges those writes
  into the canonical position tree.
- Reading it directly will give the wrong answer when positions disagree
  (which they routinely will once a position is created or moved).

If you find code reading `reports_to_id` for routing, that code is wrong.
Replace it with an `OrgResolver` call.

## Canonical organogram URL

`/people/hr/org-chart` renders the position-based tree (incumbents, vacancies,
covering assignments). The old URLs `/people/hr/employees/org-chart` and
`/people/hr/positions/tree` 301-redirect here.

## One `OrgChartNode`, in `positions.py`

```python
from app.services.people.hr.positions import OrgChartNode
```

There is no `OrgChartNode` at the package root. The dataclass keyed by
`employee_id` was removed — render employees as a *view* of the position
tree, not as a parallel structure.
