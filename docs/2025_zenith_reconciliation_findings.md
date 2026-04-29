# 2025 Zenith Reconciliation Findings

Date: 2026-04-28

Source files:

- `/root/zenith-statements/Account Statement - Soft Copy.xlsx`
- `/root/zenith-statements/Account Statement - Soft Copy (1).xlsx`
- `/root/zenith-statements/Account Statement - Soft Copy (2).xlsx`
- `/root/zenith-statements/Account Statement - Soft Copy (4).xlsx`
- `/root/zenith-statements/BOP_CBA_003_Report.xlsx`
- `/root/zenith-statements/BOP_CBA_003_Report (1).xlsx`
- `/root/zenith-statements/BOP_CBA_003_Report (2).xlsx`
- `/root/zenith-statements/BOP_CBA_003_Report (5).xlsx`

Scope:
- Zenith accounts mapped to GL `1204`, `1205`, `1206`, `1207`
- Year-end balance tie and movement logic for 2025

## Accounts Covered

| GL Code | Account Number | Currency | Statement 2025 Closing | GL 2025-12-31 Balance | Result |
|---|---|---|---:|---:|---|
| 1204 | 1011649523 | NGN | 2,562,798.73 | 2,562,798.73 | Exact tie |
| 1205 | 1016946461 | NGN | 118,054.84 | 118,054.84 | Exact tie |
| 1206 | 1016946454 | NGN | 77,738.18 | 77,738.18 | Exact tie |
| 1207 | 5070061296 | USD | 5.98 USD | 12,318,165.17 NGN functional | FX treatment required |

## Key Finding

For the three NGN Zenith accounts, the statement closing balances at `2025-12-31` tie exactly to the GL closing balances.

The apparent January movement differences are caused by the GL including separate `2025-01-01` opening journals.

That means:

- February to December movement should be compared directly to statement movement.
- January must be analyzed as:
  - opening journal effect
  - plus January statement movement
  - equals January GL movement

## 1204 - Zenith 523 Bank

### Statement basis

- 2024-12-31 closing balance: `2,666,175.75`
- 2025-12-31 closing balance: `2,562,798.73`
- Net 2025 statement movement: `(103,377.02)`

### GL basis

- 2025 full-year GL movement: `2,562,798.73`
- Opening journal on `2025-01-01`: `2,666,175.75`

### January explanation

- January statement movement: `(737,112.52)`
- January GL movement: `1,929,063.23`
- Difference: `2,666,175.75`
- This equals the carried-forward opening journal.

### Conclusion

No substantive reconciliation break found. January is explained by opening balance loading.

## 1205 - Zenith 461 Bank

### Statement basis

- 2024-12-31 closing balance: `3,078,524.51`
- 2025-12-31 closing balance: `118,054.84`
- Net 2025 statement movement: `(2,960,469.67)`

### GL basis

- 2025 full-year GL movement: `118,054.84`
- Opening journal on `2025-01-01`: `3,078,524.51`

### January explanation

- January statement movement: `(2,522,485.26)`
- January GL movement: `556,039.25`
- Difference: `3,078,524.51`
- This equals the carried-forward opening journal.

### Conclusion

No substantive reconciliation break found. January is explained by opening balance loading.

## 1206 - Zenith 454 Bank

### Statement basis

- 2024-12-31 closing balance: `61,402.51`
- 2025-12-31 closing balance: `77,738.18`
- Net 2025 statement movement: `16,335.67`

### GL basis

- 2025 full-year GL movement: `77,738.18`
- Opening journal on `2025-01-01`: `61,402.51`

### January explanation

- January statement movement: `(30,677.59)`
- January GL movement: `30,724.92`
- Difference: `61,402.51`
- This equals the carried-forward opening journal.

### Conclusion

No substantive reconciliation break found. January is explained by opening balance loading.

## 1207 - Zenith USD Bank

### Statement basis

- 2024-12-31 closing balance: `3,482.60 USD`
- 2025-12-31 closing balance: `5.98 USD`
- 2025 net nominal movement: `(3,476.62 USD)`

### GL basis

