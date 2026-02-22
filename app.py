"""
app.py — Tuva Grant Radar: Streamlit Frontend

Tab 1 — Lead Radar:
    Sortable table of fresh R01 grantees ranked by outbound_score.
    Sidebar filters (global). Score breakdown panel on row selection.
    Download buttons for JSON and Excel.

Tab 2 — Grant Advisor:
    PI name input → NIH disambiguation → 5 grant match cards with LLM explanations.
    Flags shown only when True (AI methodology, data management plan).
"""

import json
import os
import re
import sys

import pandas as pd
import requests
import streamlit as st

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT_DIR    = os.path.dirname(os.path.abspath(__file__))
LEADS_CSV   = os.path.join(ROOT_DIR, "data", "recently_funded_profs", "scored_leads.csv")
RAW_CSV     = os.path.join(ROOT_DIR, "data", "recently_funded_profs", "raw_nih_leads.csv")
OUTPUT_XL   = os.path.join(ROOT_DIR, "output", "Tuva_Strategic_Radar_Final.xlsx")
OUTPUT_JSON = os.path.join(ROOT_DIR, "output", "outbound_leads.json")

sys.path.insert(0, os.path.join(ROOT_DIR, "scripts", "recently_funded_profs"))
sys.path.insert(0, os.path.join(ROOT_DIR, "scripts", "similar_grants"))

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Tuva Grant Radar",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Tuva Grant Radar")


# ── Name / org formatting helpers ─────────────────────────────────────────────

def _fmt_pi_name(raw):
    """'BEBELL, LISA M' -> 'Lisa M. Bebell'"""
    raw = str(raw).strip()
    if "," not in raw:
        return raw.title()
    last, rest = raw.split(",", 1)
    tokens = rest.strip().split()
    formatted = " ".join(t + "." if len(t) == 1 else t.title() for t in tokens)
    return f"{formatted} {last.title()}"


def _fmt_org(raw):
    """'MASSACHUSETTS GENERAL HOSPITAL' -> 'Massachusetts General Hospital'
    Fixes .title() artifact on apostrophes: "Children'S" -> "Children's"
    """
    s = str(raw).strip().title()
    return re.sub(r"'([A-Z])", lambda m: "'" + m.group(1).lower(), s)


def _nih_name_to_first_last(raw):
    """'SCHMITZ, ROBERT' -> 'Robert Schmitz'"""
    if "," in raw:
        last, first = raw.split(",", 1)
        return f"{first.strip().title()} {last.strip().title()}"
    return raw.title()


