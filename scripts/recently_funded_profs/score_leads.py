"""
score_leads.py — Tuva Grant Radar: Lead Scorer

Reads raw_nih_leads.csv, deduplicates by PI identity, then scores every
unique lead with five signals and writes scored_leads.csv ranked by
outbound priority.

Signals
-------
ai_signal        Weighted keyword density for AI/ML/computational methods.
                 High = PI is doing sophisticated computation and likely needs
                 research data infrastructure.
data_signal      Weighted keyword density for data management, sharing, and
                 reproducibility language — Tuva's direct value prop.
grant_freshness  1.0 = awarded today, decays linearly to 0.0 at 90 days.
                 Fresh grants = unspent budget + active infrastructure decisions.
award_size_score Log-normalized award amount. Larger grants have more headroom
                 for tooling purchases.
is_new_award     1.0 if this is a brand-new R01 (type code '1'), 0.0 for
                 renewals/continuations. New awardees are actively setting up
                 data workflows; renewal PIs already have infrastructure.
"""

import re
import sys
import pandas as pd
import numpy as np
import os
from datetime import datetime

# Make tuva_tool/ importable when running score_leads.py standalone
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from config import (
    SCORING_WEIGHTS,
    FRESHNESS_DECAY_DAYS,
    AWARD_SIZE_LOG_MIN,
    AWARD_SIZE_LOG_MAX,
    ABSTRACT_MIN_WORDS,
)


# ── Keyword dictionaries ───────────────────────────────────────────────────────
# Weight 3 = strong Tuva ICP signal
# Weight 2 = moderate signal
# Weight 1 = weak / background signal

AI_KEYWORDS = {
    # Explicit AI/ML methodology
    "machine learning": 3,
    "deep learning": 3,
    "neural network": 3,
    "artificial intelligence": 3,
    "large language model": 3,
    "foundation model": 3,
    "generative ai": 3,
    "natural language processing": 2,
    "computer vision": 2,
    "random forest": 2,
    "gradient boosting": 2,
    "predictive model": 2,
    "predictive modeling": 2,
    # Computational biology / biopharma
    "single-cell": 2,
    "single cell": 2,
    "multi-omics": 2,
    "multiomics": 2,
    "bioinformatics": 2,
    "computational biology": 2,
    "in silico": 2,
    "high-performance computing": 2,
    "next-generation sequencing": 2,
    "spatial transcriptomics": 2,
    "image analysis": 2,
    # Broad computational signals
    "genomics": 1,
    "transcriptomics": 1,
    "proteomics": 1,
    "algorithm": 1,
    "computational": 1,
    "simulation": 1,
}

DATA_KEYWORDS = {
    # Direct Tuva value prop
    "data management": 3,
    "data sharing": 3,
    "sharing plan": 3,
    "data harmonization": 3,
    "rigor and reproducibility": 3,
    "data management and sharing": 3,
    # Strong data signals
    "reproducibility": 2,
    "fair data": 2,
    "interoperable": 2,
    "standardization": 2,
    "repository": 2,
    "curation": 2,
    "data integration": 2,
    "version control": 2,
    "cloud computing": 2,
    # Moderate signals
    "pipeline": 1,
    "workflow": 1,
    "infrastructure": 1,
    "database": 1,
    "cloud": 1,
}


# ── Signal helpers ─────────────────────────────────────────────────────────────

def keyword_signal(text, keyword_dict):
    """
    Weighted keyword hit score normalized to [0, 1].

    Multi-word phrases use substring matching (no false-positive risk).
    Single-word terms use regex word boundaries to prevent "ai" from matching
    "said", "available", "brain", etc.
    """
    if pd.isna(text) or not str(text).strip():
        return 0.0
    text_lower = str(text).lower()
    max_possible = sum(keyword_dict.values())
    hit_score = 0.0
    for kw, w in keyword_dict.items():
        if " " in kw:
            if kw in text_lower:
                hit_score += w
        else:
            if re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
                hit_score += w
    return min(hit_score / max_possible, 1.0)


