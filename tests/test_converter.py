from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import csv
from decimal import Decimal
from io import BytesIO
import json
import unittest
import zipfile
from wsgiref.util import setup_testing_defaults

from cashew_converter.models import CASHEW_COLUMNS
from cashew_converter.rules import LEARNED_RULES_PATH
from cashew_converter.statement import convert_statement, load_statement_rows, row_to_transaction
from cashew_converter.web import application, convert_uploaded_statement, render_page
from cashew_converter.xlsx import load_xlsx_table


ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "res" / "bstate.xlsx"
requires_sample_workbook = unittest.skipUnless(
    WORKBOOK.exists(),
    "requires a local res/bstate.xlsx fixture (a real bank statement, not committed for privacy)",
)


def _write_minimal_xlsx(
    path: Path,
    *,
    rows: list[list[str]],
    date_cell_style: int | None = None,
    absolute_relationship_target: bool = False,
) -> None:
    """Build a tiny but real .xlsx file by hand, so xlsx-parsing tests don't need openpyxl.

    If date_cell_style is given, the first cell of every data row (rows[1:]) is written as
    a numeric Excel date serial styled with that cellXfs index, mimicking a real date cell
    (as opposed to a plain text date string).
    """
    sheet_rows_xml = []
    for row_index, row in enumerate(rows, start=1):
        cells_xml = []
        for col_index, value in enumerate(row):
            column_letter = chr(ord("A") + col_index)
            ref = f"{column_letter}{row_index}"
            if date_cell_style is not None and row_index > 1 and col_index == 0:
                cells_xml.append(f'<c r="{ref}" s="{date_cell_style}"><v>{value}</v></c>')
            else:
                cells_xml.append(f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>')
        sheet_rows_xml.append(f'<row r="{row_index}">{"".join(cells_xml)}</row>')

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows_xml)}</sheetData></worksheet>'
    )

    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )

    target = "/xl/worksheets/sheet1.xml" if absolute_relationship_target else "worksheets/sheet1.xml"
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="{target}"/>'
        "</Relationships>"
    )

    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<cellXfs count="2">'
        '<xf numFmtId="0"/>'
        '<xf numFmtId="14"/>'
        "</cellXfs></styleSheet>"
    )

    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        "</Types>"
    )

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types_xml)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", rels_xml)
        archive.writestr("xl/styles.xml", styles_xml)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)


