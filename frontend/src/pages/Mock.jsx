import { useEffect, useRef, useState } from "react";
import { useAuth } from "../auth/AuthProvider";
import { fetchMock, recordAnswer } from "../lib/queries";
import {
  BLUEPRINT, MOCK_TOTAL, MOCK_DURATION_MIN, MOCK_PASS_PCT,
} from "../blueprint";
import QuestionCard from "../components/QuestionCard";

function fmt(secs) {
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export default function Mock() {
  const { user } = useAuth();
  const [phase, setPhase] = useState("intro"); // intro | running | done
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({}); // idx -> chosen option
  const [idx, setIdx] = useState(0);
  const [remaining, setRemaining] = useState(MOCK_DURATION_MIN * 60);
  const [loading, setLoading] = useState(false);
  const timer = useRef(null);

  useEffect(() => () => clearInterval(timer.current), []);

  async function begin() {
    setLoading(true);
    const qs = await fetchMock(BLUEPRINT);
    setQuestions(qs);
    setAnswers({});
    setIdx(0);
    setRemaining(MOCK_DURATION_MIN * 60);
    setPhase("running");
    setLoading(false);
    timer.current = setInterval(() => {
      setRemaining((r) => {
        if (r <= 1) { clearInterval(timer.current); finish(); return 0; }
        return r - 1;
      });
    }, 1000);
  }

  function pick(i) {
    setAnswers((a) => ({ ...a, [idx]: i }));
  }

  function finish() {
    clearInterval(timer.current);
    setPhase("done");
    if (user) {
      questions.forEach((q, i) => {
        const chosen = answers[i];
        if (chosen !== undefined)
          recordAnswer(user.id, q.id, chosen === q.correct_index).catch(console.error);
      });
    }
  }

  if (phase === "intro") {
    return (
      <div className="page">
        <div className="card">
          <h2>Timed Mock Exam</h2>
          <ul className="facts">
            <li><strong>{MOCK_TOTAL}</strong> questions in official blueprint proportions</li>
            <li><strong>{MOCK_DURATION_MIN / 60} hours</strong> ({MOCK_DURATION_MIN} min)</li>
            <li>Pass mark <strong>{MOCK_PASS_PCT}%</strong></li>
            <li>No feedback until you submit — just like the real exam</li>
          </ul>
          <button className="btn primary" disabled={loading} onClick={begin}>
            {loading ? "Assembling exam…" : "Start mock exam"}
          </button>
        </div>
      </div>
    );
  }

  if (phase === "done") {
    const answered = Object.keys(answers).length;
    let right = 0;
    questions.forEach((q, i) => { if (answers[i] === q.correct_index) right++; });
    const pct = Math.round((right / questions.length) * 100);
    const passed = pct >= MOCK_PASS_PCT;

    // Per-domain breakdown
    const byDomain = {};
    questions.forEach((q, i) => {
      const d = (byDomain[q.domain] ||= { right: 0, total: 0 });
      d.total++;
      if (answers[i] === q.correct_index) d.right++;
    });

    return (
      <div className="page">
        <div className={`card result ${passed ? "pass" : "fail"}`}>
          <h2>{passed ? "PASS" : "Below pass mark"}</h2>
          <p className="big-score">{pct}%</p>
          <p className="muted">{right} / {questions.length} correct · {answered} answered · pass mark {MOCK_PASS_PCT}%</p>
        </div>
        <div className="card">
          <h3>By domain</h3>
          {Object.entries(byDomain).map(([d, v]) => (
            <div key={d} className="bar-row">
              <span className="bar-label">{d}</span>
              <div className="bar"><div className="bar-fill" style={{ width: `${(v.right / v.total) * 100}%` }} /></div>
              <span className="bar-val">{Math.round((v.right / v.total) * 100)}%</span>
            </div>
          ))}
        </div>
        <div className="row">
          <button className="btn primary" onClick={() => setPhase("intro")}>New mock exam</button>
        </div>
      </div>
    );
  }

  // running
  const q = questions[idx];
  const low = remaining < 600;
  return (
    <div className="page mock">
      <div className="mock-bar">
        <span className="muted">Q {idx + 1} / {questions.length}</span>
        <span className={`timer ${low ? "low" : ""}`}>{fmt(remaining)}</span>
        <button className="btn small danger" onClick={finish}>Submit exam</button>
      </div>

      <QuestionCard
        q={q}
        index={idx}
        total={questions.length}
        selectedIndex={answers[idx] ?? null}
        onSelect={pick}
        revealed={false}
        userId={user?.id}
      />

      <div className="row spread">
        <button className="btn" disabled={idx === 0} onClick={() => setIdx((i) => i - 1)}>← Prev</button>
        {idx + 1 < questions.length
          ? <button className="btn primary" onClick={() => setIdx((i) => i + 1)}>Next →</button>
          : <button className="btn primary" onClick={finish}>Review &amp; submit</button>}
      </div>

      <div className="grid-nav">
        {questions.map((_, i) => (
          <button
            key={i}
            className={`grid-dot ${i in answers ? "answered" : ""} ${i === idx ? "current" : ""}`}
            onClick={() => setIdx(i)}
          >{i + 1}</button>
        ))}
      </div>
    </div>
  );
}
