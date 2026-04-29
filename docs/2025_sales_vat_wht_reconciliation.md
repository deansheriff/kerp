# 2025 Sales VAT and WHT Reconciliation

This workpaper covers the **sales side** of tax reconciliation for 2025:

- sales invoice base
- output VAT
- VAT withheld at source by customers
- WHT receivable from customers

## Conclusion

The sales-side reconciliation is possible, but the data model is weak.

What is usable:

- `ar.invoice` for sales base and output VAT
- `gl.posted_ledger_line` on customer-payment journals for:
  - `4031 Value Added Tax Withheld`
  - `1420 Withholding Taxes`

What is not usable:

- AR invoice withholding fields
- customer payment withholding fields

Those fields are effectively unused in 2025, so the withholding evidence sits in the GL rather than the AR subledger.

## Annual totals

### Sales invoices

- 2025 non-credit-note AR invoices: `18,713`
- sales subtotal: `1,530,101,854.24`
- output VAT: `106,537,489.89`

### VAT withheld at source by customers

From GL account `4031 Value Added Tax Withheld` on customer-payment journals:

- annual total: `17,391,154.36`

### WHT receivable from customers

From GL account `1420 Withholding Taxes` on customer-payment journals:

- annual total: `82,255,265.40`

## Data-model gaps

### AR invoice withholding fields are empty

For 2025 sales invoices:

- invoice rows: `18,713`
- rows with `withholding_tax_amount <> 0`: `0`
- rows with `vat_withheld = true`: `0`

### Customer-payment withholding fields are empty

For 2025 customer payments:

- payment rows: `16,574`
- rows with `wht_amount <> 0`: `0`

So the application is not storing customer-side tax deduction evidence in the AR tables, even though the GL clearly records it.

## Monthly sales-side totals

### Output VAT from AR invoices

- `2025-01` `15,563,882.57`
- `2025-02` `7,044,985.37`
- `2025-03` `4,038,823.61`
- `2025-04` `3,741,480.52`
- `2025-05` `4,313,734.49`
- `2025-06` `13,137,662.85`
- `2025-07` `12,745,355.67`
- `2025-08` `23,550,061.24`
- `2025-09` `11,104,172.42`
- `2025-10` `4,915,188.85`
- `2025-11` `3,171,351.41`
- `2025-12` `3,210,790.89`

### VAT withheld at source from GL `4031`

- `2025-01` `424,147.28`
- `2025-02` `693,000.00`
- `2025-04` `1,098,660.83`
- `2025-06` `9,028,046.25`
- `2025-09` `1,081,395.35`
- `2025-10` `3,525,404.65`
- `2025-12` `1,540,500.00`

Months with no `4031` movement:

- `2025-03`
- `2025-05`
- `2025-07`
- `2025-08`
- `2025-11`

### WHT receivable from GL `1420`

- `2025-01` `68,753,505.96`
- `2025-02` `522,171.00`
- `2025-03` `233,896.58`
- `2025-04` `1,408,508.38`
- `2025-05` `64,200.00`
- `2025-06` `6,649,293.55`
- `2025-07` `257,601.00`
- `2025-08` `104,171.00`
- `2025-09` `937,804.03`
- `2025-10` `1,847,659.90`
- `2025-11` `397,257.00`
- `2025-12` `1,079,197.00`

## Customer-level VAT withheld trace (`4031`)

Largest customers:

- `Nigerian Airspace Management Agency` `6,803,921.25`
- `Tax Appeal Tribunal` `3,081,000.00`
- `STATE HOUSE , ABUJA . NIGERIA` `2,040,404.65`
- `Presidential Metering Initiative -Smart Grid Development Ltd)` `1,485,000.00`
- `Standard Organisation of Nigeria (Abuja Corporate Headquarter)` `1,356,880.81`
- `NEXIM` `1,081,395.35`
- `FCT Internal Revenue Service` `849,552.30`
- `PTAD` `693,000.00`

These are traceable through customer-payment journals even though `ar.customer_payment.wht_amount` is blank.

## Customer-level WHT receivable trace (`1420`)

Largest customers:

- `Nigerian Airspace Management Agency` `4,535,947.50`
- `Tax Appeal Tribunal` `2,054,000.00`
- `Standard Organisation of Nigeria (Abuja Corporate Headquarter)` `1,809,174.42`
- `STATE HOUSE , ABUJA . NIGERIA` `1,360,269.77`
- `NEXIM` `720,930.23`
- `FCT Internal Revenue Service` `582,561.78`
- `Norrenberger Financial Group` `495,000.00`
- `PTAD` `462,000.00`
- `Presidential Metering Initiative -Smart Grid Development Ltd)` `396,000.00`

## Main risk

There is a major control gap:

- customer-side tax deductions are recorded in GL
- but not carried in the AR invoice / AR payment tax fields

That means:

- subledger-to-tax reconciliation is weaker than it should be
- certificate tracking likely depends on external schedules
- audit support for customer deductions must rely on:
  - payment journals
  - bank references
  - external certificates

## Practical next step

To complete the sales-side pack, build two customer schedules:

1. `VAT withheld at source`
   - customer
   - payment number
   - payment date
   - gross receipt
   - VAT withheld from `4031`
   - certificate/reference support

2. `WHT receivable`
   - customer
   - payment number
   - payment date
   - gross receipt
   - WHT from `1420`
   - certificate/reference support

Then compare those schedules to:

- TaxPro deducted-at-source summary
- 2025 WHT schedules
- certificate inventory from customers
