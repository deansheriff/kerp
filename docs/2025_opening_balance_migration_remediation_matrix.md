# 2025 Opening Balance Migration Remediation Matrix

Date: 2026-04-28

Purpose:

- classify remaining opening-balance import artifacts
- state whether each should be deleted, line-deleted, kept, or investigated
- give a safe dependency order for DB-level migration cleanup

## Important Framing

This matrix assumes:

- these are migration import errors, not genuine business postings
- the cleanup will be executed as a controlled remediation with backup and memo support
- posted-history rows are removed only when the entire duplicate artifact chain is removed together

## Action Codes

- `DELETE`: remove the record and its dependent artifacts from the database
- `LINE_DELETE`: surgically remove specific duplicated lines from a multi-purpose journal
- `KEEP`: retain as the surviving opening-balance representation
- `INVESTIGATE`: do not delete yet; needs external support first

## Group A: Exact Duplicate Cash and Wallet Openings

These are cleanest to remove because they duplicate amounts already loaded elsewhere.

| Record | Table(s) | Primary Key(s) | Action | Reason | Dependency Order |
|---|---|---|---|---|---|
| `JE-2025-00015` | `gl.journal_entry`, `gl.journal_entry_line`, `gl.posted_ledger_line` | JE `249bcc89-9529-42fe-af86-ee389103296c` | `DELETE` | duplicate UBA opening `2,487,543.70`; already exists in `OB-000001` | after backup; no subledger dependency |
| `JE-2025-00016` | same | JE `ec44873b-591a-431f-9f8a-28894c364d7a` | `DELETE` | duplicate Paystack OPEX opening `40,615.65`; already in `OB-000001` | after backup |
| `JE-2025-00017` | same | JE `5dcc935f-090a-43af-bf03-146bfd323a87` | `DELETE` | duplicate Paystack opening `297,500.00`; already in `OB-000001` | after backup |
| `JE-2025-00018` | same | JE `e2597e57-3e1a-49cc-b98a-1eb492cc0c12` | `DELETE` | duplicate cash-at-hand opening `3,245.44`; already in `OB-000001` | after backup |
| `JE-2025-00080` | same | JE `17efa38a-b9e3-47fc-be24-4273297e3e4b` | `DELETE` | duplicate `1420 Withholding Taxes` opening `68,308,470.18`; `OB-000001` already has `68,308,470.02` | after backup |

## Group B: AR Duplicate Opening Invoices

These are later recreated invoice detail on top of surviving `CUS OP BAL` openings.

### Step B1: Delete allocation rows first

| Record | Table | Primary Key | Action | Reason |
|---|---|---|---|---|
| allocation for `ACC-SINV-2025-00456` | `ar.payment_allocation` | `bd628556-6894-4332-af5e-07eda4d3eb23` | `DELETE` | duplicate-invoice allocation |
| allocation for `ACC-SINV-2025-00457` | `ar.payment_allocation` | `c8872ed9-89a2-41c7-a759-9a4d3e893f59` | `DELETE` | duplicate-invoice allocation |
| allocation for `ACC-SINV-2025-00457` split receipt | `ar.payment_allocation` | `f2c43247-a88a-490a-9f24-622194ff2b8a` | `DELETE` | remove only duplicate-linked portion; keep the payment |
| allocation for `ACC-SINV-2025-00460` | `ar.payment_allocation` | `3f2e026d-d902-4a61-a2fe-2b591f9cbce1` | `DELETE` | duplicate-invoice allocation |
| allocation for `ACC-SINV-2025-00461` | `ar.payment_allocation` | `c7becc65-895b-474c-a3f7-63a3328b2cb0` | `DELETE` | duplicate-invoice allocation |
| allocation for `ACC-SINV-2025-00462` | `ar.payment_allocation` | `a2c0b57e-8e04-4893-bb50-12437d75b050` | `DELETE` | remove only duplicate-linked portion; keep the payment |
| allocation for `ACC-SINV-2025-00462` | `ar.payment_allocation` | `49231ce0-c1a4-43dd-81fd-f82f873ada64` | `DELETE` | duplicate-invoice allocation |
| allocation for `ACC-SINV-2025-00463` | `ar.payment_allocation` | `f7860e33-24d8-48c2-9388-78ff327fabda` | `DELETE` | duplicate-invoice allocation |
| allocation for `ACC-SINV-2025-00464` | `ar.payment_allocation` | `92e3a785-8c4a-430d-8b2d-f5f7924e5cf2` | `DELETE` | duplicate-invoice allocation |

### Step B2: Keep the customer payments, do not delete them

Keep these `ar.customer_payment` rows. Only their duplicate-linked allocations should be removed:

