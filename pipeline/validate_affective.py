"""Validate Affective Skills answer keys using Haiku. Flags suspected wrong answers."""
import re
from config import anthropic_client, supabase_admin

MODEL = "claude-haiku-4-5-20251001"
SYSTEM = (
    "You are a dental ethics and professionalism examiner. Determine if the marked "
    "correct answer is correct. Apply GDC principles, dental ethics frameworks "
    "(autonomy, beneficence, non-maleficence, justice, veracity), and "
    "professionalism standards. Reply with AGREE or DISAGREE on the first line, "
    "then one sentence explaining why."
)


def check(client, row):
    opts = row["options"] if isinstance(row["options"], list) else []
    ci = row["correct_index"] or 0
    if ci >= len(opts):
        return None
    letter = chr(65 + ci)
    options_text = "\n".join(f"{chr(65+i)}: {o}" for i, o in enumerate(opts))
    user = (
        f"STEM: {row['stem']}\n"
        f"OPTIONS:\n{options_text}\n"
        f"MARKED CORRECT: Option {letter} — {opts[ci]}\n"
        "Is this answer correct? Reply AGREE or DISAGREE, then one sentence why."
    )
    msg = client.messages.create(model=MODEL, max_tokens=100, system=SYSTEM,
                                  messages=[{"role": "user", "content": user}])
    return msg.content[0].text.strip()


def main():
    sb = supabase_admin()
    client = anthropic_client()

    rows = sb.table("questions").select(
        "id,stem,options,correct_index,correct_explanation,subdomain"
    ).eq("domain", "Affective Skills").eq("verification_status", "pass").execute().data

    print(f"Checking {len(rows)} Affective Skills questions...\n")
    agreed = disagreed = errors = 0
    flagged = []

    for i, row in enumerate(rows):
        try:
            resp = check(client, row)
            if not resp:
                errors += 1
                continue
            first_word = resp.split()[0].upper().strip(".,")
            reason = " ".join(resp.split()[1:]).strip()
            if first_word == "DISAGREE":
                disagreed += 1
                flagged.append((row, reason))
                existing = row.get("correct_explanation") or ""
                dispute_note = f"⚠️ Community answer disputed: {reason}"
                if "disputed" not in existing:
                    new_expl = f"{dispute_note} | {existing}" if existing else dispute_note
                    sb.table("questions").update({"correct_explanation": new_expl}).eq("id", row["id"]).execute()
                print(f"  ⚠️  Q[{row['subdomain']}] {row['stem'][:80]}")
                print(f"       Marked: {(row['options'] or [])[row['correct_index'] or 0][:60]}")
                print(f"       Haiku:  {reason[:100]}\n")
            else:
                agreed += 1
            if (i + 1) % 20 == 0:
                print(f"  …{i+1}/{len(rows)} checked")
        except Exception as e:
            errors += 1
            print(f"  error on {row['id']}: {e}")

    print(f"\n{'='*50}")
    print(f"SUMMARY: {len(rows)} checked | {agreed} AGREE | {disagreed} DISAGREE | {errors} errors")
    if flagged:
        print(f"\n{disagreed} questions flagged with disputed answers in Supabase.")


if __name__ == "__main__":
    main()
