"""Local SQLite store for ingested textbook chunks + their metadata."""
import re
import sqlite3
from contextlib import contextmanager
from config import CHUNK_DB

SCHEMA = """
create table if not exists chunks (
  id            integer primary key autoincrement,
  book          text not null,
  source_file   text not null,
  edition       text,
  domain        text not null,
  subdomain     text not null,
  page_start    integer not null,
  page_end      integer not null,
  section_title text,
  text          text not null,
  char_count    integer not null,
  figure_dependent integer not null default 0,
  excluded      integer not null default 0,   -- 1 = front matter / refs / index / low value
  exclude_reason text,
  clinical_score integer not null default 0,   -- count of clinical-signal hits
  route_score   integer not null default 0,   -- keyword hits for a routed subdomain
  used          integer not null default 0,   -- set once an MCQ is generated from it
  created_at    text not null default (datetime('now'))
);
create index if not exists chunks_subdomain_idx on chunks (subdomain);
create index if not exists chunks_book_idx on chunks (book);
create index if not exists chunks_usable_idx on chunks (subdomain, figure_dependent, used);

-- Draft MCQs flow through here: generated -> verified -> pushed to Supabase.
create table if not exists drafts (
  id            integer primary key autoincrement,
  chunk_id      integer not null references chunks(id),
  domain        text not null,
  subdomain     text not null,
  stem          text not null,
  options       text not null,        -- json array
  correct_index integer not null,
  correct_explanation   text not null,
  distractor_rationales text not null, -- json array
  supporting_quote text not null,
  visual_type   text not null default 'none',
  diagram_svg   text,
  source_book   text not null,
  source_edition text,
  source_page_or_section text,
  source_passage text not null,
  verification_status text not null default 'flagged',  -- pass | fail | flagged
  verifier_quote text,
  pushed        integer not null default 0,
  created_at    text not null default (datetime('now'))
);
create index if not exists drafts_status_idx on drafts (verification_status, pushed);
create index if not exists drafts_subdomain_idx on drafts (subdomain);
"""


@contextmanager
def connect():
    CHUNK_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CHUNK_DB)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)
        # add classification columns to pre-existing chunk tables
        cols = {r["name"] for r in conn.execute("pragma table_info(chunks)")}
        for ddl, col in (
            ("alter table chunks add column excluded integer not null default 0", "excluded"),
            ("alter table chunks add column exclude_reason text", "exclude_reason"),
            ("alter table chunks add column clinical_score integer not null default 0", "clinical_score"),
            ("alter table chunks add column route_score integer not null default 0", "route_score"),
        ):
            if col not in cols:
                conn.execute(ddl)


def insert_chunks(rows):
    with connect() as conn:
        conn.executemany(
            """insert into chunks
               (book, source_file, edition, domain, subdomain, page_start,
                page_end, section_title, text, char_count, figure_dependent,
                excluded, exclude_reason, clinical_score)
               values (:book, :source_file, :edition, :domain, :subdomain,
                       :page_start, :page_end, :section_title, :text,
                       :char_count, :figure_dependent,
                       :excluded, :exclude_reason, :clinical_score)""",
            rows,
        )
    return len(rows)


def reclassify_all():
    """Recompute excluded/clinical_score for every chunk (used after the
    classifier heuristics change). Returns count updated."""
    from classify import classify
    with connect() as conn:
        # max page per source_file, for front/back-matter detection
        maxp = {r["source_file"]: r["mx"] for r in conn.execute(
            "select source_file, max(page_start) mx from chunks group by source_file")}
        rows = conn.execute("select id, source_file, page_start, text from chunks").fetchall()
        for r in rows:
            excl, reason, score = classify(r["text"], r["page_start"], maxp.get(r["source_file"], 0))
            conn.execute(
                "update chunks set excluded=?, exclude_reason=?, clinical_score=? where id=?",
                (excl, reason, score, r["id"]),
            )
        return len(rows)


def reset_used(subdomain=None):
    with connect() as conn:
        if subdomain:
            conn.execute("update chunks set used=0 where subdomain=?", (subdomain,))
        else:
            conn.execute("update chunks set used=0")


def book_already_ingested(source_file):
    with connect() as conn:
        cur = conn.execute(
            "select count(*) c from chunks where source_file = ?", (source_file,)
        )
        return cur.fetchone()["c"] > 0


def stats():
    with connect() as conn:
        rows = conn.execute(
            """select subdomain,
                      count(*) total,
                      sum(case when excluded=0 then 1 else 0 end) kept,
                      sum(figure_dependent) fig,
                      count(distinct book) books
               from chunks group by subdomain order by subdomain"""
        ).fetchall()
        return [dict(r) for r in rows]


