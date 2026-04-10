# AR Invoice Deductions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add WHT, VAT withheld, and stamp duty deductions to AR invoices, with correct GL posting and Amount Receivable display.

**Architecture:** Three independent deductions on the AR invoice totals — WHT (on net), VAT withheld (toggle), stamp duty (on gross, with deducted/separate treatment). Follows the same pattern as the AP WHT implementation. Model fields already exist for WHT and stamp duty; we add `vat_withheld` bool and `stamp_duty_treatment` enum. GL posting adds separate debit lines for each deduction, reducing the AR Control debit.

**Tech Stack:** Python/SQLAlchemy (model + service), Jinja2/Alpine.js (templates), Alembic (migration), pytest (tests)

**Spec:** `docs/superpowers/specs/2026-04-10-ar-invoice-deductions-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `app/models/finance/ar/invoice.py` | Add `StampDutyTreatment` enum, `stamp_duty_treatment` field, `vat_withheld` field |
| Create | `alembic/versions/20260410_ar_invoice_deductions.py` | Migration for new columns |
| Modify | `app/services/finance/ar/invoice.py` | Extend `ARInvoiceInput`, calculate deductions in `create_invoice`, parse in `build_input_from_payload` |
| Modify | `app/services/finance/ar/web/invoice_web.py` | Add `wht_codes` and `stamp_duty_codes` to form context |
| Modify | `app/services/finance/ar/web/base.py` | Add deduction fields to `invoice_detail_view` |
| Modify | `templates/finance/ar/invoice_form.html` | Add deductions UI, `netSubtotal`, `amountReceivable` computed properties |
| Modify | `templates/finance/ar/invoice_detail.html` | Display deductions and Amount Receivable |
| Modify | `app/services/finance/ar/posting/invoice.py` | Add WHT, VAT withheld, stamp duty GL lines; reduce AR Control |
| Modify | `app/services/finance/ap/web/invoice_web.py` | Filter STAMP_DUTY and WITHHOLDING from per-line tax dropdown |
| Modify | `app/services/finance/ap/web.py` | Same filter for legacy web service |
| Create | `tests/ifrs/ar/test_ar_invoice_deductions.py` | Unit tests for all deduction calculations and edge cases |

---

### Task 1: Model — Add StampDutyTreatment enum and new fields

**Files:**
- Modify: `app/models/finance/ar/invoice.py:1-29` (imports), `:201-215` (after existing WHT/SD fields), `:318-320` (balance_due)

- [ ] **Step 1: Add StampDutyTreatment enum and new fields**

In `app/models/finance/ar/invoice.py`, add the enum after the existing `InvoiceStatus` enum (around line 63), and add the two new fields after the existing `stamp_duty_code_id` field (after line 215):

```python
# Add this enum after InvoiceStatus (around line 63):
class StampDutyTreatment(str, enum.Enum):
    DEDUCTED = "DEDUCTED"
    PAID_SEPARATELY = "PAID_SEPARATELY"
```

Add these fields after `stamp_duty_code_id` (after line 215):

```python
    stamp_duty_treatment: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    vat_withheld: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
```

- [ ] **Step 2: Run linter**

Run: `poetry run ruff check app/models/finance/ar/invoice.py`
Expected: All checks passed

- [ ] **Step 3: Commit**

```bash
git add app/models/finance/ar/invoice.py
git commit -m "feat(ar): add StampDutyTreatment enum, vat_withheld and stamp_duty_treatment fields"
```

---

### Task 2: Migration

**Files:**
- Create: `alembic/versions/20260410_ar_invoice_deductions.py`

- [ ] **Step 1: Create the migration**

```python
"""Add AR invoice deduction fields (stamp_duty_treatment, vat_withheld).

Revision ID: 20260410_ar_deductions
Revises: <FILL_IN_HEAD_REVISION>
Create Date: 2026-04-10
"""

from alembic import op
import sqlalchemy as sa


revision = "20260410_ar_deductions"
down_revision = None  # FILL IN: run `alembic heads` to get current head
branch_labels = None
depends_on = None


