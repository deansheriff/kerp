# 2025 AR Opening Customer Bridge

Date: 2026-04-28

Scope:

- `CUS OP BAL` opening entries dated `2025-01-01`
- overlap with January 1 AR invoices
- legacy ERPNext opening-entry provenance

## Summary

The AR opening is now much better identified than before.

- total `CUS OP BAL` journals: `20,917,253.35`
- confirmed exact overlap with January 1 posted AR invoices: `593,722.50`
- additional opening balances now proven to be genuine carryforwards later cleared against opening journals: `3,398,343.75`
- remaining identified customer opening balances: `20,323,530.85`

Unlike AP, the residual AR block is not currently an unnamed placeholder problem. The ERPNext legacy extract preserves customer names and, in several cases, legacy invoice references for the opening entries.

## Confirmed Duplicated Customer Detail

These opening amounts also appear as January 1 posted AR invoices in the live 2025 subledger.

| Customer | Amount | ERPNext Opening Ref | January 1 AR Invoice |
|---|---:|---|---|
| `Hyperia Churchgate` | `134,375.00` | `CUS OP BAL 10` | `ACC-SINV-2025-00464` |
| `HYPERIA VFS South Africa` | `134,375.00` | `CUS OP BAL 12` | `ACC-SINV-2025-00457` |
| `HYPERIA VFS Canada` | `59,125.00` | `CUS OP BAL 13` | `ACC-SINV-2025-00456` |
| `Hyperia Quantun` | `29,562.50` | `CUS OP BAL 14` | `ACC-SINV-2025-00463` |
| `NTEL KADO` | `48,375.00` | `CUS OP BAL 15` | `ACC-SINV-2025-00460` |
| `NTEL Lord Lugard` | `93,955.00` | `CUS OP BAL 16` | `ACC-SINV-2025-00461` |
| `NTEL CBD` | `93,955.00` | `CUS OP BAL 17` | `ACC-SINV-2025-00462` |

Subtotal:

- `593,722.50`

These are the clearest AR duplicates found so far.

## Identified Customer Opening Balances Not Yet Proven Duplicated

These balances are now directly identified from ERPNext `Opening Entry` journals, but they are not yet proven to have been recreated as duplicate January 1 AR invoices.

| ERPNext Opening Ref | Customer | Amount | Legacy Note / Ref |
|---|---|---:|---|
| `CUS OP BAL 1` | `National Health Insurance Authority` | `14,072,652.10` | legacy ref `INV-006451`, ref date `2023-09-06` |
| `CUS OP BAL 2` | `Ascomnet Intl Ltd (karasana)` | `287,500.00` | legacy ref `INV-008439`, ref date `2024-02-15` |
| `CUS OP BAL 3` | `NTEL FHA` | `290,035.00` | legacy ref `INV-010751`, ref date `2024-07-29` |
| `CUS OP BAL 4` | `International IDEA ? Nigeria` | `1,200,000.00` | no clean live duplicate proven yet |
| `CUS OP BAL 5` | `Hyperia PWC` | `612,750.00` | legacy ref `INV-012819`, ref date `2024-11-27` |
| `CUS OP BAL 6` | `Phase 3 Telecom` | `1,462,000.00` | note says provision of leased line service to CMC World Bank for `2024-06-06` to `2024-12-31`; legacy ref `INV-009311` |
| `CUS OP BAL 7` | `Hyancinth (BCN), BCN (Lokogoma), Dr Makinde (BCN), BCN (Dutse)` | `150,500.00` | grouped customer opening across four BCN names |
| `CUS OP BAL 8` | `NTEL Wuse-1, NTEL Wuse-2` | `1,213,406.25` | split across customer lines in ERPNext opening entry |
| `CUS OP BAL 9` | `Hyperia Skysat` | `311,750.00` | legacy ref `INV-012467`, ref date `2024-12-09` |
| `CUS OP BAL 11` | `Hyperia Maitama` | `722,937.50` | legacy ref `INV-012814`, ref date `2024-12-20` |
| `CUS OP BAL 19` | `Solidarity Center(USD)` | `1,000.00` | legacy USD-labelled customer opening |

Subtotal:

- `20,323,530.85`

## Interpretation

AR now looks different from AP in an important way.

- AP had a large unresolved supplier tail until the ERPNext extract filled it in.
- AR does not have a large unidentified tail anymore.
- The real AR question is whether these identified openings were valid carryforward detail, or whether some were later rebuilt again in the live 2025 customer subledger.

The strongest duplicate evidence remains the `593,722.50` exact-match block above.

The remaining `20,323,530.85` is mostly concentrated in a few large named customers:

