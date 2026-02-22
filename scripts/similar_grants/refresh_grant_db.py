"""
refresh_grant_db.py — Incremental Grant Database Refresh

Run weekly (or on-demand from Streamlit) to keep the grant database current:
  1. Load existing open_opportunities_deep.csv
  2. Drop grants whose close_date is in the past
  3. Run all 5 Grants.gov searches → collect only new opp_ids
  4. Fetch full descriptions for the new grants
  5. Append to existing dataset and save
  6. Re-embed ONLY the new grants and vstack onto existing grant_embeddings.pkl
  7. Write a .last_refresh timestamp file

This avoids re-embedding the full dataset on every refresh.
"""

import pickle
import time
import os
from datetime import datetime, date

import numpy as np
import pandas as pd
import requests
from sentence_transformers import SentenceTransformer

from find_open_grants import SEARCH_QUERIES, PAGE_SIZE, RATE_LIMIT, FETCH_URL, _fetch_description


def _search_page(keyword, offset):
    """Thin wrapper — avoids circular import from find_open_grants."""
    from find_open_grants import SEARCH_URL
    payload = {
        "rows":            PAGE_SIZE,
        "startRecordNum":  offset,
        "keyword":         keyword,
        "oppStatuses":     "posted",
        "keywordEncoded":  False,
    }
    resp = requests.post(SEARCH_URL, json=payload, timeout=30)
    if resp.status_code != 200:
        return [], 0
    data      = resp.json().get("data", {})
    hits      = data.get("oppHits", [])
    hit_count = data.get("hitCount", 0)
    return hits, hit_count


def _parse_close_date(s):
    """Return a date object or None."""
    if not s or pd.isna(s):
        return None
    s = str(s).strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def refresh_grant_db(verbose=True):
    """
    Incrementally refresh the grant database. Returns a summary dict.
    """
    script_dir    = os.path.dirname(os.path.abspath(__file__))
    root_dir      = os.path.dirname(os.path.dirname(script_dir))
    data_dir      = os.path.join(root_dir, "data", "similar_grants")
    csv_path      = os.path.join(data_dir, "open_opportunities_deep.csv")
    embed_path    = os.path.join(data_dir, "grant_embeddings.pkl")
    refresh_stamp = os.path.join(data_dir, ".last_refresh")

    os.makedirs(data_dir, exist_ok=True)
    today = date.today()

    # ── Step 1: Load existing data ───────────────────────────────────────────
    if os.path.exists(csv_path):
        df_existing = pd.read_csv(csv_path)
    else:
        df_existing = pd.DataFrame(columns=["opp_id", "title", "number",
                                             "agency", "close_date", "description"])

    if verbose:
        print(f"Existing database: {len(df_existing)} grants")

    # ── Step 2: Expire past-close-date grants ────────────────────────────────
    if len(df_existing) > 0:
        close_dates  = df_existing["close_date"].apply(_parse_close_date)
        active_mask  = close_dates.apply(lambda d: d is None or d >= today)
        expired      = (~active_mask).sum()
        df_existing  = df_existing[active_mask].reset_index(drop=True)
        if verbose and expired > 0:
            print(f"  Removed {expired} expired grants")

    seen_ids = set(df_existing["opp_id"].astype(str).tolist())

    # ── Step 3: Fetch new grants ─────────────────────────────────────────────
    new_rows = []

    for query in SEARCH_QUERIES:
        label   = query["label"]
        keyword = query["keyword"]
        offset  = 0
        added   = 0

        while True:
            hits, hit_count = _search_page(keyword, offset)
            if not hits:
                break

            for hit in hits:
                opp_id = str(hit.get("id", ""))
                if not opp_id or opp_id in seen_ids:
                    continue
                seen_ids.add(opp_id)

                description = _fetch_description(opp_id)
                new_rows.append({
                    "opp_id":      opp_id,
                    "title":       hit.get("title"),
                    "number":      hit.get("number"),
                    "agency":      hit.get("agency"),
                    "close_date":  hit.get("closeDate"),
                    "description": description,
                })
                added += 1
                time.sleep(RATE_LIMIT)

            offset += PAGE_SIZE
            if offset >= hit_count:
                break

        if verbose:
            print(f"  {label}: {added} new grants")

    if verbose:
        print(f"Total new grants: {len(new_rows)}")

    if not new_rows:
        if verbose:
            print("Database is up to date — no new grants found.")
        with open(refresh_stamp, "w") as f:
            f.write(today.isoformat())
        return {"new": 0, "expired": 0, "total": len(df_existing)}

    df_new  = pd.DataFrame(new_rows)
    df_new["description"] = df_new["description"].fillna("No description provided")

    # ── Step 4: Merge and save CSV ───────────────────────────────────────────
    df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    df_combined.to_csv(csv_path, index=False)
    if verbose:
        print(f"Saved {len(df_combined)} total grants to {csv_path}")

    # ── Step 5: Incremental re-embedding (new rows only) ─────────────────────
    model = SentenceTransformer("all-MiniLM-L6-v2")
    new_embeddings = model.encode(df_new["description"].tolist(), show_progress_bar=verbose)

    if os.path.exists(embed_path):
        with open(embed_path, "rb") as f:
            existing_embeddings = pickle.load(f)
        # Trim to match the (possibly pruned) existing dataset
        existing_embeddings = existing_embeddings[:len(df_existing)]
        combined_embeddings = np.vstack([existing_embeddings, new_embeddings])
    else:
        combined_embeddings = new_embeddings

    with open(embed_path, "wb") as f:
        pickle.dump(combined_embeddings, f)

    if verbose:
        print(f"Embeddings updated: {len(combined_embeddings)} total vectors")

    # ── Step 6: Write refresh timestamp ──────────────────────────────────────
    with open(refresh_stamp, "w") as f:
        f.write(today.isoformat())

    return {
        "new":     len(new_rows),
        "expired": 0,  # already counted above
        "total":   len(df_combined),
    }


def last_refresh_date():
    """Return the last refresh date string, or None if never refreshed."""
    script_dir    = os.path.dirname(os.path.abspath(__file__))
    root_dir      = os.path.dirname(os.path.dirname(script_dir))
    refresh_stamp = os.path.join(root_dir, "data", "similar_grants", ".last_refresh")
    if not os.path.exists(refresh_stamp):
        return None
    with open(refresh_stamp) as f:
        return f.read().strip()


if __name__ == "__main__":
    refresh_grant_db(verbose=True)
