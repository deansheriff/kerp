# 2025 Opening Balance Closure Schedule

Date: 2026-04-28

Scope:

- all opening-style journals dated `2025-01-01`
- interaction between `OB-000001` and detailed opening journals
- closure actions needed to eliminate duplicate or structurally weak opening balances

## Executive Position

The opening-balance problem is now narrow enough to close with a controlled cleanup.

The opening layer should be treated in three buckets:

1. keep as the surviving detailed opening representation
2. reverse as duplicate opening
3. bridge or reclass where `OB-000001` overlaps with detailed subledger openings

## What Is Already Sound

- `OB-000001` is the main 2024 audited-TB carryforward journal
- most AR opening customers are now identified from ERPNext
- most AP opening suppliers are now identified from ERPNext
- retained earnings provenance is understood
- detailed Zenith subaccounts `1204`, `1205`, `1206`, and `1207` explain the old aggregate Zenith opening exactly

Key identity:

- `1200 Zenith Bank` in `OB-000001`: `21,442,780.30`
- detailed Zenith openings:
  - `JE-2025-00012` `1204 Zenith 523 Bank`: `2,666,175.75`
  - `JE-2025-00013` `1205 Zenith 461 Bank`: `3,078,524.51`
  - `JE-2025-00014` `1206 Zenith 454 Bank`: `61,402.51`
  - `JE-2025-00078` `1207 Zenith USD Bank`: `15,636,677.53`
- total detailed Zenith openings: `21,442,780.30`

So `1200` is not a separate real bank opening. It is a legacy aggregate duplicated by the detailed Zenith bank openings.

## Opening Issues To Reverse

### 1. Duplicate cash/wallet openings

These are exact duplicates against balances already carried in `OB-000001`.

| Account | Duplicate Journal(s) | Amount | Recommended Action |
|---|---|---:|---|
| `1202 UBA` | `JE-2025-00015` | `2,487,543.70` | reverse duplicate journal; keep `OB-000001` line or supported bank opening layer, not both |
| `1211 Paystack OPEX Account` | `JE-2025-00016`, `JE-2025-00017` | `338,115.65` | reverse duplicate journals; `OB-000001` already carries both components |
| `1220 Cash at Hand` | `JE-2025-00018` | `3,245.44` | reverse duplicate journal |

### 2. Legacy aggregate Zenith opening

| Account | Journal | Amount | Recommended Action |
|---|---|---:|---|
| `1200 Zenith Bank` | `OB-000001` line | `21,442,780.30` | reverse or reclass out of `1200`; keep detailed Zenith openings in `1204/1205/1206/1207` |

This is not an arithmetic mismatch. It is a chart-of-accounts migration overlap.

### 3. Duplicate or unsupported WHT/tax openings

| Account | Journal | Amount | Assessment | Recommended Action |
|---|---|---:|---|---|
| `1420 Withholding Taxes` | `JE-2025-00080` | `68,308,470.18` | duplicates `OB-000001` opening `68,308,470.02` almost exactly | reverse `JE-2025-00080`; investigate residual `0.16` difference separately |
| `2110 WHT` | `JE-2025-00079` | `14,536,448.13` | extra opening loaded outside audited-TB opening | reverse unless an external 2024 WHT-liability schedule proves it should survive |
| `2100 Income Tax` | `JE-2025-00076` | `7,587,459.00` | extra opening-style tax entry outside `OB-000001` | keep only if 2024 tax-close support exists; otherwise reverse as unsupported opening load |

## Opening Issues To Keep As Surviving Detail

### 1. Detailed bank openings

Keep:

- `JE-2025-00012` `1204 Zenith 523 Bank`
- `JE-2025-00013` `1205 Zenith 461 Bank`
- `JE-2025-00014` `1206 Zenith 454 Bank`
- `JE-2025-00078` `1207 Zenith USD Bank`

Important note:

- `1207 Zenith USD Bank` remains structurally weak for FX accounting
- but from an opening-balance perspective, it is part of the detailed Zenith split and should not coexist with the old aggregate `1200`