- `7f49df97-c0d6-42b3-ba95-bf7353b0927b` `ACC-PAY-2025-07194`
- `27e0eacf-635a-4193-8e52-e406e706ef07` `ACC-PAY-2025-07201-1`
- `e8d08b53-113a-4124-ae1e-6a4027fb1f35` `ACC-PAY-2025-07203`
- `30d03dc7-ee32-4d8a-b9d4-d69be8181575` `ACC-PAY-2025-07204-2`
- `bf401729-e9d7-42fc-9b82-088f59f5d896` `ACC-PAY-2025-11232`
- `d90c9caa-e7b5-45c8-9f2a-e163ed53fc16` `ACC-PAY-2025-15444`
- `84fb76f5-32c1-4235-a31c-08f3795f3337` `ACC-PAY-2025-15446`
- `b61beb1d-9202-4bc4-96c6-1d7667d577c5` `ACC-PAY-2025-15435`
- `79aeb7ea-882c-4ba2-9455-4a8fca8d3ee1` `ACC-PAY-2025-15448`

Reason:

- these are real receipts
- some are split across valid later invoices
- deleting them would damage valid customer cash history

### Step B3: Delete the duplicate invoices and their GL journals

| Invoice | `ar.invoice.invoice_id` | GL Journal | `gl.journal_entry_id` | Action |
|---|---|---|---|---|
| `ACC-SINV-2025-00456` | `3251730b-177e-487a-b3e7-0012088dc261` | `JE-2025-00178` | `f37bf164-94c7-49ee-8600-c988c5d5e804` | `DELETE` |
| `ACC-SINV-2025-00457` | `14c6b81c-1226-4226-9697-8e3110a917f0` | `JE-2025-00179` | `4cbba8c0-53d8-4f20-867e-f47021e283a4` | `DELETE` |
| `ACC-SINV-2025-00460` | `4006a0dd-ead9-41b4-b027-cef2cea76a0f` | `JE-2025-00182` | `42deb460-348a-470f-bf58-aeb5a7f0e623` | `DELETE` |
| `ACC-SINV-2025-00461` | `0cb5c2b9-651e-46b9-828a-47dc55cbecdc` | `JE-2025-00183` | `5f5050b4-f223-4f47-b03d-1c3d85bb9c5f` | `DELETE` |
| `ACC-SINV-2025-00462` | `54410efa-1b88-47ff-8b64-2e091323dd71` | `JE-2025-00184` | `a17b0155-b90c-4366-8113-680182f7099a` | `DELETE` |
| `ACC-SINV-2025-00463` | `bd2f41ce-09f3-4748-b8ab-717d27582cbc` | `JE-2025-00185` | `8fc381e3-046f-4915-8204-1fb85f9b61e2` | `DELETE` |
| `ACC-SINV-2025-00464` | `567e92da-99df-4c06-858b-3a73dab0cf41` | `JE-2025-00186` | `32bdd22f-c9cd-4729-9559-3fb78c617878` | `DELETE` |

## Group C: AP Mirrored Opening Invoices

These are later mirrored supplier invoices that duplicate surviving `PUR OP BAL` openings.

### Step C1: Delete dependent AP allocation rows

| Record | Table | Primary Key | Action |
|---|---|---|---|
| allocation for `SINV202603-1439` | `ap.payment_allocation` | `e4d1e2de-ad9c-4630-b58d-67701756e7e9` | `DELETE` |
| allocation for `SINV202603-1440` | `ap.payment_allocation` | `88e31778-ceaa-4817-8467-4e328ae53ab0` | `DELETE` |
| allocation for `SINV202603-1441` | `ap.payment_allocation` | `b5e0feb3-79a2-4449-9bfd-e9c8d9675cfd` | `DELETE` |

### Step C2: Delete the dependent draft AP payments

| Payment | `ap.supplier_payment.payment_id` | Action | Reason |
|---|---|---|---|
| `PMT202604-132042` | `3d3c4c7a-28d8-41a8-8618-4b49630d4517` | `DELETE` | draft-only payment servicing duplicate invoice |
| `PMT202604-132043` | `3a61d8f0-7264-425d-956d-58c7bdc81a26` | `DELETE` | same |
| `PMT202604-132044` | `06503125-a411-490f-8a78-ecd171b0b82b` | `DELETE` | same |

### Step C3: Delete the mirrored AP invoices and posted journals

