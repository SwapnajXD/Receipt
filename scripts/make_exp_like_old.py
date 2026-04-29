from pathlib import Path
import csv
from datetime import datetime


def normalize_date(value: str) -> str:
    value = value.strip()
    # Current exp format is DD-MM-YYYY HH:MM:SS.mmm
    dt = datetime.strptime(value, '%d-%m-%Y %H:%M:%S.%f')
    # old.csv uses YYYY-MM-DD and a noon timestamp
    return dt.strftime('%Y-%m-%d') + ' 12:00:00.000'


def normalize_income(value: str) -> str:
    v = value.strip().lower()
    if v in ('true', '1', 'yes'):
        return 'True'
    return 'False'


def main():
    path = Path('res/final/exp.csv')
    rows = list(csv.DictReader(path.open('r', encoding='utf-8')))
    fieldnames = rows[0].keys() if rows else []

    for row in rows:
        row['date'] = normalize_date(row['date'])
        row['income'] = normalize_income(row['income'])
        if row.get('type', '').strip().lower() == 'null':
            row['type'] = ''

    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f'updated_rows:{len(rows)}')


if __name__ == '__main__':
    main()
