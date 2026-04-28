from __future__ import annotations

from html import escape
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server
import csv
import json
import re

from .models import CASHEW_COLUMNS, CashewRow
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
        <button type="submit">Convert and preview</button>
        <span class="hint">You can edit the data before downloading.</span>
      </div>
    </form>
    {message_placeholder}
  </section>
</main>
</body>
</html>
"""

PREVIEW_FORM = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Cashew Converter - Preview</title>
  <style>
    :root { color-scheme: light; --accent: #0f766e; --accent-2: #115e59; }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: linear-gradient(180deg, #f8f4eb 0%, #efe7da 100%); color: #1f2937; }
    main { min-height: 100vh; padding: 24px; }
    .container { max-width: 1200px; margin: 0 auto; }
    h1 { margin-top: 0; font-size: 2rem; }
    .controls { margin-bottom: 20px; display: flex; gap: 12px; flex-wrap: wrap; }
    button { appearance: none; border: 0; border-radius: 999px; padding: 10px 16px; background: linear-gradient(135deg, var(--accent), var(--accent-2)); color: white; font: inherit; font-weight: 600; cursor: pointer; }
    button.secondary { background: #9ca3af; }
    .table-wrapper { background: white; border-radius: 12px; border: 1px solid #d8d3c7; overflow: auto; max-height: 600px; box-shadow: 0 4px 12px rgba(31,41,55,0.08); }
    table { width: 100%; border-collapse: collapse; }
    th, td { padding: 12px; text-align: left; border-bottom: 1px solid #e5e7eb; }
    th { background: #f9fafb; font-weight: 700; position: sticky; top: 0; }
    td { cursor: text; }
    td:hover { background: #fef3c7; }
    input[type="text"] { width: 100%; padding: 4px 6px; border: 1px solid #3b82f6; border-radius: 4px; font-family: inherit; }
    .row-count { font-size: 0.9rem; color: #6b7280; margin-bottom: 12px; }
  </style>
  <script>
    function makeTableEditable() {
      const cells = document.querySelectorAll('table td');
      cells.forEach(cell => {
        cell.addEventListener('click', function(e) {
          if (e.target.tagName === 'INPUT') return;
          const value = this.textContent;
          this.innerHTML = '<input type="text" value="' + value.replace(/"/g, '&quot;') + '">';
          const input = this.querySelector('input');
          input.focus();
          input.select();
          input.addEventListener('blur', function() {
            cell.textContent = this.value;
          });
          input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') this.blur();
            if (e.key === 'Escape') cell.textContent = value;
          });
        });
      });
    }
    window.addEventListener('load', makeTableEditable);
    
    function collectTableData() {
      const rows = [];
      const table = document.querySelector('table');
      const headers = Array.from(table.querySelectorAll('th')).map(th => th.textContent);
      const bodyRows = table.querySelectorAll('tbody tr');
      bodyRows.forEach(tr => {
        const cells = tr.querySelectorAll('td');
        const row = {}</;
        headers.forEach((header, i) => {
          row[header] = cells[i]?.textContent || '';
        });
        rows.push(row);
      });
      return rows;
    }
    
    function downloadEdited() {
      const data = collectTableData();
      const csv = [Array.from(document.querySelectorAll('table th')).map(th => '"' + th.textContent.replace(/"/g, '""') + '"').join(',')];
      data.forEach(row => {
        csv.push(Object.values(row).map(v => '"' + String(v).replace(/"/g, '""') + '"').join(','));
      });
      const blob = new Blob([csv.join('\n')], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'cashew-export.csv';
      a.click();
      URL.revokeObjectURL(url);
    }
  </script>
</head>
<body>
<main>
  <div class="container">
    <h1>Preview & Edit</h1>
    <p>Review and edit your transactions below. Click any cell to edit it.</p>
    <div class="row-count">{row_count} transactions</div>
    <div class="controls">
      <button onclick="downloadEdited()">Download CSV</button>
      <form action="/" method="get" style="margin:0; display:inline;">
        <button type="submit" class="secondary">Convert another</button>
      </form>
    </div>
    <div class="table-wrapper">
      <table>
        <thead><tr>{table_headers}</tr></thead>
        <tbody>{table_rows}</tbody>
      </table>
    </div>
  </div>
</main>
</body>
</html>
"""


def application(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "/")
    
    if method == "GET":
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [render_upload_page()]

    if method != "POST":
        start_response("405 Method Not Allowed", [("Content-Type", "text/plain; charset=utf-8")])
        return [b"Method not allowed"]

    try:
        rows = convert_uploaded_statement(environ)
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [render_preview_page(rows)]
    except ValueError as exc:
        start_response("400 Bad Request", [("Content-Type", "text/html; charset=utf-8")])
        return [render_upload_page(str(exc), error=True)]


