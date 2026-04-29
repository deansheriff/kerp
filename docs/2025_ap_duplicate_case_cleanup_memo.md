# 2025 AP Duplicate Case Cleanup Memo

Date: 2026-04-28

Scope:

- three confirmed AP duplicate opening cases
- linked journals, invoices, allocations, and draft payments

## Summary

These three cases are confirmed duplicate-load defects:

| Opening Journal | Amount | Mirrored Supplier Invoice | Supplier |
|---|---:|---|---|
| `JE-2025-00041` | `11,009,288.78` | `SINV202603-1439` | `Glo Zone` |
| `JE-2025-00055` | `437,841.40` | `SINV202603-1440` | `Transglobal Projects & Allied Services` |
| `JE-2025-00043` | `179,571.50` | `SINV202603-1441` | `Ideal Cabom Services Limited` |

Total confirmed duplicate AP exposure:

- `11,626,701.68`

## Record-Level Dependency Map

### Case 1: Glo Zone

- opening journal:
  - `JE-2025-00041`
  - journal_entry_id: `e875f3da-d612-4c46-82a7-d9c97c2f7a4f`
  - created_at: `2026-03-02 11:54:51.542426+00`
  - posted_at: `2026-03-02 11:54:50.121021+00`
  - effect on `2000`: `(11,009,288.78)`

- mirrored supplier invoice:
  - `SINV202603-1439`
  - invoice_id: `11efb18d-0fab-4946-8b2e-977ba7d47894`
  - invoice_created_at: `2026-03-14 13:52:00.812792+00`
  - invoice_date: `2025-01-01`
  - status: `POSTED`
  - posting_status: `NOT_POSTED`
  - amount: `11,009,288.78`

- mirrored invoice journal:
  - `JE202604-43253`
  - journal_entry_id: `bc4f9734-c445-4fdd-a80a-ae3645436e4d`
  - created_at: `2026-04-18 21:18:14.984426+00`
  - posted_at: `2026-04-18 21:18:17.225519+00`

- linked allocation:
  - allocation_id: `e4d1e2de-ad9c-4630-b58d-67701756e7e9`
  - allocated_amount: `11,009,288.78`
  - allocation_date: `2026-04-16`

- linked payment:
  - `PMT202604-132042`
  - payment_id: `3d3c4c7a-28d8-41a8-8618-4b49630d4517`
  - status: `DRAFT`
  - amount: `11,009,288.78`
  - journal_entry_id: null

### Case 2: Transglobal Projects & Allied Services

- opening journal:
  - `JE-2025-00055`
  - journal_entry_id: `cb3f7c4a-a2f6-4233-898b-c65740345533`
  - created_at: `2026-03-02 11:54:51.542426+00`
  - posted_at: `2026-03-02 11:54:50.121021+00`
  - effect on `2000`: `(437,841.40)`

- mirrored supplier invoice:
  - `SINV202603-1440`
  - invoice_id: `e8cdffca-a3ea-4971-a2e7-a5b2705437cd`
  - invoice_created_at: `2026-03-14 13:52:00.812792+00`
  - invoice_date: `2025-01-01`
  - status: `POSTED`
  - posting_status: `NOT_POSTED`
  - amount: `437,841.40`

- mirrored invoice journal:
  - `JE202604-43255`
  - journal_entry_id: `a5154968-5ecd-4ddc-a7b8-c41f7df39875`
  - created_at: `2026-04-18 21:18:17.593086+00`
  - posted_at: `2026-04-18 21:18:17.688456+00`

- linked allocation:
  - allocation_id: `88e31778-ceaa-4817-8467-4e328ae53ab0`
  - allocated_amount: `437,841.40`
  - allocation_date: `2026-04-16`

- linked payment:
  - `PMT202604-132044`
  - payment_id: `06503125-a411-490f-8a78-ecd171b0b82b`
  - status: `DRAFT`
  - amount: `437,841.40`
  - journal_entry_id: null

### Case 3: Ideal Cabom Services Limited

- opening journal:
  - `JE-2025-00043`
  - journal_entry_id: `cf75782b-30de-408f-9cc0-bd726088b6f2`
  - created_at: `2026-03-02 11:54:51.542426+00`
  - posted_at: `2026-03-02 11:54:50.121021+00`
  - effect on `2000`: `(179,571.50)`

- mirrored supplier invoice:
  - `SINV202603-1441`
  - invoice_id: `14da5709-5e83-4046-a9b3-96ad49b2245b`
  - invoice_created_at: `2026-03-14 13:52:00.812792+00`
  - invoice_date: `2025-01-01`
  - status: `POSTED`
  - posting_status: `NOT_POSTED`
  - amount: `179,571.50`

- mirrored invoice journal:
  - `JE202604-43254`
  - journal_entry_id: `dcf77a40-9820-445c-bef8-b7d0a82ea886`
  - created_at: `2026-04-18 21:18:17.469306+00`
  - posted_at: `2026-04-18 21:18:17.581203+00`

- linked allocation:
  - allocation_id: `b5e0feb3-79a2-4449-9bfd-e9c8d9675cfd`
  - allocated_amount: `179,571.50`
  - allocation_date: `2026-04-16`

- linked payment:
  - `PMT202604-132043`
  - payment_id: `3a61d8f0-7264-425d-956d-58c7bdc81a26`
  - status: `DRAFT`
  - amount: `179,571.50`
  - journal_entry_id: null

## What Makes These Good Cleanup Candidates

- The opening journals are already posted and represent the earlier opening-load layer.
- The later supplier invoices are weaker evidence:
  - created later
  - backdated to `2025-01-01`
  - internally inconsistent: `status=POSTED`, `posting_status=NOT_POSTED`
- The linked payments are still only `DRAFT`.
- The linked payments have no `journal_entry_id`.

That means the unwind can happen before this defect spreads into posted payment accounting.

## Recommended Unwind Sequence

1. Remove the three `ap.payment_allocation` rows:
   - `e4d1e2de-ad9c-4630-b58d-67701756e7e9`
   - `88e31778-ceaa-4817-8467-4e328ae53ab0`
   - `b5e0feb3-79a2-4449-9bfd-e9c8d9675cfd`

2. Void or delete the three draft `ap.supplier_payment` records:
   - `PMT202604-132042`
   - `PMT202604-132043`
   - `PMT202604-132044`

3. Void or remove the three later supplier invoices:
   - `SINV202603-1439`
   - `SINV202603-1440`
   - `SINV202603-1441`

4. Reverse their posted GL journals if the application does not auto-reverse on invoice void:
   - `JE202604-43253`
   - `JE202604-43254`
   - `JE202604-43255`

5. Keep the original opening journals as the surviving opening representation unless supplier-level evidence shows those opening journals themselves were wrong:
   - `JE-2025-00041`
   - `JE-2025-00043`
   - `JE-2025-00055`

## What To Verify After Cleanup

- `2000 Trade Payables` should reduce by `11,626,701.68` if the later mirrored supplier invoices are the ones removed from the live AP detail layer.
- No allocation rows should remain for the three duplicate invoices.
- No draft payments should remain linked to those invoices.
- The supplier aging should no longer show these duplicated obligations twice.

## Audit Position

These three AP duplicates are the cleanest immediate correction set in the whole 2025 cleanup effort.

They are:

- material
- proven
- narrowly scoped
- not yet entangled with posted payment journals

This is the right first correction wave before touching broader AP or AR opening issues.
