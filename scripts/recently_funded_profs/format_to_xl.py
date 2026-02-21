import pandas as pd

def prettify_csv(input_csv, output_xlsx):
    df = pd.read_csv(input_csv)
    df.columns = df.columns.str.replace('_', ' ').str.title()

    # Remove time from date (it all comes out as 0:00, so it's worthless.) Time information starts w/ 'T', so we split there
    if 'Award Date' in df.columns:
        df['Award Date'] = df['Award Date'].astype(str).str.split('T').str[0]
    
    # Create Excel writer object
    writer = pd.ExcelWriter(output_xlsx, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Tuva Lead Radar')
    
    workbook  = writer.book
    worksheet = writer.sheets['Tuva Lead Radar']

    # Formatting: Header style
    header_format = workbook.add_format({
        'bold': True, 'text_wrap': True, 'valign': 'top',
        'fg_color': '#D7E4BC', 'border': 1
    })

    # Formatting: High-Score Highlight
    high_match_format = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100'})
    
    # Apply header format
    for col_num, value in enumerate(df.columns.values):
        worksheet.write(0, col_num, value, header_format)

    # Conditional formatting Highlight scores > 0.45
    worksheet.conditional_format(1, 4, len(df), 4, {
        'type': 'cell', 'criteria': '>', 'value': 0.45, 'format': high_match_format
    })

    # Auto column width
    for i, col in enumerate(df.columns):
        column_len = max(df[col].astype(str).str.len().max(), len(col)) + 2
        worksheet.set_column(i, i, min(column_len, 50)) # Cap at 50 for readability

    writer.close()
    print(f"Report saved to: {output_xlsx}")

if __name__ == "__main__":
    prettify_csv('data/recently_funded_profs/raw_nih_leads.csv', 'output/Tuva_Strategic_Radar_Final.xlsx')