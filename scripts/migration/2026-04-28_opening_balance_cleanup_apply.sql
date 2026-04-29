-- Opening-balance migration remediation apply script.
-- Assumes these rows are migration import artifacts and a full backup exists.
-- This script intentionally excludes JE-2025-00076 and JE-2025-00079 pending external support.

begin;

do $$
declare
    expected_count int;
begin
    select count(*) into expected_count
    from ar.payment_allocation
    where allocation_id in (
        '3f2e026d-d902-4a61-a2fe-2b591f9cbce1'::uuid,
        '49231ce0-c1a4-43dd-81fd-f82f873ada64'::uuid,
        '92e3a785-8c4a-430d-8b2d-f5f7924e5cf2'::uuid,
        'a2c0b57e-8e04-4893-bb50-12437d75b050'::uuid,
        'bd628556-6894-4332-af5e-07eda4d3eb23'::uuid,
        'c7becc65-895b-474c-a3f7-63a3328b2cb0'::uuid,
        'c8872ed9-89a2-41c7-a759-9a4d3e893f59'::uuid,
        'f2c43247-a88a-490a-9f24-622194ff2b8a'::uuid,
        'f7860e33-24d8-48c2-9388-78ff327fabda'::uuid
    );
    if expected_count <> 9 then
        raise exception 'Expected 9 AR allocation rows, found %', expected_count;
    end if;

    select count(*) into expected_count
    from ap.payment_allocation
    where allocation_id in (
        '88e31778-ceaa-4817-8467-4e328ae53ab0'::uuid,
        'b5e0feb3-79a2-4449-9bfd-e9c8d9675cfd'::uuid,
        'e4d1e2de-ad9c-4630-b58d-67701756e7e9'::uuid
    );
    if expected_count <> 3 then
        raise exception 'Expected 3 AP allocation rows, found %', expected_count;
    end if;

    select count(*) into expected_count
    from ap.supplier_payment
    where payment_id in (
        '3d3c4c7a-28d8-41a8-8618-4b49630d4517'::uuid,
        '3a61d8f0-7264-425d-956d-58c7bdc81a26'::uuid,
        '06503125-a411-490f-8a78-ecd171b0b82b'::uuid
    )
    and status = 'DRAFT';
    if expected_count <> 3 then
        raise exception 'Expected 3 draft AP payments, found %', expected_count;
    end if;

    select count(*) into expected_count
    from ar.invoice
    where invoice_id in (
        '3251730b-177e-487a-b3e7-0012088dc261'::uuid,
        '14c6b81c-1226-4226-9697-8e3110a917f0'::uuid,
        '4006a0dd-ead9-41b4-b027-cef2cea76a0f'::uuid,
        '0cb5c2b9-651e-46b9-828a-47dc55cbecdc'::uuid,
        '54410efa-1b88-47ff-8b64-2e091323dd71'::uuid,
        'bd2f41ce-09f3-4748-b8ab-717d27582cbc'::uuid,
        '567e92da-99df-4c06-858b-3a73dab0cf41'::uuid
    );
    if expected_count <> 7 then
        raise exception 'Expected 7 AR invoices, found %', expected_count;
    end if;

    select count(*) into expected_count
    from ap.supplier_invoice
    where invoice_id in (
        '11efb18d-0fab-4946-8b2e-977ba7d47894'::uuid,
        'e8cdffca-a3ea-4971-a2e7-a5b2705437cd'::uuid,
        '14da5709-5e83-4046-a9b3-96ad49b2245b'::uuid
    );
    if expected_count <> 3 then
        raise exception 'Expected 3 AP invoices, found %', expected_count;
    end if;

    select count(*) into expected_count
    from gl.journal_entry
    where journal_entry_id in (
        '249bcc89-9529-42fe-af86-ee389103296c'::uuid,
        'ec44873b-591a-431f-9f8a-28894c364d7a'::uuid,
        '5dcc935f-090a-43af-bf03-146bfd323a87'::uuid,
        'e2597e57-3e1a-49cc-b98a-1eb492cc0c12'::uuid,
        '17efa38a-b9e3-47fc-be24-4273297e3e4b'::uuid,
        'f37bf164-94c7-49ee-8600-c988c5d5e804'::uuid,
        '4cbba8c0-53d8-4f20-867e-f47021e283a4'::uuid,
        '42deb460-348a-470f-bf58-aeb5a7f0e623'::uuid,
        '5f5050b4-f223-4f47-b03d-1c3d85bb9c5f'::uuid,
        'a17b0155-b90c-4366-8113-680182f7099a'::uuid,
        '8fc381e3-046f-4915-8204-1fb85f9b61e2'::uuid,
        '32bdd22f-c9cd-4729-9559-3fb78c617878'::uuid,
        'bc4f9734-c445-4fdd-a80a-ae3645436e4d'::uuid,
        'dcf77a40-9820-445c-bef8-b7d0a82ea886'::uuid,
        'a5154968-5ecd-4ddc-a7b8-c41f7df39875'::uuid
    );
    if expected_count <> 15 then
        raise exception 'Expected 15 duplicate journal entries, found %', expected_count;
    end if;
