# 2025 AP Residual Opening Bridge

Date: 2026-04-28

Scope:

- residual `PUR OP BAL` opening lines after removing the three confirmed duplicate AP cases

Residual opening amount under review:

- `25,750,049.36`

This is:

- total `PUR OP BAL` opening journals `37,376,751.04`
- less confirmed duplicate mirrored supplier invoices `11,626,701.68`

## Residual Line Inventory

| Journal | Amount | Notes |
|---|---:|---|
| `JE-2025-00036` | `8,707,500.00` | description says `Vendor's Balance for October 2024 - December 2024` |
| `JE-2025-00037` | `3,968,628.00` | description says `Land use violation charges in respect of Plot 770, Cad-Zone A01, Garki-Abuja` |
| `JE-2025-00058` | `2,914,450.00` | no descriptive supplier name |
| `JE-2025-00039` | `2,881,460.70` | ERPNext legacy opening for `DIGITAL REALITY (Medallion)` |
| `JE-2025-00057` | `2,294,735.66` | ERPNext legacy opening for `Tremfolink` |
| `JE-2025-00052` | `2,180,000.00` | no descriptive supplier name |
| `JE-2025-00050` | `770,000.00` | amount later recurs in Sir Tech invoices |
| `JE-2025-00059` | `705,200.00` | amount later recurs in Zoho invoices |
| `JE-2025-00053` | `365,500.00` | no descriptive supplier name |
| `JE-2025-00075` | `230,000.00` | amount matches Ben Sonic supplier total |
| `JE-2025-00047` | `201,000.00` | amount matches James Dogara supplier total |
| `JE-2025-00038` | `136,000.00` | ERPNext legacy opening for `Danytex Global Ventures` |
| `JE-2025-00042` | `128,000.00` | ERPNext legacy opening for `Hendis Telecommunication Ent` |
| `JE-2025-00044` | `115,000.00` | weak later amount recurrence only |
| `JE-2025-00046` | `108,575.00` | ERPNext legacy opening for `Linkztix Limited` |
| `JE-2025-00049` | `44,000.00` | weak later amount recurrence only |

## Classification

### A. Strongly supported opening obligations

These lines appear to represent specific opening liabilities, even though they are not yet tied to clean supplier-detail documents:

| Journal | Amount | Basis |
|---|---:|---|
| `JE-2025-00036` | `8,707,500.00` | description says vendor balance for Oct-Dec 2024; [reports/ap_subledger_reconciliation.csv](/root/dotmac/reports/ap_subledger_reconciliation.csv:3) shows the same `8,707,500.00` AP-vs-subledger difference for `Coloplus Worldwide Services Limited` |
| `JE-2025-00037` | `3,968,628.00` | description explicitly says land-use violation charges |

Subtotal:

- `12,676,128.00`

### B. Reasonable supplier-linked indications

These lines do not have explicit supplier names in the opening journal, but they have meaningful amount-based or narrative-based support:

| Journal | Amount | Indication |
|---|---:|---|
| `JE-2025-00039` | `2,881,460.70` | ERPNext `tabJournal Entry` `ACC-JV-2025-00118` is an `Opening Entry` for supplier `DIGITAL REALITY (Medallion)` with title `PUR OP BAL 012`, posting date `2025-01-01`, reference date `2024-12-31`; matching ERPNext `tabGL Entry` rows carry the same amount to `Trade and Other Payables - DT` |
| `JE-2025-00057` | `2,294,735.66` | ERPNext `tabJournal Entry` `ACC-JV-2025-00143` is an `Opening Entry` for supplier `Tremfolink` with title `PUR OP BAL 027`, posting date `2025-01-01`, reference date `2024-12-31`; matching ERPNext `tabGL Entry` rows carry the same amount to `Trade and Other Payables - DT` |
| `JE-2025-00058` | `2,914,450.00` | later `SUPPLIER_PAYMENT` `JE-2025-01675` clears the same opening amount and names `Wiocc Nigeria Limited`; [reports/ap_subledger_reconciliation.csv](/root/dotmac/reports/ap_subledger_reconciliation.csv:4) shows the same `2,914,450.00` difference |
| `JE-2025-00052` | `2,180,000.00` | later cleared supplier payment `ACC-PAY-2025-05478` / `JE-2025-05152` names `Sunny Martins Computers Ltd`; [reports/ap_subledger_reconciliation.csv](/root/dotmac/reports/ap_subledger_reconciliation.csv:7) shows the same `2,180,000.00` difference |
| `JE-2025-00075` | `230,000.00` | amount-based indications point to both `Ben Sonic Telecom` and [reports/ap_subledger_reconciliation.csv](/root/dotmac/reports/ap_subledger_reconciliation.csv:19) `Microview Nig Abuja`; still needs source-proof tie |
| `JE-2025-00047` | `201,000.00` | exact supplier-total match to `James Dogara` |
| `JE-2025-00050` | `770,000.00` | exact amount recurs in later `Sir Tech Links & Services` invoices |
| `JE-2025-00059` | `705,200.00` | exact amount recurs repeatedly in later `Zoho Technologies` invoices |
| `JE-2025-00053` | `365,500.00` | [reports/ap_subledger_reconciliation.csv](/root/dotmac/reports/ap_subledger_reconciliation.csv:14) shows the same `365,500.00` difference for `Swift Talk Limited` |
| `JE-2025-00038` | `136,000.00` | ERPNext `tabJournal Entry` `ACC-JV-2025-00117` is an `Opening Entry` for supplier `Danytex Global Ventures` with title `PUR OP BAL 011`; later ERPNext payment `ACC-PAY-2025-05446` settles the same amount on `2025-01-10` |
| `JE-2025-00042` | `128,000.00` | ERPNext `tabJournal Entry` `ACC-JV-2025-00121` is an `Opening Entry` for supplier `Hendis Telecommunication Ent` with title `PUR OP BAL 015`; later ERPNext payment `ACC-PAY-2025-05449` settles the same amount on `2025-01-10` |
| `JE-2025-00044` | `115,000.00` | [reports/ap_subledger_reconciliation.csv](/root/dotmac/reports/ap_subledger_reconciliation.csv:28) shows the same `115,000.00` difference for `Kosy-Raph Electrical Resources` |
| `JE-2025-00046` | `108,575.00` | ERPNext `tabJournal Entry` `ACC-JV-2025-00129` is an `Opening Entry` for supplier `Linkztix Limited` with title `PUR OP BAL 021` |
| `JE-2025-00049` | `44,000.00` | [reports/ap_subledger_reconciliation.csv](/root/dotmac/reports/ap_subledger_reconciliation.csv:37) shows the same `44,000.00` difference for `Peter Bolts & Nuts` |

