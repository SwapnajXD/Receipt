from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
from pathlib import Path
from zipfile import ZipFile
import re
import xml.etree.ElementTree as ET


NAMESPACE = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

# Excel's built-in numFmtId values that render as a date and/or time.
# See ECMA-376 Part 1, section 18.8.30.
BUILTIN_DATE_FORMAT_IDS = {14, 15, 16, 17, 18, 19, 20, 21, 22, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 45, 46, 47, 50, 57}
_DATE_TOKEN_RE = re.compile(r"(?<![\\\[])[ymdhs]", re.IGNORECASE)
# Excel's epoch for serial date 1 is 1899-12-31 with a phantom 1900-02-29;
# using 1899-12-30 as the anchor makes `epoch + timedelta(days=serial)` correct
# for all real dates (this is the same trick openpyxl and Excel itself use).
_EXCEL_EPOCH = datetime(1899, 12, 30)
HEADER_HINTS = {
    "date",
    "transaction date",
    "txn date",
    "value date",
    "details",
    "description",
    "particulars",
    "narration",
    "debit",
    "credit",
    "balance",
    "amount",
    "dr",
    "cr",
}


def load_xlsx_table(path: Path) -> list[dict[str, str]]:
    with ZipFile(path) as archive:
        shared_strings = _load_shared_strings(archive)
        date_style_indices = _load_date_style_indices(archive)
        candidate_tables: list[tuple[int, list[dict[str, str]]]] = []
        for sheet_name in _all_sheet_names(archive):
            sheet_xml = archive.read(sheet_name)
            rows = _parse_sheet_rows(sheet_xml, shared_strings, date_style_indices)
            if not rows:
                continue
            score, table = _rows_to_scored_table(rows)
            if table:
                candidate_tables.append((score, table))

    if not candidate_tables:
        return []
    candidate_tables.sort(key=lambda item: item[0], reverse=True)
    return candidate_tables[0][1]


def _all_sheet_names(archive: ZipFile) -> list[str]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    relationship_map = {
        relationship.attrib["Id"]: relationship.attrib["Target"]
        for relationship in relationships
        if relationship.attrib.get("Type", "").endswith("/worksheet")
    }
    sheet_names: list[str] = []
    for sheet in workbook.findall("a:sheets/a:sheet", NAMESPACE):
        relation_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        if relation_id and relation_id in relationship_map:
            sheet_names.append(_resolve_worksheet_path(relationship_map[relation_id]))
    return sheet_names


def _resolve_worksheet_path(target: str) -> str:
    # Relationship targets are usually relative to xl/ (e.g. "worksheets/sheet1.xml"),
    # but some writers (e.g. openpyxl) emit package-absolute targets that already
    # start with "/xl/..." -- prefixing those with "xl/" again produced a bogus
    # "xl//xl/worksheets/sheet1.xml" path and a KeyError when reading the archive.
    if target.startswith("/"):
        return target.lstrip("/")
    return f"xl/{target}"


def _rows_to_scored_table(rows: list[list[str]]) -> tuple[int, list[dict[str, str]]]:
    if not rows:
        return (0, [])

    header_index = _best_header_index(rows)
    headers = rows[header_index]
    table: list[dict[str, str]] = []
    for row in rows[header_index + 1 :]:
        record = {header: row[index] if index < len(row) else "" for index, header in enumerate(headers)}
        if any(value.strip() for value in record.values()):
            table.append(record)

    header_score = _header_score(headers)
    width_score = sum(1 for value in headers if (value or "").strip())
    row_score = min(len(table), 500)
    return (header_score * 1000 + width_score * 10 + row_score, table)


def _best_header_index(rows: list[list[str]]) -> int:
    search_limit = min(len(rows), 40)
    best_index = 0
    best_score = -1
    for index in range(search_limit):
        score = _header_score(rows[index])
        if score > best_score:
            best_score = score
            best_index = index
    return best_index