# ── Data helpers ──────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_leads():
    if not os.path.exists(LEADS_CSV):
        return pd.DataFrame()
    df = pd.read_csv(LEADS_CSV)
    # Clean date display
    for col in ["award_date", "start_date"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.split("T").str[0]
    # Merge email data from outbound_leads.json (keyed by raw pi_name before formatting)
    if os.path.exists(OUTPUT_JSON):
        with open(OUTPUT_JSON) as f:
            outbound = json.load(f)
        email_map = {
            r["pi_name"]: {
                "email":            r.get("email", {}).get("best_guess") or "",
                "email_confidence": r.get("email", {}).get("confidence") or "",
            }
            for r in outbound
        }
        _conf_labels = {
            "inferred":     "Inferred",
            "llm_inferred": "LLM Inferred",
            "verified":     "Verified",
            "exact":        "Exact",
        }
        df["email"]            = df["pi_name"].map(lambda x: email_map.get(x, {}).get("email", ""))
        df["email_confidence"] = df["pi_name"].map(
            lambda x: _conf_labels.get(
                email_map.get(x, {}).get("email_confidence", ""),
                email_map.get(x, {}).get("email_confidence", "").replace("_", " ").title(),
            )
        )
    return df


def _nih_link(pi_name):
    query = str(pi_name).replace(",", "").strip().replace(" ", "+")
    return f"https://reporter.nih.gov/search/results?query={query}"


def run_pipeline():
    """Ingest + score fresh NIH leads."""
    from ingest_nih_leads import ingest_recent_r01_leads
    from score_leads import score_all_leads
    ingest_recent_r01_leads()
    score_all_leads()
    load_leads.clear()


def fetch_pi_data(prof_name):
    """Fetch PI grant history from NIH and build profile folder."""
    from fetch_pi_history import fetch_pi_data as _fetch
    _fetch(prof_name)


# ── Sidebar — Lead Radar filters (global, always visible) ────────────────────
with st.sidebar:
    st.header("Lead Radar Filters")
    min_score = st.slider("Min Outbound Score", 0.0, 1.0, 0.0, 0.01)
    min_ai    = st.slider("Min AI Signal",      0.0, 1.0, 0.0, 0.01)
    award_types = st.multiselect(
        "Award Type",
        options=["New", "Renewal", "Supplement", "Continuation", "Unknown"],
        default=[],
    )
    st.divider()
    if st.button("Refresh from NIH", use_container_width=True):
        with st.spinner("Scanning NIH for fresh R01s..."):
            run_pipeline()
        st.success("Database refreshed.")


tab1, tab2 = st.tabs(["Lead Radar", "Grant Advisor"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: LEAD RADAR
# ══════════════════════════════════════════════════════════════════════════════

with tab1:
    # ── Load data ─────────────────────────────────────────────────────────────
    df = load_leads()

    if df.empty:
        st.warning(
            "No scored leads found. Click **Refresh from NIH** in the sidebar to fetch data."
        )
        st.stop()

    # ── Apply filters ─────────────────────────────────────────────────────────
    mask = (
        (df["outbound_score"] >= min_score) &
        (df["ai_signal"]      >= min_ai)
    )
    if award_types:
        mask &= df["award_type"].isin(award_types)
    df_filtered = df[mask].reset_index(drop=True)

    # ── Summary metrics ───────────────────────────────────────────────────────
    tier1_count = (df_filtered["tier"] == "Tier 1").sum() if "tier" in df_filtered.columns else 0
    new_count   = (df_filtered["award_type"] == "New").sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Leads",   len(df_filtered))
    col2.metric("Tier 1 Leads",  tier1_count)
    col3.metric("New R01s",      new_count)

    st.divider()

    # ── Build display table ───────────────────────────────────────────────────
    display_cols = {
        "tier":             "Tier",
        "pi_name":          "PI Name",
        "organization":     "Organization",
        "email":            "Email",
        "email_confidence": "Confidence",
        "award_type":       "Award Type",
        "award_amount":     "Award Amount",
        "award_date":       "Award Date",
        "outbound_score":   "Score",
        "ai_signal":        "AI Signal",
        "data_signal":      "Data Signal",
    }
    available = [c for c in display_cols if c in df_filtered.columns]
    df_display = df_filtered[available].rename(columns=display_cols)

    # Apply name / org formatting
    if "PI Name" in df_display.columns:
        df_display["PI Name"] = df_display["PI Name"].apply(_fmt_pi_name)
    if "Organization" in df_display.columns:
        df_display["Organization"] = df_display["Organization"].apply(_fmt_org)

    # ── Interactive table ─────────────────────────────────────────────────────
    selection = st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Score":        st.column_config.NumberColumn(format="%.3f"),
            "AI Signal":    st.column_config.NumberColumn(format="%.3f"),
            "Data Signal":  st.column_config.NumberColumn(format="%.3f"),
            "Award Amount": st.column_config.NumberColumn(format="$%d"),
        },
    )

    # ── Score breakdown panel ─────────────────────────────────────────────────
    selected_rows = selection.selection.rows if selection.selection else []
    if selected_rows:
        idx = selected_rows[0]
        row = df_filtered.iloc[idx]

        st.divider()
        st.subheader(f"Score Breakdown: {_fmt_pi_name(row.get('pi_name', ''))}")

        signal_labels = {
            "grant_freshness":  "Grant Freshness  (weight: 20%)",
            "award_size_score": "Award Size       (weight: 15%)",
            "ai_signal":        "AI Signal        (weight: 30%)",
            "data_signal":      "Data Signal      (weight: 20%)",
            "is_new_award":     "New Award        (weight: 15%)",
        }
        weights = {
            "grant_freshness":  0.20,
            "award_size_score": 0.15,
            "ai_signal":        0.30,
            "data_signal":      0.20,
            "is_new_award":     0.15,
        }

        for col, label in signal_labels.items():
            val = float(row.get(col, 0))
            contribution = val * weights[col]
            st.write(f"**{label}** — raw: `{val:.3f}` | weighted: `{contribution:.3f}`")
            st.progress(val)

        st.write(f"**Total Outbound Score:** `{row.get('outbound_score', 0):.3f}`")
        if row.get("project_title"):
            with st.expander("Project Title"):
                st.write(row["project_title"])
        if row.get("abstract"):
            with st.expander("Abstract"):
                st.write(str(row["abstract"])[:1500] + ("..." if len(str(row.get("abstract", ""))) > 1500 else ""))

        st.link_button("View on NIH Reporter", _nih_link(row.get("pi_name", "")))

    # ── Download buttons ──────────────────────────────────────────────────────
    st.divider()
    dl1, dl2 = st.columns(2)

    if os.path.exists(OUTPUT_JSON):
        with open(OUTPUT_JSON) as f:
            json_bytes = f.read()
        dl1.download_button(
            "Download Outbound JSON",
            data=json_bytes,
            file_name="outbound_leads.json",
            mime="application/json",
        )

    if os.path.exists(OUTPUT_XL):
        with open(OUTPUT_XL, "rb") as f:
            xl_bytes = f.read()
        dl2.download_button(
            "Download Excel Report",
            data=xl_bytes,
            file_name="Tuva_Strategic_Radar_Final.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # ── Metric definitions ────────────────────────────────────────────────────
    with st.expander("What do these scores mean?"):
        st.markdown(
            "**Outbound Score** — Composite priority score (0–1) combining grant freshness, "
            "award size, AI signal, data signal, and whether this is a new award. "
            "Higher = stronger fit for an outbound sales conversation.\n\n"
            "**AI Signal** — Likelihood that the PI's funded research involves AI or ML methods, "
            "based on keywords and phrases in the project abstract. "
            "Tuva's AI-ready data pipelines are most relevant to these researchers.\n\n"
            "**Data Signal** — Likelihood that the grant involves significant data management, "
            "multi-site collection, or large dataset work, based on the abstract. "
            "Tuva's harmonization and data quality tools are the core pitch here."
        )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: GRANT ADVISOR
# ══════════════════════════════════════════════════════════════════════════════

with tab2:
    # Inline header + refresh button (no sidebar involvement)
    col_hdr, col_btn = st.columns([4, 1])
    col_hdr.header("Grant Advisor")
    if col_btn.button("Refresh Grant Database", use_container_width=True):
        with st.spinner("Refreshing grant database... This may take several minutes."):
            from refresh_grant_db import refresh_grant_db
            summary = refresh_grant_db(verbose=False)
        st.success(
            f"Refresh complete. {summary['new']} new grants added. "
            f"{summary['total']} total in database."
        )

    st.write("Enter a PI's name to find the best open grant opportunities for their research profile.")

    # ── Last refresh info ─────────────────────────────────────────────────────
    try:
        from refresh_grant_db import last_refresh_date
        last_refresh = last_refresh_date()
        if last_refresh:
            from datetime import date
            days_ago = (date.today() - date.fromisoformat(last_refresh)).days
            st.caption(f"Grant database last refreshed: {last_refresh} ({days_ago} days ago)")
            if days_ago > 7:
                st.warning("Grant database is over a week old. Consider refreshing.")
        else:
            st.caption("Grant database has not been refreshed yet.")
    except ImportError:
        pass

    # ── Step 1: PI name input + NIH search ───────────────────────────────────
    col_input, col_search = st.columns([4, 1])
    pi_input = col_input.text_input("PI Name", placeholder="e.g. Robert Schmitz")

    if col_search.button("Search PI", type="primary"):
        if not pi_input.strip():
            st.warning("Please enter a PI name.")
        else:
            with st.spinner("Searching NIH records..."):
                try:
                    resp = requests.post(
                        "https://api.reporter.nih.gov/v2/projects/search",
                        json={
                            "criteria": {"pi_names": [{"any_name": pi_input.strip()}]},
                            "include_fields": ["ContactPiName", "Organization"],
                            "limit": 25,
                        },
                        timeout=10,
                    )
                    results = resp.json().get("results", [])
                    candidates = {}
                    for r in results:
                        name = r.get("contact_pi_name", "")
                        org  = (r.get("organization") or {}).get("org_name", "")
                        if name:
                            key = f"{name} — {org}"
                            candidates[key] = {"raw_name": name, "org": org}
                    st.session_state.pi_candidates = candidates
                    st.session_state.confirmed_pi  = None
                except Exception as e:
                    st.error(f"NIH search error: {e}")
                    st.session_state.pi_candidates = {}

    # ── Step 2: Institution picker ────────────────────────────────────────────
    candidates = st.session_state.get("pi_candidates")
    if candidates is not None:
        if len(candidates) == 0:
            st.warning("No NIH records found for this name.")
        elif len(candidates) == 1:
            key = list(candidates.keys())[0]
            st.session_state.confirmed_pi = candidates[key]
            st.info(
                f"Found: **{_fmt_pi_name(candidates[key]['raw_name'])}** "
                f"— {_fmt_org(candidates[key]['org'])}"
            )
        else:
            selected_key = st.selectbox(
                "Select the correct researcher:", list(candidates.keys())
            )
            if st.button("Confirm Selection"):
                st.session_state.confirmed_pi = candidates[selected_key]

    # ── Step 3: Find matching grants ──────────────────────────────────────────
    confirmed = st.session_state.get("confirmed_pi")
    if confirmed:
        prof_name   = _nih_name_to_first_last(confirmed["raw_name"])
        prof_slug   = prof_name.lower().replace(" ", "_")
        data_dir    = os.path.join(ROOT_DIR, "data", "similar_grants")
        prof_folder = os.path.join(data_dir, "profiles", prof_slug)

        st.write(f"**Selected:** {prof_name} — {_fmt_org(confirmed['org'])}")

        if st.button("Find Matching Grants", type="primary"):
            try:
                from match_grants import run_strategic_advisory

                if not os.path.isdir(prof_folder):
                    with st.spinner(f"Building profile from NIH records for {prof_name}..."):
                        fetch_pi_data(prof_name)

                with st.spinner(
                    "Matching against open grants... asking Claude to rank top 5..."
                ):
                    results = run_strategic_advisory(prof_name, verbose=False)

                if not results:
                    st.error("No matches found. Check that the PI profile folder exists.")
                else:
                    has_llm = any(r.get("llm_explanation") for r in results)
                    if not has_llm:
                        st.info(
                            "LLM explanations unavailable — showing top 5 by semantic similarity. "
                            "Set ANTHROPIC_API_KEY in .env to enable LLM reranking."
                        )

                    st.subheader(f"Top Grant Matches for {prof_name}")

                    for r in results:
                        score_pct = int(r["match_score"] * 100)
                        with st.container(border=True):
                            col_score, col_title = st.columns([1, 5])
                            col_score.metric("Match", f"{score_pct}%")
                            col_title.markdown(f"**{r['title']}**")

                            meta_parts = []
                            if r.get("agency"):
                                meta_parts.append(r["agency"])
                            if r.get("close_date") and r["close_date"] not in ("None", "nan", ""):
                                meta_parts.append(f"Closes: {r['close_date']}")
                            if meta_parts:
                                st.caption(" | ".join(meta_parts))

                            if r.get("asks_about_ai"):
                                st.write("Asks about AI/ML methodology")
                            if r.get("requires_data_plan"):
                                st.write("Requires data management plan")

                            if r.get("llm_explanation"):
                                st.write(f"_{r['llm_explanation']}_")

            except FileNotFoundError as e:
                st.error(str(e))
            except ValueError as e:
                st.warning(str(e))
                st.info(
                    "To build a profile, run:\n"
                    "```\npython scripts/similar_grants/fetch_pi_history.py\n```"
                )
            except Exception as e:
                st.error(f"Unexpected error: {e}")
