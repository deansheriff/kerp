-- Dry-run report for 2025 opening-balance migration remediation.
-- This script does not modify data.

\echo 'Opening-balance cleanup dry run'

with
ar_allocs(allocation_id) as (
    values
        ('3f2e026d-d902-4a61-a2fe-2b591f9cbce1'::uuid),
        ('49231ce0-c1a4-43dd-81fd-f82f873ada64'::uuid),
        ('92e3a785-8c4a-430d-8b2d-f5f7924e5cf2'::uuid),
        ('a2c0b57e-8e04-4893-bb50-12437d75b050'::uuid),
        ('bd628556-6894-4332-af5e-07eda4d3eb23'::uuid),
        ('c7becc65-895b-474c-a3f7-63a3328b2cb0'::uuid),
        ('c8872ed9-89a2-41c7-a759-9a4d3e893f59'::uuid),
        ('f2c43247-a88a-490a-9f24-622194ff2b8a'::uuid),
        ('f7860e33-24d8-48c2-9388-78ff327fabda'::uuid)
),
ap_allocs(allocation_id) as (
    values
        ('88e31778-ceaa-4817-8467-4e328ae53ab0'::uuid),
        ('b5e0feb3-79a2-4449-9bfd-e9c8d9675cfd'::uuid),
        ('e4d1e2de-ad9c-4630-b58d-67701756e7e9'::uuid)
),
ar_invoices(invoice_id) as (
    values
        ('3251730b-177e-487a-b3e7-0012088dc261'::uuid),
        ('14c6b81c-1226-4226-9697-8e3110a917f0'::uuid),
        ('4006a0dd-ead9-41b4-b027-cef2cea76a0f'::uuid),
        ('0cb5c2b9-651e-46b9-828a-47dc55cbecdc'::uuid),
        ('54410efa-1b88-47ff-8b64-2e091323dd71'::uuid),
        ('bd2f41ce-09f3-4748-b8ab-717d27582cbc'::uuid),
        ('567e92da-99df-4c06-858b-3a73dab0cf41'::uuid)
),
ap_invoices(invoice_id) as (
    values
        ('11efb18d-0fab-4946-8b2e-977ba7d47894'::uuid),
        ('e8cdffca-a3ea-4971-a2e7-a5b2705437cd'::uuid),
        ('14da5709-5e83-4046-a9b3-96ad49b2245b'::uuid)
),
ap_payments(payment_id) as (
    values
        ('3d3c4c7a-28d8-41a8-8618-4b49630d4517'::uuid),
        ('3a61d8f0-7264-425d-956d-58c7bdc81a26'::uuid),
        ('06503125-a411-490f-8a78-ecd171b0b82b'::uuid)
),
je_delete(journal_entry_id) as (
    values
        ('249bcc89-9529-42fe-af86-ee389103296c'::uuid),
        ('ec44873b-591a-431f-9f8a-28894c364d7a'::uuid),
        ('5dcc935f-090a-43af-bf03-146bfd323a87'::uuid),
        ('e2597e57-3e1a-49cc-b98a-1eb492cc0c12'::uuid),
        ('17efa38a-b9e3-47fc-be24-4273297e3e4b'::uuid),
        ('f37bf164-94c7-49ee-8600-c988c5d5e804'::uuid),
        ('4cbba8c0-53d8-4f20-867e-f47021e283a4'::uuid),
        ('42deb460-348a-470f-bf58-aeb5a7f0e623'::uuid),
        ('5f5050b4-f223-4f47-b03d-1c3d85bb9c5f'::uuid),
        ('a17b0155-b90c-4366-8113-680182f7099a'::uuid),
        ('8fc381e3-046f-4915-8204-1fb85f9b61e2'::uuid),
        ('32bdd22f-c9cd-4729-9559-3fb78c617878'::uuid),
        ('bc4f9734-c445-4fdd-a80a-ae3645436e4d'::uuid),
        ('dcf77a40-9820-445c-bef8-b7d0a82ea886'::uuid),
        ('a5154968-5ecd-4ddc-a7b8-c41f7df39875'::uuid)
),
ob_line_delete(line_id) as (
    values
        ('4ec4bcf2-b016-4ec8-948a-489858b4a026'::uuid),
        ('9a296e07-39ac-49ac-89f0-c21273bfc4fb'::uuid),
        ('739d4ced-814f-4ce6-9b56-38692b2f5c7d'::uuid)
)
select 'ar_payment_allocation' as object_type, count(*)::text as row_count
from ar.payment_allocation
where allocation_id in (select allocation_id from ar_allocs)
union all
select 'ap_payment_allocation', count(*)::text
from ap.payment_allocation
where allocation_id in (select allocation_id from ap_allocs)
union all
select 'ar_invoice', count(*)::text
from ar.invoice
where invoice_id in (select invoice_id from ar_invoices)
union all
select 'ar_invoice_line', count(*)::text
from ar.invoice_line
where invoice_id in (select invoice_id from ar_invoices)
union all
select 'ap_supplier_invoice', count(*)::text
from ap.supplier_invoice
where invoice_id in (select invoice_id from ap_invoices)
union all
select 'ap_supplier_invoice_line', count(*)::text
from ap.supplier_invoice_line
where invoice_id in (select invoice_id from ap_invoices)
union all
select 'ap_supplier_payment', count(*)::text
from ap.supplier_payment
where payment_id in (select payment_id from ap_payments)
union all
select 'gl_journal_entry', count(*)::text
from gl.journal_entry
where journal_entry_id in (select journal_entry_id from je_delete)
union all
select 'gl_posting_batch_for_deleted_journal', count(*)::text
from gl.posting_batch
where journal_entry_id in (select journal_entry_id from je_delete)
union all
select 'gl_journal_entry_line_for_deleted_journal', count(*)::text
from gl.journal_entry_line
where journal_entry_id in (select journal_entry_id from je_delete)
union all
select 'gl_posted_ledger_line_for_deleted_journal', count(*)::text
from gl.posted_ledger_line
where journal_entry_id in (select journal_entry_id from je_delete)
union all
select 'ob_lines_to_delete', count(*)::text
from gl.journal_entry_line
where line_id in (select line_id from ob_line_delete)
union all
select 'ob_posted_lines_to_delete', count(*)::text
from gl.posted_ledger_line
where journal_line_id in (select line_id from ob_line_delete)
order by 1;