- 2025-12-31 GL balance: `12,318,165.17 NGN functional`
- Opening journal on `2025-01-01`: `15,636,677.53` functional
- 2025 net functional movement: `(3,318,512.36 NGN)`

### What the system is actually doing

- Account `1207 Zenith USD Bank` is **not** configured as multi-currency in `gl.account`.
- `gl.journal_entry` rows touching `1207` are stored with:
  - `currency_code = NGN`
  - `exchange_rate = 1.0000000000`
- There are no stored `USD -> NGN` rates in `core_fx.exchange_rate` for 2024-12-01 to 2025-12-31.
- `gl.posted_ledger_line.original_currency_code` is not carrying a usable USD basis for this account.
  - The only populated rows are a few tiny 2025 bank-fee lines, and those are also tagged `NGN`.

### Opening balance source

- The `2025-01-01` opening journal is:
  - `JE-2025-00078`
  - description: `Closing Balance as at 31st December 2024. Reference #OP BAL 09 dated 31-12-2024`
  - effect on `1207`: `15,636,677.53 NGN`
- Offset account on that opening journal: `3100 Retained Earnings`
- This opening amount does **not** represent a direct translation of the bank statement closing balance.
  - `15,636,677.53 / 3,482.60 = 4,489.94 NGN/USD`
  - that implied rate is not a credible 2024 year-end FX rate
- The opening therefore appears to be a carried-forward NGN book value, not a clean `USD balance x stored closing rate` calculation.

### Why it does not tie cleanly to the 2024 audited TB

- The audited workbook does contain a `Zenith Bank` closing balance of `21,442,780.30`.
- But the workbook does **not** break out a separate `Zenith USD Bank` line or the exact figure `15,636,677.53`.
- That means `1207` was likely loaded through a separate bank-opening process, not directly from a distinct audited-TB account line.

### Transaction translation evidence

Operational 2025 activity continues the same pattern: the statement is in USD, but the GL postings are hard-entered in NGN equivalents.

Examples:

- `2025-01-07` AFRINIC charge:
  - statement: `1,400.00 USD`
  - GL `JE-2025-01296`: `(2,148,132.00 NGN)`
  - implied rate: `1,534.38 NGN/USD`
- `2025-01-09` cash deposit:
  - statement: `1,200.00 USD`
  - GL `JE-2025-01832`: `1,986,000.00 NGN`
  - implied rate: `1,655.00 NGN/USD`
- `2025-01-20` supplier payment to Yueyang Xinghao:
  - statement: `974.00 USD`
  - GL `JE-2025-04228`: `(1,509,924.02 NGN)`
  - implied rate: `1,550.23 NGN/USD`

These implied rates vary by transaction and are not backed by a reusable FX-rate table inside the ERP.

### Additional timing issue

- Small bank-fee and stamp-duty items hit `1207` again in January-February 2026.
- One of those 2026 postings references an underlying card charge dated `2025-04-11`.
- That is a separate cutoff issue, but it is not the main reason the 2025 USD account fails a clean FX tie.

### Conclusion

This account cannot be defended by direct nominal comparison to the NGN GL balance.

The real source of the difference is structural:

- the account is not configured as multi-currency
- the opening was loaded as an NGN carried value, not a preserved USD basis
- transaction translations are being posted as standalone NGN journals
- the ERP does not hold a clean rate history or foreign-currency rollforward for this account

So the audit issue here is not simply "which FX rate should we use?" It is that the underlying ledger design does not preserve the USD bank account in auditable foreign-currency form.

## Overall Assessment

### Strong results

- Three NGN Zenith accounts tie exactly at year-end.
- Statement files are machine-readable and usable as audit evidence.
- Opening balances for the NGN accounts are explicitly represented by separate `OP BAL` journals.

### Remaining work

- Build transaction-level unmatched-item schedules for the NGN accounts if needed by the auditor.
- Perform full FX reconciliation for the Zenith USD account.
- Reconcile the non-Zenith bank and wallet accounts separately.

## Practical Implication

Zenith is now one of the cleaner areas of the 2025 audit pack.

The remaining bank-side audit risk is less about Zenith statement availability and more about:

- lack of formal approved reconciliations in the ERP
- the FX treatment of the USD account
- other non-Zenith bank/wallet accounts
