---
name: capex-accounting-ifrs
description: Classify project spend under IAS 16 and the engine's journal classifications (PRE_OPERATING, ADVANCE_TO_SUPPLIER, GUARANTEE_MARGIN, CAPEX_CWIP, RETENTION_PAYABLE, CAPEX_FIXED_ASSET, DEPRECIATION, OPEX), build depreciation schedules and the CWIP to fixed asset reclassification. Use for any journal proposal, budget, payment or G6 capitalization.
---

# CAPEX Accounting (IFRS / IAS 16) | المحاسبة الرأسمالية

## Decision tree for every cost
1. Is it a payment before the asset exists (advance, deposit)? → `ADVANCE_TO_SUPPLIER` or `GUARANTEE_MARGIN`.
2. Is it directly attributable to bringing the line to working condition? (purchase price, import duties,
   non refundable taxes, freight, insurance in transit, site preparation, foundations, installation, expert fees,
   testing net of sample sale proceeds, professional fees) → `CAPEX_CWIP`.
3. Is it general, training, admin, or start up losses? → `PRE_OPERATING` before operations begin, `OPEX` after.
   Training is never capitalized (IAS 16.19).
4. Retention withheld on a certified invoice → Dr `CAPEX_CWIP` / Cr `RETENTION_PAYABLE`.
5. Commissioning complete and G6 passed → `RECLASS` CWIP to `CAPEX_FIXED_ASSET`, by component.
6. From the month available for use → monthly `DEPRECIATION`.

## Componentization (IAS 16.43)
Split the line into components with different lives. Planning lives, auditor confirms:
| Component | Life (years) |
|---|---|
| Building, hangar | 25 to 40 |
| Machine foundations | same as building or press |
| Extrusion press frame and container | 20 to 25 |
| Hydraulic power unit | 10 to 15 |
| Billet heater, die ovens, ageing oven | 10 to 15 |
| Handling (puller, tables, stretcher, saws) | 10 to 15 |
| Electrical, PLC, drives | 7 to 10 |
| Substation, transformers | 20 to 25 |
| Dies | expensed or 1 to 2 (policy decision) |

## Schedule
```bash
python3 .claude/skills/capex-accounting-ifrs/scripts/depreciation.py --component "<name>" --cost <x> \
  --residual <x> --life-years <n> --method SL --available-for-use <YYYY-MM> --currency USD
```

## FX
Record transaction currency, amount and the rate actually obtained (`--fx-rate-to-usd`). Never translate at a
rate you could not trade at. Note the official rate in the memo when it differs.

## Engine posting
Proposals only, in the `fin-acct-controller` verdict `extra.proposed_journal_entries`. The orchestrator posts with
`python3 engine/board.py journal-add ...`. A `PAYMENT` needs `--auth-seq` from an ALLOW on a payment action.

## Flag for the auditor
Syrian tax depreciation rates and the treatment of pre operating expenses may differ from IFRS. State the difference,
do not resolve it.
