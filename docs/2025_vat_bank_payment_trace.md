# 2025 VAT Bank Payment Trace

This workpaper traces the `TaxPro` `Paid from bank` VAT schedule to:

- `6100 VAT Paid` journals
- AP supplier payments to `Federal Inland Revenue Services`
- bank GL credits
- bank statement evidence where available

## Conclusion

Yes, the bank-paid VAT schedule can be traced, with two important caveats:

1. the `TaxPro` month labels appear to represent the **tax month being settled**, not always the calendar month of cash movement
2. one `January 2025` `6100 VAT Paid` item for `886,180.60` exists in books and bank records, but does **not** appear in the TaxPro monthly bank-paid line-up

## 6100 VAT Paid entries found in GL

Six `6100 VAT Paid` postings exist in 2025:

- `2025-01-01` `JE-2025-00141` `ACC-PINV-2025-00231` `886,180.60`
- `2025-02-21` `JE-2025-11506` `ACC-PINV-2025-00306-1` `239,063.09`
- `2025-03-21` `JE-2025-18185` `ACC-PINV-2025-00375` `265,527.91`
- `2025-03-31` `JE-2025-20240` `ACC-PINV-2025-00437` `371,822.29`
- `2025-04-30` `JE-2025-27165` `ACC-PINV-2025-00582` `427,249.97`
- `2025-06-01` `JE-2025-34743` `ACC-PINV-2025-00702` `480,303.86`

All six are posted as:

- `DR 6100 VAT Paid`
- `CR 2100 Income Tax`

So these are **not the bank-payment entries themselves**. They are tax-expense / tax-liability reclasses.

## Source AP documents

Each `ACC-PINV...` reference is an AP invoice to `Federal Inland Revenue Services`:

- `ACC-PINV-2025-00231` `2025-01-01` `886,180.60`
- `ACC-PINV-2025-00306-1` `2025-02-21` `239,063.09`
- `ACC-PINV-2025-00375` `2025-03-21` `265,527.91`
- `ACC-PINV-2025-00437` `2025-03-31` `371,822.29`
- `ACC-PINV-2025-00582` `2025-04-30` `427,249.97`
- `ACC-PINV-2025-00702` `2025-06-01` `480,303.86`

All are `PAID / POSTED`.

## Actual bank payments traced

These amounts were settled through AP supplier payments:

- `ACC-PAY-2025-05666` `2025-01-21` `886,180.60`
  - bank GL: `1202 UBA`
  - journal: `JE-2025-04469`
  - reference: `UBA20250121WBBPT26119`

- `ACC-PAY-2025-09010` `2025-02-21` `239,063.09`
  - bank GL: `1204 Zenith 523 Bank`
  - journal: `JE-2025-11498`
  - reference: `ZNB10120250221PAYFEDERAL`

- `ACC-PAY-2025-12297` `2025-03-21` `265,527.91`
  - bank GL: `1204 Zenith 523 Bank`
  - journal: `JE-2025-18182`
  - reference: `ZNB10120250321PAYFEDERAL`

- `ACC-PAY-2025-14796` `2025-04-21` `371,822.29`
  - bank GL: `1204 Zenith 523 Bank`
  - journal: `JE-2025-25090`
  - reference: `ZNB10120250421PAYFEDERAL`

- `ACC-PAY-2025-19856` `2025-05-21` `427,249.97`
  - bank GL: `1204 Zenith 523 Bank`
  - journal: `JE-2025-32421`
  - reference: `ZNB10120250521PAYFEDERAL`

- `ACC-PAY-2025-22129` `2025-06-20` `480,303.86`
  - bank GL: `1204 Zenith 523 Bank`
  - journal: `JE-2025-38362`
  - reference: `ZNB10120250620PAYFEDERAL`

## Bank statement confirmation

### UBA

Confirmed in `/root/uba-statements`:

- `2025-01-21`
- narration includes `WB/BPT/261190270370/REMITA ...`
- amount `886,180.60`

This matches the AP payment:

- `ACC-PAY-2025-05666`
- UBA reference `UBA20250121WBBPT26119`

### Zenith 523

Confirmed in `/root/zenith-statements/BOP_CBA_003_Report.xlsx`:

- `2025-02-21` `Pay - FEDERAL INLAND REVENUE SERVICE ... For - VAT Filing` `239,063.09`
- `2025-03-21` `Pay - FEDERAL INLAND REVENUE SERVICE ... For - VAT Filing` `265,527.91`
- `2025-04-21` `Pay - FEDERAL INLAND REVENUE SERVICE ... For - VAT Filing` `371,822.29`
- `2025-05-21` `Pay - FEDERAL INLAND REVENUE SERVICE ... For - VAT Filing` `427,249.97`
- `2025-06-20` `Pay - FEDERAL INLAND REVENUE SERVICE ... For - VAT Filing` `480,303.86`

These all match the AP payment records and bank GL credits.

## Tie to TaxPro `Paid from bank`

TaxPro shows:

- `Jan` `239,063`
- `Feb` `265,528`
- `Mar` `371,822`
- `Apr` `427,250`
- `May` `480,304`

These amounts trace to actual bank payments, but on the following cash dates:

- TaxPro `Jan` -> paid `2025-02-21` `239,063.09`
- TaxPro `Feb` -> paid `2025-03-21` `265,527.91`
- TaxPro `Mar` -> paid `2025-04-21` `371,822.29`
- TaxPro `Apr` -> paid `2025-05-21` `427,249.97`
- TaxPro `May` -> paid `2025-06-20` `480,303.86`

This strongly suggests the TaxPro workbook is labeling the **return month**, while the actual bank movement occurred in the next month.

## Unresolved anomaly

The following real bank payment exists but is not reflected in the TaxPro monthly bank-paid series:

- `2025-01-21` `886,180.60`
  - `ACC-PAY-2025-05666`
  - UBA
  - linked to FIRS
  - tied to `ACC-PINV-2025-00231`

This needs explanation. Likely possibilities:

- it belongs to a different tax obligation, despite the `6100 VAT Paid` classification
- it was excluded from the TaxPro VAT summary
- it was treated as a prior-period or non-standard VAT settlement

## Additional evidence: VAT credit settlements

Zenith statement data also shows multiple `2025-05-02` FIRS payments labeled:

- `VATWallet Credit`
- `WHTWallet Credit`
- `SDWallet Credit`

These likely support the TaxPro `Paid from VAT Credit` column rather than `Paid from bank`.

## Control issue

Although the cash trail is traceable, the AP data model is weak here:

- FIRS invoices are marked `PAID`
- but the queried `ap.payment_allocation` rows were empty for these invoices

So the payment trail is defensible mainly through:

- `ap.supplier_payment`
- payment journals
- bank GL
- statement evidence

rather than through a complete AP allocation chain.
