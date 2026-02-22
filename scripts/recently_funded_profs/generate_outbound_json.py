"""
generate_outbound_json.py — Integration-Ready Outbound JSON

Reads scored_leads.csv, runs email inference for every lead, and writes
outbound_leads.json — a structured array ready for Clay, HubSpot, or
Smartlead import.

Schema per record:
    {
        "tier":            "Tier 1",
        "outbound_score":  0.713,
        "pi_name":         "QUINN, SHANNON",
        "organization":    "University of Georgia",
        "award_type":      "New",
        "award_amount":    412000,
        "award_date":      "2025-01-14",
        "project_title":   "Machine Learning Approaches to ...",
        "grant_count":     2,
        "email": {
            "best_guess":  "shannon.quinn@uga.edu",
            "candidates":  ["shannon.quinn@uga.edu", "squinn@uga.edu", ...],
            "confidence":  "inferred",
            "source":      "domain_lookup"
        },
        "signals": {
            "ai_signal":        0.312,
            "data_signal":      0.180,
            "grant_freshness":  0.844,
            "award_size_score": 0.521,
            "is_new_award":     1.0
        },
        "nih_link": "https://reporter.nih.gov/search/results?query=QUINN+SHANNON",
        "full_project_num": "1R01AI123456-01A1"
    }
"""

import json
import os
import sys

import pandas as pd

# Allow running as a script from any directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from email_finder import infer_emails


def _nih_search_link(pi_name):
    """Build an NIH Reporter search URL for a PI name."""
    query = str(pi_name).replace(",", "").replace("  ", " ").strip().replace(" ", "+")
    return f"https://reporter.nih.gov/search/results?query={query}"


def generate_outbound_json(top_n=None):
    """
    Generate integration-ready JSON for scored leads.

    Parameters
    ----------
    top_n : int | None
        If set, only process the top N leads by outbound_score.
        None = process all leads.

    Returns
    -------
    list[dict] — the full outbound payload.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir   = os.path.dirname(os.path.dirname(script_dir))
    input_csv  = os.path.join(root_dir, "data", "recently_funded_profs", "scored_leads.csv")
    output_dir = os.path.join(root_dir, "output")
    output_json = os.path.join(output_dir, "outbound_leads.json")

    if not os.path.exists(input_csv):
        print(f"ERROR: {input_csv} not found. Run score_leads.py first.")
        return []

    os.makedirs(output_dir, exist_ok=True)

    df = pd.read_csv(input_csv)
    if top_n is not None:
        df = df.head(top_n)

    print(f"Generating outbound JSON for {len(df)} leads...")

    signal_cols = ["ai_signal", "data_signal", "grant_freshness",
                   "award_size_score", "is_new_award"]

    records = []
    for i, row in df.iterrows():
        email_result = infer_emails(
            pi_name      = row.get("pi_name", ""),
            org_name     = row.get("organization", ""),
            pi_profile_id = row.get("pi_profile_id"),
        )

        record = {
            "tier":           row.get("tier"),
            "outbound_score": row.get("outbound_score"),
            "pi_name":        row.get("pi_name"),
            "organization":   row.get("organization"),
            "award_type":     row.get("award_type"),
            "award_amount":   row.get("award_amount"),
            "award_date":     str(row.get("award_date", "")).split("T")[0],
            "project_title":  row.get("project_title"),
            "grant_count":    int(row.get("grant_count", 1)),
            "email":          email_result,
            "signals": {
                col: round(float(row[col]), 4) if pd.notna(row.get(col)) else None
                for col in signal_cols if col in df.columns
            },
            "nih_link":         _nih_search_link(row.get("pi_name", "")),
            "full_project_num": row.get("full_project_num"),
        }
        records.append(record)

        if (i + 1) % 25 == 0:
            print(f"  {i + 1}/{len(df)} processed...")

    with open(output_json, "w") as f:
        json.dump(records, f, indent=2, default=str)

    conf_counts = {}
    for r in records:
        c = r["email"]["confidence"]
        conf_counts[c] = conf_counts.get(c, 0) + 1

    print(f"\nSUCCESS: {len(records)} leads written to {output_json}")
    print("  Email coverage:")
    for conf, count in sorted(conf_counts.items()):
        pct = 100 * count / len(records)
        print(f"    {conf:<16} {count:>4}  ({pct:.0f}%)")

    return records


if __name__ == "__main__":
    generate_outbound_json()
