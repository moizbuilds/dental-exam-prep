"""Parse ALL recall-question PDFs into structured, classified MCQs + figure map.

Recall PDFs are the PRIMARY question source: their stems, options, the ✅-marked
correct answer, and embedded clinical figures become the question bank. Textbooks
are only a secondary citation/back-up (added later, for free, via BM25).

FREE — no API calls. One unified pass per page so that the question number used
for the TEXT and the question number used for the IMAGES are always the same:

  * cluster the word layer into lines (with y positions)
  * a line that starts with a sequential "N)" / "N." / "N.\u200b" opens a question
  * every following line is body text for that question
  * every embedded figure >=250px is attached to the most-recent question

Output: data/recall_all.json — each row carries source_file + image_xrefs so the
push step can pull the exact figure bytes with fitz.
"""
import glob
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

import fitz

ARCHIVE = "/Users/moizrana/Downloads/archive_extract"
OUT = Path(__file__).resolve().parent.parent / "data" / "recall_all.json"

CORRECT = "\u2705"
UNSURE = "\U0001F501"
MIN_PX = 250

QNUM_RE = re.compile(r"^\s*(\d{1,3})\s*[\).\u200b]\s*")
OPT_RE = re.compile(r"^\s*([a-dA-D])\s*[\).\u200b]\s*(.*)$")
IMG_RE = re.compile(r"[Pp]ic\b|[Pp]icture|[Ii]mage|[Rr]adiograph|الصورة|صورة|x-?ray", re.I)
ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
REF_RE = re.compile(r"(page\s*\d+|p\s*[:.]?\s*\d+|chapter\s*\d+|\d+(?:st|nd|rd|th)\s*ed)", re.I)
MONTH_RE = re.compile(r"^[^/]*?([A-Za-z].*?Questions)", re.I)


def _clean(s: str) -> str:
    return (s.replace(CORRECT, "").replace(UNSURE, "")
             .replace("\ufe0f", "").replace("\u200b", "")
             .replace("\u25a0", "").replace("\u25cf", "")
             .strip(" .\t"))


def _strip_arabic(s: str) -> str:
    out = []
    for line in s.splitlines():
        letters = re.sub(r"[^A-Za-z\u0600-\u06FF]", "", line)
        if not letters:
            continue
        if len(ARABIC_RE.findall(line)) / max(1, len(letters)) > 0.45:
            continue
        out.append(line)
    return "\n".join(out)


def _page_lines(page):
    """Reconstruct text lines as (y, text), sorted top-to-bottom."""
    words = page.get_text("words")  # x0,y0,x1,y1,word,block,line,wordno
    lines = defaultdict(list)
    for w in words:
        lines[(w[5], w[6])].append(w)
    out = []
    for ws in lines.values():
        ws.sort(key=lambda w: w[0])
        out.append((min(w[1] for w in ws), " ".join(w[4] for w in ws)))
    return out


def _page_images(doc, page):
    """Return [(y, xref)] for embedded figures larger than MIN_PX."""
    out = []
    for info in page.get_image_info(xrefs=True):
        xref = info.get("xref", 0)
        if not xref:
            continue
        try:
            px = doc.extract_image(xref)
        except Exception:
            continue
        if max(px["width"], px["height"]) < MIN_PX:
            continue
        out.append((info["bbox"][1], xref))
    return out


def parse_pdf(path: str):
    doc = fitz.open(path)
    # build per-question body lines + image xrefs in one consistent pass
    bodies = defaultdict(list)
    images = defaultdict(list)
    order = []  # question numbers in first-seen order
    current = None
    expect = 1
    for i in range(doc.page_count):
        page = doc[i]
        anchors = [(y, "t", t) for y, t in _page_lines(page)]
        anchors += [(y, "i", x) for y, x in _page_images(doc, page)]
        anchors.sort(key=lambda a: a[0])
        for _, kind, val in anchors:
            if kind == "t":
                m = QNUM_RE.match(val)
                if m and expect <= int(m.group(1)) <= expect + 3:
                    current = int(m.group(1))
                    expect = current + 1
                    if current not in bodies:
                        order.append(current)
                    bodies[current].append(QNUM_RE.sub("", val, count=1))
                elif current is not None:
                    bodies[current].append(val)
            elif current is not None:
                images[current].append(val)
    doc.close()

    out = []
    for num in order:
        body = "\n".join(bodies[num])
        lines = bodies[num]
        opts, correct_idx, opt_start, ref_notes = [], None, None, []
        for li, raw in enumerate(lines):
            m = OPT_RE.match(raw)
            if m:
                if opt_start is None:
                    opt_start = li
                if CORRECT in raw:
                    correct_idx = len(opts)
                opts.append(_clean(m.group(2)))
            elif raw.lstrip().startswith(("\u25a0", "\u25cf")):
                note = _clean(raw)
                if note:
                    ref_notes.append(note)

        stem_src = "\n".join(lines[:opt_start]) if opt_start is not None else body
        stem = re.sub(r"\s+", " ", _strip_arabic(stem_src)).strip()
        ref = next((n for n in ref_notes if REF_RE.search(n) or len(n) > 14), None)
        opts = [o for o in opts if o]
        xrefs = images.get(num, [])

        answer_text = None
        if correct_idx is not None and correct_idx < len(opts):
            answer_text = opts[correct_idx]
        else:
            for l in lines:
                if CORRECT in l and not OPT_RE.match(l):
                    answer_text = _clean(l)
                    break

        if len(opts) >= 4 and correct_idx is not None:
            kind = "mcq4"
        elif answer_text:
            kind = "answer_only"
        elif xrefs or IMG_RE.search(body):
            kind = "image_only"
        else:
            kind = "incomplete"

        out.append({
            "num": num, "kind": kind, "stem": stem, "options": opts,
            "correct_index": correct_idx, "answer_text": answer_text,
            "reference": ref, "unsure": any(UNSURE in l for l in lines),
            "image_xrefs": xrefs,
        })
    return out


def main():
    files = sorted(glob.glob(os.path.join(ARCHIVE, "*.pdf")))
    all_q, grand = [], Counter()
    print(f'{"file":34} {"Qs":>5} {"mcq4":>5} {"ans":>5} {"img":>5} {"inc":>5} {"figs":>5}')
    for f in files:
        base = os.path.basename(f)
        m = MONTH_RE.match(base)
        month = (m.group(1) if m else base).replace("_", " ").strip()
        qs = parse_pdf(f)
        c = Counter(q["kind"] for q in qs)
        nfig = sum(len(q["image_xrefs"]) for q in qs)
        for q in qs:
            q["month"], q["source_file"] = month, base
        all_q.extend(qs)
        grand.update(c)
        print(f'{base[:34]:34} {len(qs):>5} {c["mcq4"]:>5} {c["answer_only"]:>5} '
              f'{c["image_only"]:>5} {c["incomplete"]:>5} {nfig:>5}')
    OUT.write_text(json.dumps(all_q, ensure_ascii=False, indent=2))
    nwith = sum(1 for q in all_q if q["image_xrefs"])
    print(f'\nTOTAL {len(all_q)} questions, {nwith} with >=1 figure -> {OUT}')
    for k, v in grand.most_common():
        print(f'  {k}: {v}')


if __name__ == "__main__":
    main()
