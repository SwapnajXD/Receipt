from pathlib import Path
import csv
from datetime import datetime


def parse_date(s: str):
    s = s.strip()
    fmts = ["%Y-%m-%d %H:%M:%S.%f", "%d-%m-%Y %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M:%S"]
    for f in fmts:
        try:
            return datetime.strptime(s, f)
        except Exception:
            continue
    raise ValueError(f"unrecognized date format: {s}")


def main():
    path = Path('res/final/exported_cashew.csv')
    backup = path.with_suffix('.csv.bak')
    if path.exists():
        path.replace(backup)
    rows = []
    with backup.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
        for r in reader:
            try:
                dt = parse_date(r['date'])
            except Exception:
                # keep rows with unparsable dates; place them after cutoff
                dt = None
            r['_dt'] = dt
            rows.append(r)

    cutoff = datetime(2024, 7, 15)
    before = [r for r in rows if r['_dt'] and r['_dt'] < cutoff]
    kept = [r for r in rows if not (r['_dt'] and r['_dt'] < cutoff)]

    # ensure 1600.0 is first if present
    idx_1600 = next((i for i, r in enumerate(kept) if r.get('amount') and r.get('amount').strip() in ('1600', '1600.0')), None)
    moved = False
    if idx_1600 is not None:
        row1600 = kept.pop(idx_1600)
        kept.insert(0, row1600)
        moved = True

    # write back
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        for r in kept:
            r2 = {k: v for k, v in r.items() if k in header}
            writer.writerow(r2)

    print(f'ORIGINAL_ROWS:{len(rows)} REMOVED_BEFORE_CUTOFF:{len(before)} WRITTEN_ROWS:{len(kept)} 1600_moved:{moved}')


if __name__ == '__main__':
    main()
