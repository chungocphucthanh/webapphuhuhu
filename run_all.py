#!/usr/bin/env python3
"""
run_all.py  -  THE single entry point for the CO2011 SEM261 assignment.

Grading runs exactly:  python run_all.py --seed $(cat data/seed.txt)
It must reproduce EVERY number in your report from a clean clone, with no manual steps.
Fill in each stage to call your module code; keep the CLI and the stage order stable.

This skeleton ships in the course template repository ("Use this template", not a fork).
"""
import argparse

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True, help="from data/seed.txt")
    ap.add_argument("--stage", default="all",
                    choices=["all", "m1", "m2", "m3", "m4", "m5"])
    a = ap.parse_args()

    if a.stage in ("all", "m1"):
        from m1_logic.sat_check import main as run_m1

        run_m1(a.seed)
    if a.stage in ("all", "m2"):
        from m2_ilp.run import run_m2

        run_m2(a.seed)
    if a.stage in ("all", "m3"):
        from m3_automata.run import run_m3

        run_m3(a.seed)
    if a.stage in ("all", "m4"):
        from m4_dynamics.run import run_m4

        run_m4(a.seed)
    if a.stage in ("all", "m5"):
        from app.precompute import run_m5

        run_m5(a.seed)

if __name__ == "__main__":
    main()
