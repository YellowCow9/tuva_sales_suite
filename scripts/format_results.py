import pandas as pd

def prettify_csv(input_csv, output_xlsx):
    df = pd.read_csv(input_csv)
    
    # Create an Excel writer object
    writer = pd.ExcelWriter(output_xlsx, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Tuva Lead Radar')
    
    workbook  = writer.book
    worksheet = writer.sheets['Tuva Lead Radar']

    # 1. FORMATTING: Header style
    header_format = workbook.add_format({
        'bold': True, 'text_wrap': True, 'valign': 'top',
        'fg_color': '#D7E4BC', 'border': 1
    })

    # 2. FORMATTING: High-Score Highlight
    high_match_format = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100'})
    
    # Apply header format
    for col_num, value in enumerate(df.columns.values):
        worksheet.write(0, col_num, value, header_format)

    # 3. CONDITIONAL FORMATTING: Highlight scores > 0.45
    worksheet.conditional_format(1, 4, len(df), 4, {
        'type': 'cell', 'criteria': '>', 'value': 0.45, 'format': high_match_format
    })

    # 4. AUTO-COLUMN WIDTH
    for i, col in enumerate(df.columns):
        column_len = max(df[col].astype(str).str.len().max(), len(col)) + 2
        worksheet.set_column(i, i, min(column_len, 50)) # Cap at 50 for readability

    writer.close()
    print(f"✅ Prettified report saved to: {output_xlsx}")

if __name__ == "__main__":
    prettify_csv('data/raw_nih_leads.csv', 'output/Tuva_Strategic_Radar_Final.xlsx')