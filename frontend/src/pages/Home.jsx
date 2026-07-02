import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchCounts } from "../lib/queries";
import { BLUEPRINT } from "../blueprint";

export default function Home() {
  const [total, setTotal] = useState(null);

  useEffect(() => {
    fetchCounts()
      .then((c) => setTotal(Object.values(c).reduce((a, b) => a + b, 0)))
      .catch(console.error);
  }, []);

  const target = BLUEPRINT.reduce((a, b) => a + b.bank, 0);

  return (
    <div className="page home">
      <div className="card hero-card">
        <h1>Dental Qualifying Exam Prep</h1>
        <p className="muted">
          MOPH/DHP National General Dental Qualifying Examination. Every question
          is traced to a passage in a real textbook — no source, no question.
        </p>
        <p className="bank-count">
          {total === null ? "…" : total} <span className="muted">verified questions in the bank</span>
          {total !== null && <span className="muted"> · target {target}</span>}
        </p>
      </div>

      <div className="tiles">
        <Link to="/practice" className="tile">
          <h3>Practice</h3>
          <p>Topic-by-topic with instant feedback, rationales, and citations.</p>
        </Link>
        <Link to="/mock" className="tile">
          <h3>Timed Mock</h3>
          <p>150 questions, blueprint proportions, 3.5 hours, 60% to pass.</p>
        </Link>
        <Link to="/review" className="tile">
          <h3>Review</h3>
          <p>Spaced repetition of the questions you got wrong.</p>
        </Link>
        <Link to="/analytics" className="tile">
          <h3>Analytics</h3>
          <p>See your strengths and weak domains over time.</p>
        </Link>
      </div>
    </div>
  );
}
