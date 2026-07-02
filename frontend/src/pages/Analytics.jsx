import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthProvider";
import { supabase } from "../supabaseClient";
import { fetchProgress } from "../lib/queries";
import { BLUEPRINT, DOMAINS, MOCK_PASS_PCT } from "../blueprint";

export default function Analytics() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);

  useEffect(() => {
    if (!user) return;
    (async () => {
      const progress = await fetchProgress(user.id);
      if (progress.length === 0) { setStats({ empty: true }); return; }

      const ids = [...new Set(progress.map((p) => p.question_id))];
      const { data: qs } = await supabase
        .from("questions")
        .select("id,domain,subdomain")
        .in("id", ids);
      const meta = {};
      for (const q of qs || []) meta[q.id] = q;

      const bySub = {};
      let right = 0;
      for (const p of progress) {
        const m = meta[p.question_id];
        if (!m) continue;
        const s = (bySub[m.subdomain] ||= { domain: m.domain, right: 0, total: 0 });
        s.total++;
        if (p.answered_correctly) { s.right++; right++; }
      }
      setStats({
        total: progress.length,
        right,
        pct: Math.round((right / progress.length) * 100),
        bySub,
      });
    })().catch(console.error);
  }, [user]);

  if (!stats) return <div className="page"><p className="muted">Loading…</p></div>;
  if (stats.empty)
    return (
      <div className="page">
        <h2>Analytics</h2>
        <p className="muted">No answers recorded yet. Do some practice to see your performance.</p>
      </div>
    );

  return (
    <div className="page">
      <h2>Analytics</h2>
      <div className="card result">
        <p className="big-score">{stats.pct}%</p>
        <p className="muted">{stats.right} / {stats.total} answered correctly overall</p>
      </div>

      {DOMAINS.map((domain) => {
        const rows = BLUEPRINT.filter((b) => b.domain === domain);
        const seen = rows.filter((b) => stats.bySub[b.subdomain]);
        if (seen.length === 0) return null;
        return (
          <div key={domain} className="card">
            <h3>{domain}</h3>
            {seen.map((b) => {
              const s = stats.bySub[b.subdomain];
              const pct = Math.round((s.right / s.total) * 100);
              const weak = pct < MOCK_PASS_PCT;
              return (
                <div key={b.subdomain} className="bar-row">
                  <span className="bar-label">{b.subdomain}</span>
                  <div className="bar">
                    <div className={`bar-fill ${weak ? "weak" : ""}`} style={{ width: `${pct}%` }} />
                  </div>
                  <span className="bar-val">{pct}% <span className="muted">({s.right}/{s.total})</span></span>
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}
