import pandas as pd
import os


def prettify_csv(input_csv, output_xlsx):
    df = pd.read_csv(input_csv)

    # Column ordering: priority columns first, then any extras
    priority_cols = [
        "tier", "outbound_score", "pi_name", "organization", "award_type",
        "award_amount", "award_date", "project_title",
        "ai_signal", "data_signal", "grant_freshness", "award_size_score",
        "is_new_award", "grant_count", "full_project_num", "start_date", "abstract",
    ]
    ordered = [c for c in priority_cols if c in df.columns]
    extra   = [c for c in df.columns if c not in ordered]
    df = df[ordered + extra]

    # Clean date columns — strip time component (always 00:00)
    for date_col in ["award_date", "start_date"]:
        if date_col in df.columns:
            df[date_col] = df[date_col].astype(str).str.split("T").str[0]

    # Round signal columns for readability
    signal_cols = ["outbound_score", "ai_signal", "data_signal",
                   "grant_freshness", "award_size_score"]
    for col in signal_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").round(3)

    # Rename columns for display
    df.columns = df.columns.str.replace("_", " ").str.title()

    writer    = pd.ExcelWriter(output_xlsx, engine="xlsxwriter")
    df.to_excel(writer, index=False, sheet_name="Tuva Lead Radar")
    workbook  = writer.book
    worksheet = writer.sheets["Tuva Lead Radar"]

    # ── Formats ───────────────────────────────────────────────────────────────
    header_fmt = workbook.add_format({
        "bold": True, "text_wrap": True, "valign": "top",
        "fg_color": "#D7E4BC", "border": 1,
    })
    tier1_fmt   = workbook.add_format({"bg_color": "#C6EFCE", "font_color": "#006100", "bold": True})
    tier2_fmt   = workbook.add_format({"bg_color": "#FFEB9C", "font_color": "#9C6500"})
    tier3_fmt   = workbook.add_format({"bg_color": "#DAEEF3"})
    high_score  = workbook.add_format({"bg_color": "#C6EFCE", "font_color": "#006100"})

    col_names = df.columns.tolist()

    # Apply header format
    for col_num, value in enumerate(col_names):
        worksheet.write(0, col_num, value, header_fmt)

    n_rows = len(df)

    # Conditional formatting: Outbound Score >= 0.5
    if "Outbound Score" in col_names:
        idx = col_names.index("Outbound Score")
        worksheet.conditional_format(1, idx, n_rows, idx, {
            "type": "cell", "criteria": ">=", "value": 0.5, "format": high_score,
        })

    # Conditional formatting: Tier badges
    if "Tier" in col_names:
        idx = col_names.index("Tier")
        for tier, fmt in [("Tier 1", tier1_fmt), ("Tier 2", tier2_fmt), ("Tier 3", tier3_fmt)]:
            worksheet.conditional_format(1, idx, n_rows, idx, {
                "type": "text", "criteria": "containing", "value": tier, "format": fmt,
            })

    # Auto column width (capped at 50 for readability)
    for i, col in enumerate(col_names):
        max_content = df[col].astype(str).str.len().max()
        width = min(max(max_content, len(col)) + 2, 50)
        worksheet.set_column(i, i, width)

    writer.close()
    print(f"Report saved to: {output_xlsx}")


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir   = os.path.dirname(os.path.dirname(script_dir))
    input_csv  = os.path.join(root_dir, "data", "recently_funded_profs", "scored_leads.csv")
    output_xl  = os.path.join(root_dir, "output", "Tuva_Strategic_Radar_Final.xlsx")
    os.makedirs(os.path.join(root_dir, "output"), exist_ok=True)
    prettify_csv(input_csv, output_xl)
