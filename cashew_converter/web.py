from __future__ import annotations

from cgi import FieldStorage
from html import escape
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from wsgiref.simple_server import make_server
import csv
from typing import Iterable

from .models import CASHEW_COLUMNS
from .statement import convert_statement, rows_to_csv_text


UPLOAD_FORM = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Cashew Converter</title>
  <style>
    :root { color-scheme: light; --bg: #f4f1ea; --panel: #fffaf2; --ink: #1f2937; --muted: #6b7280; --accent: #0f766e; --accent-2: #115e59; --border: #d8d3c7; }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: linear-gradient(180deg, #f8f4eb 0%, #efe7da 100%); color: var(--ink); }
    main { min-height: 100vh; display: grid; place-items: center; padding: 24px; }
    .card { width: min(720px, 100%); background: rgba(255,255,255,0.8); backdrop-filter: blur(8px); border: 1px solid rgba(216,211,199,0.9); border-radius: 24px; padding: 28px; box-shadow: 0 24px 80px rgba(31,41,55,0.10); }
    h1 { margin: 0 0 8px; font-size: clamp(2rem, 5vw, 3.25rem); line-height: 1.02; letter-spacing: -0.04em; }
    p { margin: 0 0 18px; color: var(--muted); line-height: 1.6; }
    form { display: grid; gap: 14px; margin-top: 22px; }
    label { display: grid; gap: 6px; font-weight: 600; }
    input[type="text"], input[type="file"] { width: 100%; padding: 12px 14px; border-radius: 14px; border: 1px solid var(--border); background: #fff; font: inherit; }
    .actions { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
    button { appearance: none; border: 0; border-radius: 999px; padding: 12px 18px; background: linear-gradient(135deg, var(--accent), var(--accent-2)); color: white; font: inherit; font-weight: 700; cursor: pointer; }
    .hint { font-size: 0.95rem; color: var(--muted); }
    .error { margin-top: 18px; padding: 14px 16px; border-radius: 16px; background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }
    .success { margin-top: 18px; padding: 14px 16px; border-radius: 16px; background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; }
    code { background: #f3f4f6; padding: 2px 6px; border-radius: 6px; }
  </style>
</head>
<body>
<main>
  <section class="card">
    <h1>Cashew Converter</h1>
    <p>Upload a bank statement in <code>.xlsx</code> or <code>.csv</code> format and download a Cashew-ready CSV.</p>
    <form method="post" enctype="multipart/form-data">
      <label>
        Statement file
        <input type="file" name="statement" accept=".xlsx,.csv" required>
      </label>
      <label>
        Account name
        <input type="text" name="account" value="Sbi" maxlength="64">
      </label>
      <div class="actions">
        <button type="submit">Convert and download</button>
        <span class="hint">The result uses the same mapping rules as the CLI.</span>
      </div>
    </form>
    {message}
  </section>
</main>
</body>
</html>
"""


def application(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET").upper()
    if method == "GET":
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [render_page()]

    if method != "POST":
        start_response("405 Method Not Allowed", [("Content-Type", "text/plain; charset=utf-8")])
        return [b"Method not allowed"]

    try:
        csv_text, filename = convert_uploaded_statement(environ)
    except ValueError as exc:
        start_response("400 Bad Request", [("Content-Type", "text/html; charset=utf-8")])
        return [render_page(str(exc), error=True)]

    start_response(
        "200 OK",
        [
            ("Content-Type", "text/csv; charset=utf-8"),
            ("Content-Disposition", f'attachment; filename="{filename}"'),
        ],
    )
    return [csv_text.encode("utf-8")]


def render_page(message: str = "", error: bool = False) -> bytes:
    if not message:
        return UPLOAD_FORM.format(message="").encode("utf-8")
    css_class = "error" if error else "success"
    return UPLOAD_FORM.format(message=f'<div class="{css_class}">{escape(message)}</div>').encode("utf-8")


def convert_uploaded_statement(environ) -> tuple[str, str]:
    form = FieldStorage(fp=environ["wsgi.input"], environ=environ, keep_blank_values=True)
    if "statement" not in form:
        raise ValueError("Please choose a statement file.")

    upload = form["statement"]
    if not getattr(upload, "file", None):
        raise ValueError("Uploaded file is empty.")

    account = form.getfirst("account", "Sbi")
    filename = Path(upload.filename or "statement.xlsx")
    suffix = filename.suffix.lower() or ".xlsx"
    if suffix not in {".xlsx", ".xlsm", ".xltx", ".xltm", ".csv"}:
        raise ValueError("Unsupported file type. Use .xlsx or .csv.")

    with NamedTemporaryFile(suffix=suffix, delete=True) as temp_file:
        temp_file.write(upload.file.read())
        temp_file.flush()
        rows = convert_statement(Path(temp_file.name), account=account)

    return rows_to_csv_text(rows), "cashew-export.csv"


def main(argv: list[str] | None = None) -> int:
    host = "127.0.0.1"
    port = 8000
    with make_server(host, port, application) as server:
        print(f"Serving Cashew Converter on http://{host}:{port}")
        server.serve_forever()
    return 0
