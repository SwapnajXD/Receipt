from pathlib import Path
import sys

# Ensure project root is on sys.path so `cashew_converter` imports work when run
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cashew_converter.statement import convert_statement, rows_to_csv_text

path = Path('res/State.xlsx')
rows = convert_statement(path)
print(f'total_rows:{len(rows)}')
for i, row in enumerate(rows[:80]):
    csv = row.to_csv_row()
    print(f'{i}:{csv["date"]}|{csv["amount"]}|{csv["note"]}')
idx = next((i for i, r in enumerate(rows) if str(r.amount) == '1600.0'), None)
print(f'1600_index:{idx}')
if idx is not None:
    start = max(0, idx-5)
    end = idx+5
    print('---context---')
    for i,r in enumerate(rows[start:end], start=start):
        csv = r.to_csv_row()
        print(f'{i}:{csv["date"]}|{csv["amount"]}|{csv["note"]}')

# Write full export to exp.csv in Cashew format
text = rows_to_csv_text(rows)
Path('exp.csv').write_text(text, encoding='utf-8')
print(f'WROTE exp.csv with {len(rows)} transactions')
