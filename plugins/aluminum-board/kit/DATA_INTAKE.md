# Data Intake | البيانات المطلوبة منكم

The system is built and enforcing. It cannot pass Gate G1 until you replace placeholder data. Send items in this
order. Priority 1 items block everything.

## Priority 1: blocks Gate G1 | أولوية 1

| # | What to send | Goes into | Who verifies |
|---|---|---|---|
| 1 | PLC, VFD, motor, hydraulic, relay, sensor brands your maintenance engineers can **buy and repair inside Syria today**, with supplier names | `state/syrian_market_constraints.json` → `electrical_brands` | Maintenance lead |
| 2 | Which payment rails work today: your bank name, correspondent banks that accept L/C confirmation, wire corridors, costs | `banking_and_payment_rails` | Finance director + bank letter |
| 3 | Port of entry, clearing agent, duty exemption status for production lines, free days, demurrage rates | `customs_and_ports` | Operations director |
| 4 | Site power: MV voltage, available MVA, grid hours per day, substation lead time, generator plan | `grid_and_power` | Electrical engineer |
| 5 | FX: rate source used for budgeting, obtainable rate, contract currency policy | `fx_and_currency` | Finance director |
| 6 | Market study numbers (demand, product mix, profile sizes, alloys, billet source) | `specs/market_study.md` | Sales lead |
| 7 | Press and line specification or vendor quotes received so far | `specs/rfp_spec_v1.md` | Technical director |
| 8 | CAPEX budget with quote sources and funding sources | `specs/capex_budget.md` (new) | Finance director |

## Priority 2: needed for Gate G2 | أولوية 2

- Vendor shortlist with country and bank of each vendor.
- Draft equipment contract or vendor's standard terms → `contracts/`.
- Board members: names, roles (`chair`, `finance_director`, `technical_director`, `operations_director`,
  `legal_advisor`, `hr_director`, `board_member`) for enrollment.

## Priority 3: needed for Gate G3 onward | أولوية 3

- Civil contractor shortlist and draft contract.
- Staffing plan: roles, veterans available, hiring channels.
- Freight forwarder quotes.

## How verification is recorded

1. Replace placeholder values with real ones.
2. Remove the `[[UNVERIFIED]]` line from the file (or set `"verified": true`, `"verified_by"`, `"verified_on"` in
   the constraints JSON).
3. Commit with a message naming who verified it. The constraints file expires after 90 days by design: banking and
   FX facts in Syria move faster than that.

Files under `state/` are protected from agents. A human edits them by launching Claude Code with
`BOARD_MAINTENANCE=1`, or edits them directly in a text editor.
