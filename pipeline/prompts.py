"""The two embedded prompts, verbatim from the project spec, plus the JSON
contract the generator must return."""

GENERATION_SYSTEM = (
    "You are given one passage from {book}{edition}. Write one single-best-answer "
    "MCQ with 4 options answerable using only this passage. Return: the correct "
    "option, an explanation of why it's correct, a one-line reason each wrong "
    "option is wrong, and the exact sentence from the passage justifying the "
    "answer. If the passage cannot support a defensible question, return null. "
    "Do not rely on outside knowledge."
)

# Strict JSON contract appended to the generation request.
GENERATION_FORMAT = """
Return ONLY a JSON object (no markdown, no prose) with this exact shape, or the
literal value null if the passage cannot support a defensible single-best-answer
question:

{
  "stem": "the question stem",
  "options": ["A", "B", "C", "D"],
  "correct_index": 0,
  "correct_explanation": "why the correct option is right, grounded in the passage",
  "distractor_rationales": [
    "one line: why the first WRONG option is wrong",
    "one line: why the second WRONG option is wrong",
    "one line: why the third WRONG option is wrong"
  ],
  "supporting_quote": "the exact sentence(s) copied verbatim from the passage that justify the correct answer",
  "visual_type": "none | text_vignette",
  "diagram_svg": null
}

Rules:
- exactly 4 options; correct_index is 0-3 and points to the correct option.
- distractor_rationales has exactly 3 entries, one per wrong option (in option order, skipping the correct one).
- supporting_quote MUST be copied verbatim from the passage.
- If the passage describes a figure/radiograph the reader cannot see, rewrite the
  scenario as a self-contained text vignette and set "visual_type":"text_vignette".
  Never refer to a figure the reader cannot see. Never describe the book's image
  as if shown.
- Return null if the passage is not teaching clinical/scientific content: e.g. a
  reference list or bibliography, an author/contributor list, a table of contents
  or index, a preface/foreword/dedication, or acknowledgements. NEVER write a
  question about who authored a cited paper, a citation, a page number, or other
  bibliographic trivia. Test clinical knowledge, not metadata.
- Output null (not an object) if no defensible question is possible.
"""

VERIFICATION_SYSTEM = (
    "Here is a question and a source passage. Quote the sentence(s) in the passage "
    "supporting the marked correct answer. If none do, return FAIL."
)

VERIFICATION_FORMAT = """
Return ONLY a JSON object (no markdown):
{
  "verdict": "PASS" or "FAIL",
  "supporting_sentences": "the exact sentence(s) from the passage that support the marked correct answer, or empty string if FAIL"
}
A PASS requires that the passage genuinely supports the marked correct answer and
that the other options are not equally supported. When in doubt, FAIL.
"""
