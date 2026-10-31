---
name: critical-path-scheduling
description: Build and check the dual track (civil vs equipment) critical path with CPM, find the merge point, float, demurrage and idle expert exposure. Use for G3 civil_and_logistics_plan, G4 installation_readiness, any schedule change, delay claim or expert travel window.
---

# Critical Path Scheduling | المسار الحرج

## Input file
`specs/schedule.csv` with columns `id,name,track,duration_days,depends_on` (`depends_on` is `;` separated).

Minimum task set (rename freely, keep the logic):

| id | track | depends_on |
|---|---|---|
| CONTRACT | B | |
| FDN_DWG | B | CONTRACT |
| CIVIL_AWARD | A | FDN_DWG |
| EXCAVATE | A | CIVIL_AWARD |
| POUR | A | EXCAVATE |
| CURE | A | POUR |
| HANGAR | A | CIVIL_AWARD |
| UTILITY_APP | A | CONTRACT |
| TRANSFORMER | A | CONTRACT |
| ENERGIZE | A | UTILITY_APP;TRANSFORMER;HANGAR |
| MANUFACTURE | B | CONTRACT |
| FAT | B | MANUFACTURE |
| SHIP | B | FAT |
| CUSTOMS | B | SHIP |
| HAUL | B | CUSTOMS |
| SITE_READY | A | CURE;HANGAR;ENERGIZE;HAUL |
| EXPERTS | B | SITE_READY |
| INSTALL | B | EXPERTS |
| SAT | B | INSTALL |

## Run
```bash
python3 .claude/skills/critical-path-scheduling/scripts/cpm.py specs/schedule.csv --start <YYYY-MM-DD> --merge-task SITE_READY
```

## Read the result
1. `critical_path`: every task with zero float. Name it in the packet.
2. `merge.driver`: the track that decides SITE_READY. If it is Track A, the cargo waits. Compute
   demurrage = (waits_days of HAUL − free days) × daily rate × containers.
3. Expert travel window = SITE_READY date at the earliest. Never before. The engine also blocks it until G4.
4. Utility energization (`ENERGIZE`) is usually the hidden driver in Syria. If the utility application date is
   missing, the plan is CRITICAL incomplete.
5. Recruitment: hires must finish induction 14 days before `EXPERTS` (hand this date to `hr-planner`).

## Output
Put `critical_path`, `merge` and the demurrage estimate into the `ops-logistics-coord` verdict `extra`.
