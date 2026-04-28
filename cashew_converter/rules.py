from __future__ import annotations

import json
import re
from pathlib import Path

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

LEARNED_RULES_PATH = Path(__file__).resolve().parent / "learned_rules.json"
_LEARNED_RULES_CACHE: dict[str, dict[str, str]] | None = None


def _normalize_learning_key(text: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return re.sub(r"\s+", " ", normalized)


def _style_from_payload(payload: dict[str, str]) -> CategoryStyle:
    return CategoryStyle(
        category=payload.get("category", FALLBACK_STYLE.category),
        subcategory=payload.get("subcategory", ""),
        color=payload.get("color", FALLBACK_STYLE.color),
        icon=payload.get("icon", FALLBACK_STYLE.icon),
        budget=payload.get("budget", FALLBACK_STYLE.budget),
    )


def _load_learned_rules() -> dict[str, dict[str, str]]:
    global _LEARNED_RULES_CACHE
    if _LEARNED_RULES_CACHE is not None:
        return _LEARNED_RULES_CACHE

    if not LEARNED_RULES_PATH.exists():
        _LEARNED_RULES_CACHE = {}
        return _LEARNED_RULES_CACHE

    try:
        data = json.loads(LEARNED_RULES_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {}

    _LEARNED_RULES_CACHE = data if isinstance(data, dict) else {}
    return _LEARNED_RULES_CACHE


def _save_learned_rules(rules_map: dict[str, dict[str, str]]) -> None:
    global _LEARNED_RULES_CACHE
    LEARNED_RULES_PATH.write_text(json.dumps(rules_map, indent=2, sort_keys=True), encoding="utf-8")
    _LEARNED_RULES_CACHE = rules_map


def learn_from_rows(rows: list[dict[str, str]]) -> int:
    """Persist learned merchant/category mappings from edited preview rows."""
    learned = _load_learned_rules().copy()
    updates = 0

    for row in rows:
        note = str(row.get("note", "")).strip()
        category = str(row.get("category name", "")).strip()
        if not note or not category:
            continue

        key = _normalize_learning_key(note)
        if not key:
            continue

        learned[key] = {
            "category": category,
            "subcategory": str(row.get("subcategory name", "")).strip(),
            "color": str(row.get("color", FALLBACK_STYLE.color)).strip() or FALLBACK_STYLE.color,
            "icon": str(row.get("icon", FALLBACK_STYLE.icon)).strip() or FALLBACK_STYLE.icon,
            "budget": str(row.get("budget", FALLBACK_STYLE.budget)).strip(),
        }
        updates += 1

    if updates:
        _save_learned_rules(learned)

    return updates


def classify(transaction: StatementTransaction) -> CategoryStyle:
    if transaction.income:
        return INCOME_STYLE

    learned_rules = _load_learned_rules()
    if learned_rules:
        learned_key = _normalize_learning_key(extract_note(transaction.description))
        if learned_key in learned_rules:
            return _style_from_payload(learned_rules[learned_key])

        searchable_key = _normalize_learning_key(transaction.description)
        for key, payload in learned_rules.items():
            if key and key in searchable_key:
                return _style_from_payload(payload)

    searchable_text = f"{transaction.description}".upper()
    for pattern, style in RULES:
        if pattern.search(searchable_text):
            return style
    return FALLBACK_STYLE


def extract_note(details: str) -> str:
    """Extract a precise, clean merchant or transaction note from bank statement details."""
    if not details or not details.strip():
        return ""
    
    flattened = re.sub(r"\s+", " ", details).strip()
    
    # Remove DEP/WDL TFR prefix
    flattened = re.sub(r"^(DEP|WDL)\s+TFR\s+", "", flattened, flags=re.IGNORECASE)
    
    # Try to extract from UPI transaction format: UPI/CR or UPI/DR/txnid/merchant/bank/ref/desc
    upi_match = re.search(r"UPI/(?:CR|DR)/[^/]+/([^/]+)", flattened, flags=re.IGNORECASE)
    if upi_match:
        merchant = upi_match.group(1).strip()
        # Clean up merchant name: remove extra spaces, normalize
        merchant = re.sub(r"\s+", " ", merchant).strip()
        # Truncate at common delimiters to get just the merchant name
        merchant = re.split(r"[,;]", merchant)[0].strip()
        # Remove trailing numbers/codes (like bank sort codes)
        merchant = re.sub(r"\s+\d+\s*$", "", merchant).strip()
        if merchant:
            return merchant
    
    # Fallback: use the full flattened details capped at 50 chars
    # Remove AT location suffixes (common in bank statements)
    cleaned = re.sub(r"\s+AT\s+\d+.*$", "", flattened, flags=re.IGNORECASE).strip()
    # Truncate to first meaningful phrase if very long
    if len(cleaned) > 50:
        cleaned = cleaned[:50].rsplit(" ", 1)[0].strip()
    
    return cleaned if cleaned else flattened[:50]
