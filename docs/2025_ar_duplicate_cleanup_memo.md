# 2025 AR Duplicate Cleanup Memo

Date: 2026-04-28

Scope:

- confirmed duplicate January 1 AR invoices totaling `593,722.50`
- linked receipts and payment allocations
- cleanup sequence needed to preserve valid customer receipts while removing duplicated invoice detail

## Conclusion

National Health Insurance Authority should **not** be unwound from AR opening on the basis of cash collection. It remains an open receivable.

The recommended unwind is limited to the seven small January 1 duplicate AR invoices already identified in the opening bridge. These are not valid carryforward balances; they are later recreated invoice detail sitting on top of the opening representation.

## Duplicate Invoice Set

| Customer | ERPNext Opening Ref | Duplicate Invoice | Posted Journal | Invoice Amount |
|---|---|---|---|---:|
| `HYPERIA VFS Canada` | `CUS OP BAL 13` | `ACC-SINV-2025-00456` | `JE-2025-00178` | `59,125.00` |
| `HYPERIA VFS South Africa` | `CUS OP BAL 12` | `ACC-SINV-2025-00457` | `JE-2025-00179` | `134,375.00` |
| `NTEL KADO` | `CUS OP BAL 15` | `ACC-SINV-2025-00460` | `JE-2025-00182` | `48,375.00` |
| `NTEL Lord Lugard` | `CUS OP BAL 16` | `ACC-SINV-2025-00461` | `JE-2025-00183` | `88,150.00` |
| `NTEL CBD` | `CUS OP BAL 17` | `ACC-SINV-2025-00462` | `JE-2025-00184` | `88,150.00` |
| `Hyperia Quantun` | `CUS OP BAL 14` | `ACC-SINV-2025-00463` | `JE-2025-00185` | `29,562.50` |
| `Hyperia Churchgate` | `CUS OP BAL 10` | `ACC-SINV-2025-00464` | `JE-2025-00186` | `134,375.00` |

Gross duplicate invoice total from live AR:

- `582,112.50`

Opening-bridge duplicate total previously identified:

- `593,722.50`

Important note:

- the live invoice total for `NTEL Lord Lugard` and `NTEL CBD` is `88,150.00` each
- the opening-bridge amount for those names was `93,955.00` each
- receipts on those items include withholding-tax treatment, so the cleanup should follow the customer open-item and receipt trail, not just the gross invoice face value

## Receipt and Allocation Links

These duplicate invoices are already paid. That means the unwind must start with allocations, not with invoice deletion.

| Duplicate Invoice | Allocation | Payment | Payment Date | Payment Amount | Allocated to Duplicate |
|---|---|---|---|---:|---:|
| `ACC-SINV-2025-00456` | `bd628556-6894-4332-af5e-07eda4d3eb23` | `ACC-PAY-2025-07203` | `2025-02-13` | `59,125.00` | `59,125.00` |
| `ACC-SINV-2025-00457` | `c8872ed9-89a2-41c7-a759-9a4d3e893f59` | `ACC-PAY-2025-07204-2` | `2025-02-13` | `88,125.00` | `88,125.00` |
| `ACC-SINV-2025-00457` | `f2c43247-a88a-490a-9f24-622194ff2b8a` | `ACC-PAY-2025-11232` | `2025-03-07` | `180,625.00` | `46,250.00` |
| `ACC-SINV-2025-00460` | `3f2e026d-d902-4a61-a2fe-2b591f9cbce1` | `ACC-PAY-2025-15444` | `2025-02-28` | `47,475.00` | `48,375.00` |
| `ACC-SINV-2025-00461` | `c7becc65-895b-474c-a3f7-63a3328b2cb0` | `ACC-PAY-2025-15446` | `2025-02-28` | `92,207.00` | `93,955.00` |
| `ACC-SINV-2025-00462` | `a2c0b57e-8e04-4893-bb50-12437d75b050` | `ACC-PAY-2025-15435` | `2025-01-22` | `89,585.00` | `34,652.01` |
| `ACC-SINV-2025-00462` | `49231ce0-c1a4-43dd-81fd-f82f873ada64` | `ACC-PAY-2025-15448` | `2025-02-28` | `51,749.99` | `53,497.99` |
| `ACC-SINV-2025-00463` | `f7860e33-24d8-48c2-9388-78ff327fabda` | `ACC-PAY-2025-07201-1` | `2025-02-13` | `29,562.50` | `29,562.50` |
| `ACC-SINV-2025-00464` | `92e3a785-8c4a-430d-8b2d-f5f7924e5cf2` | `ACC-PAY-2025-07194` | `2025-02-13` | `134,375.00` | `134,375.00` |

## Split-Payment Risks

Two receipts are not dedicated only to the duplicate invoices:

- `ACC-PAY-2025-11232`
  - allocated `46,250.00` to duplicate invoice `ACC-SINV-2025-00457`
  - also allocated `134,375.00` to later invoice `ACC-SINV-2025-02276`
- `ACC-PAY-2025-15435`
  - allocated `34,652.01` to duplicate invoice `ACC-SINV-2025-00462`
  - also allocated `54,932.99` to later invoice `ACC-SINV-2025-19435`

Those two payments must be edited carefully. Only the duplicate-linked allocation rows should be removed.

## Recommended Cleanup Sequence

1. Remove the nine duplicate-linked `ar.payment_allocation` rows listed above.
2. Do **not** void the underlying customer receipts unless a receipt exists solely because of the duplicate invoice and has no valid surviving application.
3. Reverse or void the seven duplicate invoices:
   - `ACC-SINV-2025-00456`
   - `ACC-SINV-2025-00457`
   - `ACC-SINV-2025-00460`
   - `ACC-SINV-2025-00461`
   - `ACC-SINV-2025-00462`
   - `ACC-SINV-2025-00463`
   - `ACC-SINV-2025-00464`
4. Reverse the posted GL journals if invoice void does not auto-reverse:
   - `JE-2025-00178`
   - `JE-2025-00179`
   - `JE-2025-00182`
   - `JE-2025-00183`
   - `JE-2025-00184`
   - `JE-2025-00185`
   - `JE-2025-00186`
5. Reapply the surviving receipts to the valid opening customer balances or their replacement open items.
   - if the system supports open-item allocation to opening journals, use that
   - if not, post a controlled AR reclass entry and document the bridge

## Why This Is Safer Than Broad AR Reversal

- the duplicate block is small and specifically identified
- receipts already exist, so deleting customer payments would create unnecessary collateral damage
- `National Health Insurance Authority` is a separate issue and should remain open
- several larger AR openings are now proven to be genuine carryforwards cleared against opening journals, not duplicates

## Immediate Audit Effect

If this duplicate block is unwound correctly:

- the confirmed AR duplicate population is removed without disturbing genuine opening carryforwards
- customer receipts remain valid
- the remaining AR risk concentrates on support for the still-open large balances rather than on obvious duplicate invoice recreation
