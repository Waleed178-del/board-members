#!/usr/bin/env python3
"""
Depreciation schedule (IAS 16). Prints only, writes nothing.

  python3 depreciation.py --component "Extrusion press" --cost 2400000 --residual 120000 \
      --life-years 25 --method SL --available-for-use 2027-09 --currency USD [--years 5]

Methods: SL straight line, DDB double declining balance (switches to SL when SL is higher).
Depreciation starts in the month the asset is AVAILABLE FOR USE (after commissioning), not on payment or delivery.
Outputs yearly totals and the monthly journal line template for engine journal-add (entry_type DEPRECIATION).
"""
import argparse
import datetime as dt
import json
from decimal import ROUND_HALF_UP, Decimal


def q(x):
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--component", required=True)
    ap.add_argument("--cost", required=True)
    ap.add_argument("--residual", default="0")
    ap.add_argument("--life-years", type=int, required=True)
    ap.add_argument("--method", choices=["SL", "DDB"], default="SL")
    ap.add_argument("--available-for-use", required=True, help="YYYY-MM")
    ap.add_argument("--currency", default="USD")
    ap.add_argument("--years", type=int, default=0, help="years to print, 0 = whole life")
    a = ap.parse_args()
    cost, residual = Decimal(a.cost), Decimal(a.residual)
    if residual >= cost:
        raise SystemExit("residual must be below cost")
    y0, m0 = map(int, a.available_for_use.split("-"))
    months = a.life_years * 12
    nbv, rows, yearly = cost, [], {}
    for i in range(months):
        remaining = months - i
        sl = (nbv - residual) / remaining
        if a.method == "DDB":
            ddb = nbv * Decimal(2) / Decimal(months)
            dep = max(ddb, sl)
        else:
            dep = (cost - residual) / months
        dep = min(q(dep), nbv - residual)
        nbv -= dep
        y, m = y0 + (m0 - 1 + i) // 12, (m0 - 1 + i) % 12 + 1
        yearly[y] = yearly.get(y, Decimal(0)) + dep
        rows.append((f"{y}-{m:02d}", dep, nbv))
    years = sorted(yearly)[: a.years or None]
    print(json.dumps({
        "component": a.component, "method": a.method, "currency": a.currency,
        "cost": str(cost), "residual": str(residual), "life_years": a.life_years,
        "first_month": rows[0][0], "first_month_charge": str(rows[0][1]),
        "yearly": [{"year": y, "depreciation": str(q(yearly[y]))} for y in years],
        "nbv_end_of_printed_period": str(q(next(r[2] for r in reversed(rows) if int(r[0][:4]) <= years[-1]))),
        "journal_template": {
            "entry_type": "DEPRECIATION", "classification": "DEPRECIATION",
            "account_dr": "Depreciation expense", "account_cr": "Accumulated depreciation",
            "amount": str(rows[0][1]), "currency": a.currency, "gate": "OPS",
            "memo": f"Monthly depreciation {a.component} ({a.method})",
        },
        "note": "Componentize: press, hydraulics, ovens, handling, electrical each get their own useful life (IAS 16.43).",
    }, indent=2))


if __name__ == "__main__":
    main()
