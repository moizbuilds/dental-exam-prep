"""Push verified (PASS) drafts into Supabase. Uses the service-role key, so it
bypasses RLS. The DB still enforces the grounding constraints, so any draft
missing a source_book/source_passage/supporting_quote is rejected at insert.

Usage:
    python push.py --limit 500
    python push.py --dry-run
"""
import argparse
import json

from config import supabase_admin
import db_local


def to_row(d):
    return {
        "domain": d["domain"],
        "subdomain": d["subdomain"],
        "stem": d["stem"],
        "options": json.loads(d["options"]),
        "correct_index": d["correct_index"],
        "correct_explanation": d["correct_explanation"],
        "distractor_rationales": json.loads(d["distractor_rationales"]),
        "source_book": d["source_book"],
        "source_edition": d["source_edition"],
        "source_page_or_section": d["source_page_or_section"],
        "source_passage": d["source_passage"],
        # prefer the independent verifier's quote as the proof sentence
        "supporting_quote": d["verifier_quote"] or d["supporting_quote"],
        "verification_status": "pass",
        "visual_type": d["visual_type"],
        "diagram_svg": d["diagram_svg"],
    }


def push_pushable(limit=1000, quiet=False):
    """Insert all PASS-and-not-yet-pushed drafts into Supabase. Returns count."""
    drafts = db_local.fetch_pushable(limit=limit)
    if not drafts:
        return 0
    sb = supabase_admin()
    pushed = 0
    for d in drafts:
        try:
            sb.table("questions").insert(to_row(d)).execute()
            db_local.mark_pushed(d["id"])
            pushed += 1
        except Exception as e:
            if not quiet:
                print(f"  draft {d['id']}: insert failed: {e}")
    return pushed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_local.init_db()
    drafts = db_local.fetch_pushable(limit=args.limit)
    if not drafts:
        print("Nothing to push (no PASS drafts pending).")
        return

    if args.dry_run:
        print(f"Would push {len(drafts)} verified questions.")
        return

    pushed = push_pushable(limit=args.limit)
    print(f"Pushed {pushed}/{len(drafts)} verified questions to Supabase.")


if __name__ == "__main__":
    main()
