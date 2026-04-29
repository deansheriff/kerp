-- Dry-run report for wave 2 cleanup of unsupported tax opening journals.
-- This script does not modify data.

\echo 'Wave 2 tax-opening cleanup dry run'

with target_journals(journal_entry_id) as (
    values
        ('2a5a6247-2133-4760-9dc7-3f6672ee9417'::uuid),
        ('90fe5e17-d52e-4de4-8c00-9c70622fd23f'::uuid)
)
select 'gl_journal_entry' as object_type, count(*)::text as row_count
from gl.journal_entry
where journal_entry_id in (select journal_entry_id from target_journals)
union all
select 'gl_journal_entry_line', count(*)::text
from gl.journal_entry_line
where journal_entry_id in (select journal_entry_id from target_journals)
union all
select 'gl_posted_ledger_line', count(*)::text
from gl.posted_ledger_line
where journal_entry_id in (select journal_entry_id from target_journals)
order by 1;

\echo ''
\echo 'Target journal details'
select je.journal_number, je.entry_date, je.reference, je.total_debit, je.total_credit, je.created_at::date as created_date
from gl.journal_entry je
where je.journal_entry_id in (
    '2a5a6247-2133-4760-9dc7-3f6672ee9417'::uuid,
    '90fe5e17-d52e-4de4-8c00-9c70622fd23f'::uuid
)
order by je.journal_number;

\echo ''
\echo 'Target journal lines'
select je.journal_number, a.account_code, a.account_name, jel.debit_amount, jel.credit_amount, jel.line_id
from gl.journal_entry je
join gl.journal_entry_line jel on jel.journal_entry_id = je.journal_entry_id
join gl.account a on a.account_id = jel.account_id
where je.journal_entry_id in (
    '2a5a6247-2133-4760-9dc7-3f6672ee9417'::uuid,
    '90fe5e17-d52e-4de4-8c00-9c70622fd23f'::uuid
)
order by je.journal_number, a.account_code;

\echo ''
\echo 'Affected account balances before cleanup'
with accts as (
    select account_id, account_code, account_name
    from gl.account
    where account_code in ('2100','2110','3100')
)
select a.account_code, a.account_name,
       round(sum(case when pll.entry_date <= date '2025-12-31' then pll.debit_amount - pll.credit_amount else 0 end)::numeric,2) as balance_2025_12_31
from accts a
left join gl.posted_ledger_line pll on pll.account_id = a.account_id
group by a.account_code, a.account_name
order by a.account_code;