end $$;

-- 1. Delete dependent AR allocations.
delete from ar.payment_allocation
where allocation_id in (
    '3f2e026d-d902-4a61-a2fe-2b591f9cbce1'::uuid,
    '49231ce0-c1a4-43dd-81fd-f82f873ada64'::uuid,
    '92e3a785-8c4a-430d-8b2d-f5f7924e5cf2'::uuid,
    'a2c0b57e-8e04-4893-bb50-12437d75b050'::uuid,
    'bd628556-6894-4332-af5e-07eda4d3eb23'::uuid,
    'c7becc65-895b-474c-a3f7-63a3328b2cb0'::uuid,
    'c8872ed9-89a2-41c7-a759-9a4d3e893f59'::uuid,
    'f2c43247-a88a-490a-9f24-622194ff2b8a'::uuid,
    'f7860e33-24d8-48c2-9388-78ff327fabda'::uuid
);

-- 2. Delete dependent AP allocations.
delete from ap.payment_allocation
where allocation_id in (
    '88e31778-ceaa-4817-8467-4e328ae53ab0'::uuid,
    'b5e0feb3-79a2-4449-9bfd-e9c8d9675cfd'::uuid,
    'e4d1e2de-ad9c-4630-b58d-67701756e7e9'::uuid
);

-- 3. Delete dependent draft AP payments.
delete from ap.supplier_payment
where payment_id in (
    '3d3c4c7a-28d8-41a8-8618-4b49630d4517'::uuid,
    '3a61d8f0-7264-425d-956d-58c7bdc81a26'::uuid,
    '06503125-a411-490f-8a78-ecd171b0b82b'::uuid
);

-- 4. Delete duplicate AR invoices.
delete from ar.invoice_line
where invoice_id in (
    '3251730b-177e-487a-b3e7-0012088dc261'::uuid,
    '14c6b81c-1226-4226-9697-8e3110a917f0'::uuid,
    '4006a0dd-ead9-41b4-b027-cef2cea76a0f'::uuid,
    '0cb5c2b9-651e-46b9-828a-47dc55cbecdc'::uuid,
    '54410efa-1b88-47ff-8b64-2e091323dd71'::uuid,
    'bd2f41ce-09f3-4748-b8ab-717d27582cbc'::uuid,
    '567e92da-99df-4c06-858b-3a73dab0cf41'::uuid
);

delete from ar.invoice
where invoice_id in (
    '3251730b-177e-487a-b3e7-0012088dc261'::uuid,
    '14c6b81c-1226-4226-9697-8e3110a917f0'::uuid,
    '4006a0dd-ead9-41b4-b027-cef2cea76a0f'::uuid,
    '0cb5c2b9-651e-46b9-828a-47dc55cbecdc'::uuid,
    '54410efa-1b88-47ff-8b64-2e091323dd71'::uuid,
    'bd2f41ce-09f3-4748-b8ab-717d27582cbc'::uuid,
    '567e92da-99df-4c06-858b-3a73dab0cf41'::uuid
);

-- 5. Delete mirrored AP invoices.
delete from ap.supplier_invoice_line
where invoice_id in (
    '11efb18d-0fab-4946-8b2e-977ba7d47894'::uuid,
    'e8cdffca-a3ea-4971-a2e7-a5b2705437cd'::uuid,
    '14da5709-5e83-4046-a9b3-96ad49b2245b'::uuid
);

delete from ap.supplier_invoice
where invoice_id in (
    '11efb18d-0fab-4946-8b2e-977ba7d47894'::uuid,
    'e8cdffca-a3ea-4971-a2e7-a5b2705437cd'::uuid,
    '14da5709-5e83-4046-a9b3-96ad49b2245b'::uuid
);

-- 6. Delete posted-ledger rows for full duplicate journals.
delete from gl.posted_ledger_line
where journal_entry_id in (
    '249bcc89-9529-42fe-af86-ee389103296c'::uuid,
    'ec44873b-591a-431f-9f8a-28894c364d7a'::uuid,
    '5dcc935f-090a-43af-bf03-146bfd323a87'::uuid,
    'e2597e57-3e1a-49cc-b98a-1eb492cc0c12'::uuid,
    '17efa38a-b9e3-47fc-be24-4273297e3e4b'::uuid,
    'f37bf164-94c7-49ee-8600-c988c5d5e804'::uuid,
    '4cbba8c0-53d8-4f20-867e-f47021e283a4'::uuid,
    '42deb460-348a-470f-bf58-aeb5a7f0e623'::uuid,
    '5f5050b4-f223-4f47-b03d-1c3d85bb9c5f'::uuid,
    'a17b0155-b90c-4366-8113-680182f7099a'::uuid,
    '8fc381e3-046f-4915-8204-1fb85f9b61e2'::uuid,
    '32bdd22f-c9cd-4729-9559-3fb78c617878'::uuid,
    'bc4f9734-c445-4fdd-a80a-ae3645436e4d'::uuid,
    'dcf77a40-9820-445c-bef8-b7d0a82ea886'::uuid,
    'a5154968-5ecd-4ddc-a7b8-c41f7df39875'::uuid
);

