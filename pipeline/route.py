"""Keyword-routing for blueprint subdomains that have no dedicated assigned book
(Evidence-based Practice, Communication, Professionalism, Teamworking/Leadership).

These topics live inside two broad donor books — the Oxford Handbook of Clinical
Dentistry and Dental Ethics & Laws. We re-tag the donor chunks that strongly match
a target subdomain so generation can pull from the right material. A chunk is
moved to the best-matching target only when it clears a keyword threshold; the
rest stay where they are (Health and Safety / Ethical and Legal).

Idempotent: routing is evaluated from the donor source files each run.

Usage:
    python route.py            # apply routing
    python route.py --dry-run  # show what would move, change nothing
"""
import argparse
import re

import db_local
from domain_map import map_filename

# Donor books (matched against source_file). Their non-routed chunks currently
# carry these "home" subdomains:
DONOR_FILES = [
    "Oxford handbook of clinical dentistry",
    "Dental Ethics And Laws",
    "Dentistry at a Glance",                 # has EBD / communication overview pages
    "Odells Clinical Problem Solving",       # diagnostic reasoning, history-taking
    "Diagnosis and Treatment Planning",      # consent, communication, planning
]

# target subdomain -> (domain, [keyword regexes])
ROUTES = {
    "Evidence-based Practice": ("Scientific Knowledge", [
        r"evidence[- ]based", r"systematic review", r"meta[- ]analys",
        r"randomi[sz]ed controlled", r"\brct\b", r"clinical audit", r"\baudit\b",
        r"critical appraisal", r"\bpico\b", r"cohort study", r"case[- ]control",
        r"confidence interval", r"\bp[ -]?value", r"sensitivity and specificity",
        r"number needed to treat", r"clinical guideline", r"research methodolog",
        r"statistical significance", r"odds ratio", r"relative risk",
    ]),
    "Communication": ("Affective Skills", [
        r"communicat", r"\brapport\b", r"informed consent", r"breaking bad news",
        r"\bempath", r"active listening", r"patient[- ]centred", r"patient[- ]centered",
        r"shared decision", r"consultation skill", r"history[- ]taking",
        r"explain(?:ing)? to the patient", r"verbal and non[- ]verbal",
        r"anxious patient", r"reassur", r"motivational interview",
    ]),
    "Professionalism": ("Affective Skills", [
        r"professionalism", r"\bgdc\b", r"general dental council", r"fitness to practise",
        r"duty of candour", r"\bconfidentialit", r"professional conduct",
        r"professional standard", r"continuing professional development", r"\bcpd\b",
        r"revalidation", r"raising concern", r"professional boundar", r"\bprobity\b",
        r"complaints handling", r"\bnegligence\b", r"duty of care",
    ]),
    "Teamworking and Leadership": ("Affective Skills", [
        r"\bteamwork", r"dental team", r"team member", r"\bleadership\b", r"\bdelegat",
        r"skill[- ]mix", r"multidisciplinar", r"referral pathway", r"working together",
        r"clinical governance", r"staff management", r"team working",
        r"inter[- ]?professional", r"dental nurse", r"dental hygienist role",
    ]),
}

COMPILED = {
    sub: (dom, [re.compile(k, re.IGNORECASE) for k in kws])
    for sub, (dom, kws) in ROUTES.items()
}
# Minimum distinct keyword hits to re-tag a chunk. Two hits keeps precision high
# so we don't pull clinically-incidental chunks (a passage that merely mentions
# "dental team" once is not a teamworking question). Routed pools are then ordered
# by route_score at generation time, so the most on-topic chunks generate first.
THRESHOLD = 2


def score(text, patterns):
    return sum(1 for p in patterns if p.search(text))


def best_route(text):
    """Return (domain, subdomain, score) for the best-matching target, or None."""
    best, best_score = None, 0
    for sub, (dom, patterns) in COMPILED.items():
        s = score(text, patterns)
        if s > best_score:
            best, best_score = (dom, sub), s
    if best and best_score >= THRESHOLD:
        return best[0], best[1], best_score
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    db_local.init_db()

    like = " or ".join(["source_file like ?"] * len(DONOR_FILES))
    params = [f"%{f}%" for f in DONOR_FILES]

    moves = {}
    with db_local.connect() as conn:
        rows = conn.execute(
            f"select id, source_file, text from chunks where ({like})", params
        ).fetchall()

        resets, updates = [], []
        for r in rows:
            # always start from the book's home subdomain (idempotent re-routing)
            home = map_filename(r["source_file"])
            if home:
                home_dom, home_sub, _ = home
                resets.append((home_dom, home_sub, r["id"]))
            route = best_route(r["text"])
            if route:
                dom, sub, sc = route
                updates.append((dom, sub, sc, r["id"]))
                moves[sub] = moves.get(sub, 0) + 1

        if not args.dry_run:
            # reset donor chunks to home + clear any prior route_score, then re-tag
            conn.executemany(
                "update chunks set domain=?, subdomain=?, route_score=0 where id=?",
                resets,
            )
            conn.executemany(
                "update chunks set domain=?, subdomain=?, route_score=? where id=?",
                updates,
            )

    verb = "Would route" if args.dry_run else "Routed"
    for sub in ROUTES:
        print(f"  {verb} {moves.get(sub, 0):>4} chunks -> {sub}")


if __name__ == "__main__":
    main()
