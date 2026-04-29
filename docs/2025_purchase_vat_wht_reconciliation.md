# 2025 Purchase VAT and WHT Reconciliation

This workpaper covers the **purchase side** of 2025 tax reconciliation:

- supplier invoice base
- input VAT
- supplier-side WHT
- comparison to GL

## Conclusion

The purchase-side data is stronger than the sales side.

What is usable:

- `ap.supplier_invoice.tax_amount` for input VAT
- `ap.supplier_invoice.withholding_tax_amount` for supplier WHT
- `gl.posted_ledger_line` on:
  - `1440 Input VAT`
  - `2110 WHT`

What is weak:

- `ap.supplier_payment.withholding_tax_amount` is unused in 2025

So the purchase-side withholding is captured on invoices and GL, but not cleanly on payment rows.

## Annual totals

### AP invoices

- AP invoices: `1,161`
- invoices with non-zero WHT: `208`
- purchase subtotal: `757,096,841.31`
- input VAT from AP invoices: `31,722,874.32`
- WHT from AP invoices: `2,130,934.94`

### AP payments

- supplier payments: `1,316`
- payments with non-zero `withholding_tax_amount`: `0`

### GL comparison

- `1440 Input VAT` 2025 movement: `31,749,478.98`
- `2110 WHT` 2025 movement: `2,373,736.02`

Comparison:

- AP invoice input VAT vs GL `1440`: difference `26,604.66`
- AP invoice WHT vs GL `2110`: difference `242,801.08`

The VAT difference is small.  
The WHT difference is concentrated in early-year cleanup / opening-style activity.

## Monthly purchase-side totals

`period | invoice input VAT | GL input VAT | difference`

- `2025-01 | 1,302,923.77 | 1,616,567.71 | (313,643.94)`
- `2025-02 | 818,278.89 | 943,411.97 | (125,133.08)`
- `2025-03 | 775,616.49 | 896,004.52 | (120,388.03)`
- `2025-04 | 1,666,221.57 | 1,801,814.06 | (135,592.49)`
- `2025-05 | 1,571,172.43 | 1,534,984.71 | 36,187.72`
- `2025-06 | 8,930,607.44 | 9,005,427.91 | (74,820.47)`
- `2025-07 | 1,638,065.47 | 1,546,257.28 | 91,808.19`
- `2025-08 | 1,556,021.73 | 1,312,468.15 | 243,553.58`
- `2025-09 | 2,433,331.51 | 2,412,016.38 | 21,315.13`
- `2025-10 | 4,703,245.98 | 4,828,532.25 | (125,286.27)`
- `2025-11 | 2,523,610.06 | 2,661,100.06 | (137,490.00)`
- `2025-12 | 3,803,778.98 | 3,190,893.98 | 612,885.00`

`period | invoice WHT | GL WHT payable | difference`

- `2025-01 | 301,301.44 | 446,855.90 | (145,554.46)`
- `2025-02 | 125,133.08 | 142,727.09 | (17,594.01)`
- `2025-03 | 120,388.03 | 204,059.24 | (83,671.21)`
- `2025-04 | 160,639.00 | 160,639.00 | 0.00`
- `2025-05 | 174,858.79 | 174,858.79 | 0.00`
- `2025-06 | 133,460.00 | 133,460.00 | 0.00`
- `2025-07 | 121,736.00 | 121,736.00 | 0.00`
- `2025-08 | 129,432.00 | 129,432.00 | 0.00`
- `2025-09 | 126,543.00 | 126,543.00 | 0.00`
- `2025-10 | 160,588.60 | 156,570.00 | 4,018.60`
- `2025-11 | 137,490.00 | 137,490.00 | 0.00`
- `2025-12 | 439,365.00 | 439,365.00 | 0.00`

## Why January-March WHT does not tie

The main January distortion is not ordinary AP invoice activity. It includes:

- opening balance `OB-000001` on `2110 WHT` `3,136,499.51`
- reversal / catch-up style journal:
  - `JE-2025-01833`
  - description: `Bill 6921 WIOCC WHT (July 2023- Dec 2024)`
  - amount: `(3,190,722.32)` on `2110`

There are also early-year supplier-payment deductions and opening-linked settlements such as:

- `Wiocc Nigeria Limited`
- `Coloplus Worldwide Services Limited`
- `Tremfolink`
- `Linkztix Limited`

So January-March should be treated as:

- mixed current-year AP WHT
- plus opening / catch-up / migration-linked WHT activity

From April onward, the purchase-side WHT ties cleanly to AP invoices.

## Largest suppliers by invoice WHT

- `Coloplus Worldwide Services Limited` `648,000.00`
- `AIRTEL BUSINESS NIGERIA` `280,600.00`
- `Swift Talk Limited` `256,485.81`
- `Tremfolink` `245,575.00`
- `Internet Exchange Point of Nigeria` `157,767.44`
- `Telecables Nigeria Ltd` `108,000.00`
- `DIGITAL REALITY (Medallion)` `99,368.59`
- `Ipnx Nigeria Limited` `93,285.71`
- `TeleAfrica Communications` `91,800.00`
- `E-lap Multi Ventures Ltd` `90,727.00`

## Practical audit position

For purchases:

- input VAT is mostly reconstructible from AP invoices
- WHT is mostly reconstructible from AP invoices plus GL
- payment-level withholding support is weaker because AP payment fields are blank
- January-March needs a separate opening / catch-up bridge

## Next step

To finish the purchase-side pack:

1. build a supplier certificate/remittance tracker for the high-WHT suppliers
2. isolate January-March as a separate bridge memo
3. reconcile the remaining WHT payable balance in `2110`
4. assemble remittance evidence to FIRS for withheld supplier tax
