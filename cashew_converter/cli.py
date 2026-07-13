from __future__ import annotations

from argparse import ArgumentParser
from collections import Counter
from decimal import Decimal
from pathlib import Path
import csv

from .models import CASHEW_COLUMNS
from .statement import convert_statement


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Convert a bank statement into Cashew CSV format")
    parser.add_argument("input", type=Path, help="Path to the source .xlsx or .csv statement")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Path to the generated Cashew CSV")
    parser.add_argument("--account", default="Sbi", help="Cashew account name to write into the export")
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Only print the transaction count, skip the category summary"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.input.exists():
        parser.error(f"input file not found: {args.input}")

    rows = convert_statement(args.input, account=args.account)
    if not rows:
        print(f"No transactions found in {args.input} - nothing was written to {args.output}")
        return 0

    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CASHEW_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_csv_row())

    print(f"Converted {len(rows)} transactions to {args.output}")

    if not args.quiet:
        _print_summary(rows)

    return 0


def _print_summary(rows) -> None:
    total_income = sum((row.amount for row in rows if row.amount > 0), start=Decimal("0"))
    total_expense = sum((-row.amount for row in rows if row.amount < 0), start=Decimal("0"))
    currency = rows[0].currency

    print(f"  Income:  +{total_income:,.2f} {currency}")
    print(f"  Expense: -{total_expense:,.2f} {currency}")
    print(f"  Net:      {total_income - total_expense:,.2f} {currency}")

    category_counts = Counter(row.category_name for row in rows)
    print("  By category:")
    for category, count in category_counts.most_common():
        print(f"    {category:<20} {count}")


if __name__ == "__main__":
    raise SystemExit(main())
