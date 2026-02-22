"""
match_grants.py — Tuva Grant Advisor: Two-Stage Grant Matcher

Stage 1 — Bi-encoder retrieval:
    Load PI profile abstracts → mean-embed → cosine similarity against all
    grant embeddings → take top 50 candidates. Fast, free, high recall.

Stage 2 — LLM reranking (single call):
    Pass all 50 candidates to claude-haiku in one structured prompt.
    Haiku selects the 5 best matches and returns one specific alignment
    sentence per match. One call per query, ~$0.001 cost.

Fallback: If ANTHROPIC_API_KEY is not set, return top 5 by embedding score
with llm_explanation set to None.

Return value: list of 5 dicts
    {
        "rank":          int,
        "opp_id":        str,
        "title":         str,
        "agency":        str,
        "close_date":    str,
        "match_score":   float,          # bi-encoder cosine similarity
        "llm_explanation": str | None,
        "asks_about_ai":          True,  # key only present when True
        "requires_data_plan":     True,  # key only present when True
    }
"""

import json
import os
import pickle
from datetime import date

import pandas as pd
import torch
from sentence_transformers import SentenceTransformer, util

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env"))
except ImportError:
    pass

_RETRIEVAL_POOL = 50  # how many candidates pass to the LLM


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_llm_prompt(pi_abstracts_text, top50_df):
    candidates_block = []
    for i, (_, row) in enumerate(top50_df.iterrows(), 1):
        desc_snippet = str(row.get("description", ""))[:250].replace("\n", " ")
        candidates_block.append(
            f"[{i}] Title: {row['title']}\n"
            f"    Agency: {row.get('agency', 'N/A')} | Closes: {row.get('close_date', 'N/A')}\n"
            f"    Description: {desc_snippet}"
        )

    candidates_text = "\n\n".join(candidates_block)

    return f"""You are a research grant strategy advisor for Tuva, a research data platform.

RESEARCHER PROFILE:
{pi_abstracts_text[:2000]}

CANDIDATE GRANTS (top {len(top50_df)} by semantic similarity):
{candidates_text}

Select the 5 best matches for this researcher. For each match, return a JSON object with:
  - "rank": integer 1-5
  - "candidate_number": the [N] index above
  - "explanation": one specific sentence about why this grant fits their research
  - "asks_about_ai": true ONLY if the grant description explicitly mentions AI/ML methodology
  - "requires_data_plan": true ONLY if the grant explicitly requires a data management plan

Rules:
  - Only include "asks_about_ai" in the object if it is true
  - Only include "requires_data_plan" in the object if it is true
  - Return a JSON array only. No other text, no markdown fences.

Example output:
[{{"rank":1,"candidate_number":3,"explanation":"...","asks_about_ai":true}},{{"rank":2,"candidate_number":7,"explanation":"..."}}]"""


# ── LLM reranker ──────────────────────────────────────────────────────────────

