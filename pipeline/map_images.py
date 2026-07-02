"""Map embedded figures in a recall PDF to their question numbers.

Strategy: per page, collect two kinds of anchors by vertical position —
question-number markers ("12)") from the word layer, and substantial image
rects from the image layer. Walk top-to-bottom; each image belongs to the most
recent question marker seen (carried across page breaks). This matches how a
reader associates a figure with the question printed just above it.
"""
import re
from collections import defaultdict

import fitz

QNUM_RE = re.compile(r"^\s*(\d+)\)")
MIN_PX = 250  # by pixel size: emoji/legend icons are <=160px; real figures larger


def _markers(page):
    """Return [(y0, qnum), …] for lines that start a numbered question."""
    words = page.get_text("words")  # x0,y0,x1,y1,word,block,line,wordno
    lines = defaultdict(list)
    for w in words:
        key = (round(w[1] / 3), w[5], w[6])  # cluster by ~y, block, line
        lines[key].append(w)
    out = []
    for ws in lines.values():
        ws.sort(key=lambda w: w[0])
        text = " ".join(w[4] for w in ws)
        m = QNUM_RE.match(text)
        if m:
            out.append((min(w[1] for w in ws), int(m.group(1))))
    return out


def _images(doc, page):
    out = []
    for info in page.get_image_info(xrefs=True):
        xref = info.get("xref", 0)
        if not xref:
            continue
        try:
            px = doc.extract_image(xref)
            if max(px["width"], px["height"]) < MIN_PX:
                continue
        except Exception:
            continue
        out.append((info["bbox"][1], xref))  # y-top, xref
    return out


def map_images(path: str):
    """Return dict: qnum -> [xref, …] in document order."""
    doc = fitz.open(path)
    mapping = defaultdict(list)
    current = None
    for i in range(doc.page_count):
        page = doc[i]
        anchors = [(y, "q", n) for y, n in _markers(page)]
        anchors += [(y, "img", x) for y, x in _images(doc, page)]
        anchors.sort(key=lambda a: a[0])
        for _, kind, val in anchors:
            if kind == "q":
                current = val
            elif current is not None:
                mapping[current].append(val)
    return doc, dict(mapping)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    src = sys.argv[1]
    doc, mp = map_images(src)
    n_q = len(mp)
    n_img = sum(len(v) for v in mp.values())
    print(f"questions with >=1 figure: {n_q}; total figures mapped: {n_img}")

    # extract a sample for visual verification
    out_dir = Path(__file__).resolve().parent.parent / "data" / "recall_images"
    out_dir.mkdir(parents=True, exist_ok=True)
    sample = [q for q in sorted(mp) if mp[q]][:12]
    for q in sample:
        xref = mp[q][0]
        pix = fitz.Pixmap(doc, xref)
        if pix.n - pix.alpha >= 4:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        fp = out_dir / f"q{q}_fig.png"
        pix.save(fp)
        print(f"  Q{q}: {len(mp[q])} fig(s) -> {fp.name} ({pix.width}x{pix.height})")
