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

from config import SCORING_WEIGHTS, SIGNAL_LABELS

# ── Session state keys ────────────────────────────────────────────────────────
_KEY_PI_CANDIDATES = "pi_candidates"
_KEY_CONFIRMED_PI  = "confirmed_pi"

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT_DIR    = os.path.dirname(os.path.abspath(__file__))

try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(os.path.join(ROOT_DIR, ".env"))
except ImportError:
    pass

# Bridge st.secrets → os.environ for deployed environments (e.g. Streamlit Cloud)
# .env covers local dev; st.secrets covers deployments where .env is gitignored.
try:
    if not os.environ.get("ANTHROPIC_API_KEY") and "ANTHROPIC_API_KEY" in st.secrets:
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    pass

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
    initial_sidebar_state="collapsed",
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

    # Direct grant project link
    if "full_project_num" in df.columns:
        df["grant_link"] = df["full_project_num"].apply(
            lambda num: f"https://reporter.nih.gov/project-details/{num}"
            if pd.notna(num) and str(num).strip() not in ("", "nan") else ""
        )

    return df


def _nih_link(pi_name):
    query = str(pi_name).replace(",", "").strip().replace(" ", "+")
    return f"https://reporter.nih.gov/search/results?query={query}"


def _format_currency(value) -> str:
    """Format a numeric value as '$1,234,567'. Returns '' if null/empty."""
    if pd.isna(value) or str(value).strip() in ("", "nan"):
        return ""
    try:
        return f"${int(float(value)):,}"
    except (ValueError, TypeError):
        return ""


def _search_nih_pi(pi_input: str) -> dict:
    """
    Search NIH Reporter for PIs matching `pi_input`.
    Returns a dict keyed by display label → {"raw_name": ..., "org": ...}.
    Returns empty dict if no matches or API error.
    """
    payload = {
        "criteria": {"pi_names": [{"any_name": pi_input}]},
        "include_fields": ["ContactPiName", "Organization"],
        "limit": 25,
    }
    try:
        resp = requests.post(
            "https://api.reporter.nih.gov/v2/projects/search",
            json=payload, timeout=10,
        )
        resp.raise_for_status()
    except Exception:
        return {}
    results = resp.json().get("results", [])
    candidates = {}
    for r in results:
        name = r.get("contact_pi_name", "")
        org  = (r.get("organization") or {}).get("org_name", "")
        if name:
            label = f"{name} — {org}"
            candidates[label] = {"raw_name": name, "org": org}
    return candidates


def _render_score_breakdown(row: pd.Series) -> None:
    """Render the signal breakdown panel for a selected lead row."""
    st.divider()
    st.markdown(
        f"**{_fmt_pi_name(row['pi_name'])}** — {_fmt_org(row.get('organization', ''))}"
    )

    for col, label in SIGNAL_LABELS.items():
        val = float(row.get(col, 0))
        contribution = val * SCORING_WEIGHTS[col]
        st.write(f"**{label}** — raw: `{val:.3f}` | weighted: `{contribution:.3f}`")
        st.progress(val)

    st.write(f"**Total Outbound Score:** `{row.get('outbound_score', 0):.3f}`")
    if row.get("project_title"):
        with st.expander("Project Title"):
            st.write(row["project_title"])
    if row.get("abstract"):
        with st.expander("Abstract"):
            abstract_text = str(row["abstract"])
            st.write(abstract_text[:1500] + ("..." if len(abstract_text) > 1500 else ""))

    st.link_button("View on NIH Reporter", _nih_link(row.get("pi_name", "")))


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



