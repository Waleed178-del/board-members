#!/usr/bin/env python3
"""
Critical Path Method on a CSV task list. Prints only, writes nothing.

CSV columns: id,name,track,duration_days,depends_on
  depends_on: semicolon separated ids, empty for none. track: A (civil) or B (equipment).

  python3 cpm.py schedule.csv --start 2026-12-01 [--merge-task SITE_READY]

Output: ES/EF/LS/LF/float per task, the critical path, project finish, and for --merge-task the
earliest date and which track drives it (the dual track merge point).
"""
import argparse
import csv
import datetime as dt
import json
import sys


def load(path):
    tasks = {}
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            tid = r["id"].strip()
            if tid in tasks:
                sys.exit(f"duplicate id {tid}")
            tasks[tid] = {
                "name": r.get("name", "").strip(), "track": r.get("track", "").strip(),
                "dur": int(float(r["duration_days"])),
                "deps": [d.strip() for d in (r.get("depends_on") or "").split(";") if d.strip()],
            }
    for tid, t in tasks.items():
        for d in t["deps"]:
            if d not in tasks:
                sys.exit(f"task {tid} depends on unknown {d}")
    return tasks


def topo(tasks):
    order, state = [], {}

    def visit(n, stack):
        if state.get(n) == 1:
            sys.exit("dependency cycle: " + " -> ".join(stack + [n]))
        if state.get(n) == 2:
            return
        state[n] = 1
        for d in tasks[n]["deps"]:
            visit(d, stack + [n])
        state[n] = 2
        order.append(n)

    for n in tasks:
        visit(n, [])
    return order


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--start", default=dt.date.today().isoformat())
    ap.add_argument("--merge-task")
    a = ap.parse_args()
    start = dt.date.fromisoformat(a.start)
    t = load(a.csv)
    order = topo(t)
    for n in order:
        t[n]["es"] = max((t[d]["ef"] for d in t[n]["deps"]), default=0)
        t[n]["ef"] = t[n]["es"] + t[n]["dur"]
    finish = max(x["ef"] for x in t.values())
    succ = {n: [m for m in t if n in t[m]["deps"]] for n in t}
    for n in reversed(order):
        t[n]["lf"] = min((t[s]["ls"] for s in succ[n]), default=finish)
        t[n]["ls"] = t[n]["lf"] - t[n]["dur"]
        t[n]["float"] = t[n]["ls"] - t[n]["es"]
    day = lambda k: (start + dt.timedelta(days=k)).isoformat()  # noqa: E731
    critical = [n for n in order if t[n]["float"] == 0]
    out = {
        "start": a.start, "finish": day(finish), "duration_days": finish,
        "critical_path": critical,
        "tasks": [{"id": n, "name": t[n]["name"], "track": t[n]["track"], "duration": t[n]["dur"],
                   "start": day(t[n]["es"]), "finish": day(t[n]["ef"]),
                   "late_finish": day(t[n]["lf"]), "float_days": t[n]["float"]} for n in order],
    }
    if a.merge_task:
        m = t[a.merge_task]
        drivers = sorted(m["deps"], key=lambda d: -t[d]["ef"])
        out["merge"] = {
            "task": a.merge_task, "earliest": day(m["es"]),
            "driver": drivers[0] if drivers else None,
            "inputs": [{"id": d, "track": t[d]["track"], "ready": day(t[d]["ef"]),
                        "waits_days": m["es"] - t[d]["ef"]} for d in drivers],
        }
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
