"""Tag every question with easy / medium / hard using a free heuristic. No API."""
import re
from config import supabase_admin

AGE_RE = re.compile(r"\d+.{0,3}(year|yr|y\.?o)", re.I)
HISTORY_RE = re.compile(r"presents?|complains?|history|weeks?|months?|days?", re.I)
FINDINGS_RE = re.compile(r"examination|probing|radiograph|swelling|reveals?|upon|findings?", re.I)
DRUG_RE = re.compile(r"warfarin|aspirin|bisphosphonate|methotrexate|interaction|contraindic", re.I)
CLINICAL_RE = re.compile(r"patient|presents?|complains?|history|pain|bleeding|swelling|fracture", re.I)


def classify(stem, options):
    s = (stem or "").strip()
    opts = options if isinstance(options, list) else []

    # HARD
    if len(s) > 180:
        return "hard"
    clinical_hits = sum([
        bool(AGE_RE.search(s)),
        bool(HISTORY_RE.search(s)),
        bool(FINDINGS_RE.search(s)),
    ])
    if clinical_hits >= 2:
        return "hard"
    if DRUG_RE.search(s):
        return "hard"

    # EASY
    if len(s) < 80 and "," not in s and not CLINICAL_RE.search(s):
        return "easy"
    if opts and all(len(o) < 15 for o in opts):
        return "easy"

    return "medium"


def main():
    sb = supabase_admin()
    offset, PAGE = 0, 500
    counts = {"easy": 0, "medium": 0, "hard": 0}
    examples = {"easy": [], "medium": [], "hard": []}
    total = 0

    while True:
        rows = sb.table("questions").select("id,stem,options").range(offset, offset + PAGE - 1).execute().data
        if not rows:
            break
        for row in rows:
            d = classify(row["stem"], row["options"])
            sb.table("questions").update({"difficulty": d}).eq("id", row["id"]).execute()
            counts[d] += 1
            total += 1
            if len(examples[d]) < 3:
                examples[d].append((row["stem"] or "")[:100])
        offset += PAGE
        print(f"  …{total} tagged")
        if len(rows) < PAGE:
            break

    print(f"\nDifficulty distribution ({total} total):")
    for d in ("easy", "medium", "hard"):
        pct = counts[d] / total * 100 if total else 0
        print(f"  {d:8}: {counts[d]:>5}  ({pct:.1f}%)")
        for ex in examples[d]:
            print(f"    • {ex}")


if __name__ == "__main__":
    main()