-- 7. Delete posting batches referencing duplicate journals.
delete from gl.posting_batch
where journal_entry_id in (
    'bc4f9734-c445-4fdd-a80a-ae3645436e4d'::uuid,
    'dcf77a40-9820-445c-bef8-b7d0a82ea886'::uuid,
    'a5154968-5ecd-4ddc-a7b8-c41f7df39875'::uuid
);

-- 8. Delete journal-entry lines for full duplicate journals.
delete from gl.journal_entry_line
where journal_entry_id in (
    '249bcc89-9529-42fe-af86-ee389103296c'::uuid,
    'ec44873b-591a-431f-9f8a-28894c364d7a'::uuid,
    '5dcc935f-090a-43af-bf03-146bfd323a87'::uuid,
    'e2597e57-3e1a-49cc-b98a-1eb492cc0c12'::uuid,
    '17efa38a-b9e3-47fc-be24-4273297e3e4b'::uuid,
    'f37bf164-94c7-49ee-8600-c988c5d5e804'::uuid,
    '4cbba8c0-53d8-4f20-867e-f47021e283a4'::uuid,
    '42deb460-348a-470f-bf58-aeb5a7f0e623'::uuid,
    '5f5050b4-f223-4f47-b03d-1c3d85bb9c5f'::uuid,
    'a17b0155-b90c-4366-8113-680182f7099a'::uuid,
    '8fc381e3-046f-4915-8204-1fb85f9b61e2'::uuid,
    '32bdd22f-c9cd-4729-9559-3fb78c617878'::uuid,
    'bc4f9734-c445-4fdd-a80a-ae3645436e4d'::uuid,
    'dcf77a40-9820-445c-bef8-b7d0a82ea886'::uuid,
    'a5154968-5ecd-4ddc-a7b8-c41f7df39875'::uuid
);

-- 9. Delete duplicate journal entries.
delete from gl.journal_entry
where journal_entry_id in (
    '249bcc89-9529-42fe-af86-ee389103296c'::uuid,
    'ec44873b-591a-431f-9f8a-28894c364d7a'::uuid,
    '5dcc935f-090a-43af-bf03-146bfd323a87'::uuid,
    'e2597e57-3e1a-49cc-b98a-1eb492cc0c12'::uuid,
    '17efa38a-b9e3-47fc-be24-4273297e3e4b'::uuid,
    'f37bf164-94c7-49ee-8600-c988c5d5e804'::uuid,
    '4cbba8c0-53d8-4f20-867e-f47021e283a4'::uuid,
    '42deb460-348a-470f-bf58-aeb5a7f0e623'::uuid,
    '5f5050b4-f223-4f47-b03d-1c3d85bb9c5f'::uuid,
    'a17b0155-b90c-4366-8113-680182f7099a'::uuid,
    '8fc381e3-046f-4915-8204-1fb85f9b61e2'::uuid,
    '32bdd22f-c9cd-4729-9559-3fb78c617878'::uuid,
    'bc4f9734-c445-4fdd-a80a-ae3645436e4d'::uuid,
    'dcf77a40-9820-445c-bef8-b7d0a82ea886'::uuid,
    'a5154968-5ecd-4ddc-a7b8-c41f7df39875'::uuid
);

-- 10. Delete duplicated lines from OB-000001.
delete from gl.posted_ledger_line
where journal_line_id in (
    '4ec4bcf2-b016-4ec8-948a-489858b4a026'::uuid,
    '9a296e07-39ac-49ac-89f0-c21273bfc4fb'::uuid,
    '739d4ced-814f-4ce6-9b56-38692b2f5c7d'::uuid
);

delete from gl.journal_entry_line
where line_id in (
    '4ec4bcf2-b016-4ec8-948a-489858b4a026'::uuid,
    '9a296e07-39ac-49ac-89f0-c21273bfc4fb'::uuid,
    '739d4ced-814f-4ce6-9b56-38692b2f5c7d'::uuid
);

-- 11. Rebalance OB-000001 by reducing the retained-earnings credit line.
update gl.journal_entry_line
set credit_amount = 5011140.74,
    credit_amount_functional = 5011140.74
where line_id = '459290a2-7f34-461b-a3b9-11378eaf2ae8'::uuid;

update gl.posted_ledger_line
set credit_amount = 5011140.74,
    original_credit_amount = 5011140.74
where journal_line_id = '459290a2-7f34-461b-a3b9-11378eaf2ae8'::uuid;

update gl.journal_entry
set total_debit = 325261764.85,
    total_credit = 325261764.85,
    total_debit_functional = 325261764.85,
    total_credit_functional = 325261764.85
where journal_entry_id = 'a0000001-0000-0000-0000-000000000001'::uuid;

commit;
