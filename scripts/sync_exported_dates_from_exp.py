from pathlib import Path
import csv


def read_rows(path: Path):
    with path.open('r', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def main():
    exp_path = Path('res/final/exp.csv')
    exported_path = Path('res/final/exported_cashew.csv')

    exp_rows = read_rows(exp_path)
    exported_rows = read_rows(exported_path)

    if len(exp_rows) != len(exported_rows):
        raise SystemExit(f'Row count mismatch: exp={len(exp_rows)} exported={len(exported_rows)}')

    # Force exact date alignment by row index.
    for i in range(len(exported_rows)):
        exported_rows[i]['date'] = exp_rows[i]['date']

    fieldnames = list(exported_rows[0].keys()) if exported_rows else []
    with exported_path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(exported_rows)

    print(f'updated_rows:{len(exported_rows)}')


if __name__ == '__main__':
    main()
