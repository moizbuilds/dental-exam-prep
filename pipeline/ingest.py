"""Ingestion: read textbook PDFs, chunk by section/paragraph, tag with the
blueprint subdomain, detect figure-dependent chunks, store locally in SQLite.

Usage:
    python ingest.py                # ingest every mapped PDF
    python ingest.py --only Malamed # ingest only files whose name contains substr
    python ingest.py --stats        # print per-subdomain chunk counts
"""
import argparse
import re
import sys

import fitz  # PyMuPDF

from config import TEXTBOOK_DIR
from domain_map import map_filename
from classify import classify
import db_local

TARGET_CHARS = 2600       # aim for ~passage-sized chunks
MIN_CHARS = 700           # discard slivers (TOC fragments, page headers)
MAX_CHARS = 4200          # hard cap so a chunk fits a generation prompt cleanly

# Phrases that mean a chunk leans on a figure/table/radiograph the reader can't see.
FIGURE_RE = re.compile(
    r"\b(fig(?:ure|s)?\.?\s*\d|figure\s+\d|table\s+\d|"
    r"see\s+(?:fig|figure|image|illustration|photograph)|"
    r"radiograph(?:\b|s)|as\s+shown\s+(?:in|below|above)|"
    r"the\s+(?:image|diagram|photograph)\s+(?:shows|below|above))",
    re.IGNORECASE,
)

# Boilerplate lines to strip (running headers, page numbers, z-lib stamps).
NOISE_RE = re.compile(r"z-?lib|1lib|libgen|^\s*\d+\s*$", re.IGNORECASE)


def clean_title(filename: str) -> str:
    """Turn a messy z-library filename into a readable book title."""
    name = re.sub(r"\.pdf$", "", filename, flags=re.IGNORECASE)
    name = re.sub(r"\([^)]*z-?lib[^)]*\)", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\(\d{4}[^)]*\)", "", name)            # (2022, Elsevier)
    name = re.sub(r"\{[^}]*\}", "", name)                  # {…libgen…}
    name = re.sub(r"libgen\.li.*$", "", name, flags=re.IGNORECASE)
    # drop the trailing author parenthetical if present
    name = re.sub(r"\s*\([^)]*(?:etc\.|, [A-Z])[^)]*\)\s*$", "", name)
    return re.sub(r"\s{2,}", " ", name).strip(" -")


def page_text(page) -> str:
    raw = page.get_text("text")
    lines = [ln for ln in raw.splitlines() if not NOISE_RE.search(ln.strip())]
    return "\n".join(lines)


def paragraphs(text: str):
    for para in re.split(r"\n\s*\n", text):
        p = re.sub(r"[ \t]+", " ", para).strip()
        if p:
            yield p


def chunk_pages(doc):
    """Yield (text, page_start, page_end) chunks built from paragraph runs."""
    buf, buf_start, buf_pages = "", None, []
    for pno in range(doc.page_count):
        ptext = page_text(doc[pno])
        for para in paragraphs(ptext):
            if buf_start is None:
                buf_start = pno
            candidate = (buf + "\n\n" + para).strip() if buf else para
            if len(candidate) <= MAX_CHARS:
                buf = candidate
                buf_pages.append(pno)
            else:
                if len(buf) >= MIN_CHARS:
                    yield buf, buf_start, max(buf_pages)
                buf, buf_start, buf_pages = para[:MAX_CHARS], pno, [pno]
            if len(buf) >= TARGET_CHARS:
                yield buf, buf_start, max(buf_pages)
                buf, buf_start, buf_pages = "", None, []
    if len(buf) >= MIN_CHARS:
        yield buf, buf_start, max(buf_pages or [0])


def ingest_pdf(path):
    filename = path.name
    mapping = map_filename(filename)
    if not mapping:
        print(f"  SKIP (unmapped): {filename}")
        return 0
    domain, subdomain, edition = mapping

    if db_local.book_already_ingested(filename):
        print(f"  SKIP (already ingested): {filename}")
        return 0

    try:
        doc = fitz.open(path)
    except Exception as e:
        print(f"  ERROR opening {filename}: {e}")
        return 0

    book = clean_title(filename)
    max_page = doc.page_count
    rows = []
    for text, p_start, p_end in chunk_pages(doc):
        excl, reason, score = classify(text, p_start + 1, max_page)
        rows.append({
            "book": book,
            "source_file": filename,
            "edition": edition,
            "domain": domain,
            "subdomain": subdomain,
            "page_start": p_start + 1,        # 1-indexed for human citation
            "page_end": p_end + 1,
            "section_title": None,
            "text": text,
            "char_count": len(text),
            "figure_dependent": 1 if FIGURE_RE.search(text) else 0,
            "excluded": excl,
            "exclude_reason": reason,
            "clinical_score": score,
        })
    doc.close()
    if rows:
        db_local.insert_chunks(rows)
    fig = sum(r["figure_dependent"] for r in rows)
    kept = sum(1 for r in rows if not r["excluded"])
    print(f"  OK: {book}  ->  {subdomain}  ({len(rows)} chunks, {kept} kept, "
          f"{fig} figure-dependent)")
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="only ingest files whose name contains this substring")
    ap.add_argument("--stats", action="store_true", help="print chunk stats and exit")
    ap.add_argument("--reclassify", action="store_true",
                    help="recompute excluded/clinical_score for existing chunks")
    ap.add_argument("--reset-used", metavar="SUBDOMAIN", nargs="?", const="__all__",
                    help="clear the 'used' flag (optionally for one subdomain)")
    args = ap.parse_args()

    db_local.init_db()

    if args.reclassify:
        n = db_local.reclassify_all()
        print(f"Reclassified {n} chunks.")
        return

    if args.reset_used:
        sub = None if args.reset_used == "__all__" else args.reset_used
        db_local.reset_used(sub)
        print(f"Reset 'used' flag for {sub or 'all subdomains'}.")
        return

    if args.stats:
        print(f"{'subdomain':<34}{'chunks':>8}{'kept':>7}{'figure':>8}{'books':>7}")
        for s in db_local.stats():
            print(f"{s['subdomain']:<34}{s['total']:>8}{s['kept'] or 0:>7}"
                  f"{s['fig'] or 0:>8}{s['books']:>7}")
        return

    if not TEXTBOOK_DIR.exists():
        sys.exit(f"TEXTBOOK_DIR does not exist: {TEXTBOOK_DIR}")

    pdfs = sorted(p for p in TEXTBOOK_DIR.iterdir() if p.suffix.lower() == ".pdf")
    if args.only:
        pdfs = [p for p in pdfs if args.only.lower() in p.name.lower()]

    total = 0
    for path in pdfs:
        if path.stat().st_size == 0:
            print(f"  SKIP (empty file): {path.name}")
            continue
        total += ingest_pdf(path)
    print(f"\nDone. {total} chunks ingested into {db_local.CHUNK_DB}")


if __name__ == "__main__":
    main()
