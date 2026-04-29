from pathlib import Path
import csv
from datetime import datetime


def main():
    path = Path('res/final/exported_cashew.csv')
    rows = list(csv.DictReader(path.open('r', encoding='utf-8')))
    parsed = [datetime.strptime(r['date'], '%Y-%m-%d %H:%M:%S.%f') for r in rows]
    cutoff = datetime(2024, 7, 15)
    before = [
        (i + 2, r['date'], r['amount'], r['note'])
        for i, r in enumerate(rows)
        if datetime.strptime(r['date'], '%Y-%m-%d %H:%M:%S.%f') < cutoff
    ]

    print(f'rows:{len(rows)}')
    print(f'before_cutoff:{len(before)}')
    print(f'min_date:{min(parsed)}')
    print(f'max_date:{max(parsed)}')
    for rec in before[:20]:
        print(f'bad:{rec[0]}|{rec[1]}|{rec[2]}|{rec[3]}')


if __name__ == '__main__':
    main()