class ConverterTests(unittest.TestCase):
    def tearDown(self) -> None:
        if LEARNED_RULES_PATH.exists():
            LEARNED_RULES_PATH.unlink()

    @requires_sample_workbook
    def test_xlsx_reader_extracts_rows(self) -> None:
        rows = load_statement_rows(WORKBOOK)
        self.assertGreater(len(rows), 0)
        self.assertEqual(rows[0]["Date"], "05/09/2024")
        self.assertIn("DEP TFR", rows[0]["Details"])

    @requires_sample_workbook
    def test_statement_row_to_transaction_uses_debit_and_credit(self) -> None:
        rows = load_statement_rows(WORKBOOK)
        income_row = row_to_transaction(rows[0])
        expense_row = row_to_transaction(rows[2])
        self.assertTrue(income_row.income)
        self.assertEqual(str(income_row.amount), "50000.00")
        self.assertFalse(expense_row.income)
        self.assertEqual(str(expense_row.amount), "-100000.00")

    @requires_sample_workbook
    def test_converter_writes_cashew_schema(self) -> None:
        rows = convert_statement(WORKBOOK)
        self.assertGreater(len(rows), 0)
        first_row = rows[0].to_csv_row()
        self.assertEqual(list(first_row.keys()), CASHEW_COLUMNS)
        self.assertEqual(first_row["income"], "True")
        self.assertEqual(first_row["category name"], "Income")

    @requires_sample_workbook
    def test_keyword_rules_cover_sample_transactions(self) -> None:
        rows = convert_statement(WORKBOOK)
        grocery_row = next(row for row in rows if row.note == "DMART AV")
        self.assertEqual(grocery_row.category_name, "Groceries")
        self.assertEqual(grocery_row.icon, "groceries.png")

    @requires_sample_workbook
    def test_can_export_to_csv(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "cashew.csv"
            rows = convert_statement(WORKBOOK)
            with output.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=CASHEW_COLUMNS)
                writer.writeheader()
                for row in rows[:3]:
                    writer.writerow(row.to_csv_row())
            self.assertTrue(output.exists())
            self.assertGreater(output.read_text(encoding="utf-8").count("account,"), 0)

    def test_xlsx_reader_converts_real_date_cells(self) -> None:
        # Regression test: dates stored as real Excel date cells (numeric serials with a
        # date-formatted style) used to be read as raw serial numbers like "45540", which
        # never matched a known date format and caused the row to be silently dropped.
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "date_cells.xlsx"
            _write_minimal_xlsx(
                path,
                rows=[
                    ["Date", "Details", "Debit", "Credit", "Balance"],
                    ["45540", "DEP TFR UPI/CR/1/DMART AV/x/y", "", "50000", "50000"],
                ],
                date_cell_style=1,
            )
            table = load_xlsx_table(path)
            self.assertEqual(len(table), 1)
            self.assertEqual(table[0]["Date"], "2024-09-05")

            rows = convert_statement(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].amount, Decimal("50000"))

    def test_xlsx_reader_handles_absolute_relationship_targets(self) -> None:
        # Regression test: some writers (e.g. openpyxl) emit package-absolute relationship
        # targets like "/xl/worksheets/sheet1.xml", which used to be prefixed with another
        # "xl/" and crash with a KeyError when reading the archive.
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "absolute_target.xlsx"
            _write_minimal_xlsx(
                path,
                rows=[["Date", "Details", "Debit", "Credit", "Balance"]],
                absolute_relationship_target=True,
            )
            table = load_xlsx_table(path)
            self.assertEqual(table, [])  # header-only sheet, but no crash

    def test_preview_page_bulk_edit_and_toast_elements_are_wired_up(self) -> None:
        # Regression test: the bulk-edit value control and the toast notification used
        # to reference DOM ids/classes that didn't exist in the rendered markup
        # ("bulk-value-input"/"bulk-value-select" vs "bulk-value", and ".success-banner"
        # vs "#toast"), so both features silently threw JS errors and did nothing.
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "single_row.xlsx"
            _write_minimal_xlsx(
                path,
                rows=[
                    ["Date", "Details", "Debit", "Credit", "Balance"],
                    ["05/09/2024", "DEP TFR UPI/CR/1/DMART AV/x/y", "", "50000", "50000"],
                ],
            )
            rows = convert_statement(path)

        from cashew_converter.web import render_preview_page

        html = render_preview_page(rows).decode("utf-8")
        self.assertIn('id="bulk-value-input"', html)
        self.assertIn('id="bulk-value-select"', html)
        self.assertIn('id="toast"', html)
        self.assertNotIn("success-banner", html)
        self.assertNotIn("{total_income}", html)
        self.assertNotIn("{category_colors}", html)


        environ = {}
        setup_testing_defaults(environ)
        environ["REQUEST_METHOD"] = "GET"
        status: list[str] = []

        def start_response(value, headers):
            status.append(value)

        body = b"".join(application(environ, start_response))
        self.assertEqual(status[0], "200 OK")
        self.assertIn(b"Cashew Converter", body)

    @requires_sample_workbook
    def test_web_upload_conversion_returns_preview(self) -> None:
        boundary = "----CashewBoundary7e3f8c"
        workbook_bytes = WORKBOOK.read_bytes()
        body = b"".join(
            [
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"account\"\r\n\r\nSbi\r\n".encode("utf-8"),
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"statement\"; filename=\"bstate.xlsx\"\r\nContent-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n\r\n".encode("utf-8"),
                workbook_bytes,
                f"\r\n--{boundary}--\r\n".encode("utf-8"),
            ]
        )
        environ = {}
        setup_testing_defaults(environ)
        environ["REQUEST_METHOD"] = "POST"
        environ["CONTENT_TYPE"] = f"multipart/form-data; boundary={boundary}"
        environ["CONTENT_LENGTH"] = str(len(body))
        environ["wsgi.input"] = BytesIO(body)

        status: list[str] = []
        headers: list[tuple[str, str]] = []

        def start_response(value, response_headers):
            status.append(value)
            headers.extend(response_headers)

        response_body = b"".join(application(environ, start_response))
        self.assertEqual(status[0], "200 OK")
        self.assertEqual(dict(headers)["Content-Type"], "text/html; charset=utf-8")
        self.assertIn(b"Conversion Complete", response_body)
        self.assertIn(b"139 transactions", response_body)
        self.assertIn(b"<th>account</th>", response_body)
        self.assertIn(b"<th>amount</th>", response_body)
        self.assertIn(b'<select class="cell-control select-control"', response_body)
        self.assertIn(b'name="subcategory name"', response_body)
        self.assertIn(b'type="date"', response_body)
        self.assertIn(b'<input class="cell-control input-control"', response_body)
        self.assertIn(b"Download CSV", response_body)

    def test_web_learn_endpoint_accepts_rows(self) -> None:
        payload = {
            "rows": [
                {
                    "note": "DMART AV",
                    "category name": "Groceries",
                    "subcategory name": "",
                    "color": "0xff26a69a",
                    "icon": "groceries.png",
                    "budget": "Month",
                }
            ]
        }

        body = json.dumps(payload).encode("utf-8")
        environ = {}
        setup_testing_defaults(environ)
        environ["REQUEST_METHOD"] = "POST"
        environ["PATH_INFO"] = "/learn"
        environ["CONTENT_TYPE"] = "application/json"
        environ["CONTENT_LENGTH"] = str(len(body))
        environ["wsgi.input"] = BytesIO(body)

        status: list[str] = []
        headers: list[tuple[str, str]] = []

        def start_response(value, response_headers):
            status.append(value)
            headers.extend(response_headers)

        response_body = b"".join(application(environ, start_response))
        self.assertEqual(status[0], "200 OK")
        self.assertEqual(dict(headers)["Content-Type"], "application/json; charset=utf-8")
        self.assertIn(b'"learned": 1', response_body)
        self.assertTrue(LEARNED_RULES_PATH.exists())


if __name__ == "__main__":
    unittest.main()
