"""Strip leaked PDF symbols and expand dental abbreviations in stems + options. Free, no API."""
import re
import argparse
from config import supabase_admin

INVISIBLE = "\u200b\u200c\u200d\u2060\ufeff\u00a0"
SYMBOLS = "\u2705\U0001F501\u25a0\u25cf\ufe0f"

ABBREVS = [
    (r"(?<!\()\bCEJ\b", "cemento-enamel junction (CEJ)"),
    (r"(?<!\()\bPDL\b", "periodontal ligament (PDL)"),
    (r"(?<!\()\bRCT\b", "root canal treatment (RCT)"),
    (r"(?<!\()\bGIC\b", "glass ionomer cement (GIC)"),
    (r"(?<!\()\bRMGI\b", "resin-modified glass ionomer (RMGI)"),
    (r"(?<!\()\bOPG\b", "orthopantomogram (OPG)"),
    (r"(?<!\()\bCBCT\b", "cone beam CT (CBCT)"),
    (r"(?<!\()\bTMJ\b", "temporomandibular joint (TMJ)"),
    (r"(?<!\()\bMRONJ\b", "medication-related osteonecrosis of the jaw (MRONJ)"),
    (r"(?<!\()\bBOP\b", "bleeding on probing (BOP)"),
]
COMPILED = [(re.compile(p), r) for p, r in ABBREVS]


def clean_text(s):
    if not s:
        return s
    for ch in INVISIBLE + SYMBOLS:
        s = s.replace(ch, "")
    for pat, rep in COMPILED:
        s = pat.sub(rep, s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    s = re.sub(r"\n{2,}", "\n", s)
    return s.strip(" .\t-")


def clean_options(opts):
    if not isinstance(opts, list):
        return opts, False
    cleaned = [clean_text(o) for o in opts]
    return cleaned, cleaned != opts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    sb = supabase_admin()
    offset = 0
    PAGE = 500
    stems_changed = options_changed = total = 0
    examples = []

    while True:
        rows = sb.table("questions").select("id,stem,options").range(offset, offset + PAGE - 1).execute().data
        if not rows:
            break
        for row in rows:
            total += 1
            orig_stem = row["stem"] or ""
            new_stem = clean_text(orig_stem)
            new_opts, opts_dirty = clean_options(row["options"])
            stem_dirty = new_stem != orig_stem

            if stem_dirty or opts_dirty:
                update = {}
                if stem_dirty:
                    update["stem"] = new_stem
                    stems_changed += 1
                    if len(examples) < 5:
                        examples.append((orig_stem[:80], new_stem[:80]))
                if opts_dirty:
                    update["options"] = new_opts
                    options_changed += 1
                sb.table("questions").update(update).eq("id", row["id"]).execute()

        offset += PAGE
        if args.limit and total >= args.limit:
            break
        if len(rows) < PAGE:
            break

    print(f"\nProcessed {total} questions")
    print(f"Stems cleaned: {stems_changed}")
    print(f"Options cleaned: {options_changed}")
    print("\n--- Before/After examples ---")
    for before, after in examples:
        print(f"  BEFORE: {before}")
        print(f"  AFTER:  {after}")
        print()


if __name__ == "__main__":
    main()
