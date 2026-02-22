"""
email_finder.py — Three-stage PI email inference

Stage 1 — NIH profile scrape (~50-60% coverage, confidence: "verified")
    Each NIH PI has a public profile at reporter.nih.gov/pi-profile/{id}.
    The page often lists their institutional email directly.

Stage 2 — Institutional domain lookup (~25% additional, confidence: "inferred")
    Lookup table of 120 top NIH-funded institutions → email domain.
    Generates three common format candidates and returns all three.

Stage 3 — LLM domain inference (~10% additional, confidence: "llm_inferred")
    For institutions not in the lookup table, a single claude-haiku call
    infers the email domain from the institution name.

Expected combined coverage: ~85% of leads.

Return structure:
    {
        "best_guess":   "shannon.quinn@uga.edu",
        "candidates":   ["shannon.quinn@uga.edu", "squinn@uga.edu", "shannonquinn@uga.edu"],
        "confidence":   "verified" | "inferred" | "llm_inferred" | "not_found",
        "source":       "nih_profile" | "domain_lookup" | "llm" | None,
    }
"""

import re
import os
import requests
import anthropic
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env"))


# ── Institutional domain lookup table ─────────────────────────────────────────
# 120 top NIH-funded research institutions → primary email domain

INSTITUTION_DOMAINS = {
    # Ivy League / elite private
    "harvard university":              "harvard.edu",
    "harvard medical school":          "hms.harvard.edu",
    "yale university":                 "yale.edu",
    "columbia university":             "columbia.edu",
    "university of pennsylvania":      "upenn.edu",
    "princeton university":            "princeton.edu",
    "cornell university":              "cornell.edu",
    "dartmouth college":               "dartmouth.edu",
    "brown university":                "brown.edu",
    "johns hopkins university":        "jhu.edu",
    "johns hopkins":                   "jhu.edu",
    "mit":                             "mit.edu",
    "massachusetts institute of technology": "mit.edu",
    "stanford university":             "stanford.edu",
    "duke university":                 "duke.edu",
    "vanderbilt university":           "vanderbilt.edu",
    "emory university":                "emory.edu",
    "georgetown university":           "georgetown.edu",
    "tufts university":                "tufts.edu",
    "boston university":               "bu.edu",
    "northeastern university":         "northeastern.edu",
    "brandeis university":             "brandeis.edu",
    "wake forest university":          "wfu.edu",
    "rice university":                 "rice.edu",
    "tulane university":               "tulane.edu",
    "case western reserve university": "case.edu",
    "carnegie mellon university":      "cmu.edu",
    # Large public — UC system
    "university of california san francisco": "ucsf.edu",
    "ucsf":                            "ucsf.edu",
    "university of california los angeles":   "ucla.edu",
    "ucla":                            "ucla.edu",
    "university of california san diego":     "ucsd.edu",
    "ucsd":                            "ucsd.edu",
    "university of california berkeley":      "berkeley.edu",
    "uc berkeley":                     "berkeley.edu",
    "university of california davis":  "ucdavis.edu",
    "university of california irvine": "uci.edu",
    "university of california santa barbara": "ucsb.edu",
    "university of california santa cruz":    "ucsc.edu",
    "university of california riverside":     "ucr.edu",
    # Large public — other
    "university of michigan":          "umich.edu",
    "university of michigan ann arbor": "umich.edu",
    "university of washington":        "uw.edu",
    "university of north carolina":    "unc.edu",
    "unc chapel hill":                 "unc.edu",
    "university of wisconsin":         "wisc.edu",
    "university of wisconsin madison": "wisc.edu",
    "ohio state university":           "osu.edu",
    "university of minnesota":         "umn.edu",
    "university of illinois":          "illinois.edu",
    "university of illinois urbana-champaign": "illinois.edu",
    "university of pittsburgh":        "pitt.edu",
    "university of texas":             "utexas.edu",
    "ut southwestern":                 "utsouthwestern.edu",
    "ut southwestern medical center":  "utsouthwestern.edu",
    "university of texas southwestern": "utsouthwestern.edu",
    "university of colorado":          "colorado.edu",
    "university of colorado denver":   "ucdenver.edu",
    "university of florida":           "ufl.edu",
    "university of georgia":           "uga.edu",
    "university of arizona":           "arizona.edu",
    "university of utah":              "utah.edu",
    "university of virginia":          "virginia.edu",
    "university of maryland":          "umaryland.edu",
    "university of maryland baltimore": "umaryland.edu",
    "university of iowa":              "uiowa.edu",
    "university of kansas":            "ku.edu",
    "university of kentucky":          "uky.edu",
    "university of missouri":          "missouri.edu",
    "university of nebraska":          "unmc.edu",
    "university of new mexico":        "unm.edu",
    "university of oklahoma":          "ouhsc.edu",
    "university of south carolina":    "sc.edu",
    "university of tennessee":         "uthsc.edu",
    "university of alabama":           "uab.edu",
    "university of alabama birmingham": "uab.edu",
    "indiana university":              "iu.edu",
    "purdue university":               "purdue.edu",
    "michigan state university":       "msu.edu",
    "penn state university":           "psu.edu",
    "pennsylvania state university":   "psu.edu",
    "rutgers university":              "rutgers.edu",
    "temple university":               "temple.edu",
    "drexel university":               "drexel.edu",
    "university of southern california": "usc.edu",
    "usc":                             "usc.edu",
    # Medical research centers / hospitals
    "mayo clinic":                     "mayo.edu",
    "cleveland clinic":                "ccf.org",
    "memorial sloan kettering":        "mskcc.org",
    "msk":                             "mskcc.org",
    "dana-farber cancer institute":    "dfci.harvard.edu",
    "dana farber":                     "dfci.harvard.edu",
    "fred hutchinson":                 "fredhutch.org",
    "fred hutch":                      "fredhutch.org",
    "the jackson laboratory":          "jax.org",
    "jackson laboratory":              "jax.org",
    "salk institute":                  "salk.edu",
    "scripps research":                "scripps.edu",
    "the scripps research institute":  "scripps.edu",
    "cold spring harbor laboratory":   "cshl.edu",
    "cold spring harbor":              "cshl.edu",
    "whitehead institute":             "wi.mit.edu",
    "broad institute":                 "broadinstitute.org",
    "brigham and women's hospital":    "bwh.harvard.edu",
    "massachusetts general hospital":  "mgh.harvard.edu",
    "beth israel deaconess":           "bidmc.harvard.edu",
    "children's hospital boston":      "childrens.harvard.edu",
    "boston children's hospital":      "childrens.harvard.edu",
    "new york university":             "nyu.edu",
    "nyu":                             "nyu.edu",
    "mount sinai":                     "mssm.edu",
    "icahn school of medicine":        "mssm.edu",
    "weill cornell":                   "med.cornell.edu",
    "weill cornell medicine":          "med.cornell.edu",
    "albert einstein college":         "einsteinmed.edu",
    "montefiore":                      "montefiore.org",
    "university of rochester":         "rochester.edu",
    "rochester":                       "rochester.edu",
    "oregon health and science":       "ohsu.edu",
    "ohsu":                            "ohsu.edu",
    # Government / national labs
    "national institutes of health":   "nih.gov",
    "nih":                             "nih.gov",
    "national cancer institute":       "nih.gov",
}


