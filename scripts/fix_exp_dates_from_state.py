from pathlib import Path
import csv
from datetime import datetime
import sys

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cashew_converter.statement import convert_statement


def main():
    exp_path = Path('res/final/exp.csv')
    exp_rows = list(csv.DictReader(exp_path.open('r', encoding='utf-8')))
    state_rows = convert_statement(Path('res/State.xlsx'))

    if len(exp_rows) != len(state_rows):
        raise SystemExit(f'Row count mismatch: exp={len(exp_rows)} state={len(state_rows)}')

    for i, row in enumerate(exp_rows):
        state_date = state_rows[i].to_csv_row()['date']
        dt = datetime.strptime(state_date, '%Y-%m-%d %H:%M:%S.%f')
        row['date'] = dt.strftime('%Y-%m-%d') + ' 12:00:00.000'

    fieldnames = list(exp_rows[0].keys()) if exp_rows else []
    with exp_path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(exp_rows)

    print(f'updated_rows:{len(exp_rows)}')


if __name__ == '__main__':
    main()