| Invoice | `ap.supplier_invoice.invoice_id` | GL Journal | `gl.journal_entry_id` | Action |
|---|---|---|---|---|
| `SINV202603-1439` | `11efb18d-0fab-4946-8b2e-977ba7d47894` | `JE202604-43253` | `bc4f9734-c445-4fdd-a80a-ae3645436e4d` | `DELETE` |
| `SINV202603-1440` | `e8cdffca-a3ea-4971-a2e7-a5b2705437cd` | `JE202604-43255` | `a5154968-5ecd-4ddc-a7b8-c41f7df39875` | `DELETE` |
| `SINV202603-1441` | `14da5709-5e83-4046-a9b3-96ad49b2245b` | `JE202604-43254` | `dcf77a40-9820-445c-bef8-b7d0a82ea886` | `DELETE` |

## Group D: `OB-000001` Surgical Line Deletes

Do not delete the whole journal. Remove only the duplicated control-account lines.

| Account | `gl.journal_entry_line.line_id` | Matching posted line key | Amount | Action | Reason |
|---|---|---|---:|---|---|
| `1200 Zenith Bank` | `4ec4bcf2-b016-4ec8-948a-489858b4a026` | `gl.posted_ledger_line.journal_line_id = 4ec4bcf2-b016-4ec8-948a-489858b4a026` | `21,442,780.30` | `LINE_DELETE` | aggregate Zenith opening duplicated by `1204/1205/1206/1207` |
| `1400 Trade Receivables` | `9a296e07-39ac-49ac-89f0-c21273bfc4fb` | same key in `posted_ledger_line` | `20,591,053.35` | `LINE_DELETE` | summary AR opening overlaps with detailed `CUS OP BAL` openings |
| `2000 Trade Payables` | `739d4ced-814f-4ce6-9b56-38692b2f5c7d` | same key in `posted_ledger_line` | `(40,310,713.50)` | `LINE_DELETE` | summary AP opening overlaps with detailed `PUR OP BAL` openings |
| `1420 Withholding Taxes` | `15e0ffb0-c8c0-4702-879a-df9db440e3cd` | same key in `posted_ledger_line` | `68,308,470.02` | `LINE_DELETE` only if `JE-2025-00080` is kept; otherwise `KEEP` | choose only one WHT-receivable opening layer |

Default recommendation:

- delete `JE-2025-00080`
- keep the `OB-000001` `1420` line

That is the cleaner option because `OB-000001` is the audited-TB import layer.

## Group E: Surviving Detail To Keep

These should remain as the detailed opening representation:

- `JE-2025-00012` `1204 Zenith 523 Bank`
- `JE-2025-00013` `1205 Zenith 461 Bank`
- `JE-2025-00014` `1206 Zenith 454 Bank`
- `JE-2025-00078` `1207 Zenith USD Bank`
- customer opening journals `JE-2025-00019` to `JE-2025-00035`
- supplier opening journals `JE-2025-00036` to `JE-2025-00059`, `JE-2025-00075`, and `JE-2025-00077`

## Group F: Do Not Delete Yet

These are opening-style journals but are not yet proven duplicate artifacts in the same clean way.

| Journal | `gl.journal_entry_id` | Action | Why |
|---|---|---|---|
| `JE-2025-00079` | `90fe5e17-d52e-4de4-8c00-9c70622fd23f` | `INVESTIGATE` | extra WHT liability opening `14,536,448.13`; may be real carryforward or bad migration load |
| `JE-2025-00076` | `2a5a6247-2133-4760-9dc7-3f6672ee9417` | `INVESTIGATE` | income-tax opening `7,587,459.00`; needs 2024 tax-close support |

## Recommended Execution Order

1. Backup the database.
2. Delete Group B1 AR allocation rows.
3. Delete Group C1 AP allocation rows.
4. Delete Group C2 draft AP payments.
5. Delete Group B3 duplicate AR invoices and their journal rows.
6. Delete Group C3 duplicate AP invoices and their journal rows.
7. Delete Group A exact duplicate opening journals.
8. Apply Group D line deletes to `OB-000001`.
9. Recompute balances and confirm:
   - `1200` is gone or zeroed
   - `1202` is no longer doubled
   - `1211` is no longer doubled
   - `1220` is no longer doubled
   - `1400` survives only on detailed customer opening support
   - `2000` survives only on detailed supplier opening support
10. Reassess Group F tax journals against 2024 support before any deletion.

## Expected Residual After Cleanup

If this matrix is executed correctly, the remaining opening-balance issues should be limited to:

- small AR bridge difference `326,200.00`
- small AP bridge difference `123,962.46`
- `1207 Zenith USD Bank` as an FX-structure issue, not a duplicate-opening issue
- tax journals `JE-2025-00079` and `JE-2025-00076` pending support

That would eliminate the obvious migration duplication layer and leave only the narrower support and FX issues.
