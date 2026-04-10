# AR Invoice Deductions: WHT, VAT Withheld & Stamp Duty

**Date:** 2026-04-10
**Status:** Draft
**Scope:** AR invoice form, detail, creation service, GL posting, AP cleanup

---

## Problem

Government agency invoices require up to three deductions from the invoice total before payment reaches us:

1. **Withholding Tax (WHT)** — percentage of the net (pre-VAT) amount
2. **VAT Withheld** — government remits our VAT directly to FIRS instead of paying it to us
3. **Stamp Duty** — 1% of the gross invoice amount, either deducted from payment or paid separately by us

None of these are currently implemented on the AR invoice form or creation service. The model fields exist (`withholding_tax_amount`, `stamp_duty_amount`, etc.) but are never populated.

Additionally, `STAMP_DUTY` tax codes appear in the AP per-line tax dropdown where they don't belong — stamp duty is not an AP concern.

---

## Design

### Calculation Rules

| Deduction | Base Amount | Calculation | User Control |
|-----------|-------------|-------------|--------------|
| WHT | Net subtotal (pre-VAT) — `subtotal - inclusiveVatAmount` | `netSubtotal * whtRate` | Dropdown: select WHT tax code or "None" |
| VAT Withheld | Full VAT amount from invoice lines | No new calculation — uses existing `taxAmount` | Checkbox: on/off |
| Stamp Duty | Gross total (`subtotal + exclusiveVatAmount`) | `total * stampDutyRate` | Dropdown: select SD tax code or "None", plus treatment mode |

**Key rules:**
- All three deductions are independent — none affects another's base.
- WHT base is the net subtotal before any VAT (same logic as AP, handles both inclusive and exclusive tax lines).
- Stamp duty base is the gross total including VAT.
- VAT withheld is always the full VAT amount — no partial withholding.
- All three are at user discretion per invoice. No auto-detection from customer config.

### Stamp Duty Treatment Modes

| Mode | Effect on Amount Receivable | GL Impact on Invoice Posting |
|------|----------------------------|------------------------------|
| **Deducted** | Reduces Amount Receivable | Debit Stamp Duty Expense account |
| **Paid Separately** | No effect — informational only | No GL lines on invoice posting |

### Amount Receivable Formula

```
Amount Receivable = total_amount
                  - withholding_tax_amount
                  - vat_withheld_amount
                  - stamp_duty_amount (only if treatment = DEDUCTED)
```

### Worked Example

Invoice: 1 line item at ₦100,000, exclusive VAT 7.5%, WHT 5%, stamp duty 1% (deducted), VAT withheld.

```
Subtotal                                    ₦100,000.00
Tax (VAT 7.5%)                                ₦7,500.00
                                    ───────────────────
Total                                       ₦107,500.00

Deductions:
  WHT (5%) on ₦100,000 net                  -₦5,000.00
  VAT Withheld                               -₦7,500.00
  Stamp Duty (1%) on ₦107,500 gross          -₦1,075.00
                                    ───────────────────
Amount Receivable                            ₦93,925.00
```

---

## Model Changes

### New enum: `StampDutyTreatment`

```python
class StampDutyTreatment(str, enum.Enum):
    DEDUCTED = "DEDUCTED"
    PAID_SEPARATELY = "PAID_SEPARATELY"
```

### AR Invoice model — new fields

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `stamp_duty_treatment` | `StampDutyTreatment \| None` | `None` | Treatment mode |
| `vat_withheld` | `bool` | `False` | Whether VAT is withheld by the payer |

Existing fields already on the model (currently unused):
- `withholding_tax_amount` (Decimal, default 0)
- `withholding_tax_code_id` (UUID, nullable)
- `stamp_duty_amount` (Decimal, default 0)
- `stamp_duty_code_id` (UUID, nullable)

### Alembic migration

- Add `stamp_duty_treatment` enum + column to `ar.invoice`
- Add `vat_withheld` boolean column to `ar.invoice` (default `False`)

---

## Input Schema Changes

### `ARInvoiceInput` — new fields

```python
wht_code_id: UUID | None = None
stamp_duty_code_id: UUID | None = None
stamp_duty_treatment: str | None = None  # "DEDUCTED" or "PAID_SEPARATELY"
vat_withheld: bool = False
```

---

## Service Changes

### `app/services/finance/ar/invoice.py` — `create_invoice()`

After calculating `subtotal`, `tax_total`, and `total_amount`:

