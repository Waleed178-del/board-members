---
name: extrusion-press-sizing
description: Size and sanity check an aluminum extrusion press and line against the market study. Use when reviewing an RFP, a vendor quote, a technical annex or acceptance test results for the press, container, billet, puller, cooling table, stretcher, saws and ageing oven.
---

# Extrusion Press Sizing | تحجيم مكبس البثق

## When to use
Gate G1 `rfp_spec`, G2 `contract_technical_annex`, G6 `acceptance_test_results`, and any vendor quote comparison.

## Procedure
1. Pull the product mix from `specs/market_study.md`: largest circumscribing circle diameter (CCD), thinnest wall,
   alloys, kg/m of the top 20 profiles, target t/year.
2. For the heaviest and the hardest profile, run the calculator (orchestrator runs it, agents read the output):
   ```bash
   python3 .claude/skills/extrusion-press-sizing/scripts/press_calc.py --force-usTon <t> --container-mm <d> \
     --billet-dia-mm <D> --billet-len-mm <L> --profile-area-mm2 <A> --holes <n> --ram-mm-s <v> \
     --dead-cycle-s <s> --alloy <6063|6061|6082...> --hours-per-year <h> --recovery <r>
   ```
3. Check the line is balanced. Each station must handle the press peak, not the average:
   | Station | Must match |
   |---|---|
   | Billet heater | t/h ≥ press peak billet consumption |
   | Container / CCD | largest profile CCD ≤ about 0.8 × container bore (vendor confirms) |
   | Puller | pulling force and speed ≥ exit speed of the fastest alloy |
   | Cooling table | length ≥ max extrusion length + handling margin |
   | Stretcher | capacity (t) ≥ largest section × alloy yield × 1.2 |
   | Ageing oven | t per batch × batches/day ≥ daily press output |
   A downstream station below press output caps the whole line. Severity CRITICAL.
4. Cross check `net_output_t_year` against the market target:
   - below target by more than 10%: HIGH (`UNDERSIZED_FOR_MARKET`)
   - above target by more than 40% with no expansion plan: MEDIUM (`OVERSIZED_CAPITAL`)
5. Every number used must trace to a file and line. Assumed values go in the verdict as `UNVERIFIED_INPUTS`.

## Rules of thumb (planning only, vendor must guarantee)
- Specific pressure: soft alloys 6060/6063 about 550 MPa and up, hard 6061/6082 about 700 MPa and up.
- Extrusion ratio 10 to 100 is the normal window.
- Exit speed, not tonnage, limits most 6063 lines. Hard alloys are limited by pressure and temperature.
- 1 US ton force = 8.896 kN. 1 MN ≈ 112.4 US ton.

## Output
Put the calculator JSON in the verdict `extra.sizing_check`, and every flag becomes a finding with the same code.
