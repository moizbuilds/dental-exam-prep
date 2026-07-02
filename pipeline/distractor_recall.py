"""Generate distractors for answer_only recall questions using claude-haiku-4-5.

Answer-only recalls have a stem and a ✅ answer but no wrong options. Haiku
generates 3 clinically-plausible distractors. The correct answer is inserted at
a RANDOM position (not always A). Token spend is minimised: tight prompt, no
rationales, no explanations.

Usage:
    python distractor_recall.py --dry-run          # count only
    python distractor_recall.py --limit 200        # first 200
    python distractor_recall.py                    # all
    python distractor_recall.py --images-only      # prioritise with figure
"""
import argparse
import json
import random
import re
from pathlib import Path

import fitz
from anthropic import Anthropic

from classify_recall import classify
from config import ANTHROPIC_API_KEY, supabase_admin
import db_local

ARCHIVE = Path("/Users/moizrana/Downloads/archive_extract")
DATA = Path(__file__).resolve().parent.parent / "data" / "recall_all.json"
BUCKET = "question-images"
HAIKU = "claude-haiku-4-5-20251001"

_alnum = re.compile(r"[^a-z0-9]+")
_STOP = set(
    "the a an of to in for and or with on at by is are was were be as that this what "
    "which who how when where why will would should can could may might you your patient "
    "case about after before following best most main does do has have not no".split()
)


def _norm(s: str) -> str:
    return _alnum.sub("", (s or "").lower())


def _clean_stem(s: str) -> str:
    s = s.replace("\u200b", "").replace("\u2060", "").replace("\ufeff", "")
    s = s.replace("\u2705", "").replace("\U0001F501", "").replace("\ufe0f", "")
    return s.strip(" .\t-\u25a0\u25cf")


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
    return (m.group(1) if m else p)[:limit].strip()


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:24]


SYSTEM = (
    "You are a dental qualifying-exam question writer. "
    "Given a question stem and the CORRECT answer, produce exactly 3 WRONG but "
    "plausible distractors that a dental student might confuse with the correct answer. "
    "Each distractor must be in the same grammatical form as the correct answer "
    "(e.g., if the answer is a procedure name, all distractors are procedure names). "
    "Return ONLY a JSON array of 3 strings. No explanations, no extra text."
)


def generate_distractors(client, stem, answer):
    msg = client.messages.create(
        model=HAIKU,
        max_tokens=200,
        system=SYSTEM,
        messages=[{
            "role": "user",
            "content": f"STEM: {stem}\nCORRECT ANSWER: {answer}\n3 distractors:"
        }],
    )
    txt = msg.content[0].text.strip()
    m = re.search(r"\[.*?\]", txt, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
        return [str(x).strip() for x in d if str(x).strip()] if len(d) == 3 else None
    except json.JSONDecodeError:
        return None


def citation(q):
    terms = _terms(f"{q['answer_text']} {q['answer_text']} {q['stem']}")
    hits = db_local.fts_search(terms, k=1)
    if not hits:
        return {}
    p = hits[0]
    return {
        "source_book": p["book"],
        "source_edition": p.get("edition"),
        "source_page_or_section": f"p.{p['page_start']}" if p.get("page_start") else p.get("section_title"),
        "source_passage": p["text"],
        "supporting_quote": _first_sentence(p["text"]),
    }


def upload_figure(doc, xref, key):
    pix = fitz.Pixmap(doc, xref)
    if pix.n - pix.alpha >= 4:
        pix = fitz.Pixmap(fitz.csRGB, pix)
    sb = supabase_admin()
    sb.storage.from_(BUCKET).upload(
        key, pix.tobytes("png"), {"content-type": "image/png", "upsert": "true"}
    )
    return sb.storage.from_(BUCKET).get_public_url(key)


def dedupe(questions):
    by_stem = {}
    for q in questions:
        k = _norm(q["stem"])[:120]
        if len(k) < 15 or not q.get("answer_text"):
            continue
        cur = by_stem.get(k)
        if cur is None or (q["image_xrefs"] and not cur.get("image_xrefs")):
            by_stem[k] = q
    return list(by_stem.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--images-only", action="store_true")
    args = ap.parse_args()

    db_local.init_db()
    db_local.ensure_fts()

    all_q = json.loads(DATA.read_text())
    pool = [q for q in all_q
            if q["kind"] == "answer_only"
            and q.get("answer_text")
            and len(_clean_stem(q.get("stem", ""))) > 20]
    if args.images_only:
        pool = [q for q in pool if q["image_xrefs"]]
    uniq = dedupe(pool)
    # images first
    uniq.sort(key=lambda q: -len(q["image_xrefs"]))
    if args.limit:
        uniq = uniq[: args.limit]
    n_img = sum(1 for q in uniq if q["image_xrefs"])
    print(f"answer_only: {len(pool)} usable -> {len(uniq)} unique ({n_img} with figures)")
    if args.dry_run:
        return

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    sb = supabase_admin()
    docs = {}
    pushed = with_img = failed = skipped = 0

    for q in uniq:
        stem = _clean_stem(q["stem"])
        answer = q["answer_text"].strip()
        distractors = generate_distractors(client, stem, answer)
        if not distractors:
            skipped += 1
            continue

        # place correct answer at a RANDOM position
        ci = random.randint(0, 3)
        options = distractors.copy()
        options.insert(ci, answer)

        domain, subdomain, _ = classify(stem, options)
        row = {
            "domain": domain, "subdomain": subdomain,
            "stem": stem, "options": options,
            "correct_index": ci, "correct_explanation": "",
            "distractor_rationales": [], "verification_status": "pass",
            "visual_type": "none", "source_origin": "recall",
        }
        row.update(citation(q))

        if q["image_xrefs"]:
            src = q["source_file"]
            if src not in docs:
                docs[src] = fitz.open(ARCHIVE / src)
            key = f"recall_ao/{_slug(src)}/q{q['num']}.png"
            try:
                row["image_url"] = upload_figure(docs[src], q["image_xrefs"][0], key)
                row["visual_type"] = "image"
                with_img += 1
            except Exception as e:
                pass  # continue without image

        try:
            sb.table("questions").insert(row).execute()
            pushed += 1
            if pushed % 100 == 0:
                print(f"  …{pushed} pushed ({skipped} skipped, {with_img} with images)")
        except Exception as e:
            failed += 1
            if failed <= 5:
                print(f"  Q{q['num']}: {str(e)[:100]}")

    for d in docs.values():
        d.close()
    print(f"\nPushed {pushed} distractor questions ({with_img} with images), "
          f"{skipped} skipped (bad JSON), {failed} DB errors.")


if __name__ == "__main__":
    main()
