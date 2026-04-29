from pathlib import Path
import csv


def main():
    bak = Path('res/final/exported_cashew.csv.bak')
    out = Path('res/final/exported_cashew.csv')
    if not bak.exists():
        print('backup not found:', bak)
        return

    rows = []
    with bak.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
        for r in reader:
            rows.append(r)

    # find 1600 row from State.xlsx canonical form (amount may be '1600' or '1600.0')
    idx = next((i for i, r in enumerate(rows) if r.get('amount') and r.get('amount').strip() in ('1600', '1600.0')), None)
    moved = False
    if idx is not None:
        row1600 = rows.pop(idx)
        rows.insert(0, row1600)
        moved = True

    with out.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print(f'RESTORED:{len(rows)} 1600_moved:{moved}')


if __name__ == '__main__':
    main()
