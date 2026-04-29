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
    state_dates = [r.to_csv_row()['date'] for r in state_rows]

    print(f'exp_rows:{len(exp_rows)}')
    print(f'state_rows:{len(state_dates)}')

    if len(exp_rows) != len(state_dates):
        print('row_count_match:False')
        return

    print('row_count_match:True')

    mismatches = []
    for i, (exp_row, state_date) in enumerate(zip(exp_rows, state_dates), start=2):
        exp_dt = datetime.strptime(exp_row['date'], '%Y-%m-%d %H:%M:%S.%f')
        state_dt = datetime.strptime(state_date, '%Y-%m-%d %H:%M:%S.%f')
        if exp_dt.date() != state_dt.date():
            mismatches.append((i, exp_row['date'], state_date))

    print(f'date_mismatches:{len(mismatches)}')
    for line_no, exp_date, st_date in mismatches[:20]:
        print(f'mismatch_line:{line_no}|exp:{exp_date}|state:{st_date}')


if __name__ == '__main__':
    main()
