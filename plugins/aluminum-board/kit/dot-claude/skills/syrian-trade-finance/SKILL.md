---
name: syrian-trade-finance
description: Structure cross border payments, L/Cs, guarantees and FX for importing machinery into Syria under current banking constraints. Use for G2 payment_instrument, every payment:<ref>, budget FX assumptions, and any vendor's question about payment terms.
---

# Syrian Trade Finance | التمويل التجاري والدفع عبر الحدود

## First rule
Facts here change monthly. Use only rails marked VERIFIED in `state/syrian_market_constraints.json`
(`banking_and_payment_rails`, `fx_and_currency`) with a `verified_on` date inside the 90 day window.
If none is verified, the verdict is VETOED with `NO_VERIFIED_PAYMENT_RAIL`. Do not reason from memory or news.

## Standard structure (board default, adjust to what is verified)
| Milestone | Typical % | Instrument | Protection for us |
|---|---|---|---|
| Advance | 20 to 30% | Wire or L/C sight portion | Advance payment guarantee 100% (EQ-06) |
| Shipment documents | 50 to 60% | L/C against B/L, invoice, packing list, CoO, inspection certificate | Documents must match the locked spec |
| SAT / commissioning | 10% | Wire or deferred L/C | Performance bond (EQ-07) |
| Final acceptance | 5 to 10% retention | Wire | Released only against warranty bond |

## Checks for every instrument
1. **Issuing and confirming bank**: name, country, written acceptance of Syrian counterparty funds.
2. **Vendor's bank**: has it confirmed in writing it will receive the funds? Ask for the letter before shortlisting.
3. **Guarantee issuer**: is the vendor's bank guarantee callable and enforceable from our side? Who pays the call?
4. **Expiry dates**: every guarantee expires at least 30 days after the event it secures. Record them.
5. **Documents required under the L/C**: they must be producible. Inspection certificate by a named third party.
6. **Cost**: issuance, confirmation, amendment, SWIFT, cash margin (`GUARANTEE_MARGIN`).
7. **Currency**: contract currency, our funding currency, the rate we can actually obtain, the spread.

## Red flags (severity)
- Advance without guarantee: CRITICAL.
- Guarantee from a bank that is unreachable for a call: CRITICAL.
- Payment through an informal transfer (hawala): HIGH, cannot secure guarantees, refer to legal-counsel.
- Payment to a third country account not named in the contract: CRITICAL (fraud and compliance risk).
- Bank details received by email or chat only: HIGH. Confirm by a call to a known number before any payment.

## Output
`extra.funding_map` and `extra.fx_exposure` in the `fin-acct-controller` verdict.