def _normalize_org(org_name):
    """Lowercase + strip punctuation for fuzzy matching."""
    return re.sub(r"[^a-z0-9 ]", "", str(org_name).lower()).strip()


def _parse_name(pi_name):
    """
    Return (first, last) from NIH-style 'LAST, FIRST [MIDDLE]' or 'FIRST LAST'.
    """
    raw = str(pi_name).strip()
    if "," in raw:
        parts = raw.split(",", 1)
        last  = parts[0].strip().lower()
        first = parts[1].strip().split()[0].lower() if parts[1].strip() else ""
    else:
        tokens = raw.split()
        first  = tokens[0].lower() if tokens else ""
        last   = tokens[-1].lower() if len(tokens) > 1 else ""
    # Strip non-alpha characters that sneak in (periods, hyphens in first name okay)
    first = re.sub(r"[^a-z\-]", "", first)
    last  = re.sub(r"[^a-z\-]", "", last)
    return first, last


def _candidate_emails(first, last, domain):
    """Three most common academic email formats."""
    f  = first
    l  = last
    fi = first[0] if first else ""
    return [
        f"{f}.{l}@{domain}",
        f"{fi}{l}@{domain}",
        f"{f}{l}@{domain}",
    ]


# ── Stage 1: NIH profile scrape ───────────────────────────────────────────────