def render_upload_page(message: str = "", error: bool = False) -> bytes:
    if not message:
        message_html = ""
    else:
        css_class = "error" if error else "success"
        message_html = f'<div class="{css_class}">{escape(message)}</div>'
    
    form = UPLOAD_FORM.replace("{message_placeholder}", message_html)
    return form.encode("utf-8")


def render_preview_page(rows: list[CashewRow]) -> bytes:
    """Render an editable preview table of the converted transactions."""
    headers = " ".join(f"<th>{escape(col)}</th>" for col in CASHEW_COLUMNS)
    
    table_rows_html = ""
    for row in rows:
        csv_row = row.to_csv_row()
        cells = " ".join(f"<td>{escape(str(csv_row.get(col, '')))}</td>" for col in CASHEW_COLUMNS)
        table_rows_html += f"<tr>{cells}</tr>\n"
    
    preview = PREVIEW_FORM.replace("{row_count}", str(len(rows)))
    preview = preview.replace("{table_headers}", headers)
    preview = preview.replace("{table_rows}", table_rows_html)
    return preview.encode("utf-8")


def render_page(message: str = "", error: bool = False) -> bytes:
    return render_upload_page(message, error)


def convert_uploaded_statement(environ) -> list[CashewRow]:
    """Parse multipart form data from WSGI environ and convert the uploaded statement."""
    content_type = environ.get("CONTENT_TYPE", "")
    content_length = int(environ.get("CONTENT_LENGTH", 0))
    
    if not content_type.startswith("multipart/form-data"):
        raise ValueError("Request must be multipart/form-data.")
    
    if content_length == 0:
        raise ValueError("Request body is empty.")

    boundary = extract_boundary(content_type)
    if not boundary:
        raise ValueError("Invalid multipart boundary.")

    body = environ["wsgi.input"].read(content_length)
    fields = parse_multipart_body(body, boundary)
    
    if "statement" not in fields or not fields["statement"]:
        raise ValueError("Please choose a statement file.")
    
    file_data, filename = fields["statement"][0]
    if not file_data:
        raise ValueError("Uploaded file is empty.")

    suffix = Path(filename).suffix.lower() or ".xlsx"
    if suffix not in {".xlsx", ".xlsm", ".xltx", ".xltm", ".csv"}:
        raise ValueError("Unsupported file type. Use .xlsx or .csv.")

    account = fields.get("account", ["Sbi"])[0][0] if "account" in fields else "Sbi"

    with NamedTemporaryFile(suffix=suffix, delete=True) as temp_file:
        temp_file.write(file_data)
        temp_file.flush()
        rows = convert_statement(Path(temp_file.name), account=account)

    return rows


def extract_boundary(content_type: str) -> str:
    """Extract the multipart boundary from the Content-Type header."""
    match = re.search(r'boundary=([^;\s]+)', content_type)
    return match.group(1).strip('"') if match else ""


def parse_multipart_body(body: bytes, boundary: str) -> dict[str, list[tuple[bytes, str]]]:
    """Parse a multipart/form-data body and return a dict of {field_name: [(content, filename), ...]}."""
    fields: dict[str, list[tuple[bytes, str]]] = {}
    parts = body.split(f"--{boundary}".encode())
    
    for part in parts[1:-1]:
        if not part or part == b"--\r\n" or part == b"--":
            continue
            
        try:
            header_end = part.find(b"\r\n\r\n")
            if header_end == -1:
                continue
            
            headers_section = part[:header_end].decode("utf-8", errors="replace")
            content = part[header_end + 4:]
            
            if content.endswith(b"\r\n"):
                content = content[:-2]
            elif content.endswith(b"\n"):
                content = content[:-1]
            
            name = extract_form_field_name(headers_section)
            filename = extract_filename(headers_section)
            
            if name:
                if filename:
                    fields.setdefault(name, []).append((content, filename))
                else:
                    fields.setdefault(name, []).append((content.decode("utf-8", errors="replace"), ""))
        except Exception:
            continue
    
    return fields


def extract_form_field_name(headers_section: str) -> str:
    """Extract the field name from multipart headers."""
    match = re.search(r'name="([^"]*)"', headers_section)
    return match.group(1) if match else ""


def extract_filename(headers_section: str) -> str:
    """Extract the filename from multipart headers."""
    match = re.search(r'filename="([^"]*)"', headers_section)
    return match.group(1) if match else ""


def main(argv: list[str] | None = None) -> int:
    host = "127.0.0.1"
    port = 8000
    with make_server(host, port, application) as server:
        print(f"Serving Cashew Converter on http://{host}:{port}")
        server.serve_forever()
    return 0
