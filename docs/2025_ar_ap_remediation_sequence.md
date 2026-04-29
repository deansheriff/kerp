# 2025 AR/AP Remediation Sequence

Date: 2026-04-28

Purpose:

- turn the AR/AP opening-duplication findings into a concrete cleanup order
- identify which records are entangled with later allocations/payments

## 1. AP First: Confirmed Duplicate Cases

These three supplier invoices are the clearest AP cleanup candidates:

| Supplier Invoice | Amount | Supplier | Current State |
|---|---:|---|---|
| `SINV202603-1439` | `11,009,288.78` | `Glo Zone` | `status=POSTED`, `posting_status=NOT_POSTED` |
| `SINV202603-1440` | `437,841.40` | `Transglobal Projects & Allied Services` | `status=POSTED`, `posting_status=NOT_POSTED` |
| `SINV202603-1441` | `179,571.50` | `Ideal Cabom Services Limited` | `status=POSTED`, `posting_status=NOT_POSTED` |

These exactly mirror:

- `JE-2025-00041`
- `JE-2025-00055`
- `JE-2025-00043`

from the `PUR OP BAL` opening-journal set.

### Why these cannot be ignored

They already have downstream allocations:

| Supplier Invoice | Allocated Amount | Allocation Date | Linked Payment |
|---|---:|---|---|
| `SINV202603-1439` | `11,009,288.78` | `2026-04-16` | `PMT202604-132042` |
| `SINV202603-1440` | `437,841.40` | `2026-04-16` | `PMT202604-132044` |
| `SINV202603-1441` | `179,571.50` | `2026-04-16` | `PMT202604-132043` |

The linked payments are all still `DRAFT`, which is good news. It means the contamination has spread into allocations, but not yet into posted payment journals.

### AP cleanup order

1. Break the three draft payment allocations.
2. Void or remove the three draft payments:
   - `PMT202604-132042`
   - `PMT202604-132043`
   - `PMT202604-132044`
3. Decide which opening representation survives:
   - keep the original `PUR OP BAL` journals, or
   - keep the supplier invoices and reverse the mirrored opening journals
4. Do not keep both.
5. After that, bridge the remaining unresolved `PUR OP BAL` amount:
   - `25,750,049.36`

### Preferred AP direction

From an audit-cleanup standpoint, the more defensible route is usually:

- preserve one coherent supplier-detail method only
- remove mixed-state documents (`POSTED` but `NOT_POSTED`)

That means these three later backfilled supplier invoices are the weaker records and are the first candidates to unwind.

## 2. AR Next: Confirmed Duplicate Cases Already Paid

The confirmed exact-duplicate AR invoices are:

| AR Invoice | Amount | Customer | Current State |
|---|---:|---|---|
| `ACC-SINV-2025-00457` | `134,375.00` | `HYPERIA VFS South Africa` | `PAID`, `POSTED` |
| `ACC-SINV-2025-00464` | `134,375.00` | `Hyperia Churchgate` | `PAID`, `POSTED` |
| `ACC-SINV-2025-00461` | `93,955.00` | `NTEL Lord Lugard` | `PAID`, `POSTED` |
| `ACC-SINV-2025-00462` | `93,955.00` | `NTEL CBD` | `PAID`, `POSTED` |
| `ACC-SINV-2025-00456` | `59,125.00` | `HYPERIA VFS Canada` | `PAID`, `POSTED` |
| `ACC-SINV-2025-00460` | `48,375.00` | `NTEL KADO` | `PAID`, `POSTED` |
| `ACC-SINV-2025-00463` | `29,562.50` | `Hyperia Quantun` | `PAID`, `POSTED` |

Total confirmed exact AR overlap:

- `593,722.50`

### Why AR is harder than AP

These invoices are not just present. They are already allocated and paid.

Allocation evidence:

- `ACC-SINV-2025-00456` allocated `59,125.00`
- `ACC-SINV-2025-00457` allocated `134,375.00`
- `ACC-SINV-2025-00460` allocated `48,375.00`
- `ACC-SINV-2025-00461` allocated `93,955.00`
- `ACC-SINV-2025-00462` allocated `88,150.00`
- `ACC-SINV-2025-00463` allocated `29,562.50`
- `ACC-SINV-2025-00464` allocated `134,375.00`

Allocation dates run from `2025-01-22` to `2025-03-07`.

That means AR cleanup cannot start with reversals. It must start with a customer schedule and payment trace.

## 3. Recommended Order of Work

### Step 1

Clean the three confirmed AP duplicate cases first.

Reason:

- they are material
- they are clearly duplicated
- their linked payments are only `DRAFT`
- they are still easier to unwind than the AR duplicates

### Step 2

Build the remaining AP supplier opening bridge for:

- `25,750,049.36`

Goal:

- decide whether each remaining supplier opening belongs in:
  - summary opening only
  - detail opening only
  - duplicated
  - unresolved

### Step 3

Build the AR customer schedule for all `CUS OP BAL` lines, starting with the seven confirmed duplicates.

For AR, every duplicated line must be traced through:

- opening journal
- invoice
- receipt allocation
- residual balance

## 4. What Not To Do

- Do not reverse AR invoices before unlinking or understanding their receipts.
- Do not leave AP invoices in `status=POSTED` and `posting_status=NOT_POSTED`.
- Do not adjust control accounts only at summary level without preserving a customer/supplier bridge.

## 5. Immediate Deliverables Needed

- AP duplicate-case resolution memo for the three exact mirrored supplier invoices
- supplier opening bridge for the remaining `25,750,049.36`
- customer opening bridge for the remaining `20,323,530.85` of unresolved `CUS OP BAL`

## 6. Practical Conclusion

The next operational move should be:

1. unwind the three AP duplicate cases cleanly
2. freeze the AP bridge after that
3. then move into AR customer-level proof

That is the fastest path to making AR/AP auditable without making the ledger messier.
