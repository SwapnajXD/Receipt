from pathlib import Path
import csv
from collections import Counter


def load_dates(path: Path):
    with path.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return [r['date'].strip() for r in reader]


def main():
    exp_path = Path('res/final/exp.csv')
    exported_path = Path('res/final/exported_cashew.csv')

    exp_dates = load_dates(exp_path)
    exported_dates = load_dates(exported_path)

    print(f'exp_rows:{len(exp_dates)}')
    print(f'exported_rows:{len(exported_dates)}')

    same_len = len(exp_dates) == len(exported_dates)
    print(f'same_length:{same_len}')

    # positional comparison
    mismatch_positions = []
    for i, (a, b) in enumerate(zip(exp_dates, exported_dates), start=2):
        if a != b:
            mismatch_positions.append((i, a, b))
            if len(mismatch_positions) >= 20:
                break
    print(f'positional_mismatches_sample:{len(mismatch_positions)}')
    for rec in mismatch_positions:
        print(f'mismatch_line:{rec[0]}|exp:{rec[1]}|exported:{rec[2]}')

    # multiset comparison
    c_exp = Counter(exp_dates)
    c_exported = Counter(exported_dates)
    missing_in_exported = list((c_exp - c_exported).items())
    extra_in_exported = list((c_exported - c_exp).items())

    print(f'missing_distinct_dates_in_exported:{len(missing_in_exported)}')
    print(f'extra_distinct_dates_in_exported:{len(extra_in_exported)}')
    for d, n in missing_in_exported[:20]:
        print(f'missing:{d}|count:{n}')
    for d, n in extra_in_exported[:20]:
        print(f'extra:{d}|count:{n}')


if __name__ == '__main__':
    main()
