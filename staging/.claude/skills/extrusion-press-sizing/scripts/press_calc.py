#!/usr/bin/env python3
"""
Extrusion press sizing check. Prints only, writes nothing.

Example:
  python3 press_calc.py --force-usTon 1800 --container-mm 178 --billet-mm 7 inch? no: use --billet-dia-mm 170
        --billet-len-mm 650 --profile-area-mm2 450 --holes 2 --ram-mm-s 8 --dead-cycle-s 22
        --alloy 6063 --hours-per-year 5000 --recovery 0.85

Physics used (standard first order relations):
  specific pressure  p = F / (pi d^2 / 4)
  extrusion ratio    R = A_container / (A_profile * holes)
  exit speed         v_exit = v_ram * R
  billet mass        m = rho * pi (D/2)^2 * L, rho = 2.70 g/cm3
  cycle time         t = L_push / v_ram + dead cycle
  net output         = m * recovery / t
The alloy limits below are planning heuristics, not vendor guarantees. The vendor must confirm them in writing.
"""
import argparse
import json
import math

RHO = 2.70e-6  # kg per mm3
US_TON_TO_MN = 0.0088964
ALLOY = {  # min specific pressure MPa, typical max exit speed m/min (planning heuristics)
    "6060": (500, 80), "6063": (550, 70), "6005": (650, 40), "6061": (700, 30), "6082": (750, 25),
}


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--force-MN", type=float)
    g.add_argument("--force-usTon", type=float)
    ap.add_argument("--container-mm", type=float, required=True)
    ap.add_argument("--billet-dia-mm", type=float, required=True)
    ap.add_argument("--billet-len-mm", type=float, required=True)
    ap.add_argument("--butt-mm", type=float, default=20)
    ap.add_argument("--profile-area-mm2", type=float, required=True)
    ap.add_argument("--holes", type=int, default=1)
    ap.add_argument("--ram-mm-s", type=float, required=True)
    ap.add_argument("--dead-cycle-s", type=float, required=True)
    ap.add_argument("--alloy", choices=sorted(ALLOY), default="6063")
    ap.add_argument("--hours-per-year", type=float, default=5000)
    ap.add_argument("--recovery", type=float, default=0.85, help="net saleable / billet input")
    a = ap.parse_args()

    force_mn = a.force_MN if a.force_MN is not None else a.force_usTon * US_TON_TO_MN
    a_cont = math.pi * (a.container_mm / 2) ** 2
    p_spec = force_mn * 1e6 / a_cont  # N/mm2 = MPa
    ratio = a_cont / (a.profile_area_mm2 * a.holes)
    v_exit = a.ram_mm_s * ratio * 60 / 1000  # m/min
    billet_kg = RHO * math.pi * (a.billet_dia_mm / 2) ** 2 * a.billet_len_mm
    push_mm = a.billet_len_mm * (a.billet_dia_mm / a.container_mm) ** 2 - a.butt_mm  # upset then push
    cycle_s = max(push_mm, 0) / a.ram_mm_s + a.dead_cycle_s
    net_kg_h = billet_kg * a.recovery * 3600 / cycle_s
    annual_t = net_kg_h * a.hours_per_year / 1000
    p_min, v_max = ALLOY[a.alloy]

    flags = []
    if p_spec < p_min:
        flags.append({"severity": "CRITICAL", "code": "SPECIFIC_PRESSURE_LOW",
                      "detail": f"{p_spec:.0f} MPa < {p_min} MPa planning minimum for {a.alloy}"})
    if ratio < 10:
        flags.append({"severity": "HIGH", "code": "EXTRUSION_RATIO_LOW", "detail": f"R={ratio:.1f} < 10, poor grain structure"})
    if ratio > 100:
        flags.append({"severity": "HIGH", "code": "EXTRUSION_RATIO_HIGH", "detail": f"R={ratio:.1f} > 100, check pressure and die"})
    if v_exit > v_max:
        flags.append({"severity": "HIGH", "code": "EXIT_SPEED_HIGH",
                      "detail": f"{v_exit:.1f} m/min > {v_max} m/min typical for {a.alloy}. Output will not be reached"})
    if a.billet_dia_mm >= a.container_mm:
        flags.append({"severity": "CRITICAL", "code": "BILLET_TOO_LARGE", "detail": "billet diameter must be below container bore"})

    print(json.dumps({
        "inputs": vars(a),
        "force_MN": round(force_mn, 2),
        "specific_pressure_MPa": round(p_spec, 0),
        "extrusion_ratio": round(ratio, 1),
        "exit_speed_m_min": round(v_exit, 1),
        "billet_mass_kg": round(billet_kg, 1),
        "cycle_time_s": round(cycle_s, 1),
        "net_output_kg_h": round(net_kg_h, 0),
        "net_output_t_year": round(annual_t, 0),
        "flags": flags,
        "caveat": "First order planning numbers. Vendor must guarantee output in the contract (clause EQ-05).",
    }, indent=2))


if __name__ == "__main__":
    main()