\echo ''
\echo 'OB-000001 lines selected for surgical deletion'
select a.account_code, a.account_name, jel.line_id, jel.debit_amount, jel.credit_amount, jel.description
from gl.journal_entry_line jel
join gl.account a on a.account_id = jel.account_id
where jel.line_id in (
    '4ec4bcf2-b016-4ec8-948a-489858b4a026'::uuid,
    '9a296e07-39ac-49ac-89f0-c21273bfc4fb'::uuid,
    '739d4ced-814f-4ce6-9b56-38692b2f5c7d'::uuid
)
order by a.account_code;

\echo ''
\echo 'Retained earnings line to adjust inside OB-000001'
select a.account_code, a.account_name, jel.line_id, jel.debit_amount, jel.credit_amount,
       5011140.74::numeric(18,2) as credit_after_cleanup
from gl.journal_entry_line jel
join gl.account a on a.account_id = jel.account_id
where jel.line_id = '459290a2-7f34-461b-a3b9-11378eaf2ae8'::uuid;

\echo ''
\echo 'Expected OB-000001 totals after cleanup'
select
    '367295598.50'::numeric(18,2) as old_total,
    '42033833.65'::numeric(18,2) as reduction,
    '325261764.85'::numeric(18,2) as new_total;

\echo ''
\echo 'Investigate-only journals not included in apply script'
select journal_number, journal_entry_id, description
from gl.journal_entry
where journal_entry_id in (
    '2a5a6247-2133-4760-9dc7-3f6672ee9417'::uuid,
    '90fe5e17-d52e-4de4-8c00-9c70622fd23f'::uuid
)
order by journal_number;