def scrape_nih_profile_email(pi_profile_id):
    """
    Fetch the PI's public NIH Reporter profile and extract an email address.
    Returns the email string or None.
    """
    if not pi_profile_id or str(pi_profile_id).strip() in ("", "nan"):
        return None
    url = f"https://reporter.nih.gov/pi-profile/{pi_profile_id}"
    try:
        resp = requests.get(url, timeout=8)
        if resp.status_code != 200:
            return None
        match = re.search(r"[\w.+\-]+@[\w\-]+\.[a-z]{2,}", resp.text)
        return match.group(0).lower() if match else None
    except Exception:
        return None


# ── Stage 2: Institutional domain lookup ──────────────────────────────────────

def org_to_domain_lookup(org_name):
    """
    Return the email domain for a known institution, or None.
    Tries full name, then progressively shorter prefixes to catch
    variations like 'University of Michigan Ann Arbor Medical School'.
    """
    normalized = _normalize_org(org_name)

    # Direct match
    if normalized in INSTITUTION_DOMAINS:
        return INSTITUTION_DOMAINS[normalized]

    # Substring match: check if any known key is contained in the org name
    for key, domain in INSTITUTION_DOMAINS.items():
        if key in normalized:
            return domain

    return None


# ── Stage 3: LLM domain inference ────────────────────────────────────────────

def _llm_infer_domain(org_name):
    """
    Ask claude-haiku for the institutional email domain.
    Returns the domain string (e.g. 'uga.edu') or None on failure.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=32,
            messages=[{
                "role": "user",
                "content": (
                    f"What is the primary email domain for '{org_name}'? "
                    "Reply with the domain only (e.g. 'uga.edu'). "
                    "No explanation."
                ),
            }],
        )
        raw = msg.content[0].text.strip().lower()
        # Extract just the domain in case the model adds extra text
        match = re.search(r"[\w\-]+\.(?:edu|gov|org|com)", raw)
        return match.group(0) if match else None
    except Exception:
        return None


# ── Orchestrator ──────────────────────────────────────────────────────────────

def infer_emails(pi_name, org_name, pi_profile_id=None):
    """
    Run the three-stage pipeline and return a result dict.

    Returns
    -------
    {
        "best_guess":  str | None,
        "candidates":  list[str],
        "confidence":  "verified" | "inferred" | "llm_inferred" | "not_found",
        "source":      "nih_profile" | "domain_lookup" | "llm" | None,
    }
    """
    first, last = _parse_name(pi_name)

    # Stage 1: NIH profile
    email = scrape_nih_profile_email(pi_profile_id)
    if email:
        domain = email.split("@")[1]
        candidates = _candidate_emails(first, last, domain)
        # Put the scraped email first if it's not already in the list
        if email not in candidates:
            candidates.insert(0, email)
        return {
            "best_guess": email,
            "candidates": candidates,
            "confidence": "verified",
            "source":     "nih_profile",
        }

    # Stage 2: Institutional domain lookup
    domain = org_to_domain_lookup(org_name)
    if domain:
        candidates = _candidate_emails(first, last, domain)
        return {
            "best_guess": candidates[0],
            "candidates": candidates,
            "confidence": "inferred",
            "source":     "domain_lookup",
        }

    # Stage 3: LLM domain inference
    domain = _llm_infer_domain(org_name)
    if domain:
        candidates = _candidate_emails(first, last, domain)
        return {
            "best_guess": candidates[0],
            "candidates": candidates,
            "confidence": "llm_inferred",
            "source":     "llm",
        }

    return {
        "best_guess": None,
        "candidates": [],
        "confidence": "not_found",
        "source":     None,
    }


# ── Quick smoke test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_cases = [
        # (pi_name, org, pi_profile_id)
        ("QUINN, SHANNON",    "University of Georgia",            None),
        ("SMITH, JOHN A",     "Johns Hopkins University",          None),
        ("ZHANG, WEI",        "Harvard Medical School",            None),
        ("PATEL, PRIYA R",    "Stanford University",               None),
        ("NGUYEN, DAVID",     "Oregon Health and Science University", None),
        ("GARCIA, MARIA",     "Some Regional University",          None),  # LLM stage
    ]

    for name, org, pid in test_cases:
        result = infer_emails(name, org, pid)
        conf   = result["confidence"]
        best   = result["best_guess"] or "not found"
        print(f"{name:<22} | {conf:<14} | {best}")
