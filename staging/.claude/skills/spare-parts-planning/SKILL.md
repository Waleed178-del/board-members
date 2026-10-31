---
name: spare-parts-planning
description: Build and check the 24 month commissioning and operating spare parts BOM against Syrian serviceability, and verify the spare parts handover. Use for G1 rfp_spec, G2 contract_technical_annex, G5 spare_parts_handover.
---

# Spare Parts Planning | تخطيط قطع الغيار

## Classify every electrical, hydraulic and wear component
| Class | Definition | Rule |
|---|---|---|
| S (serviceable) | Brand in `electrical_brands` with local_stock YES and local_repair YES, constraints VERIFIED | Normal stock |
| C (critical import) | Not locally serviceable, failure stops the press | 24 month qty in contract + 1 complete spare for single points of failure |
| W (wear) | Consumed by operation | 24 month consumption qty |
| D (dies and tooling) | Die steel, bolsters, backers, containers liners | Separate die budget, not spares |

## Minimum quantities (planning defaults, refine with vendor MTBF data)
- Single point of failure electronics (PLC CPU, main VFD, safety relay, HMI): 1 complete spare each.
- Proportional valves and servo valves on the main press: 1 per type in use.
- Main pump: 1 rebuild kit, and 1 complete pump if local rebuild is not VERIFIED.
- Seals for main cylinder, side cylinders, container: 2 sets.
- Thermocouples, proximity sensors, encoders: 20% of installed qty, minimum 2 per type.
- Contactors, relays, fuses, breakers: 10% of installed qty, minimum 2 per rating.
- Saw blades, puller grips, belt and felt for tables: 24 months consumption.

## BOM line format
`component | brand | part_no | installed_qty | class | qty_24m | unit_price | currency | lead_time_weeks | reason`

## Handover check (G5)
Line by line diff of delivered vs contract BOM, physical count signed by the warehouse. Missing class C item = CRITICAL.
Part numbers must match exactly. A "compatible" substitute needs a written equivalence from the vendor.

## Output
`extra.spare_parts_bom` and `extra.unserviceable_components` in the `tech-spec-auditor` verdict.