1. **WHT calculation:**
   ```
   if input.wht_code_id:
       wht_amount, _ = TaxCalculationService.calculate_wht(
           db, org_id, subtotal, input.wht_code_id, input.invoice_date
       )
   ```
   Note: `subtotal` here is already the net amount (inclusive VAT extracted), matching the AP fix.

2. **VAT withheld:**
   ```
   vat_withheld_amount = tax_total if input.vat_withheld else Decimal("0")
   ```

3. **Stamp duty:**
   ```
   if input.stamp_duty_code_id:
       sd_code = get_effective_tax_code(db, org_id, input.stamp_duty_code_id, input.invoice_date)
       stamp_duty_amount = (total_amount * sd_code.tax_rate).quantize(Decimal("0.01"))
   ```

4. **Store on invoice:**
   - `withholding_tax_amount = wht_amount`
   - `withholding_tax_code_id = input.wht_code_id`
   - `stamp_duty_amount = stamp_duty_amount`
   - `stamp_duty_code_id = input.stamp_duty_code_id`
   - `stamp_duty_treatment = input.stamp_duty_treatment`
   - `vat_withheld = input.vat_withheld`

5. **`total_amount` is NOT changed** — it remains `subtotal + tax_total`. The deductions are tracked separately and affect the balance/receivable calculation.

### Balance due

Update the `balance_due` property or the web service view to compute:

```python
deductions = (
    (self.withholding_tax_amount or Decimal("0"))
    + (self.tax_amount if self.vat_withheld else Decimal("0"))
    + (self.stamp_duty_amount if self.stamp_duty_treatment == StampDutyTreatment.DEDUCTED else Decimal("0"))
)
effective_receivable = self.total_amount - deductions
balance_due = effective_receivable - self.amount_paid
```

---

## GL Posting Changes

### `app/services/finance/ar/posting/invoice.py`

The current posting debits AR Control for `total_amount`. With deductions, the AR Control debit must be reduced, and separate debit lines added for each deduction.

**Journal entry lines for a standard invoice:**

| Line | Account | Debit | Credit |
|------|---------|-------|--------|
| 1 | Revenue (per line) | | ₦100,000 |
| 2 | VAT Collected (tax account) | | ₦7,500 |
| 3 | WHT Receivable (`tax_paid_account_id` on WHT code) | ₦5,000 | |
| 4 | VAT Receivable (`tax_paid_account_id` on VAT code, or a configured account) | ₦7,500 | |
| 5 | Stamp Duty Expense (`tax_expense_account_id` on SD code) | ₦1,075 | |
| 6 | AR Control | ₦93,925 | |

**AR Control amount:**
```
ar_amount = total_amount - wht_amount - vat_withheld_amount - stamp_duty_deducted
```

**Credit note:** All signs reverse.

**Stamp Duty — Paid Separately:** Stamp duty debit line (line 5) is skipped. AR Control = `total_amount - wht_amount - vat_withheld_amount`.

### VAT Withheld GL account

When VAT is withheld, we need to debit a "VAT Receivable" or "VAT Withheld at Source" account. This account should be configurable. Options:

- Use the `tax_paid_account_id` on the VAT tax code (exists on the model).
- If not configured, fall back to the same VAT account used for the credit (net zero — VAT cancels out in AR).

The service will look up the VAT tax codes used on the invoice lines and use their `tax_paid_account_id` for the debit. If multiple VAT codes are used, create one debit line per unique `tax_paid_account_id`.

---

## Frontend Changes

### AR Invoice Form (`templates/finance/ar/invoice_form.html`)

**Totals section — add after the Total row:**

```
Deductions (optional):

WHT          [Select WHT code ▾]     -₦5,000.00
  WHT Base (Net of VAT)         ₦100,000.00

☑ VAT Withheld                       -₦7,500.00

Stamp Duty   [SD-1% ▾]  [Deducted ▾] -₦1,075.00
                         ───────────────────
Amount Receivable                    ₦93,925.00
```

**Alpine.js computed properties to add:**

```javascript
get netSubtotal()      // subtotal - inclusiveTaxAmount (WHT base)
get whtAmount()        // netSubtotal * whtRate
get vatWithheldAmount() // vat_withheld ? taxAmount : 0
get stampDutyAmount()  // total * stampDutyRate
get stampDutyDeducted() // treatment === 'DEDUCTED' ? stampDutyAmount : 0
get amountReceivable() // total - whtAmount - vatWithheldAmount - stampDutyDeducted
```

**Form data to add:**
```javascript
wht_code_id: '',
stamp_duty_code_id: '',
stamp_duty_treatment: 'DEDUCTED',  // default when SD is selected
vat_withheld: false,
```

