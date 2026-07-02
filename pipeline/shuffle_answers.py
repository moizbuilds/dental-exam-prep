"""Redistribute correct answers uniformly across A/B/C/D in existing questions.

The recall PDFs list the ✅ answer first, so correct_index==0 (A) is heavily
overrepresented (~41%). This script fetches every question, shuffles its options
array with a random permutation, updates the correct_index to match, and writes
the rows back to Supabase.

Safe to re-run — idempotent on the options content, just changes order each time.
After running once, the distribution should be ~25% per position.
"""
import json
import random

from config import supabase_admin

BATCH = 50  # rows per upsert


def shuffle_question(row):
    opts = row["options"] if isinstance(row["options"], list) else json.loads(row["options"])
    ci = row["correct_index"]
    correct_text = opts[ci]
    perm = list(range(len(opts)))
    random.shuffle(perm)
    new_opts = [opts[i] for i in perm]
    new_ci = new_opts.index(correct_text)
    return {"id": row["id"], "options": new_opts, "correct_index": new_ci}


def main():
    sb = supabase_admin()
    # fetch all questions
    rows = sb.table("questions").select("id,options,correct_index").execute().data
    print(f"Fetched {len(rows)} questions")

    updates = [shuffle_question(r) for r in rows]

    for i, u in enumerate(updates):
        sb.table("questions").update(
            {"options": u["options"], "correct_index": u["correct_index"]}
        ).eq("id", u["id"]).execute()
        if (i + 1) % 200 == 0 or i + 1 == len(updates):
            print(f"  …{i + 1} updated")

    # verify distribution
    counts = {}
    for u in updates:
        counts[u["correct_index"]] = counts.get(u["correct_index"], 0) + 1
    print("\nNew correct_index distribution:")
    for k in sorted(counts):
        pct = counts[k] / len(updates) * 100
        print(f"  {k} ({chr(65+k)}): {counts[k]:>4}  {pct:.1f}%")


if __name__ == "__main__":
    main()
