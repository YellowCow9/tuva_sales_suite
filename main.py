import sys
import os

# 1. Ensure the 'scripts' folder is in the system path so we can import your logic
sys.path.append(os.path.join(os.getcwd(), 'scripts', 'similar_grants'))

# 2. Import your modular functions
from find_open_grants import ingest_open_grants
from match_grants import run_strategic_advisory

def main():
    print("="*60)
    print("TUVA STRATEGIC RADAR: MVP PIPELINE")
    print("="*60)

    # FEATURE 1: Generate/Refresh the Lead Database
    print("\n[1/2] Refreshing Grant Database...")
    try:
        ingest_open_grants()
        print("SUCCESS: Database updated in data/similar_grants/")
    except Exception as e:
        print(f"ERROR during ingestion: {e}")

    # FEATURE 2: Strategic Matching
    print("\n" + "-"*40)
    target_prof = "Shannon Quinn" # You can change this or use input()
    print(f"[2/2] Running Strategic Match for: {target_prof}")
    print("-"*40)
    
    try:
        run_strategic_advisory(target_prof)
    except Exception as e:
        print(f"ERROR during matching: {e}")

    print("\n" + "="*60)
    print("PIPELINE COMPLETE: Outputs available in /data and /output")
    print("="*60)

if __name__ == "__main__":
    main()