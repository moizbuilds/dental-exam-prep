import { DOMAINS, subdomainsByDomain } from "../blueprint";

export default function TopicSelector({ counts, onPick }) {
  return (
    <div className="topics">
      {DOMAINS.map((domain) => (
        <div key={domain} className="topic-domain">
          <h3>{domain}</h3>
          <div className="topic-grid">
            {subdomainsByDomain(domain).map((b) => {
              const n = counts[b.subdomain] || 0;
              return (
                <button
                  key={b.subdomain}
                  className="topic"
                  disabled={n === 0}
                  onClick={() => onPick(b.subdomain)}
                >
                  <span className="topic-name">{b.subdomain}</span>
                  <span className="topic-count">{n} q</span>
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
