# Deferred VAT Reconciliation

## Scope

This note captures the completed deferred VAT backfill rollout state for:

- January 2026
- February 2026
- March 2026
- April 2026

May 2026 currently has no source transactions to backfill.

## Month-by-Month GL State

| Month | AR Invoice Deferrals | AP Invoice Deferrals | AR Payment Reclasses | AP Payment Reclasses |
| --- | ---: | ---: | ---: | ---: |
| 2026-01 | 1408 | 35 | 0 | 1 |
| 2026-02 | 1297 | 30 | 0 | 0 |
| 2026-03 | 1312 | 46 | 0 | 0 |
| 2026-04 | 752 | 4 | 0 | 0 |

These figures come from live `gl.journal_entry` counts where:

- `source_document_type = 'AR_INVOICE_VAT_DEFERRAL'`
- `source_document_type = 'SUPPLIER_INVOICE_VAT_DEFERRAL'`
- `source_document_type = 'CUSTOMER_PAYMENT_VAT_RECLASS'`
- `source_document_type = 'SUPPLIER_PAYMENT_VAT_RECLASS'`
- `status = 'POSTED'`

## Month-by-Month Cash-Basis Tax Rows

| Month | AR Cash Tax Rows | AP Cash Tax Rows |
| --- | ---: | ---: |
| 2026-01 | 0 | 2 |
| 2026-02 | 0 | 0 |
| 2026-03 | 0 | 0 |
| 2026-04 | 0 | 0 |

These figures come from live `tax.tax_transaction` counts where:

- `source_document_type = 'CUSTOMER_PAYMENT'` or `source_document_type = 'SUPPLIER_PAYMENT'`
- `recognition_basis = 'cash'`

## Interpretation

- Invoice-side deferred VAT is populated for January through April 2026.
- Payment-side cash VAT recognition is minimal in the current dataset.
- The only month with actual AP payment VAT recognition was January 2026:
  - `1` posted AP VAT reclass journal
  - `2` AP cash-basis tax rows
- AR payment backfill sweeps for January through April completed cleanly but did not produce any cash VAT reclass journals.

## Operational Notes

- The recurring operational issue during invoice apply rollout was intermittent `gl.account_balance` deadlocks.
- Those deadlocks did not indicate logic defects in the deferred VAT design.
- Idempotent retries on the affected windows cleared the remaining invoice backlog in each month.
- April 2026 completed without any invoice deadlock retry cleanup.

## Completion Status

Completed rollout months:

- January 2026
- February 2026
- March 2026
- April 2026

No further live backfill work is pending for May 2026 at this time.