def freshness_score(award_date_str):
    """
    1.0 = awarded today. Decays linearly to 0.0 at 90 days.
    Returns 0.5 (neutral) if the date cannot be parsed.
    """
    try:
        award_dt = pd.to_datetime(award_date_str, utc=True).replace(tzinfo=None)
        days_old = (datetime.now() - award_dt).days
        return max(0.0, 1.0 - (days_old / FRESHNESS_DECAY_DAYS))
    except Exception:
        return 0.5


def award_size_score(amount):
    """
    Log-normalize award amount to [0, 1].
    Reference: ~$50k → 0.0,  ~$500k → 0.5,  ~$5M+ → 1.0
    """
    try:
        val = float(amount)
        if val <= 0:
            return 0.0
        log_val = np.log(val)
        return max(0.0, min(1.0, (log_val - AWARD_SIZE_LOG_MIN) / (AWARD_SIZE_LOG_MAX - AWARD_SIZE_LOG_MIN)))
    except Exception:
        return 0.0


def assign_tier(score, p90, p75, p50):
    """Map outbound_score to a ranked tier label."""
    if score >= p90:
        return "Tier 1"
    elif score >= p75:
        return "Tier 2"
    elif score >= p50:
        return "Tier 3"
    else:
        return "Tier 4"


# ── Deduplication ──────────────────────────────────────────────────────────────

def _pi_dedup_key(row):
    """
    Build a stable identity key for deduplication.

    Primary key: NIH pi_profile_id (integer, unique per PI in NIH's system).
    Fallback: first initial + last name + org prefix (for older data without the ID).
    """
    profile_id = row.get("pi_profile_id")
    if pd.notna(profile_id) and str(profile_id).strip() not in ("", "nan"):
        return f"nih:{profile_id}"

    pi_name = str(row.get("pi_name", "")).strip()
    org     = str(row.get("organization", ""))

    if "," in pi_name:
        parts      = pi_name.split(",", 1)
        last       = parts[0].strip().lower()
        first_raw  = parts[1].strip().split()
        first_init = first_raw[0][0].lower() if first_raw else ""
    else:
        parts      = pi_name.split()
        last       = parts[-1].lower() if parts else ""
        first_init = parts[0][0].lower() if parts else ""

    org_slug = re.sub(r"[^a-z]", "", org.lower())[:15]
    return f"{first_init}.{last}@{org_slug}"


def deduplicate_leads(df):
    """
    Merge rows belonging to the same PI into a single record.

    Aggregation rules:
      award_amount   → maximum (most significant grant wins)
      award_date     → most recent
      award_type     → 'New' wins over anything else (if any grant is new,
                       the PI is in active setup mode and is high priority)
      abstract       → concatenated (gives the scorer a fuller research profile)
      project_title  → concatenated with ' | '
      grant_count    → number of R01s this PI won in the window (signal itself)
    """
    df = df.copy()
    df["_key"] = df.apply(_pi_dedup_key, axis=1)

    before = len(df)

    def aggregate(group):
        base = group.loc[group["award_amount"].fillna(0).idxmax()].copy()
        base["grant_count"] = len(group)

        if len(group) > 1:
            base["award_amount"] = group["award_amount"].max()
            base["award_date"]   = group["award_date"].dropna().max()
            base["award_type"]   = (
                "New" if "New" in group["award_type"].values
                else group["award_type"].iloc[0]
            )
            abstracts = group["abstract"].dropna().tolist()
            base["abstract"] = " ".join(abstracts)
            titles = group["project_title"].dropna().tolist()
            base["project_title"] = " | ".join(titles)

        return base

    deduped = (
        df.groupby("_key", group_keys=False)
        .apply(aggregate, include_groups=False)
        .reset_index(drop=True)
    )
    if "_key" in deduped.columns:
        deduped = deduped.drop(columns=["_key"])

    removed = before - len(deduped)
    if removed > 0:
        print(f"  Dedup: merged {removed} duplicate rows → {len(deduped)} unique PIs")

    return deduped