**Hidden form fields:**
```html
<input type="hidden" name="wht_code_id" :value="form.wht_code_id">
<input type="hidden" name="stamp_duty_code_id" :value="form.stamp_duty_code_id">
<input type="hidden" name="stamp_duty_treatment" :value="form.stamp_duty_treatment">
<input type="hidden" name="vat_withheld" :value="form.vat_withheld">
```

### AR Invoice Form Context (`invoice_form_context`)

Add to context:
- `wht_codes` — query `TaxCode` where `tax_type == TaxType.WITHHOLDING` and `is_active`
- `stamp_duty_codes` — query `TaxCode` where `tax_type == TaxType.STAMP_DUTY` and `is_active`

### AR Invoice Detail (`templates/finance/ar/invoice_detail.html`)

**Totals section — add after Total Amount:**

```html
{% if invoice.withholding_tax_raw and invoice.withholding_tax_raw > 0 %}
    WHT                              -₦5,000.00
{% endif %}
{% if invoice.vat_withheld %}
    VAT Withheld                     -₦7,500.00
{% endif %}
{% if invoice.stamp_duty_raw and invoice.stamp_duty_raw > 0 %}
    Stamp Duty ({{ invoice.stamp_duty_treatment_label }})  -₦1,075.00
{% endif %}
{% if invoice.amount_receivable %}
    Amount Receivable                 ₦93,925.00
{% endif %}
```

### AR Invoice Detail View (`web/base.py` — `invoice_detail_view`)

Add to view dict:
- `withholding_tax` / `withholding_tax_raw`
- `vat_withheld` (bool)
- `vat_withheld_amount` / `vat_withheld_amount_raw`
- `stamp_duty` / `stamp_duty_raw`
- `stamp_duty_treatment_label` ("Deducted" or "Paid Separately")
- `amount_receivable` / `amount_receivable_raw`

---

## AP Cleanup

### Filter STAMP_DUTY from AP per-line tax dropdown

In both `app/services/finance/ap/web.py` and `app/services/finance/ap/web/invoice_web.py`, the tax code query for the per-line dropdown currently fetches all active purchase-applicable tax codes. Add a filter:

```python
TaxCode.tax_type != TaxType.STAMP_DUTY
```

This removes SD-1% from the line-level tax dropdown on AP invoices. STAMP_DUTY codes remain available in the tax admin for AR use.

Also filter `TaxType.WITHHOLDING` from the per-line dropdown — WHT is already handled at the invoice level via the dedicated WHT dropdown, so it shouldn't appear in per-line tax selection either.

---

## Route Changes

### AR invoice create/update route

Parse new form fields from POST data:
- `wht_code_id` (optional UUID)
- `stamp_duty_code_id` (optional UUID)
- `stamp_duty_treatment` (optional string)
- `vat_withheld` (optional bool)

Pass to `ARInvoiceInput`.

---

## Migration

Single Alembic migration:

1. Create `stamp_duty_treatment` PostgreSQL enum in `ar` schema
2. Add `stamp_duty_treatment` column to `ar.invoice` (nullable)
3. Add `vat_withheld` boolean column to `ar.invoice` (default `False`)

No changes needed for `withholding_tax_amount`, `withholding_tax_code_id`, `stamp_duty_amount`, `stamp_duty_code_id` — these already exist.

---

## Testing

### Unit tests

- WHT calculation on net subtotal (exclusive, inclusive, mixed lines)
- Stamp duty calculation on gross total
- VAT withheld amount equals tax_amount
- Amount receivable formula with all combinations:
  - WHT only
  - VAT withheld only
  - Stamp duty deducted only
  - Stamp duty paid separately (no effect)
  - All three active
  - None active
- Credit note: all signs reversed

### Integration tests

- Create invoice with all deductions, verify model fields populated
- Post invoice, verify GL journal has correct lines and amounts
- Stamp duty paid separately: verify no GL lines for stamp duty

### Playwright UI tests

- Form: select WHT, verify amount calculated on net
- Form: toggle VAT withheld, verify full VAT deducted
- Form: select stamp duty with "Deducted", verify reduces receivable
- Form: switch to "Paid Separately", verify receivable restored
- Form: all three active, verify Amount Receivable is correct
- Detail page: all deduction rows display correctly

---

## Out of Scope

- Auto-detecting deductions from customer type (GOVERNMENT)
- Stamp duty thresholds or minimum invoice amounts
- Partial VAT withholding
- AR payment receipt integration with deductions (future work)
- Remita RRR generation for stamp duty remittance
