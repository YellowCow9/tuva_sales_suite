"""
app.py — Tuva Grant Radar: Streamlit Frontend

Tab 1 — Lead Radar:
    Sortable table of fresh R01 grantees ranked by outbound_score.
    Sidebar filters. Score breakdown panel on row selection.
    Download buttons for JSON and Excel.

Tab 2 — Grant Advisor:
    PI name input → 5 grant match cards with LLM explanations.
    Flags shown only when True (AI methodology, data management plan).
"""

import json
import os
import sys

import pandas as pd
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


# ── Helpers ───────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_leads():
    if not os.path.exists(LEADS_CSV):
        return pd.DataFrame()
    df = pd.read_csv(LEADS_CSV)
    # Clean date display
    for col in ["award_date", "start_date"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.split("T").str[0]
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


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: LEAD RADAR
# ══════════════════════════════════════════════════════════════════════════════

tab1, tab2 = st.tabs(["Lead Radar", "Grant Advisor"])

with tab1:
    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("Filters")
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
        "tier":           "Tier",
        "pi_name":        "PI Name",
        "organization":   "Organization",
        "award_type":     "Award Type",
        "award_amount":   "Award Amount",
        "award_date":     "Award Date",
        "outbound_score": "Score",
        "ai_signal":      "AI Signal",
        "data_signal":    "Data Signal",
    }
    available = [c for c in display_cols if c in df_filtered.columns]
    df_display = df_filtered[available].rename(columns=display_cols)

    # ── Interactive table ─────────────────────────────────────────────────────
    selection = st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Score":      st.column_config.NumberColumn(format="%.3f"),
            "AI Signal":  st.column_config.NumberColumn(format="%.3f"),
            "Data Signal": st.column_config.NumberColumn(format="%.3f"),
            "Award Amount": st.column_config.NumberColumn(format="$%d"),
        },
    )

    # ── Score breakdown panel ─────────────────────────────────────────────────
    selected_rows = selection.selection.rows if selection.selection else []
    if selected_rows:
        idx = selected_rows[0]
        row = df_filtered.iloc[idx]

        st.divider()
        st.subheader(f"Score Breakdown: {row.get('pi_name', '')}")

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


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: GRANT ADVISOR
# ══════════════════════════════════════════════════════════════════════════════

with tab2:
    st.header("Grant Advisor")
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

    with st.sidebar:
        if tab2:
            st.divider()
            if st.button("Refresh Grant Database", use_container_width=True, key="refresh_grants"):
                with st.spinner("Refreshing grant database... This may take several minutes."):
                    from refresh_grant_db import refresh_grant_db
                    summary = refresh_grant_db(verbose=False)
                st.success(
                    f"Refresh complete. {summary['new']} new grants added. "
                    f"{summary['total']} total in database."
                )

    # ── PI name input ─────────────────────────────────────────────────────────
    pi_input = st.text_input("PI Name", placeholder="e.g. Shannon Quinn")

    if st.button("Find Matching Grants", type="primary"):
        if not pi_input.strip():
            st.warning("Please enter a PI name.")
        else:
            try:
                from match_grants import run_strategic_advisory

                with st.spinner(
                    "Fetching PI profile... matching against open grants... asking Claude to rank top 5..."
                ):
                    results = run_strategic_advisory(pi_input.strip(), verbose=False)

                if not results:
                    st.error("No matches found. Check that the PI profile folder exists.")
                else:
                    has_llm = any(r.get("llm_explanation") for r in results)
                    if not has_llm:
                        st.info(
                            "LLM explanations unavailable — showing top 5 by semantic similarity. "
                            "Set ANTHROPIC_API_KEY in .env to enable LLM reranking."
                        )

                    st.subheader(f"Top Grant Matches for {pi_input.strip()}")

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
                # Profile not found or empty
                st.warning(str(e))
                st.info(
                    "To build a profile, run:\n"
                    "```\npython scripts/similar_grants/fetch_pi_history.py\n```"
                )
            except Exception as e:
                st.error(f"Unexpected error: {e}")