Subtotal:

- `12,307,921.36`

These are not as strong as the three confirmed duplicate cases, but they are no longer completely opaque. The ERPNext extract now preserves direct supplier identity for `PUR OP BAL 011`, `012`, `015`, `021`, and `027`.

### C. Still unresolved placeholders

No residual placeholder lines remain from the reviewed `PUR OP BAL` set.

## Interpretation

The residual AP opening is no longer just one unexplained block.

It splits into:

- `12,676,128.00` strongly supported obligations
- `12,307,921.36` supplier-linked balances, now including direct ERPNext supplier identity for `DIGITAL REALITY (Medallion)`, `Tremfolink`, `Danytex Global Ventures`, `Hendis Telecommunication Ent`, and `Linkztix Limited`
- `0.00` residual placeholders in this reviewed `PUR OP BAL` set

## Practical Next Steps

### Highest-value supplier proof still needed

The largest lines are now materially explained:

- `JE-2025-00039` `2,881,460.70` -> `DIGITAL REALITY (Medallion)` from ERPNext `ACC-JV-2025-00118`
- `JE-2025-00057` `2,294,735.66` -> `Tremfolink` from ERPNext `ACC-JV-2025-00143`
- `JE-2025-00058` `2,914,450.00` -> `Wiocc Nigeria Limited`
- `JE-2025-00052` `2,180,000.00` -> `Sunny Martins Computers Ltd`

There is no longer a residual unresolved `PUR OP BAL` tail in this reviewed set.

### What to look for next

- prior-year AP schedule by supplier from the audited close
- supporting vendor statements or invoices where you want stronger third-party evidence beyond the ERPNext opening-entry trail
- confirmation of whether any later supplier-detail records duplicate these opening entries

## ERPNext Proof Added

The legacy ERPNext accounting extract now directly supports two of the formerly unresolved lines:

- `PUR OP BAL 012`
  - supplier: `DIGITAL REALITY (Medallion)`
  - ERPNext journal: `ACC-JV-2025-00118`
  - type: `Opening Entry`
  - posting date: `2025-01-01`
  - reference date: `2024-12-31`
  - amount: `2,881,460.70`

- `PUR OP BAL 027`
  - supplier: `Tremfolink`
  - ERPNext journal: `ACC-JV-2025-00143`
  - type: `Opening Entry`
  - posting date: `2025-01-01`
  - reference date: `2024-12-31`
  - amount: `2,294,735.66`

It also directly supports the smaller lines:

- `PUR OP BAL 011`
  - supplier: `Danytex Global Ventures`
  - ERPNext journal: `ACC-JV-2025-00117`
  - type: `Opening Entry`
  - posting date: `2025-01-01`
  - reference date: `2024-12-31`
  - amount: `136,000.00`
  - later ERPNext payment: `ACC-PAY-2025-05446` on `2025-01-10`

- `PUR OP BAL 015`
  - supplier: `Hendis Telecommunication Ent`
  - ERPNext journal: `ACC-JV-2025-00121`
  - type: `Opening Entry`
  - posting date: `2025-01-01`
  - reference date: `2024-12-31`
  - amount: `128,000.00`
  - later ERPNext payment: `ACC-PAY-2025-05449` on `2025-01-10`

- `PUR OP BAL 021`
  - supplier: `Linkztix Limited`
  - ERPNext journal: `ACC-JV-2025-00129`
  - type: `Opening Entry`
  - posting date: `2025-01-01`
  - reference date: `2024-12-31`
  - amount: `108,575.00`

## Audit Position

After isolating the three confirmed duplicate cases, the remaining AP opening in this reviewed set is now explainable from ERPNext legacy evidence.

That means:

- the AP defect is not only duplication
- it is also a documentation and migration-traceability problem, though the specific reviewed `PUR OP BAL` lines now have much better provenance

The next AP bridge should focus on correction decisions:

- unwind the three confirmed duplicate mirrored supplier invoices
- decide whether any other later supplier-detail records duplicate the legacy opening entries
- then move to AR customer-level opening proof
