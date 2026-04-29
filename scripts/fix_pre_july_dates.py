from pathlib import Path
import csv
from datetime import datetime
import sys

# Ensure project root is on sys.path so `cashew_converter` imports work when run
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cashew_converter.statement import convert_statement


def swap_month_day(dt: datetime) -> datetime:
    return datetime(dt.year, dt.day, dt.month, dt.hour, dt.minute, dt.second, dt.microsecond)


def main():
    target = Path('res/final/exported_cashew.csv')
    rows = list(csv.DictReader(target.open('r', encoding='utf-8')))
    header = list(rows[0].keys()) if rows else []

    cutoff = datetime(2024, 7, 15)
    fixed = 0

    for r in rows:
        dt = datetime.strptime(r['date'], '%Y-%m-%d %H:%M:%S.%f')
        if dt < cutoff:
            corrected = swap_month_day(dt)
            r['date'] = corrected.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            fixed += 1

    with target.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)

    # Cross-check timeline start against State.xlsx conversion
    state_rows = convert_statement(Path('res/State.xlsx'))
    state_first = state_rows[0].to_csv_row()['date'] if state_rows else 'N/A'

    # Post-fix checks
    parsed = [datetime.strptime(r['date'], '%Y-%m-%d %H:%M:%S.%f') for r in rows]
    before_cutoff = sum(1 for d in parsed if d < cutoff)
    first_amount = rows[0]['amount'] if rows else 'N/A'
    first_date = rows[0]['date'] if rows else 'N/A'

    print(f'rows:{len(rows)} fixed_rows:{fixed} before_cutoff_after_fix:{before_cutoff}')
    print(f'first_row_amount:{first_amount} first_row_date:{first_date}')
    print(f'state_first_date:{state_first}')


if __name__ == '__main__':
    main()
