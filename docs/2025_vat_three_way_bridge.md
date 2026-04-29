# 2025 VAT Three-Way Bridge

This workpaper compares three monthly VAT views for `2025`:

1. `TaxPro workbook`
2. `ERP transaction basis`
   - sales invoices
   - purchase invoices
   - credit notes
   - WHT/VAT Form A credit from GL `4031`
3. `GL-derived basis`
   - `2120 VAT Payables` credit movement
   - less `1440 Input VAT` debit movement
   - less `4031` WHT/VAT credit movement

## Conclusion

Using GL is useful, but it should be treated as a **control bridge**, not the sole filing basis.

In this dataset:

- the `GL-derived net VAT payable` tracks the `ERP transaction basis` closely
- the `TaxPro workbook` is materially lower than both for much of the year

Annual comparison:

- TaxPro net payable: `19,879,217.90`
- ERP transaction basis net payable: `57,736,054.23`
- GL-derived net payable: `56,908,323.55`

Variance:

- TaxPro vs ERP: `(37,856,836.33)`
- TaxPro vs GL: `(37,029,105.65)`
- ERP vs GL: `827,730.68`

That means the main mismatch is **not** between ERP transactions and GL.  
The main mismatch is between **TaxPro summary** and the books.

There is also a critical timing fact:

- `100%` of the 2025 AR invoices currently driving ERP output VAT were created in `2026-03`
- `100%` of the 2025 AP supplier invoices currently driving ERP input VAT were created in `2026-03`

So the ERP VAT schedule is a **March 2026 backfilled reconstruction of 2025 activity**, not a contemporaneous 2025 filing ledger.

## Method

### TaxPro workbook

Source:
- `/root/VAT SUmmary on Tax Pro 2025 (3) (2) (1).xlsx`

Fields used:
- output VAT
- input VAT
- deducted at source
- payable
- paid from bank
- paid from VAT credit

### ERP transaction basis

Derived from:
- `ar.invoice`
- `ap.supplier_invoice`
- credit notes in `ar.invoice`
- WHT/VAT Form A credits from GL account `4031`

Formula:
- `net output VAT`
- less `input VAT`
- less `WHT/VAT credit`
- equals `computed net payable`

### GL-derived basis

Derived from monthly GL movements:
- `2120 VAT Payables`
- `1440 Input VAT`
- `4031` withheld VAT credits
- `6100 VAT Paid` shown separately as settlement evidence, not part of the pre-payment liability computation

Formula:
- `2120 credit movement`
- less `1440 input VAT movement`
- less `4031 WHT/VAT movement`
- equals `GL-derived net payable`

## Monthly comparison

`period | TaxPro payable | ERP payable | GL-derived payable | TaxPro vs GL | ERP vs GL | VAT paid GL`

- `2025-01 | 239,063.00 | 13,836,811.52 | 13,554,472.22 | (13,315,409.22) | 282,339.30 | 886,180.60`
- `2025-02 | 958,527.90 | 5,533,706.48 | 5,470,224.23 | (4,511,696.33) | 63,482.25 | 239,063.09`
- `2025-03 | 371,822.00 | 3,263,207.12 | 3,223,917.80 | (2,852,095.80) | 39,289.32 | 637,350.20`
- `2025-04 | 427,250.00 | 1,004,156.26 | 834,648.00 | (407,398.00) | 169,508.26 | 427,249.97`
- `2025-05 | 480,304.00 | 2,798,724.85 | 2,625,024.90 | (2,144,720.90) | 173,699.95 | 0.00`
- `2025-06 | 2,637,323.00 | (4,816,107.12) | (4,891,694.16) | 7,529,017.16 | 75,587.04 | 480,303.86`
- `2025-07 | 2,736,625.00 | 11,207,755.31 | 10,990,201.41 | (8,253,576.41) | 217,553.90 | 0.00`
- `2025-08 | 2,603,296.00 | 22,022,644.16 | 21,922,075.47 | (19,318,779.47) | 100,568.69 | 0.00`
- `2025-09 | 1,875,361.00 | 7,625,236.26 | 7,502,893.77 | (5,627,532.77) | 122,342.49 | 0.00`
- `2025-10 | 3,054,572.00 | (3,297,066.43) | (3,390,524.27) | 6,445,096.27 | 93,457.84 | 0.00`
- `2025-11 | 1,443,957.00 | 647,741.35 | 575,044.89 | 868,912.11 | 72,696.46 | 0.00`
- `2025-12 | 3,051,117.00 | (2,090,755.53) | (1,507,960.71) | 4,559,077.71 | (582,794.82) | 0.00`

## What this means

### 1. GL is useful

The GL-derived basis is a good cross-check. It lands within `827,730.68` of the ERP transaction basis for the full year, which is relatively tight compared with the much larger TaxPro gap.

### 2. TaxPro is not reconciling to the books

The TaxPro workbook appears to be a filing/finance-prepared schedule, but not one that currently ties to:

- ERP invoice data
- tax transactions
- GL movement

### 2a. Timing likely explains much of the gap

Because all 2025 VAT-driving invoices in the ERP were created in `2026-03`, TaxPro may reflect:

- actual 2025/early-2026 filing positions prepared outside the ERP, while
- the ERP reflects a later reconstructed 2025 dataset loaded during migration/backfill

This does not automatically make TaxPro correct, but it does explain why the ERP and GL align with each other while still differing sharply from TaxPro.

### 3. The main problem is not the GL

If the objective is to understand what VAT “ought” to have been, the biggest variance driver is the external TaxPro summary versus the ERP-recorded activity.

### 4. Payments are incomplete in-book

`6100 VAT Paid` shows only `2,670,147.72` for the year, while the TaxPro workbook shows:

- bank paid: `1,783,967.00`
- paid from VAT credit: `14,764,928.00`

So cash payment evidence and VAT-credit utilization support still need to be assembled outside the ERP.

## Timing evidence

AR invoices contributing output VAT:

- `2025-01` invoice-date VAT `15,563,882.57` — created in `2026-03`
- `2025-02` invoice-date VAT `7,044,985.37` — created in `2026-03`
- `2025-03` invoice-date VAT `4,038,823.61` — created in `2026-03`
- `2025-04` invoice-date VAT `3,741,480.52` — created in `2026-03`
- `2025-05` invoice-date VAT `4,313,734.49` — created in `2026-03`
- `2025-06` invoice-date VAT `13,137,662.85` — created in `2026-03`
- `2025-07` invoice-date VAT `12,745,355.67` — created in `2026-03`
- `2025-08` invoice-date VAT `23,550,061.24` — created in `2026-03`
- `2025-09` invoice-date VAT `11,104,172.42` — created in `2026-03`
- `2025-10` invoice-date VAT `4,915,188.85` — created in `2026-03`
- `2025-11` invoice-date VAT `3,171,351.41` — created in `2026-03`
- `2025-12` invoice-date VAT `3,210,790.89` — created in `2026-03`

AP supplier invoices contributing input VAT:

- all monthly 2025 input VAT currently in ERP was also created in `2026-03`

## Recommended next step

Build the final monthly VAT reconciliation with four layers:

1. `TaxPro filed summary`
2. `ERP transaction basis`
3. `GL-derived basis`
4. `evidence / explanation`

Explanation buckets should include:

- missing or backfilled invoices
- credit notes
- inclusive-VAT treatment
- timing/cutoff
- VAT withheld at source certificates
- VAT credit carryforward usage
- manual GL journals or tax backfills