- `National Health Insurance Authority` `14,072,652.10`
- `Phase 3 Telecom` `1,462,000.00`
- `NTEL Wuse-1, NTEL Wuse-2` `1,213,406.25`
- `International IDEA ? Nigeria` `1,200,000.00`
- `Hyperia Maitama` `722,937.50`
- `Hyperia PWC` `612,750.00`

## Validity Testing of Major Named Balances

The first pass of live 2025 invoice and receipt testing shows that several of the large named openings were not later recreated as the same invoice amount. Instead, they were collected explicitly against opening journal entries.

| Customer | Opening Amount | 2025 Live Pattern | First Clear Evidence | Current View |
|---|---:|---|---|---|
| `Hyperia Maitama` | `722,937.50` | recurring 2025 invoices exist, but the January 1 invoice is only `507,937.50` | `ACC-PAY-2025-17745` on `2025-01-06` says `Amount NGN 722937.5 against Journal Entry ACC-JV-2025-00042` | valid carryforward, cleared |
| `Phase 3 Telecom` | `1,462,000.00` | a January 1 invoice exists for only `860,000.00` | `ACC-PAY-2025-19825` on `2025-05-03` says `Amount NGN 1462000 against Journal Entry ACC-JV-2025-00038` | valid carryforward, cleared |
| `NTEL Wuse-1` + `NTEL Wuse-2` | `1,213,406.25` | January 1 invoices exist, but their amounts do not recreate the opening total | `ACC-PAY-2025-15419` and `ACC-PAY-2025-17746` on `2025-01-15` clear `1,170,070.31` and `43,335.94` against `Journal Entry ACC-JV-2025-00039` | valid carryforward, cleared |
| `National Health Insurance Authority` | `14,072,652.10` | a new January 1 invoice for `83,592,000.00` was posted with no 2025 receipts | no receipt or allocation evidence yet clearing the opening | still high-risk / unsupported from live 2025 activity |
| `International IDEA ? Nigeria` | `1,200,000.00` | twelve `400,000.00` monthly invoices and five `1,200,000.00` receipts exist in 2025 | no receipt text yet ties a payment back to the opening journal | identified but still unresolved from live activity alone |
| `Hyperia PWC` | `612,750.00` | the opening sits on customer `Hyperia PWC`, but 2025 invoices/payments run through separate master `Hyperia  PWC` | no live receipt against the opening customer record yet; `Hyperia  PWC` has its own recurring 2025 invoicing | customer-master split; needs merge/bridge logic |

Subtotal now supported as genuine opening carryforward later collected:

- `3,398,343.75`

This changes the AR picture materially. The larger named balances are not one homogeneous duplicate bucket.

- some are confirmed duplicate opening recreations as January 1 invoices
- some are valid opening journals later cleared by receipts
- some are identified but still need support from the 2024 customer schedule or legacy statement

## Highest-Risk Residual Items

After the first live-activity pass, the main AR risk is no longer broad name-discovery. It is concentrated in a smaller set of customer-specific support gaps:

- `National Health Insurance Authority` `14,072,652.10`
  - opening is identified from ERPNext
  - a separate `83,592,000.00` invoice was posted on `2025-01-01`
  - no 2025 receipt or allocation was found clearing the opening
- `International IDEA ? Nigeria` `1,200,000.00`
  - opening is identified from ERPNext
  - 2025 shows normal monthly `400,000.00` invoicing and periodic `1,200,000.00` receipts
  - no receipt text yet proves the opening itself was cleared
- `Hyperia PWC` `612,750.00`
  - opening is identified from ERPNext
  - 2025 trading appears under duplicate customer master `Hyperia  PWC`
  - this is now a master-data and bridge issue rather than a pure duplication issue

## Audit Position

At this stage:

- the AR opening-detail population is largely identifiable
- a small but real portion is confirmed duplicated in January 1 invoices
- another meaningful portion is now supported as valid carryforward collected against opening journals
- the larger remaining balances now need customer-schedule support and master-data cleanup, not name-discovery

That validity test should ask:

- does each opening line tie to a 2024 customer closing schedule
- was it collected or invoiced again during 2025 in a way that duplicates the opening
- should the opening journal survive, or should later recreated invoice detail survive

## Next Step

The highest-value AR follow-up is now narrower:

- obtain the `2024-12-31` customer closing schedule for `National Health Insurance Authority`, `International IDEA ? Nigeria`, and `Hyperia PWC`
- decide whether `Hyperia PWC` and `Hyperia  PWC` should be merged or bridged in the customer master
- unwind the `593,722.50` exact-duplicate January 1 invoice block

If those steps are completed, AR becomes mostly a targeted cleanup and support exercise rather than a broad opening-balance reconstruction.
