# 2024 TB to 2025 Opening Bridge

Date: 2026-04-28

Purpose: bridge the audited 2024 trial balance in `/root/2024 TB.xlsx` to the posted `2025-01-01` opening journal `OB-000001` in Dotmac ERP.

## Summary

- The 2025 opening journal appears to have been loaded from the 2024 close.
- Most major balance sheet lines tie by amount but were loaded into a remapped chart of accounts.
- The retained earnings difference is now substantially explained by the 2024 nominal account close.
- The WHT and Paystack differences are also explainable from the workbook itself.
- P&L lines in the 2024 TB should not appear directly in the 2025 opening journal except through retained earnings and any explicit year-end reclassification.

## Balance Sheet Bridge

| 2024 TB Code | 2024 TB Account | 2024 Close | 2025 Opening Code | 2025 Opening Account | 2025 Opening | Status | Note |
|---|---|---:|---|---|---:|---|---|
| 1110 | Office Equipment | 114,463,000.50 | 1100 | Office Equipment | 114,463,000.50 | `COA_REMAP` | Amount ties exactly |
| 1211 | Accumulated Depreciation - Office Equipment | (63,884,514.07) | 1100-AD | Office Equipment - Accumulated Depreciation | (63,884,514.07) | `COA_REMAP` | Amount ties exactly |
| 1120 | Motor Vehicle | 24,680,000.00 | 1110 | Motor Vehicle | 24,680,000.00 | `COA_REMAP` | Amount ties exactly |
| 1212 | Accumulated Depreciation - Motor Vehicle | (23,106,250.00) | 1110-AD | Motor Vehicle - Accumulated Depreciation | (23,106,250.00) | `COA_REMAP` | Amount ties exactly |
| 1130 | Furniture & Fittings | 15,756,660.00 | 1120 | Furniture & Fittings | 15,756,660.00 | `COA_REMAP` | Amount ties exactly |
| 1213 | Accumulated Depreciation - Furniture & Fittings | (9,330,740.00) | 1120-AD | Furniture & Fittings - Accumulated Depreciation | (9,330,740.00) | `COA_REMAP` | Amount ties exactly |
| 1140 | Plant & Machinery | 8,502,151.11 | 1130 | Plant & Machinery | 8,502,151.11 | `COA_REMAP` | Amount ties exactly |
| 1214 | Accumulated Depreciation - Plant & Machinery | (3,400,860.44) | 1130-AD | Plant & Machinery - Accumulated Depreciation | (3,400,860.44) | `COA_REMAP` | Amount ties exactly |
| 1310 | Zenith Bank | 21,442,780.30 | 1200 | Zenith Bank | 21,442,780.30 | `COA_REMAP` | Amount ties exactly |
| 1330 | UBA | 2,487,543.70 | 1202 | UBA | 2,487,543.70 | `COA_REMAP` | Amount ties exactly |
| 1360 | First Bank | 50,000.00 | 1203 | First Bank | 50,000.00 | `COA_REMAP` | Amount ties exactly |
| 1380 | Cash at Hand | 3,245.44 | 1220 | Cash at Hand | 3,245.44 | `COA_REMAP` | Amount ties exactly |
| 1340 | Paystack | 297,500.00 | 1211 | Paystack OPEX Account | 338,115.65 | `AGGREGATED` | Combined into a single opening wallet balance |
| 1341 | Paystack OPEX Account | 40,615.65 | 1211 | Paystack OPEX Account | 338,115.65 | `AGGREGATED` | `297,500.00 + 40,615.65 = 338,115.65` |
| 1610 | Materials | 37,438,550.79 | 1300 | Materials | 37,438,550.79 | `COA_REMAP` | Amount ties exactly |
| 1410 | Trade Receivables | 20,591,053.35 | 1400 | Trade Receivables | 20,591,053.35 | `COA_REMAP` | Amount ties exactly |
| 1520 | Withholding Taxes | 68,308,470.02 | 1420 | Withholding Taxes | 68,308,470.02 | `COA_REMAP` | Amount ties exactly |
| 2110 | Trade Payables | (40,310,713.50) | 2000 | Trade Payables | (40,310,713.50) | `COA_REMAP` | Amount ties exactly |
| 2120 | Accurued Expenses | (599,999.52) | 2020 | Accrued Expenses | (599,999.52) | `COA_REMAP` | Amount ties exactly |
| 2280 | Tax Audit Liability | (7,587,458.53) | 2140 | Tax Audit Liability | (7,587,458.53) | `COA_REMAP` | Amount ties exactly |
| 2510 | Long Term Borrowings | (194,554,302.04) | 2500 | Long Term Borrowings | (194,554,302.04) | `COA_REMAP` | Amount ties exactly |
| 3110 | Issued and Fully Paid | (14,650,000.00) | 3000 | Issued and Fully Paid | (14,650,000.00) | `COA_REMAP` | Amount ties exactly |
| 3210 | Retained Earnings | (6,734,260.89) | 3100 | Retained Earnings | 46,499,766.75 | `EXPLAINED` | Difference is explained by 2024 nominal account close; residual rounding difference is 1.42 |