def _call_llm_reranker(prompt):
    """
    Single claude-haiku call. Returns parsed list of dicts or None on failure.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic          # lazy — works even if package not installed
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        # Strip markdown code fences if the model adds them
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        return json.loads(raw)
    except Exception as e:
        print(f"  LLM reranker error: {e}")
        return None


# ── Main ──────────────────────────────────────────────────────────────────────

def run_strategic_advisory(prof_name, verbose=False):
    """
    Find the 5 best open grant opportunities for a PI.

    Parameters
    ----------
    prof_name : str
        Display name (e.g. "Shannon Quinn"). Converted to folder slug internally.
    verbose : bool
        Print progress messages.

    Returns
    -------
    list[dict] — 5 match dicts, or empty list on error.
    """
    prof_slug  = prof_name.lower().replace(" ", "_")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir   = os.path.dirname(os.path.dirname(script_dir))
    data_dir   = os.path.join(root_dir, "data", "similar_grants")
    embed_path = os.path.join(data_dir, "grant_embeddings.pkl")
    csv_path   = os.path.join(data_dir, "open_opportunities_deep.csv")
    prof_folder = os.path.join(data_dir, "profiles", prof_slug)

    # ── Load grant database ───────────────────────────────────────────────────
    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"Grant database not found at {csv_path}. Run find_open_grants.py first."
        )
    if not os.path.exists(embed_path):
        raise FileNotFoundError(
            f"Grant embeddings not found at {embed_path}. Run embed_grants.py first."
        )

    df_grants = pd.read_csv(csv_path)

    # Filter to currently open grants only
    today = date.today()
    def _is_open(s):
        if not s or pd.isna(s):
            return True
        for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
            try:
                from datetime import datetime
                return datetime.strptime(str(s).strip(), fmt).date() >= today
            except ValueError:
                continue
        return True

    open_mask = df_grants["close_date"].apply(_is_open)
    df_open   = df_grants[open_mask].reset_index(drop=True)

    if verbose:
        print(f"  {len(df_open)} of {len(df_grants)} grants currently open")

    # ── Load embeddings (aligned to df_grants row order) ─────────────────────
    with open(embed_path, "rb") as f:
        all_embeddings = pickle.load(f)

    # Slice to open grants only (by integer index)
    open_indices = df_grants.index[open_mask].tolist()
    if torch.is_tensor(all_embeddings):
        grant_embeddings = all_embeddings[open_indices].to("cpu")
    else:
        grant_embeddings = torch.from_numpy(all_embeddings[open_indices]).to("cpu")

    # ── Load PI profile abstracts ─────────────────────────────────────────────
    if not os.path.isdir(prof_folder):
        raise ValueError(
            f"No profile folder found at {prof_folder}. "
            "Run fetch_pi_history.py first."
        )

    abstract_files = sorted(
        f for f in os.listdir(prof_folder) if f.lower().endswith(".txt")
    )
    if not abstract_files:
        raise ValueError(
            f"Profile folder exists but is empty: {prof_folder}. "
            "Run fetch_pi_history.py to populate it."
        )

    model = SentenceTransformer("all-MiniLM-L6-v2")
    all_vectors     = []
    pi_texts        = []

    for filename in abstract_files:
        with open(os.path.join(prof_folder, filename), encoding="utf-8") as f:
            text = f.read().strip()
        if text:
            all_vectors.append(model.encode(text, convert_to_tensor=True).to("cpu"))
            pi_texts.append(text)

    if not all_vectors:
        raise ValueError(
            f"All abstract files in {prof_folder} are empty. "
            "Run fetch_pi_history.py to populate them."
        )

    pi_abstracts_text = "\n\n".join(pi_texts)
    combined_vec      = torch.mean(torch.stack(all_vectors), dim=0)

    # ── Stage 1: Bi-encoder retrieval → top 50 ───────────────────────────────
    scores = util.cos_sim(combined_vec, grant_embeddings)[0]
    df_open = df_open.copy()
    df_open["match_score"] = scores.tolist()
    top50 = df_open.sort_values("match_score", ascending=False).head(_RETRIEVAL_POOL)

    if verbose:
        print(f"  Retrieved top {len(top50)} candidates via bi-encoder")

    # ── Stage 2: LLM reranking ────────────────────────────────────────────────
    prompt    = _build_llm_prompt(pi_abstracts_text, top50)
    llm_ranks = _call_llm_reranker(prompt)

    top50_rows = top50.reset_index(drop=True)

    if llm_ranks is None:
        # Fallback: top 5 by embedding score, no LLM explanation
        if verbose:
            print("  LLM unavailable — using top 5 by embedding score")
        results = []
        for rank, (_, row) in enumerate(top50_rows.head(5).iterrows(), 1):
            entry = {
                "rank":            rank,
                "opp_id":          str(row["opp_id"]),
                "title":           row["title"],
                "agency":          row.get("agency", ""),
                "close_date":      str(row.get("close_date", "")),
                "match_score":     round(float(row["match_score"]), 4),
                "llm_explanation": None,
            }
            results.append(entry)
        return results

    # Map LLM selections back to grant rows
    results = []
    for item in llm_ranks:
        try:
            idx  = int(item["candidate_number"]) - 1  # 1-indexed → 0-indexed
            row  = top50_rows.iloc[idx]
            entry = {
                "rank":            item["rank"],
                "opp_id":          str(row["opp_id"]),
                "title":           row["title"],
                "agency":          row.get("agency", ""),
                "close_date":      str(row.get("close_date", "")),
                "match_score":     round(float(row["match_score"]), 4),
                "llm_explanation": item.get("explanation"),
            }
            # Only include flags when True (per user requirement)
            if item.get("asks_about_ai") is True:
                entry["asks_about_ai"] = True
            if item.get("requires_data_plan") is True:
                entry["requires_data_plan"] = True
            results.append(entry)
        except (IndexError, KeyError, TypeError) as e:
            if verbose:
                print(f"  Skipping malformed LLM result: {item} ({e})")
            continue

    results.sort(key=lambda x: x["rank"])
    return results[:5]


if __name__ == "__main__":
    results = run_strategic_advisory("Shannon Quinn", verbose=True)
    for r in results:
        print(f"\nRank #{r['rank']} | Score: {r['match_score']:.4f}")
        print(f"  {r['title']}")
        print(f"  {r.get('agency', '')} | Closes: {r.get('close_date', '')}")
        if r.get("llm_explanation"):
            print(f"  {r['llm_explanation']}")
        if r.get("asks_about_ai"):
            print("  Asks about AI/ML methodology")
        if r.get("requires_data_plan"):
            print("  Requires data management plan")
