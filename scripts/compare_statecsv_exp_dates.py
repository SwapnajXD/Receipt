from pathlib import Path
import csv
from datetime import datetime


def main():
    state_path = Path('res/State.csv')
    exp_path = Path('res/final/exp.csv')

    state_rows = list(csv.DictReader(state_path.open('r', encoding='utf-8')))
    exp_rows = list(csv.DictReader(exp_path.open('r', encoding='utf-8')))

    print(f'state_rows:{len(state_rows)}')
    print(f'exp_rows:{len(exp_rows)}')

    if len(state_rows) != len(exp_rows):
        print('row_count_match:False')
        return

    print('row_count_match:True')

    mismatches = []
    for i, (s, e) in enumerate(zip(state_rows, exp_rows), start=2):
        s_date = datetime.strptime(s['Date'].strip(), '%d/%m/%Y').date()
        e_date = datetime.strptime(e['date'].strip(), '%Y-%m-%d %H:%M:%S.%f').date()
        if s_date != e_date:
            mismatches.append((i, s['Date'].strip(), e['date'].strip()))

    print(f'date_mismatches:{len(mismatches)}')
    for rec in mismatches[:20]:
        print(f'mismatch_line:{rec[0]}|state:{rec[1]}|exp:{rec[2]}')


if __name__ == '__main__':
    main()
