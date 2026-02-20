import requests
import pandas as pd
import time
import os

def ingest_open_grants():
    search_url = "https://api.grants.gov/v1/api/search2"
    fetch_url = "https://api.grants.gov/v1/api/fetchOpportunity"
    
    payload = {
        "rows": 100,
        # Trying to find computational science grants
        "keyword": "(\"computational\" OR \"in silico\" OR \"modeling\" OR \"simulation\") AND (biology OR physics OR genomics OR biophysics OR mechanobiology)",
        "oppStatuses": "posted",
        "keywordEncoded": False
    }

    print("Step 1: Searching for opportunities...")
    response = requests.post(search_url, json=payload)
    
    if response.status_code != 200:
        print(f"Search failed: {response.status_code}")
        return

    # Extract IDs from the search results
    hits = response.json().get('data', {}).get('oppHits', [])
    print(f"Found {len(hits)} opportunities. Step 2: Fetching full abstracts...")

    full_data = []

    for hit in hits:
        opp_id = hit.get('id')
        print(f"  Fetching details for {opp_id}: {hit.get('title')[:50]}...")
        
        # Use the fetch endpoint to get the deep 'synopsis'
        fetch_res = requests.post(fetch_url, json={"opportunityId": opp_id})
        
        if fetch_res.status_code == 200:
            details = fetch_res.json().get('data', {})
            synopsis = details.get('synopsis', {})
            
            # Use the field identified in the official sample response
            description = (
                synopsis.get('synopsisDesc') or 
                details.get('opportunityDescription') or 
                "No description found"
            )
            
            full_data.append({
                'opp_id': opp_id,
                'title': hit.get('title'),
                'number': hit.get('number'),
                'agency': hit.get('agencyName'),
                'description': description, # This will now grab the 'synopsisDesc'
                'close_date': hit.get('closeDate')
            })
        
        # Rate limiting safety
        time.sleep(0.3)

    # Save to CSV
    os.makedirs('data', exist_ok=True)
    df = pd.DataFrame(full_data)
    df.to_csv('data/open_opportunities_deep.csv', index=False)
    
    print(f"\nSUCCESS: Saved {len(df)} opportunities with full abstracts to data/open_opportunities_deep.csv")

if __name__ == "__main__":
    ingest_open_grants()