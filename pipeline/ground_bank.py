"""Ground recalled exam questions against the ingested textbooks.

Honours "no source, no question": a recall question is only kept if a real
textbook passage supports its marked answer, proven by a verbatim quote. This
also validates the community answer key (which the source file warns may be
wrong) — unsupported answers are dropped.

For image questions, the embedded figure is uploaded to Supabase Storage and
attached via image_url. For answer-only recalls (no distractors in the file),
the model writes 3 plausible distractors grounded in the same passage.
"""
import json
import mimetypes
import re
import sys
from pathlib import Path

import fitz
from config import GEN_MODEL, anthropic_client, supabase_admin
from db_local import connect, ensure_fts, fts_search
from map_images import map_images

ROOT = Path(__file__).resolve().parent.parent
PARSED = ROOT / "data" / "recall_parsed.json"
BUCKET = "question-images"

_alnum = re.compile(r"[^a-z0-9]+")
_STOP = set(
    "the a an of to in for and or with on at by is are was were be as that this "
    "what which who whom how when where why will would should can could may might "
    "you your his her their patient case scenario pic picture about after before "
    "found tooth teeth following best most main does do has have not no".split()
)


def _norm(s: str) -> str:
    return _alnum.sub("", (s or "").lower())


def _terms(text: str):
    words = re.findall(r"[A-Za-z][A-Za-z\-]{3,}", text.lower())
    seen, out = set(), []
    for w in words:
        if w in _STOP or w in seen:
            continue
        seen.add(w)
        out.append(w)
    return out


def retrieve(stem: str, answer: str, k=5):
    """Top-k passages by BM25 over an answer-weighted term query."""
    terms = _terms(f"{answer} {answer} {stem}")  # answer terms first & weighted
    return fts_search(terms, k=k)


GROUND_SYSTEM = (
    "You ground a recalled dental qualifying-exam question against ONE candidate "
    "textbook passage. Decide whether the passage substantively supports the "
    "marked correct answer. Be strict: tangential mentions do not count. Never "
    "invent a quote — the supporting_quote must be copied verbatim (an exact "
    "substring) from the passage."
)


def ground_prompt(q, passage):
    opts = q["options"]
    have_opts = len(opts) >= 4
    answer = q["answer_text"] or (opts[q["correct_index"]] if q.get("correct_index") is not None and opts else "")
    parts = [
        f"QUESTION STEM:\n{q['stem']}\n",
        f"MARKED CORRECT ANSWER: {answer}\n",
    ]
    if have_opts:
        parts.append("OPTIONS:\n" + "\n".join(f"- {o}" for o in opts) + "\n")
    else:
        parts.append("(The recall gives only the correct answer; no distractors.)\n")
    parts.append(f"CANDIDATE PASSAGE:\n\"\"\"\n{passage['text']}\n\"\"\"\n")
    parts.append(
        "Return ONLY JSON:\n"
        "{\n"
        '  "verdict": "PASS" | "FAIL",\n'
        '  "supporting_quote": "<verbatim sentence from passage proving the answer>",\n'
        '  "correct_explanation": "<one sentence why the answer is correct>",\n'
        '  "options": ["<4 options>"],   // echo the 4 given, OR if none given, '
        "write the correct answer plus 3 plausible but clearly-wrong distractors\n"
        '  "correct_index": <0-3>,\n'
        '  "distractor_rationales": ["<why wrong>", "<why wrong>", "<why wrong>"]\n'
        "}\n"
        "FAIL if the passage does not actually support the marked answer."
    )
    return "\n".join(parts)


def call_ground(client, q, passage):
    msg = client.messages.create(
        model=GEN_MODEL,
        max_tokens=1200,
        system=GROUND_SYSTEM,
        messages=[{"role": "user", "content": ground_prompt(q, passage)}],
    )
    txt = msg.content[0].text.strip()
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def valid(res, passage):
    if not res or res.get("verdict") != "PASS":
        return False
    if _norm(res.get("supporting_quote", "")) not in _norm(passage["text"]):
        return False
    opts = res.get("options") or []
    if len(opts) != 4:
        return False
    ci = res.get("correct_index")
    if not isinstance(ci, int) or not 0 <= ci <= 3:
        return False
    if len(res.get("distractor_rationales") or []) != 3:
        return False
    return True


def upload_image(doc, xref, qnum):
    pix = fitz.Pixmap(doc, xref)
    if pix.n - pix.alpha >= 4:
        pix = fitz.Pixmap(fitz.csRGB, pix)
    data = pix.tobytes("png")
    path = f"sep2025/q{qnum}.png"
    sb = supabase_admin()
    sb.storage.from_(BUCKET).upload(
        path, data, {"content-type": "image/png", "upsert": "true"}
    )
    return sb.storage.from_(BUCKET).get_public_url(path)


def to_row(q, res, passage, image_url):
    return {
        "domain": passage["domain"],
        "subdomain": passage["subdomain"],
        "stem": q["stem"],
        "options": res["options"],
        "correct_index": res["correct_index"],
        "correct_explanation": res["correct_explanation"],
        "distractor_rationales": res["distractor_rationales"],
        "source_book": passage["book"],
        "source_edition": passage.get("edition"),
        "source_page_or_section": (
            f"p.{passage['page_start']}" if passage.get("page_start") else passage.get("section_title")
        ),
        "source_passage": passage["text"],
        "supporting_quote": res["supporting_quote"],
        "verification_status": "pass",
        "visual_type": "image" if image_url else "none",
        "image_url": image_url,
        "source_origin": "recall",
    }


def run(limit, images_only=True):
    questions = json.loads(PARSED.read_text())
    by_num = {q["num"]: q for q in questions}
    doc, img_map = map_images(sys.argv_src)

    client = anthropic_client()
    sb = supabase_admin()

    # candidate pool: questions with an answer; if images_only, must have a figure
    pool = []
    for num in sorted(by_num):
        q = by_num[num]
        if q["kind"] in ("incomplete", "image_only") and not q.get("answer_text"):
            # image_only often has answer in stem like "X ✅" — skip if truly empty
            pass
        if not q.get("answer_text") and q.get("correct_index") is None:
            continue
        if images_only and not img_map.get(num):
            continue
        pool.append(q)

    kept = dropped = 0
    for q in pool:
        if kept >= limit:
            break
        cands = retrieve(q["stem"], q.get("answer_text") or "")
        res = passage = None
        for c in cands:
            r = call_ground(client, q, c)
            if valid(r, c):
                res, passage = r, c
                break
        if not res:
            dropped += 1
            print(f"  Q{q['num']}: DROP (no grounding) — {q['stem'][:60]}")
            continue
        image_url = upload_image(doc, img_map[q["num"]][0], q["num"]) if img_map.get(q["num"]) else None
        row = to_row(q, res, passage, image_url)
        sb.table("questions").insert(row).execute()
        kept += 1
        tag = "IMG" if image_url else "txt"
        print(f"  Q{q['num']}: KEEP [{tag}] {passage['book'][:28]} — {q['stem'][:50]}")
    print(f"\nkept {kept}, dropped {dropped}")


if __name__ == "__main__":
    # usage: ground_bank.py <pdf> [limit]
    sys.argv_src = sys.argv[1]
    lim = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    run(lim)
