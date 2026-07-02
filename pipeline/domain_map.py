"""Blueprint definition and textbook -> blueprint-subdomain mapping.

The examiners' assigned textbook defines the scope for each blueprint line, so
generation only ever pulls chunks tagged with the matching subdomain.

BLUEPRINT counts are the official 150-question proportions scaled x4 = 600.
"""

# (domain, subdomain, target_count) — sums to 600.
BLUEPRINT = [
    ("Scientific Knowledge", "Biomedical Sciences", 120),
    ("Scientific Knowledge", "Evidence-based Practice", 20),
    ("Clinical Skills", "Patient Assessment", 40),
    ("Clinical Skills", "Treatment Planning", 24),
    ("Clinical Skills", "Health and Safety", 24),
    ("Clinical Skills", "Emergencies", 24),
    ("Clinical Skills", "Prevention and Population Health", 24),
    ("Clinical Skills", "Pain and Anxiety Management", 20),
    ("Clinical Skills", "Periodontics", 40),
    ("Clinical Skills", "Paediatric Dentistry", 40),
    ("Clinical Skills", "Orthodontics", 20),
    ("Clinical Skills", "Restorative and Endodontics", 64),
    ("Clinical Skills", "Prosthodontics", 40),
    ("Clinical Skills", "Oral Surgery and Oral Medicine", 40),
    ("Affective Skills", "Communication", 24),
    ("Affective Skills", "Professionalism", 16),
    ("Affective Skills", "Ethical and Legal", 12),
    ("Affective Skills", "Teamworking and Leadership", 8),
]

SUBDOMAIN_DOMAIN = {sub: dom for dom, sub, _ in BLUEPRINT}
TARGET_COUNTS = {sub: n for _, sub, n in BLUEPRINT}

# Each entry: (filename_substring, domain, subdomain, edition_or_None).
# Matched case-insensitively against the PDF filename. First match wins, so
# order more specific substrings before broader ones.
BOOK_MAP = [
    # ── Scientific Knowledge / Biomedical Sciences ──
    ("Anatomy for dental students",        "Scientific Knowledge", "Biomedical Sciences", "4th"),
    ("Oral Anatomy, Histology",            "Scientific Knowledge", "Biomedical Sciences", "5th"),
    ("Essential physiology for dental",     "Scientific Knowledge", "Biomedical Sciences", None),
    ("Vander",                              "Scientific Knowledge", "Biomedical Sciences", None),
    ("Soames",                              "Scientific Knowledge", "Biomedical Sciences", "3rd"),
    ("Systemic Pathology",                  "Scientific Knowledge", "Biomedical Sciences", None),
    ("Clinical Dental Pharmacology",        "Scientific Knowledge", "Biomedical Sciences", None),
    ("Applied dental materials",            "Scientific Knowledge", "Biomedical Sciences", "9th"),

    # ── Clinical Skills / Patient Assessment ──
    ("Odells Clinical Problem Solving",     "Clinical Skills", "Patient Assessment", "4th"),
    ("Diagnosis and Treatment Planning",    "Clinical Skills", "Patient Assessment", "3rd"),
    ("Essentials of Dental Radiography",    "Clinical Skills", "Patient Assessment", None),
    ("Dentistry at a Glance",               "Clinical Skills", "Patient Assessment", None),

    # ── Treatment Planning ──
    ("TREATMENT PLANNING IN PRIMARY",       "Clinical Skills", "Treatment Planning", None),
    ("Integrated_dental_treatment",         "Clinical Skills", "Treatment Planning", None),

    # ── Emergencies ──
    ("Medical Emergencies in the Dental",   "Clinical Skills", "Emergencies", "2022"),

    # ── Prevention and Population Health ──
    ("The Prevention of Oral Disease",      "Clinical Skills", "Prevention and Population Health", None),

    # ── Pain and Anxiety Management ──
    ("Handbook of Local Anesthesia",        "Clinical Skills", "Pain and Anxiety Management", None),

    # ── Periodontics ──
    ("Guide to periodontics",               "Clinical Skills", "Periodontics", None),

    # ── Paediatric Dentistry ──
    ("Paediatric dentistry",                "Clinical Skills", "Paediatric Dentistry", None),

    # ── Orthodontics ──
    ("Orthodontic Notes",                   "Clinical Skills", "Orthodontics", None),

    # ── Restorative and Endodontics ──
    ("Pickards Manual of Operative",        "Clinical Skills", "Restorative and Endodontics", None),
    ("Restorative Dentistry (A",            "Clinical Skills", "Restorative and Endodontics", None),
    ("Endodontics E-Book Principles",       "Clinical Skills", "Restorative and Endodontics", None),
    ("Hartys Endodontics",                  "Clinical Skills", "Restorative and Endodontics", "7th"),
    ("Master Dentistry Volume Two",         "Clinical Skills", "Restorative and Endodontics", None),

    # ── Prosthodontics ──
    ("complete denture prosthetics",        "Clinical Skills", "Prosthodontics", None),
    ("Removable Partial Denture Design",    "Clinical Skills", "Prosthodontics", None),
    ("Treatment of edentulous patients",    "Clinical Skills", "Prosthodontics", None),
    ("Planning and Making Crowns",          "Clinical Skills", "Prosthodontics", "4th"),

    # ── Oral Surgery and Oral Medicine ──
    ("Oral and Maxillofacial Surgery",      "Clinical Skills", "Oral Surgery and Oral Medicine", None),
    ("Master Dentistry Volume One",         "Clinical Skills", "Oral Surgery and Oral Medicine", None),
    ("clinical guide to oral medicine",     "Clinical Skills", "Oral Surgery and Oral Medicine", None),
    ("Burkets Oral Medicine",               "Clinical Skills", "Oral Surgery and Oral Medicine", None),
    ("Scullys Medical Problems",            "Clinical Skills", "Oral Surgery and Oral Medicine", "7th"),
    ("Handbook of Medical Problems",        "Clinical Skills", "Oral Surgery and Oral Medicine", None),

    # ── Affective Skills / Ethical and Legal ──
    ("Dental Ethics And Laws",              "Affective Skills", "Ethical and Legal", None),

    # ── Broad fallback: Oxford handbook covers H&S, EBP, comms, teamworking ──
    # tagged Health and Safety as primary; sparse affective/EBP subdomains are
    # routed by keyword at generation time (see KEYWORD_ROUTES).
    ("Oxford handbook of clinical dentistry", "Clinical Skills", "Health and Safety", None),
]

# Subdomains with no dedicated assigned textbook. Until a source is mapped these
# stay at 0 generated questions (refusal is correct — no source, no question).
# Handled later via keyword routing through the Oxford handbook + ethics book.
UNSOURCED_SUBDOMAINS = {
    "Evidence-based Practice",
    "Communication",
    "Professionalism",
    "Teamworking and Leadership",
}


def map_filename(filename: str):
    """Return (domain, subdomain, edition) for a PDF filename, or None."""
    low = filename.lower()
    for sub, dom, subd, edition in (
        (s, d, sd, e) for s, d, sd, e in BOOK_MAP
    ):
        if sub.lower() in low:
            return dom, subd, edition
    return None
