# Deferred VAT Release Note

## What is shipping

This rollout completes the deferred VAT design for cash-basis VAT recognition:

- invoice-time VAT posts to deferred VAT accounts
- payment-time VAT reclass posts from deferred VAT to live VAT payable/input VAT
- `tax.tax_transaction` supports `recognition_basis = accrual | cash`
- VAT reports can be driven from posting truth instead of report-time prorate logic

## Included fixes

### Deferred VAT account repair

The live COA already used `1450` for `Inter-Branch Account`.

This rollout uses:

- `1440` = `Input VAT`
- `1450` = `Inter-Branch Account`
- `1455` = `Deferred Input VAT`
- `2120` = `VAT Payables`
- `2125` = `Deferred Output VAT`

### Inclusive VAT tax-code repair

`VAT-7.5 (inclusive)` was live with:

- `tax_paid_account_id = null`
- `tax_collected_account_id = null`

This affected:

- `147` AP invoices
- `123` AR invoices

The repair aligns it with `VAT-7.5`:

- `tax_paid_account_id -> 1440`
- `tax_collected_account_id -> 2120`

Validated impact:

- January 2026 AP deferred-VAT dry-run moved from `35 candidates / 14 skipped`
  to `35 candidates / 0 skipped`

## Deployment prerequisites

- Deploy the new application image with the updated Python services and Alembic files.
- Do not rely on the direct SQL repair alone for long-term correctness.

## Required migrations

Run:

```bash
poetry run alembic upgrade head
```

Expected head:

```text
20260429_fix_vat_75_inclusive_accounts
```

## Post-deploy checks

### Schema and master-data checks

```sql
select version_num from alembic_version;

select account_code, account_name, is_deferral,
       deferral_pair_account_id is not null as has_pair
from gl.account
where account_code in ('1440','1450','1455','2120','2125')
order by account_code;

select tax_code,
       tax_paid_account_id is not null as has_paid,
       tax_collected_account_id is not null as has_collected
from tax.tax_code
where tax_code in ('VAT-7.5','VAT-7.5 (inclusive)')
order by tax_code;
```

Expected:

- Alembic head is correct
- `1455 Deferred Input VAT` exists and is paired
- `1450 Inter-Branch Account` remains untouched
- `2125 Deferred Output VAT` is paired to `2120`
- `VAT-7.5 (inclusive)` has both tax account mappings

### Backfill smoke checks

```bash
python /app/scripts/2026-04-30_backfill_deferred_vat.py \
  --dry-run --phase ap-invoices \
  --from-date 2026-01-01 --to-date 2026-01-31 \
  --report-ap-invoice-skips

python /app/scripts/2026-04-30_backfill_deferred_vat.py \
  --dry-run --phase ar-invoices \
  --limit 25 \
  --from-date 2026-01-01 --to-date 2026-01-31

python /app/scripts/2026-04-30_backfill_deferred_vat.py \
  --dry-run --phase ar-payments \
  --limit 25 \
  --from-date 2026-01-01 --to-date 2026-01-31
```

Expected:

- AP January skip count stays at `0`
- all smoke runs complete with `Failures: 0`

## Operational note

The backfill runner is correct on live slices, but AR month-scale dry-runs are still throughput-bound.

Recommended review batch sizes:

- AR invoices: `--batch-size 100`
- AR payments: start at `--batch-size 250`
- AP invoices: monthly single pass is acceptable
- AP payments: monthly single pass is acceptable

## Local verification completed

- `poetry run pytest tests/ifrs/tax/test_tax_master_service.py -q`
- `poetry run pytest tests/ifrs/tax/test_tax_web_service.py -q`
- `poetry run pytest tests/ifrs/tax/test_tax_transaction_service.py -q`
- `poetry run pytest tests/ifrs/ar/test_customer_payment_service.py -q`
- `poetry run pytest tests/ifrs/ap/test_supplier_payment_service.py -q`
- `poetry run pytest tests/ifrs/ar/test_ar_posting_adapter.py -q`
- `poetry run pytest tests/ifrs/ap/test_ap_posting_adapter.py -q`
- `poetry run ruff check ...` on all touched tax/AR/AP files

## Immediate next action after deploy

Run the January AP invoice dry-run first. If that remains at `skipped=0`, proceed to batched AR validation and then finance review of the backfill totals.
