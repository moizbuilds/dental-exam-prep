"""Generation: for a blueprint subdomain, retrieve local chunks and generate one
grounded single-best-answer MCQ per chunk. Refusal (null) is a valid, correct
outcome when a passage can't support a defensible question.

Usage:
    python generate.py --subdomain Emergencies --limit 20
"""
import argparse
import json
import re

from tenacity import retry, stop_after_attempt, wait_exponential

from config import anthropic_client, GEN_MODEL
from prompts import GENERATION_SYSTEM, GENERATION_FORMAT
import db_local

_alnum = re.compile(r"[^a-z0-9]+")


def _norm(s: str) -> str:
    """Reduce to lowercase alphanumerics so PDF artifacts (line-break hyphens like
    'manage- ment', ligatures, stray spaces/punctuation) don't break the verbatim
    containment check."""
    return _alnum.sub("", (s or "").lower())


@retry(stop=stop_after_attempt(4), wait=wait_exponential(min=2, max=30))
def _call(client, system, passage):
    msg = client.messages.create(
        model=GEN_MODEL,
        max_tokens=1500,
        system=system,
        messages=[{"role": "user", "content": f"PASSAGE:\n{passage}\n\n{GENERATION_FORMAT}"}],
    )
    return msg.content[0].text.strip()


def _parse(raw: str):
    """Return parsed dict, or None for a (valid) refusal."""
    text = raw.strip()
    if text.lower() in ("null", "none", '"null"'):
        return None
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.IGNORECASE).strip()
    if text.lower() == "null":
        return None
    obj = json.loads(text)
    return obj


def _valid(obj, passage) -> str | None:
    """Return an error string if invalid, else None."""
    if not isinstance(obj, dict):
        return "not an object"
    opts = obj.get("options")
    if not isinstance(opts, list) or len(opts) != 4:
        return "options not a 4-element list"
    ci = obj.get("correct_index")
    if not isinstance(ci, int) or not 0 <= ci <= 3:
        return "correct_index out of range"
    dr = obj.get("distractor_rationales")
    if not isinstance(dr, list) or len(dr) != 3:
        return "distractor_rationales not 3 entries"
    quote = obj.get("supporting_quote", "")
    if not quote or len(quote.strip()) < 10:
        return "missing supporting_quote"
    # quote must actually appear in the passage (whitespace-normalised substring)
    if _norm(quote) not in _norm(passage):
        return "supporting_quote not found verbatim in passage"
    for k in ("stem", "correct_explanation"):
        if not str(obj.get(k, "")).strip():
            return f"missing {k}"
    return None


def generate_subdomain(subdomain, limit):
    client = anthropic_client()
    chunks = db_local.fetch_unused_chunks(subdomain, limit)
    if not chunks:
        print(f"No unused chunks for '{subdomain}'. (Ingest first?)")
        return

    made = refused = invalid = 0
    for ch in chunks:
        edition = f", {ch['edition']} edition" if ch["edition"] else ""
        system = GENERATION_SYSTEM.format(book=ch["book"], edition=edition)
        try:
            raw = _call(client, system, ch["text"])
            obj = _parse(raw)
        except Exception as e:
            print(f"  chunk {ch['id']}: API/parse error: {e}")
            continue

        db_local.mark_chunk_used(ch["id"])
        if obj is None:
            refused += 1
            continue
        err = _valid(obj, ch["text"])
        if err:
            invalid += 1
            print(f"  chunk {ch['id']}: invalid ({err})")
            continue

        db_local.insert_draft({
            "chunk_id": ch["id"],
            "domain": ch["domain"],
            "subdomain": ch["subdomain"],
            "stem": obj["stem"].strip(),
            "options": json.dumps(obj["options"]),
            "correct_index": obj["correct_index"],
            "correct_explanation": obj["correct_explanation"].strip(),
            "distractor_rationales": json.dumps(obj["distractor_rationales"]),
            "supporting_quote": obj["supporting_quote"].strip(),
            "visual_type": obj.get("visual_type") or "none",
            "diagram_svg": obj.get("diagram_svg"),
            "source_book": ch["book"],
            "source_edition": ch["edition"],
            "source_page_or_section": f"p.{ch['page_start']}-{ch['page_end']}",
            "source_passage": ch["text"],
        })
        made += 1
        print(f"  chunk {ch['id']}: drafted (visual={obj.get('visual_type','none')})")

    print(f"\n{subdomain}: {made} drafted, {refused} refused, {invalid} invalid "
          f"(of {len(chunks)} chunks)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subdomain", required=True)
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()
    db_local.init_db()
    generate_subdomain(args.subdomain, args.limit)


if __name__ == "__main__":
    main()