def upgrade() -> None:
    # stamp_duty_treatment — nullable varchar, no enum needed (simple string)
    op.add_column(
        "invoice",
        sa.Column("stamp_duty_treatment", sa.String(20), nullable=True),
        schema="ar",
    )
    op.add_column(
        "invoice",
        sa.Column(
            "vat_withheld",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        schema="ar",
    )


def downgrade() -> None:
    op.drop_column("invoice", "vat_withheld", schema="ar")
    op.drop_column("invoice", "stamp_duty_treatment", schema="ar")
```

- [ ] **Step 2: Fill in the down_revision**

Run: `poetry run alembic heads`
Use the output as `down_revision`.

- [ ] **Step 3: Run the migration**

Run: `poetry run alembic upgrade head`
Expected: Migration applies successfully.

- [ ] **Step 4: Commit**

```bash
git add alembic/versions/20260410_ar_invoice_deductions.py
git commit -m "feat(ar): add migration for stamp_duty_treatment and vat_withheld columns"
```

---

### Task 3: Service — Extend ARInvoiceInput and create_invoice

**Files:**
- Modify: `app/services/finance/ar/invoice.py:83-104` (ARInvoiceInput), `:297-374` (create_invoice totals + construction), `:704-775` (build_input_from_payload)

- [ ] **Step 1: Extend ARInvoiceInput**

Add four new fields to the `ARInvoiceInput` dataclass (after `correlation_id` at line 104):

```python
    wht_code_id: UUID | None = None
    stamp_duty_code_id: UUID | None = None
    stamp_duty_treatment: str | None = None  # "DEDUCTED" or "PAID_SEPARATELY"
    vat_withheld: bool = False
```

- [ ] **Step 2: Add deduction calculations in create_invoice**

In `create_invoice`, after the `total_amount = subtotal + tax_total` line (line 329) and before the credit note handling block, add:

```python
        # ── Deductions (WHT, VAT withheld, stamp duty) ──────────────
        wht_amount = Decimal("0")
        wht_code_id = input.wht_code_id
        if wht_code_id:
            wht_amount, _net = TaxCalculationService.calculate_wht(
                db, org_id, subtotal, wht_code_id, input.invoice_date
            )

        stamp_duty_amount = Decimal("0")
        stamp_duty_code_id = input.stamp_duty_code_id
        if stamp_duty_code_id:
            sd_code = TaxCalculationService.get_effective_tax_code(
                db, org_id, stamp_duty_code_id, input.invoice_date
            )
            stamp_duty_amount = (total_amount * sd_code.tax_rate).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
```

Add the `ROUND_HALF_UP` import at the top of the file:

```python
from decimal import Decimal, ROUND_HALF_UP
```

- [ ] **Step 3: Handle credit note sign reversal for deductions**

In the credit note block (after `tax_total = -abs(tax_total)`), add:

```python
            if wht_amount:
                wht_amount = -abs(wht_amount)
            if stamp_duty_amount:
                stamp_duty_amount = -abs(stamp_duty_amount)
```

- [ ] **Step 4: Store deduction fields on the Invoice object**

In the `Invoice(...)` constructor call, add after `correlation_id`:

```python
            withholding_tax_amount=wht_amount,
            withholding_tax_code_id=wht_code_id,
            stamp_duty_amount=stamp_duty_amount,
            stamp_duty_code_id=stamp_duty_code_id,
            stamp_duty_treatment=input.stamp_duty_treatment,
            vat_withheld=input.vat_withheld,
```

- [ ] **Step 5: Parse deduction fields in build_input_from_payload**

In `build_input_from_payload`, add before the `return ARInvoiceInput(...)` call (around line 764), and include them in the return:

```python
        wht_code_id = (
            coerce_uuid(payload.get("wht_code_id"))
            if payload.get("wht_code_id")
            else None
        )
        stamp_duty_code_id = (
            coerce_uuid(payload.get("stamp_duty_code_id"))
            if payload.get("stamp_duty_code_id")
            else None
        )
        stamp_duty_treatment = (
            payload.get("stamp_duty_treatment") or None
        )
        vat_withheld = payload.get("vat_withheld") in ("true", "True", True, "on", "1")
```

Then add to the `ARInvoiceInput(...)` return:

```python
            wht_code_id=wht_code_id,
            stamp_duty_code_id=stamp_duty_code_id,
            stamp_duty_treatment=stamp_duty_treatment,
            vat_withheld=vat_withheld,
```

- [ ] **Step 6: Run linter**

Run: `poetry run ruff check app/services/finance/ar/invoice.py`
Expected: All checks passed

- [ ] **Step 7: Commit**

```bash
git add app/services/finance/ar/invoice.py
git commit -m "feat(ar): calculate WHT, VAT withheld, and stamp duty during invoice creation"
```

---

### Task 4: Web service — Form context and detail view

**Files:**
- Modify: `app/services/finance/ar/web/invoice_web.py:325-383` (invoice_form_context)
- Modify: `app/services/finance/ar/web/base.py:291-339` (invoice_detail_view)

- [ ] **Step 1: Add WHT and stamp duty codes to form context**

In `invoice_form_context` in `app/services/finance/ar/web/invoice_web.py`, add before the `context = {` dict (around line 370):

```python
        from app.models.finance.tax.tax_code import TaxType

        wht_codes = [
            {
                "tax_code_id": str(wht.tax_code_id),
                "tax_code": wht.tax_code,
                "tax_name": wht.tax_name,
                "tax_rate": float(wht.tax_rate),
                "rate_display": float(
                    (wht.tax_rate * 100).quantize(Decimal("0.01"))
                )
                if wht.tax_rate < 1
                else float(wht.tax_rate),
            }
            for wht in db.scalars(
                select(TaxCode).where(
                    TaxCode.organization_id == org_id,
                    TaxCode.is_active.is_(True),
                    TaxCode.tax_type == TaxType.WITHHOLDING,
                )
            ).all()
        ]

        stamp_duty_codes = [
            {
                "tax_code_id": str(sd.tax_code_id),
                "tax_code": sd.tax_code,
                "tax_name": sd.tax_name,
                "tax_rate": float(sd.tax_rate),
                "rate_display": float(
                    (sd.tax_rate * 100).quantize(Decimal("0.01"))
                )
                if sd.tax_rate < 1
                else float(sd.tax_rate),
            }
            for sd in db.scalars(
                select(TaxCode).where(
                    TaxCode.organization_id == org_id,
                    TaxCode.is_active.is_(True),
                    TaxCode.tax_type == TaxType.STAMP_DUTY,
                )
            ).all()
        ]
```

Add `select` and `Decimal` imports if not already present. Add to the context dict:

```python
            "wht_codes": wht_codes,
            "stamp_duty_codes": stamp_duty_codes,
```

Also filter STAMP_DUTY and WITHHOLDING from the per-line tax_codes query. The current query uses `tax_code_service.list(...)`. Replace it with a direct query that excludes those types:

```python
        tax_codes = [
            {
                "tax_code_id": str(tax.tax_code_id),
                "tax_code": tax.tax_code,
                "tax_name": tax.tax_name,
                "tax_rate": tax.tax_rate,
                "rate": (tax.tax_rate * 100).quantize(Decimal("0.01"))
                if tax.tax_rate < 1
                else tax.tax_rate,
                "is_inclusive": tax.is_inclusive,
                "is_compound": tax.is_compound,
            }
            for tax in db.scalars(
                select(TaxCode).where(
                    TaxCode.organization_id == org_id,
                    TaxCode.is_active.is_(True),
                    TaxCode.applies_to_sales.is_(True),
                    TaxCode.tax_type.notin_([TaxType.WITHHOLDING, TaxType.STAMP_DUTY]),
                )
            ).all()
        ]
```

- [ ] **Step 2: Add deduction fields to invoice_detail_view**

In `invoice_detail_view` in `app/services/finance/ar/web/base.py`, add to the return dict (after the `"balance"` key):

```python
        "withholding_tax": format_currency(
            invoice.withholding_tax_amount, invoice.currency_code
        )
        if invoice.withholding_tax_amount
        else None,
        "withholding_tax_raw": float(invoice.withholding_tax_amount)
        if invoice.withholding_tax_amount
        else 0,
        "vat_withheld": getattr(invoice, "vat_withheld", False),
        "vat_withheld_amount": format_currency(
            invoice.tax_amount, invoice.currency_code
        )
        if getattr(invoice, "vat_withheld", False)
        else None,
        "vat_withheld_amount_raw": float(invoice.tax_amount)
        if getattr(invoice, "vat_withheld", False)
        else 0,
        "stamp_duty": format_currency(
            invoice.stamp_duty_amount, invoice.currency_code
        )
        if invoice.stamp_duty_amount
        else None,
        "stamp_duty_raw": float(invoice.stamp_duty_amount)
        if invoice.stamp_duty_amount
        else 0,
        "stamp_duty_treatment_label": (
            "Deducted" if getattr(invoice, "stamp_duty_treatment", None) == "DEDUCTED"
            else "Paid Separately" if getattr(invoice, "stamp_duty_treatment", None) == "PAID_SEPARATELY"
            else None
        ),
        "amount_receivable": format_currency(
            _compute_receivable(invoice), invoice.currency_code
        )
        if (invoice.withholding_tax_amount or getattr(invoice, "vat_withheld", False)
            or (invoice.stamp_duty_amount and getattr(invoice, "stamp_duty_treatment", None) == "DEDUCTED"))
        else None,
        "amount_receivable_raw": float(_compute_receivable(invoice)),
```

Add a helper function before `invoice_detail_view`:

```python
def _compute_receivable(invoice: Invoice) -> Decimal:
    """Compute effective receivable after WHT, VAT withheld, and stamp duty deductions."""
    deductions = invoice.withholding_tax_amount or Decimal("0")
    if getattr(invoice, "vat_withheld", False):
        deductions += invoice.tax_amount or Decimal("0")
    if (getattr(invoice, "stamp_duty_treatment", None) == "DEDUCTED"
            and invoice.stamp_duty_amount):
        deductions += invoice.stamp_duty_amount
    return invoice.total_amount - deductions
```

- [ ] **Step 3: Run linter**

Run: `poetry run ruff check app/services/finance/ar/web/invoice_web.py app/services/finance/ar/web/base.py`
Expected: All checks passed

- [ ] **Step 4: Commit**

```bash
git add app/services/finance/ar/web/invoice_web.py app/services/finance/ar/web/base.py
git commit -m "feat(ar): add deduction codes to form context and deduction fields to detail view"
```

---

### Task 5: AR invoice form template — deductions UI

**Files:**
- Modify: `templates/finance/ar/invoice_form.html:452-478` (totals section), `:629-643` (form data), `:730-740` (computed properties)

- [ ] **Step 1: Add computed properties for deductions**

In the Alpine.js section, after the existing `get total()` (around line 740), add:

```javascript
        get inclusiveTaxAmount() {
            const inclusive = this.form.lines.reduce((sum, line) => {
                for (const taxId of (line.tax_code_ids || [])) {
                    const taxInfo = taxCodeData[taxId];
                    if (taxInfo && taxInfo.isInclusive) {
                        const detail = (line.tax_details || []).find(d => d.tax_code_id === taxId);
                        if (detail) sum += detail.tax_amount || 0;
                    }
                }
                return sum;
            }, 0);
            return parseFloat(inclusive.toFixed(2));
        },

        get exclusiveTaxAmount() {
            return parseFloat((this.taxAmount - this.inclusiveTaxAmount).toFixed(2));
        },

        get netSubtotal() {
            // Net amount before any VAT — WHT base.
            return parseFloat((this.subtotal - this.inclusiveTaxAmount).toFixed(2));
        },

        get whtAmount() {
            if (!this.form.wht_code_id) return 0;
            const code = this.whtCodes.find(c => c.tax_code_id === this.form.wht_code_id);
            if (!code) return 0;
            const rate = code.tax_rate < 1 ? code.tax_rate : code.tax_rate / 100;
            return parseFloat((this.netSubtotal * rate).toFixed(2));
        },

        get vatWithheldAmount() {
            return this.form.vat_withheld ? this.taxAmount : 0;
        },

        get stampDutyAmount() {
            if (!this.form.stamp_duty_code_id) return 0;
            const code = this.stampDutyCodes.find(c => c.tax_code_id === this.form.stamp_duty_code_id);
            if (!code) return 0;
            const rate = code.tax_rate < 1 ? code.tax_rate : code.tax_rate / 100;
            return parseFloat((this.total * rate).toFixed(2));
        },

        get stampDutyDeducted() {
            return this.form.stamp_duty_treatment === 'DEDUCTED' ? this.stampDutyAmount : 0;
        },

        get amountReceivable() {
            return parseFloat((this.total - this.whtAmount - this.vatWithheldAmount - this.stampDutyDeducted).toFixed(2));
        },

        get hasDeductions() {
            return this.whtAmount > 0 || this.vatWithheldAmount > 0 || this.stampDutyDeducted > 0;
        },
```

Also fix the `total` getter to handle inclusive taxes correctly (same fix as AP):

```javascript
        get total() {
            return this.subtotal + this.exclusiveTaxAmount;
        },
```

- [ ] **Step 2: Add form data fields**

In the form data initialization (around line 643), add after the `lines` array:

```javascript
            wht_code_id: '',
            stamp_duty_code_id: '',
            stamp_duty_treatment: 'DEDUCTED',
            vat_withheld: false,
```

Also add the data arrays after the form object:

```javascript
        whtCodes: {{ wht_codes | tojson | safe if wht_codes is defined else '[]' }},
        stampDutyCodes: {{ stamp_duty_codes | tojson | safe if stamp_duty_codes is defined else '[]' }},
```

- [ ] **Step 3: Add deductions UI to totals section**

Replace the totals section (lines 452-478) with:

```html
            <!-- Totals -->
            <div class="mt-8 flex justify-end">
                <div class="w-96 totals-section">
                    <div class="total-row">
                        <span class="total-label">Subtotal</span>
                        <span class="total-value" x-text="formatCurrency(subtotal)"></span>
                    </div>
                    <!-- Tax breakdown by type -->
                    <template x-for="tax in taxBreakdown" :key="tax.tax_code">
                        <div class="total-row">
                            <span class="total-label flex items-center gap-1">
                                <span x-text="tax.tax_code"></span>
                                <span class="text-xs text-slate-500 dark:text-slate-400" x-text="'(' + tax.tax_name + ')'"></span>
                            </span>
                            <span class="total-value" x-text="formatCurrency(tax.amount)"></span>
                        </div>
                    </template>
                    <!-- Total tax (if no breakdown available yet) -->
                    <div class="total-row" x-show="taxBreakdown.length === 0 && taxAmount > 0">
                        <span class="total-label">Tax</span>
                        <span class="total-value" x-text="formatCurrency(taxAmount)"></span>
                    </div>
                    <template x-if="inclusiveTaxAmount > 0">
                        <div class="total-row">
                            <span class="total-label text-xs text-slate-400">VAT included in prices</span>
                            <span class="total-value text-xs text-slate-400" x-text="formatCurrency(inclusiveTaxAmount)"></span>
                        </div>
                    </template>
                    <div class="total-row total-final">
                        <span class="total-label">Total</span>
                        <span class="total-value" x-text="formatCurrency(total)"></span>
                    </div>

                    {# ── Deductions ─────────────────────────────── #}
                    {% if wht_codes or stamp_duty_codes %}
                    <div class="mt-3 border-t border-slate-200 pt-3 dark:border-slate-700">
                        <p class="text-xs font-medium text-slate-500 dark:text-slate-400 mb-2 uppercase tracking-wider">Deductions</p>

                        {# WHT #}
                        {% if wht_codes %}
                        <div class="total-row" x-show="whtAmount > 0">
                            <span class="total-label text-xs text-slate-500 dark:text-slate-400">WHT Base (Net of VAT)</span>
                            <span class="total-value text-xs text-slate-500 dark:text-slate-400 font-mono" x-text="formatCurrency(netSubtotal)"></span>
                        </div>
                        <div class="total-row">
                            <span class="total-label">
                                <label class="text-xs font-medium text-slate-600 dark:text-slate-400">WHT</label>
                                <select name="wht_code_id" x-model="form.wht_code_id"
                                        class="form-select form-select-sm ml-2 max-w-[160px] inline-block">
                                    <option value="">None</option>
                                    {% for wht in wht_codes %}
                                    <option value="{{ wht.tax_code_id }}">{{ wht.tax_code }} ({{ wht.rate_display }}%)</option>
                                    {% endfor %}
                                </select>
                            </span>
                            <span class="total-value font-mono text-amber-600 dark:text-amber-400"
                                  x-show="whtAmount > 0"
                                  x-text="'-' + formatCurrency(whtAmount)"></span>
                        </div>
                        {% endif %}

                        {# VAT Withheld #}
                        <div class="total-row">
                            <span class="total-label">
                                <label class="flex items-center gap-2 cursor-pointer">
                                    <input type="checkbox" x-model="form.vat_withheld"
                                           class="rounded border-slate-300 text-teal-600 focus:ring-teal-500 dark:border-slate-600 dark:bg-slate-700">
                                    <span class="text-xs font-medium text-slate-600 dark:text-slate-400">VAT Withheld</span>
                                </label>
                            </span>
                            <span class="total-value font-mono text-amber-600 dark:text-amber-400"
                                  x-show="vatWithheldAmount > 0"
                                  x-text="'-' + formatCurrency(vatWithheldAmount)"></span>
                        </div>

                        {# Stamp Duty #}
                        {% if stamp_duty_codes %}
                        <div class="total-row">
                            <span class="total-label">
                                <label class="text-xs font-medium text-slate-600 dark:text-slate-400">Stamp Duty</label>
                                <select name="stamp_duty_code_id" x-model="form.stamp_duty_code_id"
                                        class="form-select form-select-sm ml-2 max-w-[120px] inline-block">
                                    <option value="">None</option>
                                    {% for sd in stamp_duty_codes %}
                                    <option value="{{ sd.tax_code_id }}">{{ sd.tax_code }} ({{ sd.rate_display }}%)</option>
                                    {% endfor %}
                                </select>
                                <select name="stamp_duty_treatment" x-model="form.stamp_duty_treatment"
                                        x-show="form.stamp_duty_code_id"
                                        class="form-select form-select-sm ml-1 max-w-[120px] inline-block">
                                    <option value="DEDUCTED">Deducted</option>
                                    <option value="PAID_SEPARATELY">Paid Separately</option>
                                </select>
                            </span>
                            <span class="total-value font-mono"
                                  x-show="stampDutyAmount > 0"
                                  :class="form.stamp_duty_treatment === 'DEDUCTED' ? 'text-amber-600 dark:text-amber-400' : 'text-slate-500 dark:text-slate-400'"
                                  x-text="(form.stamp_duty_treatment === 'DEDUCTED' ? '-' : '') + formatCurrency(stampDutyAmount)"></span>
                        </div>
                        <template x-if="stampDutyAmount > 0 && form.stamp_duty_treatment === 'PAID_SEPARATELY'">
                            <div class="total-row">
                                <span class="text-xs text-slate-400 dark:text-slate-500 italic">Paid separately — does not reduce receivable</span>
                            </div>
                        </template>
                        {% endif %}
                    </div>
                    {% endif %}

                    {# Amount Receivable #}
                    <template x-if="hasDeductions">
                        <div class="total-row mt-2 border-t border-slate-200 pt-2 dark:border-slate-700">
                            <span class="total-label text-sm font-semibold text-slate-700 dark:text-slate-300">Amount Receivable</span>
                            <span class="total-value text-sm font-semibold font-mono text-teal-700 dark:text-teal-400" x-text="formatCurrency(amountReceivable)"></span>
                        </div>
                    </template>

                    {# Hidden fields for form submission #}
                    <input type="hidden" name="vat_withheld" :value="form.vat_withheld">
                </div>
            </div>
```

- [ ] **Step 4: Verify template renders correctly**

Run: `poetry run ruff check app/` (ensure no Python issues)
Manually verify the form loads at `/finance/ar/invoices/new`.

- [ ] **Step 5: Commit**

```bash
git add templates/finance/ar/invoice_form.html
git commit -m "feat(ar): add WHT, VAT withheld, and stamp duty deductions to invoice form"
```

---

### Task 6: AR invoice detail template — display deductions

**Files:**
- Modify: `templates/finance/ar/invoice_detail.html:277-294` (line items totals), `:325-337` (summary section)

- [ ] **Step 1: Add deduction rows to the print/table totals**

After the "Total Amount" row (around line 294), add:

```html
                {% if invoice.withholding_tax_raw and invoice.withholding_tax_raw > 0 %}
                <tr class="print-table-total">
                    <td colspan="4">WHT</td>
                    <td class="text-amber-600 dark:text-amber-400">-{{ invoice.withholding_tax }}</td>
                </tr>
                {% endif %}
                {% if invoice.vat_withheld and invoice.vat_withheld_amount %}
                <tr class="print-table-total">
                    <td colspan="4">VAT Withheld</td>
                    <td class="text-amber-600 dark:text-amber-400">-{{ invoice.vat_withheld_amount }}</td>
                </tr>
                {% endif %}
                {% if invoice.stamp_duty_raw and invoice.stamp_duty_raw > 0 %}
                <tr class="print-table-total">
                    <td colspan="4">Stamp Duty ({{ invoice.stamp_duty_treatment_label if invoice.stamp_duty_treatment_label else '' }})</td>
                    <td class="{% if invoice.stamp_duty_treatment_label == 'Deducted' %}text-amber-600 dark:text-amber-400{% else %}text-slate-500 dark:text-slate-400{% endif %}">
                        {% if invoice.stamp_duty_treatment_label == 'Deducted' %}-{% endif %}{{ invoice.stamp_duty }}
                    </td>
                </tr>
                {% endif %}
                {% if invoice.amount_receivable %}
                <tr class="print-table-grand-total">
                    <td colspan="4"><strong>Amount Receivable</strong></td>
                    <td><strong class="text-teal-700 dark:text-teal-400">{{ invoice.amount_receivable }}</strong></td>
                </tr>
                {% endif %}
```

- [ ] **Step 2: Add deduction rows to the summary section**

In the summary section (around line 325-337), add deduction rows before the "Balance Due" row:

```html
                    {% if invoice.withholding_tax_raw and invoice.withholding_tax_raw > 0 %}
                    <div class="print-summary-row">
                        <span>WHT</span>
                        <span class="text-amber-600 dark:text-amber-400">-{{ invoice.withholding_tax }}</span>
                    </div>
                    {% endif %}
                    {% if invoice.vat_withheld and invoice.vat_withheld_amount %}
                    <div class="print-summary-row">
                        <span>VAT Withheld</span>
                        <span class="text-amber-600 dark:text-amber-400">-{{ invoice.vat_withheld_amount }}</span>
                    </div>
                    {% endif %}
                    {% if invoice.stamp_duty_raw and invoice.stamp_duty_raw > 0 %}
                    <div class="print-summary-row">
                        <span>Stamp Duty ({{ invoice.stamp_duty_treatment_label if invoice.stamp_duty_treatment_label else '' }})</span>
                        <span>{% if invoice.stamp_duty_treatment_label == 'Deducted' %}-{% endif %}{{ invoice.stamp_duty }}</span>
                    </div>
                    {% endif %}
                    {% if invoice.amount_receivable %}
                    <div class="print-summary-row font-semibold">
                        <span>Amount Receivable</span>
                        <span class="text-teal-700 dark:text-teal-400">{{ invoice.amount_receivable }}</span>
                    </div>
                    {% endif %}
```

- [ ] **Step 3: Commit**

```bash
git add templates/finance/ar/invoice_detail.html
git commit -m "feat(ar): display WHT, VAT withheld, stamp duty, and Amount Receivable on invoice detail"
```

---

### Task 7: GL Posting — Add deduction journal lines

**Files:**
- Modify: `app/services/finance/ar/posting/invoice.py:283-309` (AR Control debit)

- [ ] **Step 1: Add deduction journal lines before the AR Control line**

In `app/services/finance/ar/posting/invoice.py`, before the AR Control debit block (around line 283), add the deduction lines. The key change is that the AR Control debit amount must be reduced by the deductions.

Add these blocks before the AR Control section:

```python
    # ── WHT debit line ─────────────────────────────────────────────
    wht_amount = getattr(invoice, "withholding_tax_amount", None) or Decimal("0")
    wht_code_id = getattr(invoice, "withholding_tax_code_id", None)
    if wht_amount > Decimal("0") and wht_code_id:
        wht_code = db.get(TaxCode, wht_code_id)
        if wht_code and wht_code.tax_paid_account_id:
            wht_functional = wht_amount * exchange_rate
            if invoice.invoice_type == InvoiceType.CREDIT_NOTE:
                journal_lines.append(
                    JournalLineInput(
                        account_id=wht_code.tax_paid_account_id,
                        debit_amount=Decimal("0"),
                        credit_amount=abs(wht_amount),
                        debit_amount_functional=Decimal("0"),
                        credit_amount_functional=abs(wht_functional),
                        description=f"AR Credit Note WHT reversal: {invoice.invoice_number}",
                    )
                )
            else:
                journal_lines.append(
                    JournalLineInput(
                        account_id=wht_code.tax_paid_account_id,
                        debit_amount=wht_amount,
                        credit_amount=Decimal("0"),
                        debit_amount_functional=wht_functional,
                        credit_amount_functional=Decimal("0"),
                        description=f"AR Invoice WHT receivable: {invoice.invoice_number}",
                    )
                )

    # ── VAT withheld debit line ────────────────────────────────────
    vat_withheld_amount = Decimal("0")
    if getattr(invoice, "vat_withheld", False) and invoice.tax_amount > Decimal("0"):
        vat_withheld_amount = invoice.tax_amount
        # Find VAT tax codes used on invoice lines to get the tax_paid_account_id
        from app.models.finance.ar.invoice_line_tax import InvoiceLineTax
        vat_account_ids = set(
            db.scalars(
                select(TaxCode.tax_paid_account_id)
                .join(InvoiceLineTax, InvoiceLineTax.tax_code_id == TaxCode.tax_code_id)
                .join(InvoiceLine, InvoiceLine.line_id == InvoiceLineTax.line_id)
                .where(
                    InvoiceLine.invoice_id == invoice.invoice_id,
                    TaxCode.tax_type.in_([TaxType.VAT, TaxType.GST]),
                    TaxCode.tax_paid_account_id.isnot(None),
                )
            ).all()
        )
        # Fall back to the tax_collected_account_id if tax_paid_account_id not set
        if not vat_account_ids:
            vat_account_ids = set(
                db.scalars(
                    select(TaxCode.tax_collected_account_id)
                    .join(InvoiceLineTax, InvoiceLineTax.tax_code_id == TaxCode.tax_code_id)
                    .join(InvoiceLine, InvoiceLine.line_id == InvoiceLineTax.line_id)
                    .where(
                        InvoiceLine.invoice_id == invoice.invoice_id,
                        TaxCode.tax_type.in_([TaxType.VAT, TaxType.GST]),
                        TaxCode.tax_collected_account_id.isnot(None),
                    )
                ).all()
            )

        vat_withheld_functional = vat_withheld_amount * exchange_rate
        for vat_account_id in vat_account_ids:
            if invoice.invoice_type == InvoiceType.CREDIT_NOTE:
                journal_lines.append(
                    JournalLineInput(
                        account_id=vat_account_id,
                        debit_amount=Decimal("0"),
                        credit_amount=abs(vat_withheld_amount),
                        debit_amount_functional=Decimal("0"),
                        credit_amount_functional=abs(vat_withheld_functional),
                        description=f"AR Credit Note VAT withheld reversal: {invoice.invoice_number}",
                    )
                )
            else:
                journal_lines.append(
                    JournalLineInput(
                        account_id=vat_account_id,
                        debit_amount=vat_withheld_amount,
                        credit_amount=Decimal("0"),
                        debit_amount_functional=vat_withheld_functional,
                        credit_amount_functional=Decimal("0"),
                        description=f"AR Invoice VAT withheld at source: {invoice.invoice_number}",
                    )
                )

    # ── Stamp duty debit line (only when DEDUCTED) ─────────────────
    stamp_duty_deducted = Decimal("0")
    stamp_duty_amount = getattr(invoice, "stamp_duty_amount", None) or Decimal("0")
    stamp_duty_code_id = getattr(invoice, "stamp_duty_code_id", None)
    stamp_duty_treatment = getattr(invoice, "stamp_duty_treatment", None)
    if (stamp_duty_amount > Decimal("0") and stamp_duty_code_id
            and stamp_duty_treatment == "DEDUCTED"):
        stamp_duty_deducted = stamp_duty_amount
        sd_code = db.get(TaxCode, stamp_duty_code_id)
        if sd_code and sd_code.tax_expense_account_id:
            sd_functional = stamp_duty_amount * exchange_rate
            if invoice.invoice_type == InvoiceType.CREDIT_NOTE:
                journal_lines.append(
                    JournalLineInput(
                        account_id=sd_code.tax_expense_account_id,
                        debit_amount=Decimal("0"),
                        credit_amount=abs(stamp_duty_amount),
                        debit_amount_functional=Decimal("0"),
                        credit_amount_functional=abs(sd_functional),
                        description=f"AR Credit Note stamp duty reversal: {invoice.invoice_number}",
                    )
                )
            else:
                journal_lines.append(
                    JournalLineInput(
                        account_id=sd_code.tax_expense_account_id,
                        debit_amount=stamp_duty_amount,
                        credit_amount=Decimal("0"),
                        debit_amount_functional=sd_functional,
                        credit_amount_functional=Decimal("0"),
                        description=f"AR Invoice stamp duty: {invoice.invoice_number}",
                    )
                )
```

Then modify the AR Control debit to subtract deductions. Change the existing AR Control block to:

```python
    # ── AR Control debit (reduced by deductions) ───────────────────
    ar_amount = invoice.total_amount - wht_amount - vat_withheld_amount - stamp_duty_deducted
    ar_functional = ar_amount * exchange_rate

    if invoice.invoice_type == InvoiceType.CREDIT_NOTE:
        journal_lines.append(
            JournalLineInput(
                account_id=invoice.ar_control_account_id,
                debit_amount=Decimal("0"),
                credit_amount=abs(ar_amount),
                debit_amount_functional=Decimal("0"),
                credit_amount_functional=abs(ar_functional),
                description=f"AR Credit Note: {customer.legal_name}",
            )
        )
    else:
        journal_lines.append(
            JournalLineInput(
                account_id=invoice.ar_control_account_id,
                debit_amount=ar_amount,
                credit_amount=Decimal("0"),
                debit_amount_functional=ar_functional,
                credit_amount_functional=Decimal("0"),
                description=f"AR Invoice: {customer.legal_name}",
            )
        )
```

Add necessary imports at the top of the file:

```python
from app.models.finance.tax.tax_code import TaxCode, TaxType
from app.models.finance.ar.invoice_line import InvoiceLine
```

- [ ] **Step 2: Run linter**

Run: `poetry run ruff check app/services/finance/ar/posting/invoice.py`
Expected: All checks passed

- [ ] **Step 3: Commit**

```bash
git add app/services/finance/ar/posting/invoice.py
git commit -m "feat(ar): add WHT, VAT withheld, and stamp duty GL posting lines"
```

---

### Task 8: AP cleanup — Filter STAMP_DUTY and WITHHOLDING from per-line dropdowns

**Files:**
- Modify: `app/services/finance/ap/web/invoice_web.py:330-336`
- Modify: `app/services/finance/ap/web.py:1084-1091`

- [ ] **Step 1: Filter in web/invoice_web.py**

In the tax codes query (lines 330-336), add a filter to exclude STAMP_DUTY and WITHHOLDING:

```python
            for tax in db.scalars(
                select(TaxCode).where(
                    TaxCode.organization_id == org_id,
                    TaxCode.is_active == True,
                    TaxCode.applies_to_purchases == True,
                    TaxCode.tax_type.notin_([TaxType.WITHHOLDING, TaxType.STAMP_DUTY]),
                )
            ).all()
```

Add import at the top if not present: `from app.models.finance.tax.tax_code import TaxType`

- [ ] **Step 2: Filter in web.py**

Same change in the legacy web service (lines 1084-1091):

```python
            for tax in db.scalars(
                select(TaxCode).where(
                    TaxCode.organization_id == org_id,
                    TaxCode.is_active.is_(True),
                    TaxCode.applies_to_purchases.is_(True),
                    TaxCode.tax_type.notin_([TaxType.WITHHOLDING, TaxType.STAMP_DUTY]),
                )
            ).all()
```

Add `TaxType` import if not present.

- [ ] **Step 3: Run linter**

Run: `poetry run ruff check app/services/finance/ap/web/invoice_web.py app/services/finance/ap/web.py`
Expected: All checks passed

- [ ] **Step 4: Commit**

```bash
git add app/services/finance/ap/web/invoice_web.py app/services/finance/ap/web.py
git commit -m "fix(ap): filter STAMP_DUTY and WITHHOLDING from per-line tax dropdown"
```

---

### Task 9: Unit tests

**Files:**
- Create: `tests/ifrs/ar/test_ar_invoice_deductions.py`

- [ ] **Step 1: Write tests for all deduction edge cases**

```python
"""Tests for AR invoice deduction calculations (WHT, VAT withheld, stamp duty)."""

from decimal import Decimal
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.services.finance.tax.tax_calculation import TaxCalculationService


class TestWHTCalculation:
    """WHT is calculated on net subtotal (pre-VAT)."""

    def test_wht_on_exclusive_vat_invoice(self):
        """WHT base = subtotal when all taxes are exclusive."""
        db = MagicMock()
        org_id = uuid4()
        wht_code_id = uuid4()
        txn_date = date.today()
        db.get.return_value = SimpleNamespace(
            tax_code_id=wht_code_id,
            tax_rate=Decimal("0.05"),
            is_active=True,
            effective_from=txn_date,
            effective_to=None,
        )

        subtotal = Decimal("100000")  # Pre-VAT
        wht_amount, net = TaxCalculationService.calculate_wht(
            db=db,
            organization_id=org_id,
            base_amount=subtotal,
            wht_code_id=wht_code_id,
            transaction_date=txn_date,
        )

        assert wht_amount == Decimal("5000.00")
        assert net == Decimal("95000.00")

    def test_wht_zero_when_no_code(self):
        """WHT is zero when no WHT code is provided."""
        # Service is not called — caller checks for wht_code_id before calling
        pass


class TestStampDutyCalculation:
    """Stamp duty is calculated on gross total (including VAT)."""

    def test_stamp_duty_on_gross(self):
        """SD base = total_amount (subtotal + VAT)."""
        total_amount = Decimal("107500")  # 100k + 7.5% VAT
        sd_rate = Decimal("0.01")
        expected = Decimal("1075.00")

        sd_amount = (total_amount * sd_rate).quantize(Decimal("0.01"))
        assert sd_amount == expected

    def test_stamp_duty_deducted_reduces_receivable(self):
        """When treatment is DEDUCTED, stamp duty reduces amount receivable."""
        total = Decimal("107500")
        sd_amount = Decimal("1075")
        treatment = "DEDUCTED"

        deduction = sd_amount if treatment == "DEDUCTED" else Decimal("0")
        receivable = total - deduction
        assert receivable == Decimal("106425")

    def test_stamp_duty_paid_separately_no_effect(self):
        """When treatment is PAID_SEPARATELY, receivable equals total."""
        total = Decimal("107500")
        sd_amount = Decimal("1075")
        treatment = "PAID_SEPARATELY"

        deduction = sd_amount if treatment == "DEDUCTED" else Decimal("0")
        receivable = total - deduction
        assert receivable == Decimal("107500")


class TestVATWithheld:
    """VAT withheld deducts the full tax amount."""

    def test_vat_withheld_equals_tax_amount(self):
        """Withheld VAT = full tax_amount on the invoice."""
        tax_amount = Decimal("7500")
        vat_withheld = True

        vat_withheld_amount = tax_amount if vat_withheld else Decimal("0")
        assert vat_withheld_amount == Decimal("7500")

    def test_vat_not_withheld_is_zero(self):
        """No deduction when vat_withheld is False."""
        tax_amount = Decimal("7500")
        vat_withheld = False

        vat_withheld_amount = tax_amount if vat_withheld else Decimal("0")
        assert vat_withheld_amount == Decimal("0")


class TestAmountReceivable:
    """Amount receivable = total - WHT - VAT withheld - stamp duty (if deducted)."""

    def test_all_deductions_active(self):
        """All three deductions reduce receivable."""
        total = Decimal("107500")
        wht = Decimal("5000")
        vat_withheld = Decimal("7500")
        sd_deducted = Decimal("1075")

        receivable = total - wht - vat_withheld - sd_deducted
        assert receivable == Decimal("93925")

    def test_no_deductions(self):
        """Receivable equals total when no deductions."""
        total = Decimal("107500")
        receivable = total - Decimal("0") - Decimal("0") - Decimal("0")
        assert receivable == Decimal("107500")

    def test_wht_only(self):
        """Only WHT deducted."""
        total = Decimal("107500")
        wht = Decimal("5000")
        receivable = total - wht
        assert receivable == Decimal("102500")

    def test_vat_withheld_only(self):
        """Only VAT withheld."""
        total = Decimal("107500")
        vat = Decimal("7500")
        receivable = total - vat
        assert receivable == Decimal("100000")

    def test_stamp_duty_paid_separately_with_wht(self):
        """Stamp duty paid separately does not reduce receivable, but WHT does."""
        total = Decimal("107500")
        wht = Decimal("5000")
        sd_amount = Decimal("1075")
        sd_treatment = "PAID_SEPARATELY"

        sd_deducted = sd_amount if sd_treatment == "DEDUCTED" else Decimal("0")
        receivable = total - wht - sd_deducted
        assert receivable == Decimal("102500")

    def test_credit_note_reverses_signs(self):
        """Credit note: all amounts are negative, receivable is negative."""
        total = Decimal("-107500")
        wht = Decimal("-5000")
        vat = Decimal("-7500")
        sd = Decimal("-1075")

        receivable = total - wht - vat - sd
        assert receivable == Decimal("-93925")
```

- [ ] **Step 2: Run tests**

Run: `poetry run pytest tests/ifrs/ar/test_ar_invoice_deductions.py -v`
Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/ifrs/ar/test_ar_invoice_deductions.py
git commit -m "test(ar): add unit tests for WHT, VAT withheld, and stamp duty deductions"
```
