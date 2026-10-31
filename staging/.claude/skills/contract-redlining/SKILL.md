---
name: contract-redlining
description: Audit a contract against contracts/clause_library.md and produce a clause matrix, risk score and counterparty ready redlines in English. Use for G2 equipment_contract, G3 civil_contract, freight and clearing contracts, amendments, and claim notices.
---

# Contract Redlining | مراجعة العقود وصياغة التعديلات

## Procedure
1. Read `contracts/clause_library.md`. Pick section A (equipment), B (civil) or C (freight and clearing).
2. For every clause ID, search the contract (Grep for the topic words, not just the heading) and record:
   `PRESENT` (meets minimum), `WEAK` (present, below minimum), `MISSING`. Quote the found text and give the ref.
3. Check precedence: body vs annexes vs vendor offer. Contradictions are CRITICAL until a precedence clause fixes them.
4. Check numbers against the locked spec and budget: price, milestones, LD rates and caps, guarantee %, dates.
5. Score risk: CRITICAL 25, HIGH 10, MEDIUM 3, LOW 1, cap 100.

## Redline format (for the counterparty, English)
```
[EQ-03] Foundation drawings
Current: "Seller shall provide foundation drawings in due course."
Proposed: "Seller shall deliver certified foundation drawings and static and dynamic load data within six (6)
weeks of the Effective Date. For each week of delay Seller shall pay liquidated damages of 0.5% of the Contract
Price, capped at 5%, without prejudice to Buyer's right to extend the Delivery Date day for day."
Why: drawings gate the civil works. Each week of delay moves commissioning by a week.
```
Order redlines CRITICAL first. Keep each one self contained.

## Claim notice (shipment discrepancy)
1. Find the notice clause (EQ-24) and compute the deadline from the receipt date in the reconciliation report.
2. Draft: parties, contract reference, shipment and B/L number, item codes and quantities short or damaged,
   evidence attached (reconciliation report, photos, survey), remedy requested (replacement by date, credit note),
   reservation of rights including LD.
3. The draft is a `kind=instruction` outbound document. It needs an engine authorization before it is drafted in
   Outlook (see board-comms-drafting).

## Limits
This is a structured first review. Licensed counsel in the governing law jurisdiction signs off the final text.