### 2. AR customer opening detail

Keep the `CUS OP BAL` journals as the surviving detailed AR opening layer, subject to the duplicate-invoice unwind already documented in:

- [2025_ar_opening_customer_bridge.md](/root/dotmac/docs/2025_ar_opening_customer_bridge.md:1)
- [2025_ar_duplicate_cleanup_memo.md](/root/dotmac/docs/2025_ar_duplicate_cleanup_memo.md:1)

Do not unwind `National Health Insurance Authority` purely on the assumption of collection. It remains an open receivable.

### 3. AP supplier opening detail

Keep the supplier-level opening journals as the surviving detailed AP opening layer, subject to the mirrored-later-invoice unwind already documented in:

- [2025_ap_residual_opening_bridge.md](/root/dotmac/docs/2025_ap_residual_opening_bridge.md:1)
- [2025_ap_duplicate_case_cleanup_memo.md](/root/dotmac/docs/2025_ap_duplicate_case_cleanup_memo.md:1)

Also keep `JE-2025-00077` for the `Internet Exchange Point of Nigeria` payable if supplier support confirms it.

## Control-Account Overlaps To Bridge

### 1. Trade Receivables `1400`

Opening layers currently loaded:

- `OB-000001` on `1400`: `20,591,053.35`
- customer-detail opening journals on `1400`: `20,917,253.35`
- overlap difference: `326,200.00`

Recommended closure:

1. keep the customer-detail opening journals as the surviving AR opening support
2. unwind the seven duplicate January 1 invoices per the AR cleanup memo
3. reverse the `OB-000001` `1400` line
4. resolve the residual `326,200.00` bridge difference:
   - either by validating the customer-detail total to the 2024 closing schedule and posting a formal bridge
   - or by identifying specific customer/opening items that should not survive

### 2. Trade Payables `2000`

Opening layers currently loaded:

- `OB-000001` on `2000`: `(40,310,713.50)`
- supplier-detail opening journals on `2000` including `JE-2025-00077`: `(40,186,751.04)`
- overlap difference: `123,962.46`

Recommended closure:

1. keep the supplier-detail opening journals as the surviving AP opening support
2. unwind the three later mirrored supplier invoices per the AP cleanup memo
3. reverse the `OB-000001` `2000` line
4. resolve the residual `123,962.46` bridge difference through supplier schedule support or a controlled bridge journal

## Practical Cleanup Order

1. Reverse exact duplicate opening journals:
   - `JE-2025-00015`
   - `JE-2025-00016`
   - `JE-2025-00017`
   - `JE-2025-00018`
   - `JE-2025-00080`

2. Reverse or reclass the legacy aggregate Zenith opening:
   - `OB-000001` line on `1200 Zenith Bank`

3. Decide tax-opening support:
   - `JE-2025-00079`
   - `JE-2025-00076`

4. Execute AR duplicate cleanup:
   - remove the 9 duplicate-linked allocation rows
   - reverse the 7 duplicate January 1 invoices
   - reverse `JE-2025-00178`, `00179`, `00182`, `00183`, `00184`, `00185`, `00186` if the app does not auto-reverse
   - reallocate the surviving receipts

5. Execute AP duplicate cleanup:
   - remove the 3 AP allocation rows
   - void the 3 draft payments
   - remove the 3 mirrored supplier invoices
   - reverse `JE202604-43253`, `43254`, `43255` if the app does not auto-reverse

6. Bridge the AR/AP control-account overlaps:
   - reverse `OB-000001` line on `1400`
   - reverse `OB-000001` line on `2000`
   - post formal bridge adjustments for the residual `326,200.00` AR difference and `123,962.46` AP difference if source schedules support them

## What This Would Leave Open

If the actions above are completed, the remaining opening-balance issues should be:

- `1207 Zenith USD Bank` as an FX-structure problem, not a duplication problem
- any tax-opening journals that cannot yet be proven from 2024 schedules
- the small AR/AP bridge differences pending final source support

That is a much smaller and more defensible residual opening-balance position than the current state.
