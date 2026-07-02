import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthProvider";
import { fetchCounts, fetchPractice, recordAnswer } from "../lib/queries";
import TopicSelector from "../components/TopicSelector";
import QuestionCard from "../components/QuestionCard";

export default function Practice() {
  const { user } = useAuth();
  const [counts, setCounts] = useState({});
  const [subdomain, setSubdomain] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [idx, setIdx] = useState(0);
  const [selected, setSelected] = useState(null);
  const [revealed, setRevealed] = useState(false);
  const [score, setScore] = useState({ right: 0, total: 0 });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchCounts().then(setCounts).catch(console.error);
  }, []);

  async function start(sub) {
    setLoading(true);
    setSubdomain(sub);
    const qs = await fetchPractice(sub, 20);
    setQuestions(qs);
    setIdx(0);
    setSelected(null);
    setRevealed(false);
    setScore({ right: 0, total: 0 });
    setLoading(false);
  }

  async function choose(i) {
    if (revealed) return;
    setSelected(i);
    setRevealed(true);
    const q = questions[idx];
    const correct = i === q.correct_index;
    setScore((s) => ({ right: s.right + (correct ? 1 : 0), total: s.total + 1 }));
    if (user) recordAnswer(user.id, q.id, correct).catch(console.error);
  }

  function next() {
    setSelected(null);
    setRevealed(false);
    setIdx((i) => i + 1);
  }

  function reset() {
    setSubdomain(null);
    setQuestions([]);
  }

  if (!subdomain) {
    return (
      <div className="page">
        <h2>Practice</h2>
        <p className="muted">Pick a topic. Immediate feedback with source citations.</p>
        <TopicSelector counts={counts} onPick={start} />
      </div>
    );
  }

  if (loading) return <div className="page"><p className="muted">Loading…</p></div>;

  if (questions.length === 0) {
    return (
      <div className="page">
        <p className="muted">No questions available for {subdomain} yet.</p>
        <button className="btn" onClick={reset}>← Back to topics</button>
      </div>
    );
  }

  const done = idx >= questions.length;
  if (done) {
    const pct = Math.round((score.right / score.total) * 100);
    return (
      <div className="page">
        <div className="card result">
          <h2>{subdomain}</h2>
          <p className="big-score">{score.right} / {score.total}</p>
          <p className="muted">{pct}% correct</p>
          <div className="row">
            <button className="btn primary" onClick={() => start(subdomain)}>Practice again</button>
            <button className="btn" onClick={reset}>Choose another topic</button>
          </div>
        </div>
      </div>
    );
  }

  const q = questions[idx];
  return (
    <div className="page">
      <div className="practice-bar">
        <button className="link" onClick={reset}>← Topics</button>
        <span className="muted">Score: {score.right}/{score.total}</span>
      </div>
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
            {idx + 1 === questions.length ? "Finish" : "Next question →"}
          </button>
        </div>
      )}
    </div>
  );
}
