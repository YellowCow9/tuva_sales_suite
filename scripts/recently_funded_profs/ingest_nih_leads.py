import requests
import pandas as pd
import os
from datetime import datetime, timedelta


def parse_award_type(award_type_code):
    """
    NIH award_type is returned directly as an integer:
      1 = New competitive award  (PI in active setup mode — highest Tuva priority)
      2 = Competitive renewal    (PI already has infrastructure in place)
      3 = Supplement
      4/5 = Non-competing continuation
    """
    try:
        code = int(award_type_code)
    except (TypeError, ValueError):
        return "Unknown"
    return {1: "New", 2: "Renewal", 3: "Supplement"}.get(code, "Continuation")


def ingest_recent_r01_leads():
    url = "https://api.reporter.nih.gov/v2/projects/search"

    today = datetime.now()
    ninety_days_ago = (today - timedelta(days=90)).strftime("%Y-%m-%d")

    payload = {
        "criteria": {
            "award_notice_date": {
                "from_date": ninety_days_ago,
                "to_date": today.strftime("%Y-%m-%d"),
            },
            "activity_codes": ["R01"],
            "newly_added_projects_only": True,
        },
        "include_fields": [
            "ProjectTitle",
            "AbstractText",
            "ContactPiName",
            "AwardAmount",
            "AwardNoticeDate",
            "Organization",              # org_name nested inside
            "ProjectStartDate",
            "AwardType",                 # integer 1-5, parsed to New/Renewal/etc.
            "ProjectNum",                # full project number for reference
            "PrincipalInvestigators",    # contains profile_id for each PI
        ],
        "limit": 500,
    }

    print(f"Scanning NIH for fresh R01s since {ninety_days_ago}...")
    response = requests.post(url, json=payload)

    if response.status_code != 200:
        print(f"Error: {response.status_code} — {response.text[:200]}")
        return

    results = response.json().get("results", [])

    leads_data = []
    for proj in results:
        # Extract PI profile ID from the principal_investigators list
        pi_list    = proj.get("principal_investigators") or []
        profile_id = pi_list[0].get("profile_id") if pi_list else None

        leads_data.append({
            "pi_name":          proj.get("contact_pi_name"),
            "pi_profile_id":    profile_id,
            "organization":     (proj.get("organization") or {}).get("org_name"),
            "project_title":    proj.get("project_title"),
            "award_amount":     proj.get("award_amount"),
            "start_date":       proj.get("project_start_date"),
            "award_date":       proj.get("award_notice_date"),
            "full_project_num": proj.get("project_num"),
            "award_type":       parse_award_type(proj.get("award_type")),
            "abstract":         proj.get("abstract_text"),
        })

    os.makedirs("data/recently_funded_profs", exist_ok=True)
    df = pd.DataFrame(leads_data)
    df.to_csv("data/recently_funded_profs/raw_nih_leads.csv", index=False)

    new_count     = (df["award_type"] == "New").sum()
    renewal_count = (df["award_type"] == "Renewal").sum()
    other_count   = len(df) - new_count - renewal_count
    print(f"SUCCESS: {len(df)} leads — {new_count} New, {renewal_count} Renewals, {other_count} Other")
    print(f"Saved → data/recently_funded_profs/raw_nih_leads.csv")


if __name__ == "__main__":
    ingest_recent_r01_leads()
