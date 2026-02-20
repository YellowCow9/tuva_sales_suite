import requests
import pandas as pd
import os
from datetime import datetime, timedelta

def ingest_recent_r01_leads():
    url = "https://api.reporter.nih.gov/v2/projects/search"
    
    # 1. DEFINE "FRESHNESS"
    # Vamsi wants leads with fresh infrastructure budgets (last 90 days)
    today = datetime.now()
    ninety_days_ago = (today - timedelta(days=90)).strftime('%Y-%m-%d')
    
    # 2. DEFINE THE SEARCH CRITERIA
    payload = {
    "criteria": {
        # This is the "Hard Gate" for the 90-day window
        "award_notice_date": {
            "from_date": ninety_days_ago, 
            "to_date": today.strftime('%Y-%m-%d')
        },
        "activity_codes": ["R01"],
        # Ensure 'newly_added_projects_only' is True for outbound leads
        "newly_added_projects_only": True 
    },
    "include_fields": ["ProjectTitle", "AbstractText", "ContactPiName", "AwardAmount", "AwardNoticeDate"],
    "limit": 50
    }

    print(f"Scanning NIH for fresh R01s since {ninety_days_ago}...")
    response = requests.post(url, json=payload)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        return

    results = response.json().get('results', [])
    
    # 3. STRUCTURE THE DATA FOR TUVA
    leads_data = []
    for proj in results:
        leads_data.append({
            'pi_name': proj.get('contact_pi_name'),
            'organization': proj.get('organization', {}).get('org_name'),
            'project_title': proj.get('project_title'),
            'award_amount': proj.get('award_amount'),
            'start_date': proj.get('project_start_date'), 
            'award_date': proj.get('award_notice_date'),
            'abstract': proj.get('abstract_text')
        })

    # 4. SAVE TO DATA FOLDER
    os.makedirs('data/recently_funded_profs', exist_ok=True)
    df = pd.DataFrame(leads_data)
    df.to_csv('data/recently_funded_profs/raw_nih_leads.csv', index=False)
    
    print(f"SUCCESS: Found {len(df)} fresh R01 leads. Saved to data/recently_funded_profs/raw_nih_leads.csv")

if __name__ == "__main__":
    ingest_recent_r01_leads()