tab1, tab2 = st.tabs(["Lead Radar", "Grant Advisor"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: LEAD RADAR
# ══════════════════════════════════════════════════════════════════════════════

with tab1:
    # ── Load data ─────────────────────────────────────────────────────────────
    df = load_leads()

    if df.empty:
        st.warning(
            "No scored leads found. Run the pipeline to fetch and score NIH data."
        )
        st.stop()

    df_filtered = df.reset_index(drop=True)

    # ── Summary metrics ───────────────────────────────────────────────────────
    tier1_count = (df_filtered["tier"] == "Tier 1").sum() if "tier" in df_filtered.columns else 0
    new_count   = (df_filtered["award_type"] == "New").sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Leads",   len(df_filtered))
    col2.metric("Tier 1 Leads",  tier1_count)
    col3.metric("New R01s",      new_count)

    st.divider()

    with st.expander("What do these scores mean?", expanded=False):
        st.markdown(
            "**Tier** — Relative priority ranking based on Outbound Score percentile within the current dataset:\n"
            "- **Tier 1** — Top 10%: highest-priority leads, strong fit across multiple signals\n"
            "- **Tier 2** — Top 25%: strong leads worth prioritizing\n"
            "- **Tier 3** — Above median: solid leads for standard outreach\n"
            "- **Tier 4** — Below median: lower priority; deprioritize unless bandwidth allows\n\n"
            "**Outbound Score** — Composite priority score (0–1) combining grant freshness (20%), "
            "award size (15%), AI/ML signal (30%), data signal (20%), and whether this is a new award (15%). "
            "Higher = stronger fit for an outbound sales conversation.\n\n"
            "**Email Confidence** — Reliability of the email address found for this PI:\n"
            "- *Exact* — confirmed match from institutional directory\n"
            "- *Verified* — cross-referenced from multiple sources\n"
            "- *LLM Inferred* — derived by LLM from name/institution pattern\n"
            "- *Inferred* — best-guess pattern match, lowest confidence"
        )

    # ── Build display table ───────────────────────────────────────────────────
    display_cols = {
        "tier":             "Tier",
        "pi_name":          "PI Name",
        "organization":     "Organization",
        "email":            "Email",
        "email_confidence": "Email Confidence",
        "award_type":       "Award Type",
        "award_amount":     "Award Amount",
        "award_date":       "Award Date",
        "outbound_score":   "Score",
        "grant_link":       "Grant Detail",
    }
    available = [c for c in display_cols if c in df_filtered.columns]
    df_display = df_filtered[available].rename(columns=display_cols)

    # Apply name / org formatting
    if "PI Name" in df_display.columns:
        df_display["PI Name"] = df_display["PI Name"].apply(_fmt_pi_name)
    if "Organization" in df_display.columns:
        df_display["Organization"] = df_display["Organization"].apply(_fmt_org)

    # Pre-format Award Amount with comma separators
    if "Award Amount" in df_display.columns:
        df_display["Award Amount"] = df_display["Award Amount"].apply(_format_currency)

    # ── Interactive table ─────────────────────────────────────────────────────
    selection = st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Score":       st.column_config.NumberColumn(format="%.3f"),
            "Grant Detail": st.column_config.LinkColumn(display_text="View ↗"),
        },
    )

    # ── Score breakdown panel ─────────────────────────────────────────────────
    selected_rows = selection.selection.rows if selection.selection else []
    if selected_rows:
        _render_score_breakdown(df_filtered.iloc[selected_rows[0]])

    # ── Download buttons ──────────────────────────────────────────────────────
    st.divider()
    dl1, dl2 = st.columns(2)

    # Build download payload from in-memory DataFrame — no output file dependency.
    top50 = df.sort_values("outbound_score", ascending=False).head(50)
    export_cols = [
        "pi_name", "organization", "award_type", "award_amount",
        "award_date", "project_title", "outbound_score", "tier",
        "email", "email_confidence",
    ]
    export_cols = [c for c in export_cols if c in top50.columns]
    json_bytes = top50[export_cols].to_json(orient="records", indent=2)
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
    except ImportError:
        pass

    # ── Step 1: PI name input + NIH search ───────────────────────────────────
    col_input, col_search = st.columns([4, 1])
    pi_input = col_input.text_input("PI Name", placeholder="e.g. Robert Schmitz")

    if col_search.button("Search PI", type="primary"):
        if not pi_input.strip():
            st.warning("Please enter a PI name.")
        else:
            with st.spinner("Searching NIH..."):
                candidates = _search_nih_pi(pi_input.strip())
            st.session_state[_KEY_PI_CANDIDATES] = candidates
            st.session_state[_KEY_CONFIRMED_PI]  = None
            st.rerun()

    # ── Step 2: Institution picker ────────────────────────────────────────────
    candidates = st.session_state.get(_KEY_PI_CANDIDATES)
    if candidates is not None:
        if len(candidates) == 0:
            st.warning("No NIH records found for this name.")
        elif len(candidates) == 1:
            key = list(candidates.keys())[0]
            st.session_state[_KEY_CONFIRMED_PI] = candidates[key]
            st.info(
                f"Found: **{_fmt_pi_name(candidates[key]['raw_name'])}** "
                f"— {_fmt_org(candidates[key]['org'])}"
            )
        else:
            selected_key = st.selectbox(
                "Select the correct researcher:", list(candidates.keys())
            )
            if st.button("Confirm Selection"):
                st.session_state[_KEY_CONFIRMED_PI] = candidates[selected_key]

    # ── Step 3: Find matching grants ──────────────────────────────────────────
    confirmed = st.session_state.get(_KEY_CONFIRMED_PI)
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
                    "Matching against open grants... ranking top 5..."
                ):
                    results = run_strategic_advisory(prof_name, verbose=False)

                if not results:
                    st.error("No matches found. Check that the PI profile folder exists.")
                else:
                    has_llm = any(r.get("llm_explanation") for r in results)
                    if not has_llm:
                        llm_error = next((r.get("llm_error") for r in results if r.get("llm_error")), None)
                        if llm_error:
                            st.warning(f"LLM reranking failed: {llm_error}")
                        else:
                            st.info(
                                "LLM explanations unavailable — showing top 5 by semantic similarity. "
                                "Set ANTHROPIC_API_KEY in .env to enable LLM reranking."
                            )

                    st.subheader(f"Top Grant Matches for {prof_name}")

                    for r in results:
                        with st.container(border=True):
                            st.markdown(f"**{r['title']}**")

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

                            if r.get("opp_id"):
                                st.link_button(
                                    "View on Grants.gov ↗",
                                    f"https://grants.gov/search-results-detail/{r['opp_id']}",
                                )

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
