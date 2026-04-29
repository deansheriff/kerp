# Deferred VAT Rollout Runbook

## Scope

This runbook covers deployment and validation of the deferred VAT redesign:

- deferred VAT GL account pairing
- cash/accrual tax subledger basis tracking
- AR/AP posting changes
- historical backfill runner
- VAT inclusive tax-code repair guardrail

## Code Artifacts

Apply and deploy these local changes together:

- `alembic/versions/20260429_add_deferred_vat_basis_tracking.py`
- `alembic/versions/20260429_fix_deferred_input_vat_account_code.py`
- `alembic/versions/20260429_fix_vat_75_inclusive_accounts.py`
- `app/models/finance/gl/account.py`
- `app/models/finance/tax/tax_transaction.py`
- `app/services/finance/ar/posting/invoice.py`
- `app/services/finance/ar/posting/payment.py`
- `app/services/finance/ar/posting/helpers.py`
- `app/services/finance/ar/customer_payment.py`
- `app/services/finance/ap/posting/invoice.py`
- `app/services/finance/ap/posting/payment.py`
- `app/services/finance/ap/posting/helpers.py`
- `app/services/finance/ap/supplier_payment.py`
- `app/services/finance/tax/tax_master.py`
- `app/services/finance/tax/tax_transaction.py`
- `app/services/finance/tax/tax_reports.py`
- `app/services/finance/tax/web.py`
- `scripts/migration/2026-04-30_backfill_deferred_vat.py`

## Critical Data Fixes Included

### 1. Deferred input VAT account code

`1450` is already used by `Inter-Branch Account` in the live COA.

Do not use `1450` for deferred input VAT.

The corrected design is:

- `1440` = `Input VAT`
- `1450` = `Inter-Branch Account`
- `1455` = `Deferred Input VAT`

### 2. VAT inclusive tax code repair

The live tax code `VAT-7.5 (inclusive)` was found with:

- `tax_paid_account_id = null`
- `tax_collected_account_id = null`

The repair migration copies both mappings from `VAT-7.5`, which resolves:

- January 2026 AP skipped invoices: `14 -> 0`

## Deployment Order

### 1. Build and deploy application image

The runtime must include the updated Python service files and the new Alembic revisions.

Do not rely on manual SQL alone for the permanent fix.

### 2. Run migrations

Run:

```bash
poetry run alembic upgrade head
```

Expected head after this rollout:

```text
20260429_fix_vat_75_inclusive_accounts
```

### 3. Verify COA and tax-code state

Run:

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

- Alembic head is `20260429_fix_vat_75_inclusive_accounts`
- `1455 Deferred Input VAT` exists and is paired
- `1450 Inter-Branch Account` remains unpaired
- `2125 Deferred Output VAT` is paired to `2120`
- `VAT-7.5 (inclusive)` has both tax accounts populated

## Post-Deploy Validation

### AP skip regression check

Run:

```bash
python /app/scripts/2026-04-30_backfill_deferred_vat.py \
  --dry-run \
  --phase ap-invoices \
  --from-date 2026-01-01 \
  --to-date 2026-01-31 \
  --report-ap-invoice-skips
```

Expected:

- `AP invoices: candidates=35 posted=0 skipped=0`
- `Failures: 0`

### Narrow live smoke tests

Run:

```bash
python /app/scripts/2026-04-30_backfill_deferred_vat.py \
  --dry-run --phase ar-invoices \
  --limit 25 \
  --from-date 2026-01-01 \
  --to-date 2026-01-31

python /app/scripts/2026-04-30_backfill_deferred_vat.py \
  --dry-run --phase ar-payments \
  --limit 25 \
  --from-date 2026-01-01 \
  --to-date 2026-01-31

python /app/scripts/2026-04-30_backfill_deferred_vat.py \
  --dry-run --phase ap-payments \
  --limit 25 \
  --from-date 2026-01-01 \
  --to-date 2026-01-31
```

Expected:

- no failures
- deterministic summary output

### Batch-mode validation

Recommended review sizes from live testing:

- AR invoices: `--batch-size 100`
- AR payments: start at `--batch-size 250`
- AP invoices: monthly single pass is acceptable
- AP payments: monthly single pass is acceptable

Examples:

```bash
python /app/scripts/2026-04-30_backfill_deferred_vat.py \
  --dry-run --phase ar-invoices \
  --from-date 2026-01-01 \
  --to-date 2026-01-31 \
  --batch-size 100

python /app/scripts/2026-04-30_backfill_deferred_vat.py \
  --dry-run --phase ar-payments \
  --from-date 2026-01-01 \
  --to-date 2026-01-31 \
  --batch-size 250
```

## Known Operational Limits

- The current backfill runner is functionally correct on scoped live slices.
- Month-scale AR dry-runs are still throughput-bound.
- Larger batch sizes, especially AR invoice `250`, were too slow for comfortable live review.

This is an execution/batching issue, not a correctness issue.

## Local Verification Already Completed

### Tests

```bash
poetry run pytest tests/ifrs/tax/test_tax_master_service.py -q
poetry run pytest tests/ifrs/tax/test_tax_web_service.py -q
poetry run pytest tests/ifrs/tax/test_tax_transaction_service.py -q
poetry run pytest tests/ifrs/ar/test_customer_payment_service.py -q
poetry run pytest tests/ifrs/ap/test_supplier_payment_service.py -q
poetry run pytest tests/ifrs/ar/test_ar_posting_adapter.py -q
poetry run pytest tests/ifrs/ap/test_ap_posting_adapter.py -q
```

### Lint

```bash
poetry run ruff check app/services/finance/tax/tax_master.py \
  app/services/finance/tax/web.py \
  app/services/finance/tax/tax_transaction.py \
  app/services/finance/tax/tax_reports.py \
  app/services/finance/ar/customer_payment.py \
  app/services/finance/ap/supplier_payment.py \
  app/services/finance/ar/posting/payment.py \
  app/services/finance/ap/posting/payment.py \
  tests/ifrs/tax/test_tax_master_service.py \
  tests/ifrs/tax/test_tax_web_service.py
```

## Rollback Notes

If deployment must be rolled back:

- do not revert live data with ad hoc SQL unless finance signs off
- use Alembic downgrade only if no backfill apply has been run
- if the inclusive VAT code repair was already applied in production data, reversing it would reintroduce known AP/AR tax-code defects

For that reason, treat the `VAT-7.5 (inclusive)` account repair as a forward-only data correction.
