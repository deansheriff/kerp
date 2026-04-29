# 2025 AR/AP Opening Duplication Bridge

Date: 2026-04-28

Scope:

- AR control `1400`
- AP control `2000`
- opening-related journals dated `2025-01-01`
- overlap with January 1 subledger documents

Organization:

- `00000000-0000-0000-0000-000000000001`

## Executive Summary

The AR and AP opening problems are not identical.

- AR shows a **mixed pattern**:
  - summary opening in `OB-000001`
  - separate `CUS OP BAL` journals
  - some exact overlap with January 1 customer invoices
  - but a large portion still needs customer-level schedule proof
- AP shows a **stronger duplicate-load pattern**:
  - summary opening in `OB-000001`
  - separate `PUR OP BAL` journals
  - plus later supplier invoices dated `2025-01-01` that mirror some opening-journal amounts exactly
  - including invoices with `status = POSTED` but `posting_status = NOT_POSTED`

## 1. AR Opening Bridge

### Opening components hitting control `1400`

| Component | Amount |
|---|---:|
| `OB-000001` opening balance | `20,591,053.35` |
| `CUS OP BAL` journals on `2025-01-01` | `20,917,253.35` |
| Combined opening-style impact | `41,508,306.70` |

### Journal count

- distinct `CUS OP BAL` journals: `17`

### What overlaps directly with AR invoices

I compared the `17` `CUS OP BAL` journal amounts against `ar.invoice` documents dated `2025-01-01`.

Result:

- exact amount matches to January 1 posted AR invoices: `7` lines
- matched amount: `593,722.50`

Confirmed exact matches:

| `CUS OP BAL` Journal | Amount | AR Invoice | Customer |
|---|---:|---|---|
| `JE-2025-00028` | `134,375.00` | `ACC-SINV-2025-00457` | `HYPERIA VFS South Africa` |
| `JE-2025-00030` | `134,375.00` | `ACC-SINV-2025-00464` | `Hyperia Churchgate` |
| `JE-2025-00034` | `93,955.00` | `ACC-SINV-2025-00461` | `NTEL Lord Lugard` |
| `JE-2025-00035` | `93,955.00` | `ACC-SINV-2025-00462` | `NTEL CBD` |
| `JE-2025-00031` | `59,125.00` | `ACC-SINV-2025-00456` | `HYPERIA VFS Canada` |
| `JE-2025-00033` | `48,375.00` | `ACC-SINV-2025-00460` | `NTEL KADO` |
| `JE-2025-00032` | `29,562.50` | `ACC-SINV-2025-00463` | `Hyperia Quantun` |

### Additional directional overlap

Some larger `CUS OP BAL` amounts also match customer totals or later invoices by amount, for example:

- `JE-2025-00022` `1,200,000.00` matches a January 1 customer aggregate for `FAO Maiduguri`
- `JE-2025-00026` `1,213,406.25` matches a later invoice amount for `NTEL Wuse-2`

But these are not enough to conclude the whole AR opening was duplicated line-for-line.

### What this means

AR is not a clean one-step duplicate like UBA cash.

The evidence supports this narrower conclusion:

- at least `593,722.50` of `CUS OP BAL` was separately recreated as posted January 1 AR invoices
- the remaining `20,323,530.85` of `CUS OP BAL` still requires customer-level bridging

That remaining amount may represent:

- valid customer-detail carryforward not otherwise represented in subledger opening invoices
- or further duplicated balances that can only be proved from a customer-by-customer 2024 closing schedule

## 2. AP Opening Bridge

### Opening components hitting control `2000`

| Component | Amount |
|---|---:|
| `OB-000001` opening balance | `(40,310,713.50)` |
| `PUR OP BAL` journals on `2025-01-01` | `(37,376,751.04)` |
| Combined opening-style impact | `(77,687,464.54)` |

### Journal count

- distinct `PUR OP BAL` journals: `19`

### Exact overlap with supplier invoices

I compared the `19` `PUR OP BAL` amounts against supplier invoices dated `2025-01-01`.

Result:

- exact amount matches: `3` lines
- matched amount: `11,626,701.68`

Confirmed exact duplicates:

| `PUR OP BAL` Journal | Amount | Supplier Invoice | Supplier | Invoice State |
|---|---:|---|---|---|
| `JE-2025-00041` | `11,009,288.78` | `SINV202603-1439` | `Glo Zone` | `status=POSTED`, `posting_status=NOT_POSTED` |
| `JE-2025-00055` | `437,841.40` | `SINV202603-1440` | `Transglobal Projects & Allied Services` | `status=POSTED`, `posting_status=NOT_POSTED` |
| `JE-2025-00043` | `179,571.50` | `SINV202603-1441` | `Ideal Cabom Services Limited` | `status=POSTED`, `posting_status=NOT_POSTED` |

Important timing point:

- these three supplier invoices were created on `2026-03-14`
- but backdated to `invoice_date = 2025-01-01`

### What this means

AP has a stronger confirmed duplicate/subledger-state issue than AR.

At minimum:

- `11,626,701.68` of `PUR OP BAL` was later recreated as supplier invoices
- those supplier invoices are internally inconsistent because they are `POSTED` in business status but `NOT_POSTED` in posting status

### Remaining AP opening balance

After removing the confirmed exact duplicates:

- remaining `PUR OP BAL` not yet directly mirrored by exact January 1 invoice amount:
  - `37,376,751.04 - 11,626,701.68 = 25,750,049.36`

That remainder still needs supplier-level schedule proof.

## 3. Interpretation

### AR

- summary opening and detail opening both exist
- a small part is proven duplicated already
- the rest still needs customer schedule tracing

### AP

- summary opening and detail opening both exist
- a material part is already proven duplicated by matching supplier invoices
- the remainder is still unresolved, but AP is closer to a confirmed duplicate-load defect than AR

## 4. Practical Remediation

### AR

- build a customer schedule with:
  - 2024 closing receivable by customer
  - `OB-000001` summary load
  - `CUS OP BAL` journals
  - January 1 AR invoices
- tag each customer line as:
  - `summary only`
  - `detail only`
  - `duplicated`
  - `unresolved`

### AP

- immediately isolate the three confirmed duplicated supplier-invoice cases totaling `11,626,701.68`
- review whether the `PUR OP BAL` journal or the later supplier invoice should survive as the system-of-record opening detail
- separately build a supplier schedule for the remaining `25,750,049.36`

## 5. Audit Conclusion

The control-account differences are real opening-load control issues, not just reporting noise.

The strongest confirmed items so far are:

- AR:
  - confirmed duplicated overlap of `593,722.50`
- AP:
  - confirmed duplicated overlap of `11,626,701.68`
  - plus invalid mixed-state supplier invoices (`POSTED` but `NOT_POSTED`)

This is enough to say AR/AP are not audit-ready until the opening bridge is completed and the duplicated or conflicting opening records are resolved.
