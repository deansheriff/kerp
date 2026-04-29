# 2025 VAT TaxPro Workbook Assessment

Source workbook reviewed:
- `/root/VAT SUmmary on Tax Pro 2025 (3) (2) (1).xlsx`

## Conclusion

The workbook is usable as an external VAT summary schedule, but it is **not sufficient on its own** and it does **not tie cleanly** to the ERP-derived 2025 VAT data.

It can be used for:
- monthly filing summary
- bank-vs-VAT-credit settlement tracking
- starting point for a VAT reconciliation pack

It cannot be used alone as audit support because it does not prove:
- underlying sales invoices
- underlying purchase invoices
- VAT withheld at source support
- VAT remittance support
- ERP tax-return lifecycle

## Workbook totals

- Output VAT: `48,273,963.00`
- Input VAT: `27,285,715.53`
- VAT deducted at source: `19,718,036.00`
- Net VAT payable: `19,879,217.90`
- Paid from bank: `1,783,967.00`
- Paid from VAT credit: `14,764,928.00`

## ERP-derived comparison

Invoice-derived ERP schedule for `2025-01-01` to `2025-12-31`:

- Net output VAT: `106,850,082.91`
- Input VAT recoverable: `31,722,874.32`
- WHT/VAT credit via GL `4031`: `17,391,154.36`
- Computed net payable: `57,736,054.23`

Variance versus TaxPro workbook:

- Output VAT difference: `(58,576,119.91)`
- Input VAT difference: `(4,437,158.80)`
- WHT/VAT credit difference: `2,326,881.64`
- Net payable difference: `(37,856,836.33)`

## Stored ERP tax status

- VAT tax codes present:
  - `VAT-7.5`
  - `VAT-7.5 (inclusive)`
- Only one ERP tax return exists:
  - `return_type = VAT`
  - `status = DRAFT`
  - `total_output_tax = 3,058,595.63`
  - `total_input_tax = 1,606,358.45`
  - `net_tax_payable = 1,452,237.18`

This is not a complete 2025 return set.

## VAT transaction evidence in ERP

`tax.tax_transaction` for 2025 VAT:

- `INPUT`: `33,853,809.21`
- `OUTPUT`: `107,505,962.63`
- Total VAT tax transactions: `141,359,771.84`

This is materially above the TaxPro workbook totals and confirms the workbook is not a direct dump from ERP tax transactions.

## Largest month-level warning signs

- `2025-01`
  - TaxPro output VAT: `2,031,339.00`
  - ERP net output VAT: `15,563,882.57`
  - Difference: `(13,532,543.57)`

- `2025-08`
  - TaxPro output VAT: `3,536,638.00`
  - ERP net output VAT: `23,578,665.89`
  - Difference: `(20,042,027.89)`

- `2025-10`
  - TaxPro net payable: `3,054,572.00`
  - ERP computed net payable: `(3,297,066.43)`
  - Sign flips between the two schedules

- `2025-12`
  - TaxPro input VAT: `1,393,197.00`
  - ERP input VAT: `3,803,778.98`
  - Difference: `(2,410,581.98)`

## Practical audit use

Use the workbook as:
- filed/finance-prepared monthly VAT summary
- payment-method tracker (`bank` vs `VAT credit`)
- reference schedule to compare against ERP

Do not use it as:
- sole VAT audit evidence
- proof of VAT payable balance
- proof of output/input VAT completeness

## What is needed next

1. Build a month-by-month bridge:
   - TaxPro workbook
   - ERP invoice-derived VAT schedule
   - ERP VAT tax transactions
   - GL accounts `1440`, `2120`, `6100`

2. Gather filing support:
   - TaxPro/FIRS submission acknowledgements
   - payment receipts
   - VAT credit carryforward support
   - VAT withheld-at-source certificates

3. Resolve the variance drivers:
   - missing / extra invoices in ERP
   - inclusive-VAT handling
   - credit notes
   - timing/cutoff
   - backfilled tax transactions

4. Create final 2025 VAT pack:
   - monthly reconciliation
   - filing evidence
   - payment evidence
   - closing VAT payable bridge to GL
