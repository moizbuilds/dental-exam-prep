"""Parse a community recall-question PDF into structured MCQs.

These files list real recalled exam questions with the correct answer marked
by a ✅. They are messy: mixed Arabic commentary, ■ reference/notes lines,
image-only ("Pic of …") entries, and many "answer-only" recalls that give the
correct option without a full set of distractors.

This module ONLY parses — it does not ground. Grounding (finding a textbook
passage + verbatim quote, and generating distractors where missing) happens in
ground_bank.py, so that the "no source, no question" guarantee is preserved.
"""
import json
import re
import sys
from pathlib import Path

import fitz

CORRECT = "✅"
UNSURE = "🔁"
OPT_RE = re.compile(r"^\s*([a-dA-D])\s*[).\.]\s*(.*)$")
IMG_RE = re.compile(r"[Pp]ic\s+(?:of|and|:)|الصورة|صورة")
ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
# A reference note line, e.g. "■ McCracken_s Removable Partial Prosthodontics page 100"
REF_RE = re.compile(r"(page\s*\d+|p\s*[:.]?\s*\d+|\d+\s*-\s*\d+\s*-\s*\d+)", re.I)


def _clean(s: str) -> str:
    return s.replace(CORRECT, "").replace(UNSURE, "").replace("■", "").strip(" .\t")


def _strip_arabic(s: str) -> str:
    # keep lines that are mostly latin; drop heavy-arabic trailing commentary
    out = []
    for line in s.splitlines():
        letters = re.sub(r"[^A-Za-z\u0600-\u06FF]", "", line)
        if not letters:
            continue
        ar = len(ARABIC_RE.findall(line))
        if ar / max(1, len(letters)) > 0.4:
            continue
        out.append(line)
    return "\n".join(out)


def parse_pdf(path: str):
    doc = fitz.open(path)
    full = "\n".join(doc[i].get_text() for i in range(doc.page_count))
    parts = re.split(r"(?m)^\s*(\d+)\)\s*", full)
    blocks = [(int(parts[i]), parts[i + 1]) for i in range(1, len(parts), 2)]

    questions = []
    for num, body in blocks:
        lines = body.splitlines()
        # collect option lines and where the option region starts
        opts, correct_idx, opt_start = [], None, None
        ref_notes = []
        for li, raw in enumerate(lines):
            m = OPT_RE.match(raw)
            if m:
                if opt_start is None:
                    opt_start = li
                text = _clean(m.group(2))
                if CORRECT in raw:
                    correct_idx = len(opts)
                opts.append(text)
            elif raw.lstrip().startswith("■"):
                note = _clean(raw)
                if note:
                    ref_notes.append(note)

        stem_src = "\n".join(lines[:opt_start]) if opt_start is not None else body
        stem = _strip_arabic(stem_src).strip()
        stem = re.sub(r"\s+", " ", stem)

        ref = next((n for n in ref_notes if REF_RE.search(n) or len(n) > 12), None)
        is_image = bool(IMG_RE.search(body)) and len(stem) < 40

        if is_image:
            kind = "image_only"
        elif len([o for o in opts if o]) >= 4:
            kind = "mcq4"
        elif correct_idx is not None or any(CORRECT in l for l in lines):
            kind = "answer_only"
        else:
            kind = "incomplete"

        # answer-only: the marked option is the correct answer text
        answer_text = None
        if correct_idx is not None and correct_idx < len(opts):
            answer_text = opts[correct_idx]
        elif kind == "answer_only":
            # single answer may sit on its own ✅ line without a letter
            for l in lines:
                if CORRECT in l and not OPT_RE.match(l):
                    answer_text = _clean(l)
                    break

        questions.append({
            "num": num,
            "kind": kind,
            "stem": stem,
            "options": [o for o in opts if o],
            "correct_index": correct_idx,
            "answer_text": answer_text,
            "reference": ref,
            "unsure": any(UNSURE in l for l in lines),
        })
    return questions


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else None
    if not src:
        print("usage: parse_bank.py <pdf-path>")
        sys.exit(1)
    out = Path(__file__).resolve().parent.parent / "data" / "recall_parsed.json"
    qs = parse_pdf(src)
    out.write_text(json.dumps(qs, ensure_ascii=False, indent=2))
    from collections import Counter
    c = Counter(q["kind"] for q in qs)
    print(f"parsed {len(qs)} blocks -> {out}")
    for k, v in c.most_common():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
