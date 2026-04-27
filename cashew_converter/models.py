from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


CASHEW_COLUMNS = [
    "account",
    "amount",
    "currency",
    "title",
    "note",
    "date",
    "income",
    "type",
    "category name",
    "subcategory name",
    "color",
    "icon",
    "emoji",
    "budget",
    "objective",
]


@dataclass(frozen=True)
class StatementTransaction:
    date: datetime
    description: str
    amount: Decimal
    income: bool


@dataclass(frozen=True)
class CategoryStyle:
    category: str
    subcategory: str
    color: str
    icon: str
    budget: str


@dataclass(frozen=True)
class CashewRow:
    account: str
    amount: Decimal
    currency: str
    title: str
    note: str
    date: datetime
    income: bool
    row_type: str
    category_name: str
    subcategory_name: str
    color: str
    icon: str
    emoji: str
    budget: str
    objective: str

    def to_csv_row(self) -> dict[str, str]:
        return {
            "account": self.account,
            "amount": format_amount(self.amount),
            "currency": self.currency,
            "title": self.title,
            "note": self.note,
            "date": format_date(self.date),
            "income": "true" if self.income else "false",
            "type": self.row_type,
            "category name": self.category_name,
            "subcategory name": self.subcategory_name,
            "color": self.color,
            "icon": self.icon,
            "emoji": self.emoji,
            "budget": self.budget,
            "objective": self.objective,
        }


def format_amount(amount: Decimal) -> str:
    normalized = amount.normalize()
    text = format(normalized, "f")
    if "." not in text:
        text = f"{text}.0"
    return text


def format_date(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S.000")