# ── generation/verification helpers ──────────────────────────────────────────

def fetch_unused_chunks(subdomain, limit, min_chars=900):
    """Usable chunks for a subdomain not yet turned into a draft. Excludes
    front matter / references / index / low-value chunks, and prefers
    clinically rich, text-only passages. Figure-dependent chunks are still
    eligible (the generator rewrites them as text vignettes), but ranked last."""
    with connect() as conn:
        rows = conn.execute(
            """select * from chunks
               where subdomain = ? and used = 0 and excluded = 0
                     and char_count >= ?
               order by figure_dependent asc, route_score desc,
                        clinical_score desc, char_count desc
               limit ?""",
            (subdomain, min_chars, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def ensure_fts():
    """Build/refresh a standalone FTS5 index over chunk text (BM25 retrieval).
    Standalone (not external-content) so MATCH works after a plain insert."""
    with connect() as conn:
        conn.execute("create virtual table if not exists chunks_fts using fts5(text)")
        n_chunks = conn.execute("select count(*) c from chunks").fetchone()["c"]
        n_fts = conn.execute("select count(*) c from chunks_fts").fetchone()["c"]
        if n_fts != n_chunks:
            conn.execute("delete from chunks_fts")
            conn.execute(
                "insert into chunks_fts(rowid, text) select id, text from chunks"
            )


def fts_search(terms, k=6, min_chars=300):
    """Top-k non-excluded chunks for an OR of terms, ranked by BM25."""
    terms = [re.sub(r'[^a-z0-9]', '', t.lower()) for t in terms]
    terms = [t for t in terms if len(t) >= 3]
    if not terms:
        return []
    match = " OR ".join(f'"{t}"' for t in terms[:12])
    with connect() as conn:
        rows = conn.execute(
            """select c.* from chunks_fts f
               join chunks c on c.id = f.rowid
               where chunks_fts match ? and c.excluded = 0 and c.char_count >= ?
               order by bm25(chunks_fts) limit ?""",
            (match, min_chars, k),
        ).fetchall()
        return [dict(r) for r in rows]


def mark_chunk_used(chunk_id):
    with connect() as conn:
        conn.execute("update chunks set used = 1 where id = ?", (chunk_id,))


def insert_draft(d):
    with connect() as conn:
        cur = conn.execute(
            """insert into drafts
               (chunk_id, domain, subdomain, stem, options, correct_index,
                correct_explanation, distractor_rationales, supporting_quote,
                visual_type, diagram_svg, source_book, source_edition,
                source_page_or_section, source_passage)
               values (:chunk_id, :domain, :subdomain, :stem, :options,
                       :correct_index, :correct_explanation, :distractor_rationales,
                       :supporting_quote, :visual_type, :diagram_svg, :source_book,
                       :source_edition, :source_page_or_section, :source_passage)""",
            d,
        )
        return cur.lastrowid


def fetch_drafts(status="flagged", limit=1000):
    with connect() as conn:
        rows = conn.execute(
            "select * from drafts where verification_status = ? limit ?",
            (status, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def set_verification(draft_id, status, verifier_quote):
    with connect() as conn:
        conn.execute(
            "update drafts set verification_status = ?, verifier_quote = ? where id = ?",
            (status, verifier_quote, draft_id),
        )


def fetch_pushable(limit=1000):
    with connect() as conn:
        rows = conn.execute(
            "select * from drafts where verification_status = 'pass' and pushed = 0 limit ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def mark_pushed(draft_id):
    with connect() as conn:
        conn.execute("update drafts set pushed = 1 where id = ?", (draft_id,))


def pushed_count(subdomain):
    with connect() as conn:
        return conn.execute(
            "select count(*) c from drafts where subdomain=? and pushed=1",
            (subdomain,),
        ).fetchone()["c"]


def available_chunk_count(subdomain, min_chars=900):
    with connect() as conn:
        return conn.execute(
            "select count(*) c from chunks where subdomain=? and used=0 "
            "and excluded=0 and char_count>=?",
            (subdomain, min_chars),
        ).fetchone()["c"]


def draft_stats():
    with connect() as conn:
        rows = conn.execute(
            """select subdomain, verification_status, count(*) n,
                      sum(pushed) pushed
               from drafts group by subdomain, verification_status
               order by subdomain"""
        ).fetchall()
        return [dict(r) for r in rows]
