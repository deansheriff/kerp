# 2025 Inventory, Fixed Assets, and Tax Findings

Date: 2026-04-28

Scope:

- inventory evidence and valuation support
- fixed asset register and depreciation support
- VAT / WHT / statutory tax support and return status

## Summary

These three areas are not audit-ready yet.

- inventory has transactional activity and a material GL balance, but no usable 2025 valuation ledger
- fixed assets have material GL balances, but the asset subledger is effectively empty of value
- tax has transaction volume and material balances, but no 2025 reconciliation layer and no filed 2025 returns in the ERP

## Inventory

### What exists

- `inv.inventory_transaction`: `7,535` rows
- `inv.inventory_count`: `19` rows
- `inv.material_request`: `2,563` rows

### What is missing or weak

- `inv.inventory_valuation`: `0` rows
- `inv.item_wac_ledger`: only `14` rows
- all `item_wac_ledger` rows are dated between `2026-04-10` and `2026-04-28`, so they are not 2025 operating evidence

### GL exposure

- `1300 Materials`: `136,132,686.21`
- `5013 Materials COS`: `29,636,347.07`

### Count evidence

The inventory count table is not showing a robust year-end stock-count program.

- all `19` counts are `POSTED`
- recent counts are tiny one-item reconciliations
- latest samples:
  - `MAT-RECO-2026-00009` on `2026-01-22`, `1` item counted, `1` variance
  - `MAT-RECO-2026-00008` to `00001` on `2026-01-19`, each with `1` item counted and `1` variance
  - latest 2025 sample visible is `MAT-RECO-2025-00010` on `2025-11-05`, also `1` item counted and `1` variance

### Audit conclusion

The ERP contains movement records, but not a defensible 2025 valuation layer for the `Materials` balance. On current evidence:

- quantity support may be partially reconstructable from transactions
- valuation support is not system-complete
- year-end count evidence is too weak for a clean audit trail

### What is needed

- reconstruct inventory valuation as of `2025-12-31`
- tie that valuation to `1300 Materials`
- produce a credible count/cutoff memo for year-end stock
- explain the 2026 WAC backfill and whether it can be relied on only as a secondary reconstruction

## Fixed Assets

### What exists

- `fa.asset`: `555` rows

### What is missing or weak

- `fa.depreciation_run`: `0` rows
- `fa.depreciation_schedule`: `0` rows
- `fa.asset_disposal`: `0` rows
- `fa.asset_impairment`: `0` rows

### GL exposure

- `1100 Office Equipment`: `115,153,000.50`
- `1100-AD Office Equipment - Accumulated Depreciation`: `(63,884,514.07)`
- `1110 Motor Vehicle`: `24,680,000.00`
- `1110-AD Motor Vehicle - Accumulated Depreciation`: `(23,106,250.00)`
- `1120 Furniture & Fittings`: `15,756,660.00`
- `1120-AD Furniture & Fittings - Accumulated Depreciation`: `(9,330,740.00)`
- `1130-AD Plant & Machinery - Accumulated Depreciation`: `(3,400,860.44)`
- depreciation expense accounts sampled in GL are `0.00` for 2025

### Subledger quality

The fixed-asset subledger is not carrying the value needed to support the GL.

- total assets: `555`
- zero-cost assets: `554`
- non-zero-cost assets: `1`
- total subledger cost: `10.00`
- total subledger accumulated depreciation: `0.00`
- total subledger NBV: `10.00`
- earliest asset acquisition date in the current table: `2026-04-23`
- latest acquisition date: `2026-04-27`

Sample asset rows show the issue clearly:

- multiple `DT-AST-00xx` assets created in April 2026
- `functional_currency_cost = 0`
- `accumulated_depreciation = 0`
- `net_book_value = 0`

### Audit conclusion

The GL carries material fixed-asset balances, but the current `fa.asset` table does not support them. This is a major audit gap.

- the ERP asset register is effectively a 2026 shell, not a 2025 support register
- there is no in-system depreciation run history
- the current asset subledger cannot be used to prove cost, accumulated depreciation, or NBV at `2025-12-31`

### What is needed

- rebuild or import the 2025 fixed asset register with cost, in-service dates, useful lives, and accumulated depreciation
- tie that register to the audited 2024 opening and the 2025 GL movement
- run or reconstruct 2025 depreciation formally
- produce additions/disposals support outside the current ERP if the legacy detail lives elsewhere

## Tax, VAT, WHT, and Statutory Balances

### What exists

- `tax.tax_transaction`: `26,783` rows
- `tax.tax_period`: `98` rows
- `tax.tax_code`: `6` rows

Active tax codes:

- `VAT-7.5`
- `VAT-7.5 (inclusive)`
- `WHT 2%`
- `WHT 5%`
- `WHT 10%`
- `SD-1%`

2025 transaction activity by code is concentrated in:

- `VAT-7.5`: `20,862` rows, `141,359,771.84`
- `WHT 2%`: `802` rows, `2,130,934.94`

### What is missing or weak

- `tax.tax_reconciliation`: `0` rows
- only `1` `tax.tax_return` row exists in the whole system
- that single return is:
  - `return_type = VAT`
  - `status = DRAFT`
  - period `2026-02`
  - `final_amount = 1,452,237.18`
  - not filed
  - not paid

There are no 2025 tax returns stored in the ERP even though 2025 tax periods exist and are all marked `CLOSED`.

### GL exposure

Material year-end tax and statutory balances include:

- `1420 Withholding Taxes`: `150,563,735.58`
- `1440 Input VAT`: `31,749,478.98`
- `2110 WHT`: `(16,910,184.15)`
- `2120 VAT Payables`: `(106,090,379.39)`
- `2130 Pension`: `(2,304,612.00)`
- `2131 Payee`: `(37,228.99)`
- `2140 Tax Audit Liability`: `(7,587,458.53)`
- `2100 Income Tax`: `(3,745,613.00)`
- `6100 VAT Paid`: `2,670,147.72`
- `6040 ITF`: `1,360,067.24`

Several control-style tax accounts in the newer chart are still `0.00`, which suggests the live balances are sitting mostly in legacy/opening-style accounts rather than a fully reconciled statutory structure.

### Audit conclusion

Tax activity exists, but the compliance layer is not audit-ready.

- there is no stored 2025 monthly reconciliation set
- there are no stored 2025 VAT returns in the ERP
- material VAT and WHT balances exist in GL without an in-system closeout trail
- ITF appears in the GL as expense, but not as a dedicated tax-code workflow

### What is needed

- monthly 2025 VAT and WHT reconciliations
- return-by-return filing and payment support outside or inside the ERP
- a bridge from tax transactions to GL balances for VAT, WHT, PAYE, pension, NHF, and ITF where applicable
- confirmation of which statutory obligations are tracked in payroll or outside the tax module

## Overall Readiness Position

If cash, AR, and AP are assumed to be on a remediation path, the biggest remaining blockers to a defendable 2025 audit are now:

1. inventory valuation support for `1300 Materials`
2. a usable fixed-asset register and 2025 depreciation reconstruction
3. monthly VAT/WHT/statutory reconciliation packs and filing evidence

These are not minor cleanup items. They require reconstruction work, not just report extraction from the current ERP state.