## Opening Journal Lines Explained by Workbook Notes / Aggregation

| 2025 Opening Code | 2025 Opening Account | 2025 Opening | Current View |
|---|---|---:|---|
| 2110 | WHT | (3,136,499.51) | Ties to the 2024 TB `WHT` row and to the workbook note adjusting WHT payable to about `3,136,500` |
| 1211 | Paystack OPEX Account | 338,115.65 | Aggregate of `Paystack 297,500.00` and `Paystack OPEX Account 40,615.65` |

## Retained Earnings Rollforward

The apparent retained earnings mismatch is explained by closing the 2024 nominal accounts into retained earnings.

### Components

| Component | Amount |
|---|---:|
| 2024 TB retained earnings | (6,734,260.89) |
| 2024 revenue total | (720,321,657.44) |
| 2024 cost of sales total | 505,563,408.66 |
| 2024 operating expense total | 225,982,793.05 |
| 2024 finance / tax expense total | 39,240,094.79 |
| 2024 pension line carried in workbook | 2,769,390.00 |
| Net nominal close | 53,234,029.06 |
| Expected 2025 opening retained earnings | 46,499,768.17 |
| Actual 2025 opening retained earnings | 46,499,766.75 |
| Residual difference | (1.42) |

### Interpretation

- The 2024 TB shows a net 2024 loss of `53,234,029.06`.
- Rolling that loss into the 2024 retained earnings balance of `(6,734,260.89)` produces an expected opening retained earnings balance of `46,499,768.17`.
- The actual opening journal has `46,499,766.75`, leaving only a `1.42` rounding difference.
- That is sufficiently close to treat the retained earnings opening as explained, subject to external audit review.

## TB Lines That Should Not Carry Directly Into Opening

These lines appear in the 2024 TB but should generally roll into retained earnings rather than appear as separate 2025 opening BS lines:

- `Other Business Revenue`
- `Internet Revenue`
- `Purchases`
- `Purchase of bandwitdh and Interconnect`
- `Staff Salaries & Wage`
- `Staff Training`
- `Statutory Expenses`
- `Medical Expenses`
- `Printing & stationery`
- `Rent or Lease Payment`
- `Utilities`
- `Telephone bills`
- `Fuel & Lubricant`
- `Pension` as expense
- `Motor Vehichle Repairs & Maintenance`
- `Insurance Expenses`
- `Contract Tender Fees`
- `Finance Cost`
- `Transportation & Travelling Expenses`
- `Advertising Expenses`
- `Audit Fee`
- `Depreciation`
- `Tax Audit Expense`

## Important Workbook Notes

The 2024 workbook includes explicit audit adjustment notes near the bottom:

- Use `35,072,680` for tax audit expense instead of `48,896,176`.
- WHT payables was adjusted to `3,136,500` based on accountant input.

Those notes align with the `WHT` and tax-related opening balances and should be retained as audit evidence.

## Current Conclusion

- The opening journal is substantially traceable to the 2024 TB.
- The primary evidence gap is no formal signed bridge showing:
  - old TB code
  - new GL code
  - balance movement into retained earnings
  - tax/WHT adjustment rationale
- Before external audit use, this bridge should be converted into a signed workpaper with supporting schedules for:
  - retained earnings
  - WHT / tax liabilities
  - Paystack / bank wallet balances
