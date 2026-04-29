# 2025 UBA Reconciliation Findings

Date: 2026-04-28

Source files:

- `/root/uba-statements/101xxxxx96.xlsx`
- `/root/uba-statements/101xxxxx96 (1).xlsx`
- `/root/uba-statements/101xxxxx96 (2).xlsx`
- `/root/uba-statements/300xxxxx94.xlsx`
- `/root/uba-statements/300xxxxx94 (1).xlsx`
- `/root/uba-statements/300xxxxx94 (2).xlsx`

Passwords used:

- `89046` for account `1018904696`
- `41542` for account `3004154294`

Scope:

- UBA NGN account `1018904696`
- UBA USD account `3004154294`
- mapping to posted GL through `2025-12-31`

## Accounts Covered

| Bank Account | Currency | Statement Period Used | Statement 2025 Closing | GL Mapping | GL 2025-12-31 Balance | Result |
|---|---|---|---:|---|---:|---|
| `1018904696` | NGN | `01-Jan-2024 - 26-Jan-2026` | `8,587,096.86` | `1202 UBA` | `11,074,640.56` | Overstated by duplicated opening |
| `3004154294` | USD | `01-Jan-2024 - 26-Jan-2026` | `100.00 USD` | no clear posted USD bank account | not established | Missing / unmapped in GL |

## 1018904696 - UBA NGN

### Statement basis

- `2024-12-31` closing balance: `2,487,543.70`
- `2025-12-31` closing balance: `8,587,096.86`
- 2025 net statement movement: `6,099,553.16`

This is directly visible in the statement rows:

- `2024-12-31` final balance after last Paystack credit: `2,487,543.70`
- `2025-12-31` final balance after last Paystack credit: `8,587,096.86`

### GL basis

- GL account: `1202 UBA`
- GL balance at `2025-12-31`: `11,074,640.56`
- 2025 net GL movement: `11,074,640.56`

Difference to statement closing:

- `11,074,640.56 - 8,587,096.86 = 2,487,543.70`

That difference equals the statement opening balance exactly.

### Source of the difference

The opening balance was loaded twice into the 2025 GL:

- `OB-000001` on `2025-01-01`: `2,487,543.70`
- `JE-2025-00015` on `2025-01-01`: `2,487,543.70`

So the GL is carrying:

- one opening implicitly required to roll forward the real bank balance
- plus one extra duplicated opening journal

This is why:

- statement closing is lower than GL by exactly `2,487,543.70`
- January 2025 GL movement exceeds January bank movement by exactly `4,975,087.40`
- and `4,975,087.40 = 2 x 2,487,543.70`

### January proof

- January 2025 statement movement: `(2,110,779.58)`
- January 2025 GL movement: `2,864,307.82`
- difference: `4,975,087.40`

That January gap is explained by the two opening entries:

- `OB-000001`: `2,487,543.70`
- `JE-2025-00015`: `2,487,543.70`

### Pattern of operational activity

The live 2025 bank activity itself looks plausible and is heavily driven by:

- Paystack transfers into UBA
- supplier payments
- internal transfers to Paystack OPEX / other banks
- charges such as SMS, VAT, account maintenance, and stamp duty

Examples:

- `2025-01-02` Paystack transfer into UBA: `693,000.00`
- `2025-01-06` supplier payment to Mikemascot: `(4,000,000.00)`
- `2025-01-12` transfer from UBA to Paystack OPEX: `(1,000,000.00)`
- `2025-01-31` account maintenance and VAT: `(26,520.53)` and `(1,989.04)`

So the main issue is not random cash posting failure. It is opening-balance duplication.

## 3004154294 - UBA USD

### Statement basis

- currency: `USD`
- `2025-06-04` cash deposit: `100.00 USD`
- `2025-12-31` closing balance: `100.00 USD`

### GL basis

I did not find a clear posted USD UBA bank ledger for this account.

Relevant account master findings:

- `1202 UBA` exists, but is not multi-currency
- there is no obvious posted `UBA USD` bank account corresponding to `3004154294`

### Source of the difference

The USD bank account exists on the statement side, but it is not clearly represented in the posted GL.

What I checked:

- descriptions containing `3004154294`
- descriptions containing `MICHAEL AYOADE`
- descriptions containing `cash dep`
- UBA postings on `2025-06-04`

Result:

- no clear posted GL line ties to the `100.00 USD` bank deposit
- the UBA postings on `2025-06-04` are NGN operational movements on `1202`, not a USD-bank recognition

### Conclusion

This is not audit-ready as a bank-subledger mapping:

- the NGN UBA account is overstated by one duplicated opening balance
- the USD UBA account is not clearly mapped into a posted USD bank ledger

## Overall Assessment

### NGN UBA

- usable statement evidence exists
- most 2025 operational movements appear to be captured
- but the balance is wrong because the opening was loaded twice

### USD UBA

- statement exists and is readable
- but the ERP does not provide a clean posted-bank representation for the account

## Practical Implication

For audit readiness:

- `1202 UBA` needs an opening-balance correction / bridge memo
- `3004154294` needs explicit GL mapping and recognition, or a formal explanation of why it is outside the audited ERP cash ledger
