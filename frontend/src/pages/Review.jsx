import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthProvider";
import { fetchReviewQueue, recordAnswer } from "../lib/queries";
import QuestionCard from "../components/QuestionCard";

export default function Review() {
  const { user } = useAuth();
  const [questions, setQuestions] = useState(null);
  const [idx, setIdx] = useState(0);
  const [selected, setSelected] = useState(null);
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    if (!user) return;
    fetchReviewQueue(user.id, 20).then(setQuestions).catch(console.error);
  }, [user]);

  if (!questions) return <div className="page"><p className="muted">Loading…</p></div>;

  if (questions.length === 0)
    return (
      <div className="page">
        <h2>Review</h2>
        <p className="muted">Nothing to review — you have no outstanding incorrect answers. Nice.</p>
      </div>
    );

  function choose(i) {
    if (revealed) return;
    setSelected(i);
    setRevealed(true);
    const q = questions[idx];
    if (user) recordAnswer(user.id, q.id, i === q.correct_index).catch(console.error);
  }

  function next() {
    setSelected(null);
    setRevealed(false);
    setIdx((i) => i + 1);
  }

  if (idx >= questions.length)
    return (
      <div className="page">
        <div className="card result">
          <h2>Review complete</h2>
          <p className="muted">You worked through {questions.length} previously-missed questions.</p>
          <button className="btn primary" onClick={() => window.location.reload()}>Reload queue</button>
        </div>
      </div>
    );

  const q = questions[idx];
  return (
    <div className="page">
      <h2>Review missed questions</h2>
      <p className="muted">Questions you last answered incorrectly. Get them right to clear them.</p>
      <QuestionCard
        q={q}
        index={idx}
        total={questions.length}
        selectedIndex={selected}
        onSelect={choose}
        revealed={revealed}
        userId={user?.id}
      />
      {revealed && (
        <div className="row end">
          <button className="btn primary" onClick={next}>
            {idx + 1 === questions.length ? "Finish" : "Next →"}
          </button>
        </div>
      )}
    </div>
  );
}