# ── Main ───────────────────────────────────────────────────────────────────────

def score_all_leads():
    """
    Load raw_nih_leads.csv, deduplicate by PI identity, compute five signals,
    write scored_leads.csv sorted by outbound_score descending.
    Returns the scored DataFrame.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir   = os.path.dirname(os.path.dirname(script_dir))
    input_csv  = os.path.join(root_dir, "data", "recently_funded_profs", "raw_nih_leads.csv")
    output_csv = os.path.join(root_dir, "data", "recently_funded_profs", "scored_leads.csv")

    if not os.path.exists(input_csv):
        print(f"ERROR: {input_csv} not found. Run ingest_nih_leads.py first.")
        return None

    df = pd.read_csv(input_csv, quotechar='"')
    print(f"Loaded {len(df)} raw leads.")

    # Step 1: deduplicate before scoring so signals reflect each PI's full profile
    if "award_type" not in df.columns:
        df["award_type"] = "Unknown"
    df = deduplicate_leads(df)

    # Step 2: abstract length pre-filter
    # Abstracts under 80 words are administrative grants that pollute rankings.
    word_counts = df["abstract"].fillna("").apply(lambda x: len(str(x).split()))
    short_mask  = word_counts < ABSTRACT_MIN_WORDS
    if short_mask.sum() > 0:
        print(f"  Abstract filter: zeroing signals for {short_mask.sum()} short abstracts (<80 words)")

    # Step 3: compute signals
    df["ai_signal"]        = df["abstract"].apply(lambda x: keyword_signal(x, AI_KEYWORDS))
    df["data_signal"]      = df["abstract"].apply(lambda x: keyword_signal(x, DATA_KEYWORDS))
    df["grant_freshness"]  = df["award_date"].apply(freshness_score)
    df["award_size_score"] = df["award_amount"].apply(award_size_score)
    df["is_new_award"]     = (df["award_type"] == "New").astype(float)

    # Zero out text-based signals for short abstracts
    df.loc[short_mask, ["ai_signal", "data_signal"]] = 0.0

    # Step 4: weighted composite score (weights sum to 1.0)
    w = SCORING_WEIGHTS
    df["outbound_score"] = (
        w["grant_freshness"]  * df["grant_freshness"]  +
        w["award_size_score"] * df["award_size_score"] +
        w["ai_signal"]        * df["ai_signal"]        +
        w["data_signal"]      * df["data_signal"]      +
        w["is_new_award"]     * df["is_new_award"]
    ).round(4)

    df = df.sort_values("outbound_score", ascending=False).reset_index(drop=True)

    # Step 5: percentile-based tier labels
    p90 = df["outbound_score"].quantile(0.90)
    p75 = df["outbound_score"].quantile(0.75)
    p50 = df["outbound_score"].quantile(0.50)
    df["tier"] = df["outbound_score"].apply(lambda s: assign_tier(s, p90, p75, p50))

    tier_counts = df["tier"].value_counts().to_dict()
    print(f"  Tiers — 1: {tier_counts.get('Tier 1', 0)}  "
          f"2: {tier_counts.get('Tier 2', 0)}  "
          f"3: {tier_counts.get('Tier 3', 0)}  "
          f"4: {tier_counts.get('Tier 4', 0)}")

    df.to_csv(output_csv, index=False)

    top = df.iloc[0]
    print(f"Scoring complete — {len(df)} unique leads.")
    print(f"  Top lead : {top['pi_name']}  ({top.get('award_type', '?')})")
    print(f"  Score    : {top['outbound_score']:.3f}  "
          f"(AI: {top['ai_signal']:.3f} | Data: {top['data_signal']:.3f} | "
          f"Freshness: {top['grant_freshness']:.3f} | New: {int(top['is_new_award'])})")
    print(f"  Output   → {output_csv}")
    return df


if __name__ == "__main__":
    score_all_leads()
