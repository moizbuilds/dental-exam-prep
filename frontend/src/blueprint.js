// Official MOPH/DHP blueprint. `mock` = 150-question exam proportions;
// `bank` = the x4 = 600 target used to build the question bank.
export const BLUEPRINT = [
  { domain: "Scientific Knowledge", subdomain: "Biomedical Sciences", mock: 30, bank: 120 },
  { domain: "Scientific Knowledge", subdomain: "Evidence-based Practice", mock: 5, bank: 20 },
  { domain: "Clinical Skills", subdomain: "Patient Assessment", mock: 10, bank: 40 },
  { domain: "Clinical Skills", subdomain: "Treatment Planning", mock: 6, bank: 24 },
  { domain: "Clinical Skills", subdomain: "Health and Safety", mock: 6, bank: 24 },
  { domain: "Clinical Skills", subdomain: "Emergencies", mock: 6, bank: 24 },
  { domain: "Clinical Skills", subdomain: "Prevention and Population Health", mock: 6, bank: 24 },
  { domain: "Clinical Skills", subdomain: "Pain and Anxiety Management", mock: 5, bank: 20 },
  { domain: "Clinical Skills", subdomain: "Periodontics", mock: 10, bank: 40 },
  { domain: "Clinical Skills", subdomain: "Paediatric Dentistry", mock: 10, bank: 40 },
  { domain: "Clinical Skills", subdomain: "Orthodontics", mock: 5, bank: 20 },
  { domain: "Clinical Skills", subdomain: "Restorative and Endodontics", mock: 16, bank: 64 },
  { domain: "Clinical Skills", subdomain: "Prosthodontics", mock: 10, bank: 40 },
  { domain: "Clinical Skills", subdomain: "Oral Surgery and Oral Medicine", mock: 10, bank: 40 },
  { domain: "Affective Skills", subdomain: "Communication", mock: 6, bank: 24 },
  { domain: "Affective Skills", subdomain: "Professionalism", mock: 4, bank: 16 },
  { domain: "Affective Skills", subdomain: "Ethical and Legal", mock: 3, bank: 12 },
  { domain: "Affective Skills", subdomain: "Teamworking and Leadership", mock: 2, bank: 8 },
];

export const MOCK_TOTAL = 150;
export const MOCK_DURATION_MIN = 210; // 3.5 hours
export const MOCK_PASS_PCT = 60;

export const DOMAINS = [...new Set(BLUEPRINT.map((b) => b.domain))];

export function subdomainsByDomain(domain) {
  return BLUEPRINT.filter((b) => b.domain === domain);
}
