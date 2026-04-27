from __future__ import annotations

import re

from .models import CategoryStyle, StatementTransaction


INCOME_STYLE = CategoryStyle(
    category="Income",
    subcategory="",
    color="0xff66bb6a",
    icon="coin.png",
    budget="",
)

FALLBACK_STYLE = CategoryStyle(
    category="Transfers",
    subcategory="",
    color="0xff607d8b",
    icon="transfer.png",
    budget="Month",
)

RULES: list[tuple[re.Pattern[str], CategoryStyle]] = [
    (re.compile(r"\bDMART\b|\bD MART\b", re.IGNORECASE), CategoryStyle("Groceries", "", "0xff26a69a", "groceries.png", "Month")),
    (re.compile(r"\bDAILY\s+NE\b|\bDAILY\b", re.IGNORECASE), CategoryStyle("Groceries", "", "0xff26a69a", "groceries.png", "Month")),
    (re.compile(r"\bEGGS?\b", re.IGNORECASE), CategoryStyle("Groceries", "", "0xff26a69a", "groceries.png", "Month")),
    (re.compile(r"\bMETRO\b|\bTRAIN\b|\bCST\b|\bNGP\b", re.IGNORECASE), CategoryStyle("Travel", "Trains", "0xff005190", "plane.png", "Month")),
    (re.compile(r"\bPETROL\b|\bFUEL\b", re.IGNORECASE), CategoryStyle("Travel", "", "0xff005190", "plane.png", "Month")),
    (re.compile(r"\bRECHARGE\b|\bXEROX\b", re.IGNORECASE), CategoryStyle("Bills & Fees", "Recharge", "0xff4caf50", "bills.png", "Month")),
    (re.compile(r"\bBIKANER\b|\bKFC\b|\bBURGER\s+KING\b|\bMOMOS?\b|\bCHAI\b|\bCOF?F?EE\b|\bCHAT\b|\bPANI\b|\bBIRYANI\b|\bSANDWICH\b|\bJUICE\b|\bBURJI\b", re.IGNORECASE), CategoryStyle("Dining", "FastFood", "0xff78909c", "cutlery.png", "Month")),
    (re.compile(r"\bRUSTOM\b|\bCAF[EÉ]\b", re.IGNORECASE), CategoryStyle("Dining", "Cafes", "0xff78909c", "cutlery.png", "Month")),
    (re.compile(r"\bTOOTHPASTE\b|\bSARDI\b|\bDOCTOR\b", re.IGNORECASE), CategoryStyle("Personal Care", "Toiletries", "0xffbdbdbd", "user.png", "Month")),
    (re.compile(r"\bZERODHA\b|\bGIFT\b|\bVIDHAN\b", re.IGNORECASE), CategoryStyle("Gifts", "", "0xfff44336", "gift.png", "Month")),
    (re.compile(r"\bJERSEY\b|\bCLOTH\b|\bSHIRT\b", re.IGNORECASE), CategoryStyle("Shopping", "Clothing", "0xffe91e63", "shopping.png", "Month")),
]


def classify(transaction: StatementTransaction) -> CategoryStyle:
    if transaction.income:
        return INCOME_STYLE

    searchable_text = f"{transaction.description}".upper()
    for pattern, style in RULES:
        if pattern.search(searchable_text):
            return style
    return FALLBACK_STYLE


def extract_note(details: str) -> str:
    flattened = re.sub(r"\s+", " ", details).strip()
    flattened = re.sub(r"^(DEP|WDL)\s+TFR\s+", "", flattened, flags=re.IGNORECASE)
    matched = re.search(r"UPI/(?:CR|DR)/[^/]+/([^/]+)", flattened, flags=re.IGNORECASE)
    if matched:
        return re.sub(r"\s+", " ", matched.group(1)).strip()
    return flattened
