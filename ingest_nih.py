import requests
import pandas as pd
import os

def get_fresh_nih_grants():
    url = "https://api.reporter.nih.gov/v2/projects/search"
    
    # Filtering for R01 grants awarded in the last 90 days
    query = {
        "criteria": {
            "fiscal_years": [2025, 2026],
            "award_notice_date": {"from_date": "2026-01-20", "to_date": "2026-02-19"},
            "project_types": ["R01"],
            "advanced_text_search": {
                "operator": "or",
                "search_text": "('computational biology' OR 'biophysics' OR 'genomics') AND ('automation' OR 'simulation' OR 'pipeline' OR 'in-silico')"
            }
        },
        "limit": 50,
        "offset": 0
    }

    print("Fetching data from NIH RePORTER...")
    response = requests.post(url, json=query)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        return

    data = response.json()
    results = data.get('results', [])
    
    projects = []
    for p in results:
        projects.append({
            'pi_name': p.get('contact_pi_name'),
            'institution': p.get('organization', {}).get('org_name'),
            'title': p.get('project_title'),
            'abstract': p.get('abstract_text'),
            'amount': p.get('award_amount'),
            'notice_date': p.get('award_notice_date')
        })
    
    df = pd.DataFrame(projects)
    
    # Ensure the data folder exists
    os.makedirs('data', exist_ok=True)
    
    output_path = 'data/raw_nih_leads.csv'
    df.to_csv(output_path, index=False)
    print(f"Success! Saved {len(df)} fresh leads to {output_path}")

if __name__ == "__main__":
    get_fresh_nih_grants()