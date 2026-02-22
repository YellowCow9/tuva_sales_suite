"""
find_open_grants.py — Grants.gov Grant Database Builder

Runs five targeted keyword searches against the Grants.gov API, paginates
each fully, fetches full synopsis text, deduplicates by opp_id, and saves
the result to data/similar_grants/open_opportunities_deep.csv.

Target: 300-400 high-relevance computational biology / data science grants.
"""

import requests
import pandas as pd
import time
import os


SEARCH_URL = "https://api.grants.gov/v1/api/search2"
FETCH_URL  = "https://api.grants.gov/v1/api/fetchOpportunity"
PAGE_SIZE  = 100
RATE_LIMIT = 0.25  # seconds between fetch calls

# Five targeted searches covering Tuva's ICP:
# computational biology, ML + biomedical, data management, omics, in silico
SEARCH_QUERIES = [
    {
        "label":   "computational biology",
        "keyword": (
            '"computational biology" OR "bioinformatics" OR "genomics" OR '
            '"proteomics" OR "transcriptomics"'
        ),
    },
    {
        "label":   "ML + biomedical",
        "keyword": (
            '("machine learning" OR "deep learning" OR "neural network" OR '
            '"artificial intelligence") AND (biology OR genomics OR health OR biomedical)'
        ),
    },
    {
        "label":   "data management",
        "keyword": (
            '("data management" OR "FAIR data" OR "data sharing" OR '
            '"data harmonization") AND (research OR genomics OR health)'
        ),
    },
    {
        "label":   "omics",
        "keyword": (
            '"single-cell" OR "multi-omics" OR "spatial transcriptomics" OR '
            '"epigenomics" OR "metabolomics"'
        ),
    },
    {
        "label":   "modeling + biology",
        "keyword": (
            '("predictive modeling" OR "in silico" OR "simulation") AND '
            '(biology OR genomics OR disease OR drug)'
        ),
    },
]


def _search_page(keyword, offset):
    """Run one paginated search call. Returns (hits, hit_count)."""
    payload = {
        "rows":            PAGE_SIZE,
        "startRecordNum":  offset,
        "keyword":         keyword,
        "oppStatuses":     "posted",
        "keywordEncoded":  False,
    }
    resp = requests.post(SEARCH_URL, json=payload, timeout=30)
    if resp.status_code != 200:
        print(f"    Search error {resp.status_code} at offset {offset}")
        return [], 0
    data      = resp.json().get("data", {})
    hits      = data.get("oppHits", [])
    hit_count = data.get("hitCount", 0)
    return hits, hit_count


def _fetch_description(opp_id):
    """Fetch full synopsis text for a single opportunity."""
    try:
        resp = requests.post(FETCH_URL, json={"opportunityId": opp_id}, timeout=20)
        if resp.status_code != 200:
            return "No description found"
        details  = resp.json().get("data", {})
        synopsis = details.get("synopsis", {})
        return (
            synopsis.get("synopsisDesc")
            or details.get("opportunityDescription")
            or "No description found"
        )
    except Exception:
        return "No description found"


def ingest_open_grants():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir   = os.path.dirname(os.path.dirname(script_dir))
    output_csv = os.path.join(root_dir, "data", "similar_grants", "open_opportunities_deep.csv")
    os.makedirs(os.path.join(root_dir, "data", "similar_grants"), exist_ok=True)

    seen_ids  = set()
    all_rows  = []

    for query in SEARCH_QUERIES:
        label   = query["label"]
        keyword = query["keyword"]
        offset  = 0
        query_count = 0

        print(f"\nSearching: {label}")

        while True:
            hits, hit_count = _search_page(keyword, offset)
            if not hits:
                break

            if offset == 0:
                print(f"  {hit_count} total results — paginating...")

            for hit in hits:
                opp_id = hit.get("id")
                if not opp_id or opp_id in seen_ids:
                    continue
                seen_ids.add(opp_id)

                description = _fetch_description(opp_id)
                all_rows.append({
                    "opp_id":      opp_id,
                    "title":       hit.get("title"),
                    "number":      hit.get("number"),
                    "agency":      hit.get("agency"),
                    "close_date":  hit.get("closeDate"),
                    "description": description,
                })
                query_count += 1
                time.sleep(RATE_LIMIT)

            offset += PAGE_SIZE
            if offset >= hit_count:
                break

        print(f"  Added {query_count} unique grants from this search")

    df = pd.DataFrame(all_rows)
    df.to_csv(output_csv, index=False)
    print(f"\nSUCCESS: {len(df)} unique grants saved to {output_csv}")
    return df


if __name__ == "__main__":
    ingest_open_grants()
