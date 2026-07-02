"""Blind verification: a separate model call receives ONLY the question and its
source passage and must quote the supporting sentence(s) or return FAIL. It never
sees the generator's reasoning or its supporting_quote. FAIL -> excluded from the
served bank.

Usage:
    python verify.py --limit 100
"""
import argparse
import json
import re

from tenacity import retry, stop_after_attempt, wait_exponential

from config import anthropic_client, VERIFY_MODEL
from prompts import VERIFICATION_SYSTEM, VERIFICATION_FORMAT
import db_local


@retry(stop=stop_after_attempt(4), wait=wait_exponential(min=2, max=30))
def _call(client, question_block, passage):
    msg = client.messages.create(
        model=VERIFY_MODEL,
        max_tokens=600,
        system=VERIFICATION_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"QUESTION:\n{question_block}\n\nSOURCE PASSAGE:\n{passage}\n\n{VERIFICATION_FORMAT}",
        }],
    )
    return msg.content[0].text.strip()


def _question_block(d):
    """Render the question WITHOUT the generator's explanation/quote — only the
    stem, options, and which option is marked correct."""
    opts = json.loads(d["options"])
    lines = [d["stem"], ""]
    for i, o in enumerate(opts):
        mark = "  <-- marked correct" if i == d["correct_index"] else ""
        lines.append(f"{chr(65+i)}. {o}{mark}")
    return "\n".join(lines)


def _parse(raw):
    text = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.IGNORECASE).strip()
    try:
        obj = json.loads(text)
        verdict = str(obj.get("verdict", "")).upper()
        return verdict, obj.get("supporting_sentences", "")
    except Exception:
        # tolerate a bare FAIL/PASS token
        up = text.upper()
        if "FAIL" in up:
            return "FAIL", ""
        if "PASS" in up:
            return "PASS", text
        return "FAIL", ""


def verify_pending(limit):
    client = anthropic_client()
    drafts = db_local.fetch_drafts(status="flagged", limit=limit)
    if not drafts:
        print("No flagged drafts to verify.")
        return

    passed = failed = 0
    for d in drafts:
        block = _question_block(d)
        try:
            raw = _call(client, block, d["source_passage"])
            verdict, quote = _parse(raw)
        except Exception as e:
            print(f"  draft {d['id']}: verify error: {e}")
            continue

        if verdict == "PASS" and quote.strip():
            db_local.set_verification(d["id"], "pass", quote.strip())
            passed += 1
        else:
            db_local.set_verification(d["id"], "fail", quote.strip())
            failed += 1
        print(f"  draft {d['id']}: {verdict}")

    print(f"\nVerified {passed+failed}: {passed} PASS, {failed} FAIL")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100)
    args = ap.parse_args()
    db_local.init_db()
    verify_pending(args.limit)


if __name__ == "__main__":
    main()
