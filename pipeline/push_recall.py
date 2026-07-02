"""Push recall MCQs (PRIMARY source) into Supabase — FREE, no API calls.

Pipeline (all free):
  recall_all.json (mcq4 only)
    -> dedupe by normalized stem (prefer the copy that has a figure)
    -> classify into a blueprint subdomain (keyword)
    -> attach a textbook citation via BM25 (the "back it up with the textbooks"
       step; topically-related reading, not an LLM-verified proof)
    -> extract the embedded figure and upload to Supabase Storage
    -> insert the question row (source_origin='recall', verification_status='pass')

Only mcq4 (stem + 4 options + a ✅-marked answer) are pushed, because they need
no LLM to be complete. answer_only / image_only recalls (which would need
generated distractors) are intentionally skipped here.

Usage:
    python push_recall.py --dry-run
    python push_recall.py --limit 50
    python push_recall.py            # push all unique mcq4
"""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

import fitz

from classify_recall import classify
from config import supabase_admin
import db_local

ARCHIVE = Path("/Users/moizrana/Downloads/archive_extract")
DATA = Path(__file__).resolve().parent.parent / "data" / "recall_all.json"
BUCKET = "question-images"

_alnum = re.compile(r"[^a-z0-9]+")
_STOP = set(
    "the a an of to in for and or with on at by is are was were be as that this what "
    "which who how when where why will would should can could may might you your patient "
    "case about after before following best most main does do has have not no".split()
)


def _norm(s: str) -> str:
    return _alnum.sub("", (s or "").lower())


def _terms(text: str):
    words = re.findall(r"[A-Za-z][A-Za-z\-]{3,}", (text or "").lower())
    seen, out = set(), []
    for w in words:
        if w in _STOP or w in seen:
            continue
        seen.add(w)
        out.append(w)
    return out


def _first_sentence(passage: str, limit=320) -> str:
    p = passage.strip().replace("\n", " ")
    m = re.search(r"(.+?[.!?])\s", p)
    s = m.group(1) if m else p
    return s[:limit].strip()


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:24]


def dedupe(questions):
    """Keep one row per normalized stem, preferring the copy that has a figure."""
    by_stem = {}
    for q in questions:
        k = _norm(q["stem"])[:120]
        if len(k) < 15:
            continue
        if q["correct_index"] is None or not (4 <= len(q["options"]) <= 6):
            continue
        if q["correct_index"] >= len(q["options"]):
            continue
        cur = by_stem.get(k)
        if cur is None or (q["image_xrefs"] and not cur["image_xrefs"]):
            by_stem[k] = q
    return list(by_stem.values())


def citation(q):
    """Free textbook citation via BM25. Returns dict of source_* fields or {}."""
    terms = _terms(f"{q['answer_text']} {q['answer_text']} {q['stem']}")
    hits = db_local.fts_search(terms, k=1)
    if not hits:
        return {}
    p = hits[0]
    return {
        "source_book": p["book"],
        "source_edition": p.get("edition"),
        "source_page_or_section": (
            f"p.{p['page_start']}" if p.get("page_start") else p.get("section_title")
        ),
        "source_passage": p["text"],
        "supporting_quote": _first_sentence(p["text"]),
    }


def upload_figure(doc, xref, key):
    pix = fitz.Pixmap(doc, xref)
    if pix.n - pix.alpha >= 4:
        pix = fitz.Pixmap(fitz.csRGB, pix)
    data = pix.tobytes("png")
    sb = supabase_admin()
    sb.storage.from_(BUCKET).upload(
        key, data, {"content-type": "image/png", "upsert": "true"}
    )
    return sb.storage.from_(BUCKET).get_public_url(key)


def _clean_stem(s: str) -> str:
    s = s.replace("\u200b", "").replace("\u2060", "").replace("\ufeff", "")
    return s.strip(" \t.-\u2060")


def build_row(q):
    domain, subdomain, _ = classify(q["stem"], q["options"])
    row = {
        "domain": domain,
        "subdomain": subdomain,
        "stem": _clean_stem(q["stem"]),
        "options": q["options"],
        "correct_index": q["correct_index"],
        "correct_explanation": "",
        "distractor_rationales": [],
        "verification_status": "pass",
        "visual_type": "none",
        "source_origin": "recall",
    }
    row.update(citation(q))
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="0 = all")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_local.init_db()
    db_local.ensure_fts()

    all_q = json.loads(DATA.read_text())
    mcq4 = [q for q in all_q if q["kind"] == "mcq4"]
    uniq = dedupe(mcq4)
    if args.limit:
        uniq = uniq[: args.limit]
    n_fig = sum(1 for q in uniq if q["image_xrefs"])
    print(f"mcq4: {len(mcq4)} raw -> {len(uniq)} unique ({n_fig} with figures)")

    if args.dry_run:
        from collections import Counter
        subs = Counter(classify(q["stem"], q["options"])[1] for q in uniq)
        for s, n in subs.most_common():
            print(f"  {n:>4}  {s}")
        return

    sb = supabase_admin()
    docs = {}  # source_file -> open fitz doc (reused across questions)
    pushed = with_img = failed = 0
    for q in uniq:
        try:
            row = build_row(q)
            if q["image_xrefs"]:
                src = q["source_file"]
                if src not in docs:
                    docs[src] = fitz.open(ARCHIVE / src)
                key = f"recall/{_slug(src)}/q{q['num']}.png"
                row["image_url"] = upload_figure(docs[src], q["image_xrefs"][0], key)
                row["visual_type"] = "image"
                with_img += 1
            sb.table("questions").insert(row).execute()
            pushed += 1
            if pushed % 50 == 0:
                print(f"  …{pushed} pushed")
        except Exception as e:
            failed += 1
            print(f"  Q{q['num']} ({q['source_file'][:18]}): {str(e)[:120]}")
    for d in docs.values():
        d.close()
    print(f"\nPushed {pushed} recall questions ({with_img} with images), {failed} failed.")


if __name__ == "__main__":
    main()
