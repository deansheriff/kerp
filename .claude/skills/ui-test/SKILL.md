---
name: ui-test
description: "Run Playwright-based UI/UX tests against the live ERP app — visual checks, accessibility, design system compliance, design quality review, and functional flows"
arguments:
  - name: target
    description: "What to test: a URL path (e.g. '/finance/ar/invoices'), a module name (e.g. 'finance', 'people'), a page type (e.g. 'list', 'detail', 'form', 'dashboard'), or 'full' for all modules"
---

# UI/UX Test — Kxmeleon ERP

This extends the global `ui-test` skill with DotMac-specific rules. Follow ALL steps from the global skill, plus the DotMac-specific checks below.

## DotMac App Config

- **Production**: `http://localhost:8003` (try first)
- **Dev**: `http://localhost:8002` (fallback)
- **Login**: `/login` — Alpine.js fetch-based form. Use `browser_type` per field (not `browser_fill_form`). Supports MFA.
- **Health check**: `GET /health` returns `{"status":"ok"}`

## Module URL Map

When `$ARGUMENTS` is a module name, test these pages:

| Module | Dashboard | Key List Pages |
|--------|-----------|----------------|
| `finance` | `/finance/` | `/finance/gl/accounts`, `/finance/ar/invoices`, `/finance/ap/invoices` |
| `people` | `/people/` | `/people/hr/employees`, `/people/leave/requests` |
| `expense` | `/expense/` | `/expense/claims` |
| `inventory` | `/inventory/` | `/inventory/items`, `/inventory/warehouses` |
| `procurement` | `/procurement/` | `/procurement/purchase-orders` |
| `public-sector` | `/public-sector/` | `/public-sector/funds`, `/public-sector/warrants` |
| `admin` | `/admin/` | `/admin/users`, `/admin/organizations` |
| `operations` | `/modules/` | `/modules/projects`, `/modules/tickets` |
| `full` | All dashboards | One list page per module + click first item for detail |

## DotMac-Specific Design System Checks

Run these ADDITIONAL checks via `browser_evaluate` on every page, alongside the global quality checks:

```javascript
(function() {
    const issues = [];

    // 1. Financial values MUST use font-mono tabular-nums
    document.querySelectorAll('td, th, span, div').forEach(el => {
        if (el.textContent.match(/₦\s*[\d,]+\.?\d*/) && el.children.length === 0) {
            if (!(el.className || '').includes('font-mono') && !el.closest('.font-mono')) {
                issues.push({rule: 'financial-font', text: el.textContent.trim().slice(0, 40), fix: 'Add font-mono tabular-nums'});
            }
        }
    });

    // 2. Status badges MUST use the status_badge() macro (outputs .badge class)
    document.querySelectorAll('span').forEach(el => {
        const text = el.textContent.trim();
        if (text.match(/^(DRAFT|PENDING|APPROVED|REJECTED|PAID|OPEN|CLOSED|ACTIVE|INACTIVE|OVERDUE|SUBMITTED|POSTED|VOIDED|CANCELLED|PROCESSING)$/i)) {
            if (!el.classList.contains('badge') && !el.closest('.badge')) {
                issues.push({rule: 'use-status-badge-macro', text: text, fix: 'Use {{ status_badge(status) }}'});
            }
        }
    });

    // 3. CSRF field name is specifically "csrf_token"
    document.querySelectorAll('form[method="POST" i]').forEach(f => {
        if (!f.querySelector('input[name="csrf_token"]') && !document.querySelector('meta[name="csrf-token"]')) {
            issues.push({rule: 'missing-csrf-token', form: f.getAttribute('action') || '(inline)', severity: 'P0'});
        }
    });

    // 4. results-container required on list pages
    if (document.querySelector('.table-container') && !document.querySelector('#results-container')) {
        issues.push({rule: 'missing-results-container', fix: 'Wrap table+pagination in <div id="results-container">'});
    }

    // 5. Empty state uses .empty-state class (from macros.html)
    const rc = document.querySelector('#results-container');
    if (rc) {
        const hasRows = rc.querySelector('tbody tr');
        const hasEmpty = rc.querySelector('.empty-state') || rc.parentElement?.querySelector('.empty-state');
        if (!hasRows && !hasEmpty) {
            issues.push({rule: 'missing-empty-state', fix: 'Add {% else %} with {{ empty_state() }} macro'});
        }
    }

    // 6. Negative amounts must use parentheses (₦ required to avoid invoice number false positives)
    document.querySelectorAll('.font-mono, [class*="tabular"]').forEach(el => {
        if (el.textContent.match(/-\s*₦\s*[\d,]+\.?\d*/) && !el.textContent.match(/^[A-Z]{2,}/)) {
            issues.push({rule: 'negative-parentheses', text: el.textContent.trim().slice(0, 30), fix: 'Use (1,234.56) not -1,234.56'});
        }
    });

    // 7. Display font should be Fraunces on h1
    const h1 = document.querySelector('h1, .font-display');
    if (h1 && !getComputedStyle(h1).fontFamily.toLowerCase().includes('fraunces')) {
        issues.push({rule: 'missing-display-font', font: getComputedStyle(h1).fontFamily, fix: 'Add font-display class to h1 (Fraunces)'});
    }

    // 8. Sidebar module accent — active link should have aria-current="page"
    if (!document.querySelector('[aria-current="page"]')) {
        issues.push({rule: 'no-active-nav', fix: 'Add aria-current="page" to active sidebar link'});
    }

    return JSON.stringify({total: issues.length, issues: issues});
})()
```

## DotMac Design Quality Grading (extends global)

The global skill grades A/B/C/D. For DotMac, also check:

| Signal | What to look for |
|--------|-----------------|
| **Fraunces display font** | h1 should use `font-display` class → Fraunces serif |
| **Module accent color** | Sidebar and buttons use module color: teal (finance), violet (people), amber (expense), emerald (inventory), blue (procurement), cyan (public-sector) |
| **Status badge macro** | All status text uses `.badge` wrapper with mapped colors |
| **Stat cards macro** | Dashboard stat cards use `.stats-card` with trend indicators |
| **Dark mode pairs** | Every `bg-white` has `dark:bg-slate-800`, every `text-slate-900` has `dark:text-white` |
| **None handling** | `{{ var if var else '' }}` not `{{ var | default('') }}` — no raw "None" in output |

## DotMac Functional Checks (extends global)

For **list pages** also check:
- `live_search()` macro used (HTMX `hx-get` targeting `#results-container`)
- `bulk_action_bar()` present (fixed bottom bar with Export)
- `sortable_th()` macro on column headers

For **form pages** also check:
- `*_form_context()` method pattern — context banner if prefilled from parent entity
- Form actions: Cancel (left, `btn-secondary`) + Save (right, `btn-primary`)

For **detail pages** also check:
- Workflow stepper for multi-step entities
- Related entities section
- Activity/audit timeline
- Print button for document entities (invoices, receipts, journals)

For **dashboard pages** also check:
- 4 stat cards minimum with trend indicators
- Charts (Chart.js canvas elements)
- Recent items table
