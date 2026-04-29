# 2025 VAT Credit Trace

This workpaper assesses the `Paid from VAT Credit` column in:

- `/root/VAT SUmmary on Tax Pro 2025 (3) (2) (1).xlsx`

and traces it to:

- FIRS supplier payments
- payment journals
- bank statement narrations

## Conclusion

The `VAT credit` side is only **partially traceable** from the ERP and bank data.

What is proven:

- a real FIRS wallet-credit payment batch occurred on `2025-05-02`
- it was paid through `1205 Zenith 461 Bank`
- the Zenith statement explicitly labels items as `VATWallet Credit`, `WHTWallet Credit`, and `SDWallet Credit`

What is not proven:

- that the TaxPro monthly `Paid from VAT Credit` amounts for `Jul-Dec 2025` tie one-to-one to ERP payment records
- that the wallet-credit amounts in books are complete for the full `14,764,928.00` shown in TaxPro

## TaxPro VAT-credit schedule

TaxPro shows:

- `Jul` `2,736,625.00`
- `Aug` `2,603,296.00`
- `Sep` `1,875,361.00`
- `Oct` `3,054,572.00`
- `Nov` `1,443,957.00`
- `Dec` `3,051,117.00`

Total:

- `14,764,928.00`

## Confirmed wallet-credit batch in bank statement

From `/root/zenith-statements/BOP_CBA_003_Report (2).xlsx` on `2025-05-02`:

### VAT wallet credit

- `398,448.00`
- `499,333.00`
- `1,076,783.00`

VAT wallet credit total:

- `1,974,564.00`

### WHT wallet credit

- `421,302.00`
- `1,303,754.00`
- `18,277.00`

WHT wallet credit total:

- `1,743,333.00`

### Stamp duty wallet credit

- `13,670.00`
- `50,884.00`
- `59,395.00`

Stamp duty wallet credit total:

- `123,949.00`

Grand total wallet-credit batch:

- `3,841,846.00`

## Matching ERP payments

These `2025-05-02` FIRS payments exist in `ap.supplier_payment` and GL:

- `ACC-PAY-2025-19819` `398,448.00` `Value Added Tax LOI 31/12/2020`
- `ACC-PAY-2025-19820` `499,333.00` `Value Added Tax LOI 31/12/2021`
- `ACC-PAY-2025-19821` `1,076,783.00` `Value Added Tax LOI 31/12/2022`

All three credit:

- `1205 Zenith 461 Bank`

and debit:

- `2100 Income Tax`

They exactly match the statement lines labeled `VATWallet Credit`.

## Key mismatch

The proven VAT wallet-credit total in ERP and statement evidence is:

- `1,974,564.00`

The TaxPro `Paid from VAT Credit` total is:

- `14,764,928.00`

Unexplained difference:

- `12,790,364.00`

## Interpretation

The books prove at least one real VAT wallet-credit batch, but they do not prove the full TaxPro VAT-credit schedule.

Possible reasons:

- TaxPro reflects FIRS wallet/credit utilization not fully imported into ERP
- later months were settled outside the current AP/payment structure
- ERP only captured part of the wallet-credit history
- some amounts classified in TaxPro as VAT credit may sit under mixed tax settlements in ERP

## What is needed next

To fully close VAT credit, we need external evidence:

1. TaxPro/FIRS wallet-credit ledger or screenshots
2. Remita/FIRS receipts supporting VAT credit utilization by month
3. Any finance reconciliation showing how `Jul-Dec` credits were applied
4. Confirmation whether the `2025-05-02` batch was a historic catch-up rather than same-month settlement

## Practical position

For audit purposes:

- `bank-paid VAT` is largely traceable
- `VAT-credit-paid` is only partially traceable from ERP + statements
- the remaining support must come from `TaxPro/FIRS` evidence, not the ERP alone
