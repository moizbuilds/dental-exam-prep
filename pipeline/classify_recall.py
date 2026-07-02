"""Free keyword classifier: recall question text -> blueprint subdomain.

No API. Scores the stem+options against per-subdomain keyword sets and picks the
best match. Falls back to 'Biomedical Sciences' (the largest blueprint line) only
when nothing scores, so every question lands somewhere sensible.
"""
import re

from domain_map import SUBDOMAIN_DOMAIN

# subdomain -> list of keyword regex fragments (matched case-insensitively)
KEYWORDS = {
    "Emergencies": [
        r"anaphylax", r"adrenaline|epinephrine", r"syncope|faint", r"cardiac arrest",
        r"\bcpr\b", r"unconscious", r"hypoglyc", r"seizure|epilep", r"asthma attack",
        r"angina|myocardial|chest pain", r"choking|airway", r"collapse", r"emergency",
        r"basic life support", r"\bbls\b", r"resuscitat",
    ],
    "Pain and Anxiety Management": [
        r"local an[ae]sth", r"lidocaine|lignocaine|articaine|mepivacaine|prilocaine",
        r"\bnerve block\b", r"inferior alveolar", r"sedation", r"nitrous oxide",
        r"\banxiet|anxious|phobi", r"\banalgesi", r"\bgag(ging)? reflex",
        r"vasoconstrictor", r"maximum dose", r"\bpain control",
    ],
    "Periodontics": [
        r"periodont", r"gingiv", r"plaque|calculus", r"probing depth|pocket",
        r"attachment loss|clinical attachment", r"furcation", r"scaling|root planing",
        r"\bbop\b|bleeding on probing", r"recession", r"biofilm", r"junctional epithelium",
        r"periodontal ligament", r"\bgtr\b|guided tissue",
    ],
    "Paediatric Dentistry": [
        r"\bchild|paediatric|pediatric|infant", r"\bpedo\b", r"primary tooth|deciduous",
        r"eruption", r"avulsion|avulsed", r"pulpotomy|pulpectomy", r"\bMIH\b",
        r"fissure sealant", r"space maintainer", r"stainless steel crown",
        r"non[- ]accidental|child abuse", r"\byears? old\b.*\b(child|kid)",
    ],
    "Orthodontics": [
        r"orthodontic", r"malocclusion|class (i{1,3}|1|2|3) (div|malocc|incisor)",
        r"overjet|overbite|open bite|crossbite", r"\bbrace|bracket|archwire",
        r"removable appliance", r"\bcephalometr", r"crowding|spacing",
        r"retainer", r"hass appliance|expander", r"angle.s classification",
    ],
    "Restorative and Endodontics": [
        r"\brct\b|root canal|endodontic", r"\bpulp(itis|al)?\b", r"composite|amalgam",
        r"\bcaries|cavity preparation", r"\bcrown\b|onlay|inlay", r"working length",
        r"\bfile\b|gutta[- ]percha|obturat", r"apical|periapical", r"restorat",
        r"matrix band", r"\bglass ionomer|GIC\b", r"dentin(e)? bonding",
    ],
    "Prosthodontics": [
        r"\bdenture", r"\bRPD\b|removable partial", r"complete denture|edentulous",
        r"\bimplant", r"\babutment", r"\bocclusal (rim|registration)|occlusal record",
        r"impression material|alginate|polyvinyl|elastomer", r"\bpontic|bridge\b",
        r"overdenture", r"\bclasp\b|rest seat|major connector", r"vertical dimension",
        r"\bUCLA\b|prosthe",
    ],
    "Oral Surgery and Oral Medicine": [
        r"extraction|exodontia", r"\bcyst\b|tumou?r|lesion", r"biopsy",
        r"oral cancer|squamous cell|carcinoma", r"ulcer|lichen planus|leukoplakia",
        r"\bfracture\b|trauma", r"impacted|third molar|wisdom", r"osteo(myelitis|necrosis)",
        r"\bMRONJ\b|bisphosphonate|zometa", r"trismus", r"dry socket|alveolar osteitis",
        r"salivary gland|sialaden", r"candidiasis|glossitis|geographic tongue",
        r"\bTMJ|temporomandibular", r"\bzygomatic|maxillofacial",
    ],
    "Patient Assessment": [
        r"radiograph|x-?ray|periapical film|bitewing|panoramic|opg|cbct",
        r"medical history|history taking", r"diagnosis|differential", r"examination",
        r"vitality test|percussion", r"\bcharting", r"clinical sign|symptom",
        r"investigation", r"special test",
    ],
    "Treatment Planning": [
        r"treatment plan", r"sequenc(e|ing) of treatment", r"phase of treatment",
        r"prognosis", r"comprehensive care", r"\breferral\b", r"risk assessment",
    ],
    "Health and Safety": [
        r"steril(is|iz)ation|disinfect|decontaminat", r"infection control|cross[- ]infection",
        r"autoclave", r"\bPPE\b|personal protective", r"sharps|needle[- ]stick",
        r"hand hygiene", r"clinical waste", r"radiation protection|\bALARA\b|dose limit",
        r"hazard|COSHH", r"\baerosol",
    ],
    "Prevention and Population Health": [
        r"fluorid", r"caries risk|caries prevention", r"diet(ary)? (advice|analysis|counsel)",
        r"oral hygiene instruction|tooth ?brushing", r"public health|population",
        r"epidemiolog|prevalence|incidence", r"\bDMFT\b|\bdmft\b", r"sugar|cariogenic",
        r"water fluoridation", r"screening programme",
    ],
    "Biomedical Sciences": [
        r"anatomy|muscle|nerve\b|artery|vein|foramen", r"physiolog", r"histolog|cell\b",
        r"microbiolog|bacteri|virus|fungal", r"pharmacolog|drug interaction|antibiotic",
        r"pathology|inflammation|immun", r"\bgenetic", r"biochem|metabol",
        r"dental material|elastic modulus|setting reaction", r"embryolog|tooth development",
        r"\benzyme|hormone\b", r"blood (group|pressure|clot)",
    ],
    "Evidence-based Practice": [
        r"evidence[- ]based", r"systematic review|meta[- ]analys", r"randomi[sz]ed controlled|\brct\b study",
        r"clinical audit|\baudit\b", r"critical appraisal|\bpico\b", r"cohort|case[- ]control",
        r"confidence interval|p[- ]?value|odds ratio|relative risk", r"sensitivity and specificity",
        r"number needed to treat", r"clinical guideline",
    ],
    "Communication": [
        r"communicat", r"\brapport\b", r"informed consent", r"breaking bad news",
        r"\bempath", r"active listening", r"patient[- ]cent", r"shared decision",
        r"explain.* to the patient", r"reassur", r"motivational interview", r"interrupt",
    ],
    "Professionalism": [
        r"professionalism|professional conduct", r"\bGDC\b|general dental council",
        r"fitness to practise", r"duty of candour", r"\bconfidentialit", r"\bCPD\b",
        r"revalidation", r"complaint", r"\bnegligence\b|duty of care", r"\bprobity\b",
        r"social media|advertis|endorse", r"conflict of interest",
    ],
    "Ethical and Legal": [
        r"\bethic|consent\b|autonomy|beneficence|maleficence|justice",
        r"capacity|gillick|fraser", r"\blegal|law|litigation", r"data protection|\bGDPR\b",
        r"record keeping|documentation", r"safeguard", r"\bDPA\b", r"mental capacity",
    ],
    "Teamworking and Leadership": [
        r"\bteamwork|dental team|team member", r"\bleadership\b|\bdelegat",
        r"skill[- ]mix", r"multidisciplinar", r"dental nurse|hygienist|therapist role",
        r"clinical governance", r"inter[- ]?professional",
    ],
}

COMPILED = {sub: [re.compile(k, re.I) for k in ks] for sub, ks in KEYWORDS.items()}
FALLBACK = "Biomedical Sciences"


def classify(stem: str, options=None):
    text = stem + " " + " ".join(options or [])
    best, best_score = None, 0
    for sub, pats in COMPILED.items():
        s = sum(1 for p in pats if p.search(text))
        if s > best_score:
            best, best_score = sub, s
    sub = best or FALLBACK
    return SUBDOMAIN_DOMAIN[sub], sub, best_score


if __name__ == "__main__":
    import json
    from collections import Counter
    from pathlib import Path
    d = json.load(open(Path(__file__).resolve().parent.parent / "data" / "recall_all.json"))
    for kind in ("mcq4", "answer_only", "image_only"):
        sub = Counter()
        unmatched = 0
        for q in d:
            if q["kind"] != kind:
                continue
            _, s, sc = classify(q["stem"], q["options"])
            if sc == 0:
                unmatched += 1
            sub[s] += 1
        total = sum(sub.values())
        print(f"\n=== {kind} ({total}, unmatched->fallback: {unmatched}) ===")
        for s, n in sub.most_common():
            print(f"  {n:>4}  {s}")
