---
description: Reconcile packing list vs commercial invoice vs physical receipt for a shipment. Discrepancies freeze milestone payments and trigger a legal claim notice.
argument-hint: <shipment_id>
allowed-tools: Read, Grep, Glob, Write, Task, Bash(python3 engine/board.py:*)
---

Shipment: $ARGUMENTS

1. Expect three CSV files with columns `item_code,description,qty,critical` (critical = Y for parts the line
   cannot run without):
   - `specs/shipments/<id>_packing.csv`
   - `specs/shipments/<id>_invoice.csv`
   - `specs/shipments/<id>_received.csv` (physical count by the warehouse)
   If any is missing, list what is missing and stop.
2. Run
   `python3 engine/board.py reconcile --shipment <id> --packing specs/shipments/<id>_packing.csv --invoice specs/shipments/<id>_invoice.csv --received specs/shipments/<id>_received.csv`
   If the engine says the shipment is not registered, give the human the `register-shipment` command and stop.
3. If discrepancies exist, spawn in parallel:
   - `legal-counsel` (gate OPS, subject `claim:<id>`) with the reconciliation report and the equipment contract:
     claim notice deadline, the clause that applies, and a draft claim notice in English.
   - `ops-logistics-coord` (gate OPS, subject `shipment:<id>`): effect on the G4 merge date and demurrage.
   These verdicts are advisory (OPS subjects outside the payment pattern do not open gates). Record them anyway
   for the audit trail.
4. Reply with: critical receipt %, each discrepancy, the claim deadline date, the payment freeze status, and the
   human command to close each discrepancy once settled:
   `python3 engine/board.py resolve-discrepancy <id:item> --member <id> --evidence <credit note or receipt>`