def _header_score(headers: list[str]) -> int:
    normalized = {_normalize_header(value) for value in headers if (value or "").strip()}
    return sum(1 for value in normalized if value in HEADER_HINTS)


def _normalize_header(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _load_shared_strings(archive: ZipFile) -> list[str]:
    try:
        shared_xml = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(shared_xml)
    values: list[str] = []
    for item in root.findall("a:si", NAMESPACE):
        text_fragments = [node.text or "" for node in item.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")]
        values.append("".join(text_fragments))
    return values


def _load_date_style_indices(archive: ZipFile) -> set[int]:
    """Return the set of cellXfs style indices (the `s` attribute on <c>) that format as a date."""
    try:
        styles_xml = archive.read("xl/styles.xml")
    except KeyError:
        return set()

    root = ET.fromstring(styles_xml)
    custom_formats = {
        int(fmt.attrib["numFmtId"]): fmt.attrib.get("formatCode", "")
        for fmt in root.findall("a:numFmts/a:numFmt", NAMESPACE)
    }

    def is_date_format_id(num_fmt_id: int) -> bool:
        if num_fmt_id in BUILTIN_DATE_FORMAT_IDS:
            return True
        format_code = custom_formats.get(num_fmt_id, "")
        if not format_code or format_code.lower() == "general":
            return False
        # Strip bracketed locale/color tags like [$-409] or [Red] before checking for date tokens.
        stripped = re.sub(r"\[[^\]]*\]", "", format_code)
        return bool(_DATE_TOKEN_RE.search(stripped))

    date_style_indices: set[int] = set()
    cell_xfs = root.find("a:cellXfs", NAMESPACE)
    if cell_xfs is not None:
        for index, xf in enumerate(cell_xfs.findall("a:xf", NAMESPACE)):
            num_fmt_id = int(xf.attrib.get("numFmtId", "0") or "0")
            if is_date_format_id(num_fmt_id):
                date_style_indices.add(index)
    return date_style_indices


def _excel_serial_to_date_string(serial_text: str) -> str | None:
    try:
        serial = float(serial_text)
    except ValueError:
        return None
    value = _EXCEL_EPOCH + timedelta(days=serial)
    if value.time() == datetime.min.time():
        return value.strftime("%Y-%m-%d")
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _parse_sheet_rows(
    sheet_xml: bytes, shared_strings: list[str], date_style_indices: set[int] | None = None
) -> list[list[str]]:
    date_style_indices = date_style_indices or set()
    root = ET.fromstring(sheet_xml)
    rows: list[list[str]] = []
    for row in root.findall(".//a:row", NAMESPACE):
        cells = row.findall("a:c", NAMESPACE)
        indexed_values: dict[int, str] = {}
        max_index = -1
        for cell in cells:
            ref = cell.attrib.get("r", "A1")
            index = _column_index(ref)
            value = _cell_value(cell, shared_strings, date_style_indices)
            indexed_values[index] = value
            max_index = max(max_index, index)
        row_values = [indexed_values.get(index, "") for index in range(max_index + 1)]
        rows.append(row_values)
    return rows


def _cell_value(cell: ET.Element, shared_strings: list[str], date_style_indices: set[int]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        text = cell.findtext("a:is/a:t", default="", namespaces=NAMESPACE)
        return text or ""
    value = cell.findtext("a:v", default="", namespaces=NAMESPACE)
    if not value:
        return ""
    if cell_type == "s":
        return shared_strings[int(value)] if value.isdigit() and int(value) < len(shared_strings) else ""

    style_index = cell.attrib.get("s")
    if cell_type in (None, "n") and style_index is not None and int(style_index) in date_style_indices:
        date_string = _excel_serial_to_date_string(value)
        if date_string is not None:
            return date_string
    return value


def _column_index(reference: str) -> int:
    letters = "".join(character for character in reference if character.isalpha())
    index = 0
    for character in letters:
        index = index * 26 + (ord(character.upper()) - ord("A") + 1)
    return index - 1
