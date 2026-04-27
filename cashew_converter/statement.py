from __future__ import annotations

from csv import DictReader, Sniffer
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import StringIO
from pathlib import Path
import re

from .models import CashewRow, StatementTransaction
from .rules import classify, extract_note
from .xlsx import load_xlsx_table


HEADER_SYNONYMS = {
    "date": {"date", "transaction date", "txn date", "value date"},
    "details": {"details", "description", "particulars", "narration", "note"},
    "debit": {"debit", "withdrawal", "dr"},
    "credit": {"credit", "deposit", "cr"},
    "balance": {"balance", "running balance"},
    "amount": {"amount", "amt"},
    "type": {"type", "dr/cr", "transaction type"},
}

DATE_FORMATS = [
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
]


def convert_statement(path: Path, account: str = "Sbi") -> list[CashewRow]:
    rows = load_statement_rows(path)
    transactions: list[StatementTransaction] = []
    for row in rows:
        if _is_ignorable_row(row) or not _has_parseable_date(row):
            continue
        transactions.append(row_to_transaction(row))
    return [transaction_to_cashew(transaction, account=account) for transaction in transactions]


def load_statement_rows(path: Path) -> list[dict[str, str]]:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xlsm", ".xltx", ".xltm"}:
        return load_xlsx_table(path)
    if suffix == ".csv":
        return load_csv_table(path)
    raise ValueError(f"Unsupported file type: {path.suffix}")


def load_csv_table(path: Path) -> list[dict[str, str]]:
    content = path.read_text(encoding="utf-8-sig")
    sample = content[:4096]
    dialect = Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"])
    reader = DictReader(StringIO(content), dialect=dialect)
    return [{(key or "").strip(): (value or "").strip() for key, value in row.items()} for row in reader]


def row_to_transaction(row: dict[str, str]) -> StatementTransaction:
    date_value = _pick_value(row, HEADER_SYNONYMS["date"])
    details_value = _pick_value(row, HEADER_SYNONYMS["details"])
    debit_value = _pick_value(row, HEADER_SYNONYMS["debit"])
    credit_value = _pick_value(row, HEADER_SYNONYMS["credit"])
    amount_value = _pick_value(row, HEADER_SYNONYMS["amount"])
    type_value = _pick_value(row, HEADER_SYNONYMS["type"])

    if not date_value:
        raise ValueError("Missing date column in statement row")

    date = _parse_date(date_value)
    note = extract_note(details_value or "")

    amount = _parse_amount_from_row(debit_value, credit_value, amount_value, type_value)
    income = amount > 0
    return StatementTransaction(date=date, description=note, amount=amount, income=income)


def _is_ignorable_row(row: dict[str, str]) -> bool:
    combined = " ".join(value for value in row.values() if value).strip().lower()
    if not combined:
        return True
    ignored_markers = [
        "statement summary",
        "brought forward",
        "count total",
        "total debits",
        "total credits",
        "closing balance",
    ]
    return any(marker in combined for marker in ignored_markers)


def _has_parseable_date(row: dict[str, str]) -> bool:
    date_value = _pick_value(row, HEADER_SYNONYMS["date"])
    if not date_value:
        return False
    try:
        _parse_date(date_value)
    except ValueError:
        return False
    return True


def transaction_to_cashew(transaction: StatementTransaction, account: str) -> CashewRow:
    style = classify(transaction)
    return CashewRow(
        account=account,
        amount=transaction.amount,
        currency="INR",
        title="",
        note=transaction.description,
        date=transaction.date,
        income=transaction.income,
        row_type="null",
        category_name=style.category,
        subcategory_name=style.subcategory,
        color=style.color,
        icon=style.icon,
        emoji="",
        budget=style.budget,
        objective="",
    )


def _pick_value(row: dict[str, str], aliases: set[str]) -> str:
    normalized_row = {_normalize_header(key): value for key, value in row.items()}
    for alias in aliases:
        normalized_alias = _normalize_header(alias)
        if normalized_alias in normalized_row and normalized_row[normalized_alias].strip():
            return normalized_row[normalized_alias].strip()
    return ""


def _normalize_header(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _parse_date(value: str) -> datetime:
    cleaned = value.strip()
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, date_format)
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {value!r}")


def _parse_amount_from_row(debit: str, credit: str, amount: str, type_value: str) -> Decimal:
    debit_amount = _parse_decimal(debit)
    credit_amount = _parse_decimal(credit)
    if debit_amount is not None and credit_amount is not None:
        raise ValueError("Row contains both debit and credit values")
    if credit_amount is not None:
        return credit_amount
    if debit_amount is not None:
        return -debit_amount

    amount_value = _parse_decimal(amount)
    if amount_value is None:
        raise ValueError("Could not determine amount for statement row")
    if type_value and type_value.strip().lower() in {"dr", "debit", "withdrawal", "expense"}:
        return -amount_value.copy_abs()
    return amount_value


def _parse_decimal(value: str) -> Decimal | None:
    cleaned = value.strip().replace(",", "")
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid amount value: {value!r}") from exc
