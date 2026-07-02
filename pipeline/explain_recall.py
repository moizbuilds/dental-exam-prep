"""Generate 2-sentence explanations for questions missing correct_explanation."""
import argparse
import sys
from config import anthropic_client, supabase_admin

MODEL = "claude-haiku-4-5-20251001"
BATCH_SIZE = 100
SYSTEM_PROMPT = (
    "You are a dental exam tutor. Given a question stem, the correct answer, and a reference, "
    "write EXACTLY 2 sentences: (1) why this answer is correct, (2) the key clinical fact to remember. "
    "Be concise and specific. Return only the 2 sentences, no labels."
)


def fetch_batch(sb, offset):
    result = (
        sb.table("questions")
        .select("id, stem, options, correct_index, supporting_quote")
        .eq("correct_explanation", "")
        .range(offset, offset + BATCH_SIZE - 1)
        .execute()
    )
    return result.data or []


def generate_explanation(client, row):
    options = row.get("options") or []
    correct_index = row.get("correct_index", 0)
    stem = row.get("stem", "")
    quote = row.get("supporting_quote") or ""

    if isinstance(options, list) and 0 <= correct_index < len(options):
        correct_answer = options[correct_index]
    else:
        correct_answer = str(correct_index)

    user_msg = f"STEM: {stem}\nCORRECT ANSWER: {correct_answer}\nREFERENCE: {quote}"

    response = client.messages.create(
        model=MODEL,
        max_tokens=150,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    return response.content[0].text.strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Max questions to process")
    args = parser.parse_args()

    client = anthropic_client()
    sb = supabase_admin()

    generated = 0
    skipped = 0
    samples = []
    offset = 0

    print("Starting explanation generation...")

    while True:
        rows = fetch_batch(sb, offset)
        if not rows:
            break

        for row in rows:
            if args.limit is not None and generated >= args.limit:
                break

            qid = row["id"]
            try:
                explanation = generate_explanation(client, row)
                sb.table("questions").update({"correct_explanation": explanation}).eq("id", qid).execute()
                generated += 1

                if len(samples) < 3:
                    samples.append({
                        "id": qid,
                        "stem": (row.get("stem") or "")[:80],
                        "explanation": explanation,
                    })

                if generated % 200 == 0:
                    print(f"  Progress: {generated} generated, {skipped} skipped")

            except Exception as e:
                print(f"  ERROR on id={qid}: {e}", file=sys.stderr)
                skipped += 1

        if args.limit is not None and generated >= args.limit:
            break

        if len(rows) < BATCH_SIZE:
            break

        offset += BATCH_SIZE

    print(f"\nDone. Generated: {generated}, Skipped (errors): {skipped}")

    if samples:
        print("\n--- Sample outputs ---")
        for i, s in enumerate(samples, 1):
            print(f"\n[{i}] id={s['id']}")
            print(f"    Stem: {s['stem']}...")
            print(f"    Explanation: {s['explanation']}")


if __name__ == "__main__":
    main()
