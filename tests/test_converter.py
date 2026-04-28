from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import csv
from io import BytesIO
import unittest
from wsgiref.util import setup_testing_defaults

from cashew_converter.models import CASHEW_COLUMNS
from cashew_converter.statement import convert_statement, load_statement_rows, row_to_transaction
from cashew_converter.web import application, convert_uploaded_statement, render_page


ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "bstate.xlsx"


class ConverterTests(unittest.TestCase):
    def test_xlsx_reader_extracts_rows(self) -> None:
        rows = load_statement_rows(WORKBOOK)
        self.assertGreater(len(rows), 0)
        self.assertEqual(rows[0]["Date"], "05/09/2024")
        self.assertIn("DEP TFR", rows[0]["Details"])

    def test_statement_row_to_transaction_uses_debit_and_credit(self) -> None:
        rows = load_statement_rows(WORKBOOK)
        income_row = row_to_transaction(rows[0])
        expense_row = row_to_transaction(rows[2])
        self.assertTrue(income_row.income)
        self.assertEqual(str(income_row.amount), "50000.00")
        self.assertFalse(expense_row.income)
        self.assertEqual(str(expense_row.amount), "-100000.00")

    def test_converter_writes_cashew_schema(self) -> None:
        rows = convert_statement(WORKBOOK)
        self.assertGreater(len(rows), 0)
        first_row = rows[0].to_csv_row()
        self.assertEqual(list(first_row.keys()), CASHEW_COLUMNS)
        self.assertEqual(first_row["income"], "true")
        self.assertEqual(first_row["category name"], "Income")

    def test_keyword_rules_cover_sample_transactions(self) -> None:
        rows = convert_statement(WORKBOOK)
        grocery_row = next(row for row in rows if row.note == "DMART AV")
        self.assertEqual(grocery_row.category_name, "Groceries")
        self.assertEqual(grocery_row.icon, "groceries.png")

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

    def test_web_get_renders_upload_page(self) -> None:
        environ = {}
        setup_testing_defaults(environ)
        environ["REQUEST_METHOD"] = "GET"
        status: list[str] = []

        def start_response(value, headers):
            status.append(value)

        body = b"".join(application(environ, start_response))
        self.assertEqual(status[0], "200 OK")
        self.assertIn(b"Cashew Converter", body)

    def test_web_upload_conversion_returns_csv(self) -> None:
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
        self.assertEqual(dict(headers)["Content-Type"], "text/csv; charset=utf-8")
        self.assertTrue(response_body.startswith(b"account,amount,currency"))
        self.assertIn("cashew-export.csv", dict(headers)["Content-Disposition"])


if __name__ == "__main__":
    unittest.main()
