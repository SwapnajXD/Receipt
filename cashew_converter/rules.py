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


def _style(category: str, subcategory: str, color: str, icon: str, budget: str = "Month") -> CategoryStyle:
    return CategoryStyle(category, subcategory, color, icon, budget)


RULES: list[tuple[re.Pattern[str], CategoryStyle]] = [
    (re.compile(r"\bDMART\b|\bD MART\b|\bDAILY\s*NE\b|\bDAILY\s*NEEDS?\b|\bEGGS?\b|\bGROCER(?:Y|IES)\b", re.IGNORECASE), _style("Groceries", "", "0xff26a69a", "groceries.png")),
    (re.compile(r"\bMETRO\b|\bTRAIN\b|\bCST\b|\bNGP\b|\bRAIL\b|\bRAILWAY\b|\bLOCAL,?METRO\b|\bLOCAL\b", re.IGNORECASE), _style("Travel", "Trains", "0xff005190", "plane.png")),
    (re.compile(r"\bPETROL\b|\bFUEL\b|\bTOLL\b|\bPARKING\b", re.IGNORECASE), _style("Travel", "", "0xff005190", "plane.png")),
    (re.compile(r"\bRECHARGE\b|\bXEROX\b|\bBILL\b|\bELECTRIC\b|\bWATER\b|\bDTH\b|\bPOSTPAID\b|\bPREPAID\b", re.IGNORECASE), _style("Bills & Fees", "Recharge", "0xff4caf50", "bills.png")),
    (re.compile(r"\bBIKANER\b|\bKFC\b|\bBURGER\s+KING\b|\bMOMOS?\b|\bCHAI\b|\bCOF?F?EE\b|\bCHAT\b|\bPANI\b|\bBIRYANI\b|\bSANDWICH\b|\bJUICE\b|\bBURJI\b|\bBURGER\b|\bSNACK\b", re.IGNORECASE), _style("Dining", "FastFood", "0xff78909c", "cutlery.png")),
    (re.compile(r"\bRUSTOM\b|\bCAF[EÉ]\b|\bCOFFEE\s*SHOP\b", re.IGNORECASE), _style("Dining", "Cafes", "0xff78909c", "cutlery.png")),
    (re.compile(r"\bTOOTHPASTE\b|\bSARDI\b|\bDOCTOR\b|\bMEDICINE\b|\bPHARMACY\b|\bCLINIC\b", re.IGNORECASE), _style("Personal Care", "Toiletries", "0xffbdbdbd", "user.png")),
    (re.compile(r"\bZERODHA\b|\bGIFT\b|\bVIDHAN\b|\bDONATION\b", re.IGNORECASE), _style("Gifts", "", "0xfff44336", "gift.png")),
    (re.compile(r"\bJERSEY\b|\bCLOTH\b|\bSHIRT\b|\bT-?SHIRT\b|\bPANTS?\b|\bJEANS?\b", re.IGNORECASE), _style("Shopping", "Clothing", "0xffe91e63", "shopping.png")),
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
