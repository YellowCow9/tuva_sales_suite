import pandas as pd
import json
import os

def export_raw_nih_to_json():
    input_csv = 'data/recently_funded_profs/raw_nih_leads.csv'
    output_json = 'output/radar_leads_schema.json'
    
    if not os.path.exists(input_csv):
        print(f"Error: {input_csv} not found.")
        return

    # 1. Load the raw data
    # Use 'quotechar' because your CSV uses double quotes for abstracts
    df = pd.read_csv(input_csv, quotechar='"')

    # 2. Structure for the "Integration Layer"
    json_output = {
        "metadata": {
            "source": "NIH Raw Leads",
            "export_date": pd.Timestamp.now().strftime('%Y-%m-%d'),
            "total_leads": len(df)
        },
        "leads": []
    }

    for _, row in df.iterrows():
        # Clean up the PI name (e.g., "ABRAHAMS, VIKKI M" -> "Vikki M Abrahams")
        raw_name = str(row['pi_name'])
        clean_name = ' '.join(reversed(raw_name.split(', '))).title() if ',' in raw_name else raw_name

        lead_entry = {
            "professor": {
                "name": clean_name,
                "organization": row['organization'] if pd.notna(row['organization']) else "N/A"
            },
            "research_context": {
                "project_title": row['project_title'],
                "award_amount": row['award_amount'],
                "abstract_snippet": str(row['abstract'])[:500] # Snippet for the outbound tool
            },
            "automation_flags": {
                "is_active_grant": True,
                "start_date": row['start_date']
            }
        }
        json_output["leads"].append(lead_entry)

    # 3. Save to output folder
    os.makedirs('output', exist_ok=True)
    with open(output_json, 'w') as f:
        json.dump(json_output, f, indent=4)

    print(f"SUCCESS: Exported {len(df)} raw leads to {output_json}")

if __name__ == "__main__":
    export_raw_nih_to_json()