from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET


NAMESPACE = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def load_xlsx_table(path: Path) -> list[dict[str, str]]:
    with ZipFile(path) as archive:
        shared_strings = _load_shared_strings(archive)
        sheet_name = _first_sheet_name(archive)
        sheet_xml = archive.read(sheet_name)
    rows = _parse_sheet_rows(sheet_xml, shared_strings)
    if not rows:
        return []
    headers = rows[0]
    table: list[dict[str, str]] = []
    for row in rows[1:]:
        record = {header: row[index] if index < len(row) else "" for index, header in enumerate(headers)}
        if any(value.strip() for value in record.values()):
            table.append(record)
    return table


def _first_sheet_name(archive: ZipFile) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    relationship_map = {
        relationship.attrib["Id"]: relationship.attrib["Target"]
        for relationship in relationships
        if relationship.attrib.get("Type", "").endswith("/worksheet")
    }
    sheet = workbook.find("a:sheets/a:sheet", NAMESPACE)
    if sheet is None:
        raise ValueError("Workbook does not contain any sheets")
    target = relationship_map[sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]]
    return f"xl/{target}"


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


def _parse_sheet_rows(sheet_xml: bytes, shared_strings: list[str]) -> list[list[str]]:
    root = ET.fromstring(sheet_xml)
    rows: list[list[str]] = []
    for row in root.findall(".//a:row", NAMESPACE):
        cells = row.findall("a:c", NAMESPACE)
        indexed_values: dict[int, str] = {}
        max_index = -1
        for cell in cells:
            ref = cell.attrib.get("r", "A1")
            index = _column_index(ref)
            value = _cell_value(cell, shared_strings)
            indexed_values[index] = value
            max_index = max(max_index, index)
        row_values = [indexed_values.get(index, "") for index in range(max_index + 1)]
        rows.append(row_values)
    return rows


def _cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        text = cell.findtext("a:is/a:t", default="", namespaces=NAMESPACE)
        return text or ""
    value = cell.findtext("a:v", default="", namespaces=NAMESPACE)
    if not value:
        return ""
    if cell_type == "s":
        return shared_strings[int(value)] if value.isdigit() and int(value) < len(shared_strings) else ""
    return value


def _column_index(reference: str) -> int:
    letters = "".join(character for character in reference if character.isalpha())
    index = 0
    for character in letters:
        index = index * 26 + (ord(character.upper()) - ord("A") + 1)
    return index - 1
