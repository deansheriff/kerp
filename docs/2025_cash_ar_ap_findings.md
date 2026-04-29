# 2025 Cash, AR, and AP Audit Findings

Date: 2026-04-28

Scope:
- Bank and cash support as of 2025-12-31
- AR control account support as of 2025-12-31
- AP control account support as of 2025-12-31

Organization:
- `00000000-0000-0000-0000-000000000001`

## Executive Summary

1. Bank reconciliation support is not audit-ready.
2. AR and AP controls appear to include both the main opening journal and separate subledger opening journals dated 2025-01-01.
3. AP control movement is largely explainable from posted supplier invoices, supplier payments, opening balance, and direct opening-style journals.
4. AR control movement is directionally explainable but still needs a customer-level reconciliation workpaper.

## 1. Bank / Cash Findings

### GL balances at 2025-12-31

| GL Code | Account | Balance |
|---|---|---:|
| 1200 | Zenith Bank | 21,442,780.30 |
| 1202 | UBA | 11,074,640.56 |
| 1203 | First Bank | 39,800.00 |
| 1211 | Paystack OPEX Account | 3,488,079.80 |
| 1220 | Cash at Hand | 1,009,990.88 |

Additional live bank GL accounts also exist outside the original opening-balance set:

| GL Code | Account | Balance |
|---|---|---:|
| 1204 | Zenith 523 Bank | 2,562,798.73 |
| 1205 | Zenith 461 Bank | 118,054.84 |
| 1206 | Zenith 454 Bank | 77,738.18 |
| 1207 | Zenith USD Bank | 12,318,165.17 |
| 1208 | TAJ Bank | 450,000.00 |
| 1212 | Flutterwave | 946,141.30 |

### Reconciliation status

- No bank account has `last_reconciled_date` populated.
- No bank account has `last_reconciled_balance` populated.
- Only one reconciliation record exists, and it is a `draft` for 2026-03-31.

### Statement evidence

- Statement rows exist for several bank accounts at `2025-12-31`, but the `closing_balance` field is blank in the latest 2025 statement records sampled.
- Current `last_statement_balance` values are populated from 2026 sync activity, not from locked 2025 reconciliations.

### Conclusion

The cash and bank area is not audit-ready. The system currently has:
- ledger balances
- imported statement rows

But it does not yet have:
- approved 2025 bank reconciliations
- populated year-end closing balances in reconciliation records
- stable tie-out from statement ending balances to GL balances

## 2. AR Findings

### AR control account at 2025-12-31

| Source | Balance |
|---|---:|
| AR GL control `1400` | 747,730,962.08 |

### GL composition of account `1400`

| Source Module | Source Document Type | Balance |
|---|---|---:|
| `ar` | `INVOICE` | 1,668,040,293.44 |
| `ar` | `CUSTOMER_PAYMENT` | (962,855,138.06) |
| `gl` | `JOURNAL` | 21,954,753.35 |
| `IMPORT` | `OPENING_BALANCE` | 20,591,053.35 |

### Subledger support

Using invoice allocations:
- AR invoice residual at 2025-12-31: `758,142,932.80`

Using payment allocations:
- total posted customer receipts: `925,752,399.80`
- allocated to invoices: `899,676,252.65`
- unapplied receipts: `26,076,147.15`

### Opening-style journals in AR control

The GL journal component is not ordinary current-period adjusting activity only.

For account `1400`:
- `2025-01-01` direct journal impact: `20,917,253.35`
- these journals are described as `Customer Outstanding Balance` / `CUS OP BAL`

This sits alongside:
- `OB-000001` opening balance impact on `1400`: `20,591,053.35`

### Conclusion

AR is not yet audit-ready because the control account contains:
- invoice and payment postings
- the main opening balance journal
- a second set of opening-style customer journals on 2025-01-01

This does not automatically mean the balance is wrong, but it does mean a customer-level bridge is required to show whether the opening receivables were double-loaded or intentionally split between summary and customer-detail journals.

## 3. AP Findings

### AP control account at 2025-12-31

| Source | Balance |
|---|---:|
| AP GL control `2000` | (128,093,885.95) |

### GL composition of account `2000`

| Source Module | Source Document Type | Balance |
|---|---|---:|
| `ap` | `SUPPLIER_INVOICE` | (774,322,040.24) |
| `ap` | `SUPPLIER_PAYMENT` | 726,725,618.83 |
| `IMPORT` | `OPENING_BALANCE` | (40,310,713.50) |
| `gl` | `JOURNAL` | (40,186,751.04) |

### Subledger support

Invoice-based open AP using invoice payment fields:
- `48,696,956.70`

Important note:
- AP payment allocation records exist but are sparse relative to payment volume.
- `ap.payment_allocation` is not reliable enough yet as the primary AP close evidence.

### Opening-style journals in AP control

For account `2000`:
- `2025-01-01` direct journal impact: `(40,186,751.04)`
- the journals are clearly labelled `PUR OP BAL ...`

This sits alongside:
- `OB-000001` opening balance impact on `2000`: `(40,310,713.50)`

### Conclusion

AP is not yet audit-ready because the control account contains:
- supplier invoice postings
- supplier payment postings
- the main opening balance journal
- a second set of vendor opening-style journals on 2025-01-01

The closeness of:
- `OB-000001` AP opening `(40,310,713.50)`
- `PUR OP BAL` AP journals `(40,186,751.04)`

strongly suggests that part of the 2024 payable opening may have been loaded twice: once as a summary opening balance and again as supplier-detail opening journals.

## Immediate Remediation Required

### Banks

- Build one reconciliation pack per bank/wallet account as of 2025-12-31.
- Populate statement closing balances and reconciliation closing balances formally.
- Approve reconciliations and tie each one to the linked GL account.

### AR

- Produce a customer opening-balance bridge:
  - 2024 closing receivables schedule
  - `OB-000001` control balance
  - `CUS OP BAL` detail journals
  - proof that summary and detail are not double-counted
- Produce a customer aging as of 2025-12-31 from live data and freeze it as audit evidence.
- Reconcile unapplied receipts separately.

### AP

- Produce a supplier opening-balance bridge:
  - 2024 closing payables schedule
  - `OB-000001` control balance
  - `PUR OP BAL` detail journals
  - proof that summary and detail are not double-counted
- Produce a supplier aging as of 2025-12-31 from live data and freeze it as audit evidence.
- Clean up AP payment allocation support or document why invoice `amount_paid` is the system of record.
