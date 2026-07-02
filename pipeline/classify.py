"""Content-quality classification for ingested chunks.

Grounding (a passage supports the answer) is necessary but not sufficient for an
exam-worthy question: a verbatim-correct quote can still come from a preface or a
reference list. This module flags low-value chunks so generation skips them, and
scores clinical relevance so generation prefers dosing/management/diagnosis text.
"""
import re

# Front/back matter and non-teaching material.
FRONTMATTER_KW = re.compile(
    r"\b(table of contents|foreword|preface|dedicat\w+|acknowledg\w+|"
    r"copyright|all rights reserved|library of congress|isbn\b|"
    r"contributors?\b|list of (figures|tables)|about the (author|editor))",
    re.IGNORECASE,
)

# Academic citation fragments — dense in reference lists / bibliographies.
CITATION = re.compile(
    r"(et al\.?|doi:|\b\d{4};\s*\d+|\(\d{4}\)|\bpp?\.\s*\d+|"
    r";\s*\d+\(\d+\):\d+|\bvol\.\s*\d+)",
    re.IGNORECASE,
)

# Table-of-contents / index dot leaders ("Anaphylaxis ........ 145").
DOTTED_LEADER = re.compile(r"\.{4,}\s*\d+")

# Positive clinical signal: doses, drugs, emergency management vocabulary.
CLINICAL_SIGNAL = re.compile(
    r"(\b\d+\s?(mg|mcg|µg|ml|mg/kg|units?|mmol|mmhg|%)\b|"
    r"\bdose|\bdosage|administer|inject|contraindicat|indication|"
    r"signs? and symptoms|management|treatment|diagnos|syndrome|therapy|"
    r"adrenaline|epinephrine|glucose|oxygen|airway|seizure|anaphylax|"
    r"hypoglyc|syncope|asthma|angina|infarction|cardiac arrest|\bcpr\b|"
    r"compressions|blood pressure|allerg|sedation|anaesthe|anesthe|"
    r"prophylax|aetiolog|etiolog|pathophysiolog|complication)",
    re.IGNORECASE,
)


def classify(text: str, page_start: int, max_page: int):
    """Return (excluded:int, reason:str|None, clinical_score:int)."""
    score = len(CLINICAL_SIGNAL.findall(text))
    n_cite = len(CITATION.findall(text))
    n_leader = len(DOTTED_LEADER.findall(text))
    early = page_start <= max(10, int(0.03 * max_page)) if max_page else page_start <= 10
    late = page_start >= int(0.96 * max_page) if max_page else False

    if FRONTMATTER_KW.search(text) and (early or late):
        return 1, "front_or_back_matter", score
    if n_leader >= 3:
        return 1, "toc_or_index", score
    # reference list / bibliography: high citation density. Checked regardless of
    # clinical_score, because citations to clinical papers ("...anaphylaxis...")
    # inflate the clinical signal even though the chunk is just a bibliography.
    cite_density = n_cite / max(1, len(text) / 1000)   # citations per 1000 chars
    if n_cite >= 6 or cite_density >= 2.5:
        return 1, "reference_list", score
    # narrative intro/history/epidemiology with no clinical teaching value
    if score == 0 and len(text) < 1600:
        return 1, "low_clinical_value", score
    return 0, None, score
