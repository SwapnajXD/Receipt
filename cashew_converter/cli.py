from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import csv

from .models import CASHEW_COLUMNS
from .statement import convert_statement


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Convert a bank statement into Cashew CSV format")
    parser.add_argument("input", type=Path, help="Path to the source .xlsx or .csv statement")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Path to the generated Cashew CSV")
    parser.add_argument("--account", default="Sbi", help="Cashew account name to write into the export")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    rows = convert_statement(args.input, account=args.account)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CASHEW_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_csv_row())

    print(f"Converted {len(rows)} transactions to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
