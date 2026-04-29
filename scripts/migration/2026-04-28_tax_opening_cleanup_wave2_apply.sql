-- Wave 2 cleanup of unsupported tax opening journals.
-- Removes JE-2025-00076 and JE-2025-00079 only.

begin;

do $$
declare
    expected_count int;
begin
    select count(*) into expected_count
    from gl.journal_entry
    where journal_entry_id in (
        '2a5a6247-2133-4760-9dc7-3f6672ee9417'::uuid,
        '90fe5e17-d52e-4de4-8c00-9c70622fd23f'::uuid
    );
    if expected_count <> 2 then
        raise exception 'Expected 2 target journals, found %', expected_count;
    end if;

    select count(*) into expected_count
    from gl.journal_entry_line
    where journal_entry_id in (
        '2a5a6247-2133-4760-9dc7-3f6672ee9417'::uuid,
        '90fe5e17-d52e-4de4-8c00-9c70622fd23f'::uuid
    );
    if expected_count <> 4 then
        raise exception 'Expected 4 target journal lines, found %', expected_count;
    end if;

    select count(*) into expected_count
    from gl.posted_ledger_line
    where journal_entry_id in (
        '2a5a6247-2133-4760-9dc7-3f6672ee9417'::uuid,
        '90fe5e17-d52e-4de4-8c00-9c70622fd23f'::uuid
    );
    if expected_count <> 4 then
        raise exception 'Expected 4 posted ledger lines, found %', expected_count;
    end if;
end $$;

delete from gl.posted_ledger_line
where journal_entry_id in (
    '2a5a6247-2133-4760-9dc7-3f6672ee9417'::uuid,
    '90fe5e17-d52e-4de4-8c00-9c70622fd23f'::uuid
);

delete from gl.journal_entry_line
where journal_entry_id in (
    '2a5a6247-2133-4760-9dc7-3f6672ee9417'::uuid,
    '90fe5e17-d52e-4de4-8c00-9c70622fd23f'::uuid
);

delete from gl.journal_entry
where journal_entry_id in (
    '2a5a6247-2133-4760-9dc7-3f6672ee9417'::uuid,
    '90fe5e17-d52e-4de4-8c00-9c70622fd23f'::uuid
);

commit;
