"""Orchestrate the full bank build. For each blueprint subdomain, loop
generate -> verify -> push until the subdomain reaches its target count of
verified questions in Supabase (or runs out of usable chunks).

Usage:
    python run_all.py                 # build every subdomain to target
    python run_all.py --only Periodontics Emergencies
    python run_all.py --overshoot 1.1 # allow 10% above target
"""
import argparse
import math

from domain_map import BLUEPRINT
import db_local
import generate
import verify
import push

MAX_ROUNDS = 4          # top-up attempts per subdomain
BUFFER = 1.5            # generate deficit * BUFFER chunks (covers refusals/invalids)


def build_subdomain(subdomain, target, overshoot):
    cap = math.ceil(target * overshoot)
    for rnd in range(1, MAX_ROUNDS + 1):
        have = db_local.pushed_count(subdomain)
        if have >= target:
            break
        avail = db_local.available_chunk_count(subdomain)
        if avail == 0:
            print(f"  [{subdomain}] no more usable chunks (have {have}/{target})")
            break
        deficit = cap - have
        limit = min(avail, max(2, math.ceil(deficit * BUFFER)))
        print(f"  [{subdomain}] round {rnd}: have {have}/{target}, "
              f"generating {limit} (of {avail} available)")
        generate.generate_subdomain(subdomain, limit)
        verify.verify_pending(limit=5000)
        pushed = push.push_pushable(limit=5000, quiet=True)
        print(f"  [{subdomain}] round {rnd}: pushed {pushed} this round")
    final = db_local.pushed_count(subdomain)
    print(f"  [{subdomain}] DONE: {final}/{target}\n")
    return final


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="restrict to these subdomains")
    ap.add_argument("--overshoot", type=float, default=1.0,
                    help="cap = target * overshoot (default 1.0)")
    args = ap.parse_args()
    db_local.init_db()

    plan = [(d, s, t) for d, s, t in BLUEPRINT
            if not args.only or s in args.only]

    grand_have = grand_target = 0
    for dom, sub, tgt in plan:
        print(f"=== {dom} / {sub}  (target {tgt}) ===")
        have = build_subdomain(sub, tgt, args.overshoot)
        grand_have += have
        grand_target += tgt

    print("=" * 60)
    print(f"TOTAL verified & pushed: {grand_have}/{grand_target}")


if __name__ == "__main__":
    main()
