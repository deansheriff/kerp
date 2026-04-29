# 2025 Government and Enterprise Withholding Focus

This note narrows the sales-side VAT/WHT work to the customer segment that actually drives withholding risk.

## Conclusion

The withholding issue is concentrated in a small government / enterprise customer set, not the retail invoice population.

That means the correct audit approach is:

- ignore most retail receipts for withholding analysis
- focus on the customer-payment journals hitting:
  - `4031 Value Added Tax Withheld`
  - `1420 Withholding Taxes`

## Largest government / enterprise customers by combined withholding signal

`customer | VAT withheld (4031) | WHT receivable (1420) | total`

- `Nigerian Airspace Management Agency | 6,803,921.25 | 4,535,947.50 | 11,339,868.75`
- `Tax Appeal Tribunal | 3,081,000.00 | 2,054,000.00 | 5,135,000.00`
- `STATE HOUSE , ABUJA . NIGERIA | 2,040,404.65 | 1,360,269.77 | 3,400,674.42`
- `Standard Organisation of Nigeria (Abuja Corporate Headquarter) | 1,356,880.81 | 1,809,174.42 | 3,166,055.23`
- `Presidential Metering Initiative -Smart Grid Development Ltd) | 1,485,000.00 | 396,000.00 | 1,881,000.00`
- `NEXIM | 1,081,395.35 | 720,930.23 | 1,802,325.58`
- `FCT Internal Revenue Service | 849,552.30 | 582,561.78 | 1,432,114.08`
- `PTAD | 693,000.00 | 462,000.00 | 1,155,000.00`
- `Norrenberger Financial Group | 0.00 | 495,000.00 | 495,000.00`

## What this means

These customers should become the core withholding support pack.

For each one, finance should assemble:

1. related invoices
2. related receipts
3. deduction amount
4. certificate / remittance evidence
5. explanation of whether the deduction is VAT withheld, WHT, or both

## Next move

Use this narrowed customer set to produce:

- customer certificate tracker
- VAT withheld schedule
- WHT receivable schedule

Then move to the purchase-side VAT/WHT reconciliation.
