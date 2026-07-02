import { useState } from "react";
import { supabase } from "../supabaseClient";

const LETTERS = ["A", "B", "C", "D"];

// distractor_rationales are stored in option order, skipping the correct option.
function rationaleFor(optIndex, correctIndex, rationales) {
  if (optIndex === correctIndex) return null;
  const wrongOrder = [0, 1, 2, 3].filter((i) => i !== correctIndex);
  return rationales?.[wrongOrder.indexOf(optIndex)];
}

export default function QuestionCard({
  q, index, total, selectedIndex, onSelect, revealed, userId,
}) {
  const [flagged, setFlagged] = useState(false);
  const options = Array.isArray(q.options) ? q.options : JSON.parse(q.options);
  const rationales = Array.isArray(q.distractor_rationales)
    ? q.distractor_rationales
    : JSON.parse(q.distractor_rationales || "[]");

  async function flag() {
    setFlagged(true);
    await supabase.from("user_flags").upsert(
      { user_id: userId, question_id: q.id, reason: null },
      { onConflict: "user_id,question_id" }
    );
  }

  return (
    <div className="card question">
      <div className="q-head">
        <span className="muted">
          {typeof index === "number" ? `Q${index + 1}${total ? ` / ${total}` : ""}` : ""}
          {"  ·  "}{q.subdomain}
        </span>
        <button className="link flag" onClick={flag} disabled={flagged}>
          {flagged ? "Flagged ✓" : "⚑ Flag"}
        </button>
      </div>

      {q.diagram_svg && (
        <div className="diagram" dangerouslySetInnerHTML={{ __html: q.diagram_svg }} />
      )}

      {q.image_url && (
        <div className="q-image">
          <img src={q.image_url} alt="Clinical figure for this question" loading="lazy" />
        </div>
      )}

      <p className="stem">{q.stem}</p>

      <ul className="options">
        {options.map((opt, i) => {
          const isCorrect = i === q.correct_index;
          const isPicked = i === selectedIndex;
          let cls = "option";
          if (revealed && isCorrect) cls += " correct";
          else if (revealed && isPicked && !isCorrect) cls += " wrong";
          else if (isPicked) cls += " picked";
          return (
            <li key={i}>
              <button className={cls} disabled={revealed}
                      onClick={() => onSelect(i)}>
                <span className="letter">{LETTERS[i]}</span>
                <span>{opt}</span>
              </button>
              {revealed && isCorrect && (
                <div className="rationale">
                  <strong>Correct.</strong>
                  {q.correct_explanation
                    ? ` ${q.correct_explanation}`
                    : q.supporting_quote
                    ? ` ${q.supporting_quote}`
                    : ""}
                </div>
              )}
              {revealed && !isCorrect && rationaleFor(i, q.correct_index, rationales) && (
                <div className="rationale">
                  {rationaleFor(i, q.correct_index, rationales)}
                </div>
              )}
            </li>
          );
        })}
      </ul>

      {revealed && q.source_book && (
        <div className="source">
          <details>
            <summary>Source &amp; supporting evidence</summary>
            <p className="quote">“{q.supporting_quote}”</p>
            <p className="cite">
              {q.source_book}
              {q.source_edition ? `, ${q.source_edition} ed.` : ""}
              {q.source_page_or_section ? ` — ${q.source_page_or_section}` : ""}
            </p>
          </details>
        </div>
      )}
    </div>
  );
}
