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
    .card { width: min(720px, 100%); background: rgba(255,255,255,0.85); backdrop-filter: blur(8px); border: 1px solid rgba(216,211,199,0.9); border-radius: 20px; padding: 32px; box-shadow: 0 24px 80px rgba(31,41,55,0.12); }
    h1 { margin: 0 0 10px; font-size: clamp(2rem, 5vw, 3.25rem); line-height: 1.02; letter-spacing: -0.04em; font-weight: 700; }
    p { margin: 0 0 24px; color: var(--muted); line-height: 1.6; font-size: 1.05rem; }
    form { display: grid; gap: 18px; margin-top: 26px; }
    label { display: grid; gap: 8px; font-weight: 600; color: var(--ink); font-size: 1rem; }
    input[type="text"], input[type="file"] { width: 100%; padding: 13px 15px; border-radius: 10px; border: 2px solid var(--border); background: #fff; font: inherit; transition: border-color 0.2s; }
    input[type="text"]:focus, input[type="file"]:focus { outline: none; border-color: var(--accent); }
    .form-hint { font-size: 0.88rem; color: var(--muted); font-weight: 400; margin-top: -4px; }
    .actions { display: flex; flex-wrap: wrap; gap: 14px; align-items: center; margin-top: 28px; }
    button { appearance: none; border: 0; border-radius: 10px; padding: 13px 22px; background: linear-gradient(135deg, var(--accent), var(--accent-2)); color: white; font: inherit; font-weight: 700; cursor: pointer; font-size: 1rem; transition: transform 0.15s, box-shadow 0.15s; }
    button:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(15,118,110,0.3); }
    button:active { transform: translateY(0); }
    .hint-text { font-size: 0.95rem; color: var(--muted); }
    .features { margin-top: 28px; padding-top: 24px; border-top: 1px solid var(--border); display: grid; gap: 12px; }
    .feature { display: flex; gap: 10px; align-items: flex-start; font-size: 0.95rem; color: var(--muted); }
    .feature-icon { color: var(--accent); font-weight: 700; font-size: 1.2rem; flex-shrink: 0; }
    .error { margin-top: 20px; padding: 16px 18px; border-radius: 12px; background: #fef2f2; color: #991b1b; border-left: 4px solid #f87171; border-radius: 8px; }
    .success { margin-top: 20px; padding: 16px 18px; border-radius: 12px; background: #ecfdf5; color: #065f46; border-left: 4px solid #6ee7b7; border-radius: 8px; }
    code { background: #f3f4f6; padding: 3px 7px; border-radius: 6px; font-family: 'Courier New', monospace; }
  </style>
</head>
<body>
<main>
  <section class="card">
    <h1>💳 Cashew Converter</h1>
    <p>Convert your bank statement to Cashew-ready CSV format. Preview and edit before downloading.</p>
    
    <form method="post" enctype="multipart/form-data">
      <label>
        Statement file
        <input type="file" name="statement" accept=".xlsx,.csv" required>
        <span class="form-hint">Supports .xlsx and .csv formats</span>
      </label>
      
      <label>
        Account name
        <input type="text" name="account" value="Sbi" maxlength="64">
        <span class="form-hint">Name to label transactions with</span>
      </label>
      
      <div class="actions">
        <button type="submit">⚡ Convert & Preview</button>
        <span class="hint-text">Edit before downloading</span>
      </div>
    </form>
    
    <div class="features">
      <div class="feature">
        <span class="feature-icon">✎</span>
        <span><strong>Edit inline:</strong> Click any cell to edit dates, amounts, categories, or notes</span>
      </div>
      <div class="feature">
        <span class="feature-icon">🎯</span>
        <span><strong>Smart categories:</strong> Auto-categorize transactions; adjust with dropdown menu</span>
      </div>
      <div class="feature">
        <span class="feature-icon">⬇</span>
        <span><strong>Download:</strong> Export your customized CSV in Cashew format</span>
      </div>
    </div>
    
    {message_placeholder}
  </section>
</main>
</body>
</html>
"""

CATEGORY_OPTIONS = """<optgroup label="Income">
<option value="Income">Income</option>
</optgroup>
<optgroup label="Expense">
<option value="Groceries">Groceries</option>
<option value="Travel">Travel</option>
<option value="Bills & Fees">Bills & Fees</option>
<option value="Dining">Dining</option>
<option value="Personal Care">Personal Care</option>
<option value="Gifts">Gifts</option>
<option value="Shopping">Shopping</option>
<option value="Transfers">Transfers</option>
</optgroup>
"""

PREVIEW_FORM = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Cashew Converter - Preview</title>
  <style>
    :root { color-scheme: light; --accent: #0f766e; --accent-2: #115e59; --success: #10b981; }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: linear-gradient(180deg, #f8f4eb 0%, #efe7da 100%); color: #1f2937; }
    main { min-height: 100vh; padding: 24px; }
    .container { max-width: 1400px; margin: 0 auto; }
    .header { margin-bottom: 28px; }
    h1 { margin: 0 0 8px; font-size: 2.2rem; font-weight: 700; }
    .subtitle { margin: 0; color: #6b7280; font-size: 1.05rem; }
    .stats { display: flex; gap: 20px; margin-top: 14px; font-size: 0.95rem; color: #6b7280; }
    .controls { margin-bottom: 20px; display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
    button { appearance: none; border: 0; border-radius: 8px; padding: 11px 18px; background: linear-gradient(135deg, var(--accent), var(--accent-2)); color: white; font: inherit; font-weight: 600; cursor: pointer; transition: transform 0.15s, box-shadow 0.15s; }
    button:hover { transform: translateY(-1px); box-shadow: 0 8px 16px rgba(15,118,110,0.3); }
    button:active { transform: translateY(0); }
    button.secondary { background: #9ca3af; }
    button.secondary:hover { box-shadow: 0 8px 16px rgba(156,163,175,0.3); }
    .divider { width: 1px; height: 20px; background: #d8d3c7; }
    .table-wrapper { background: white; border-radius: 12px; border: 1px solid #d8d3c7; overflow: auto; max-height: 700px; box-shadow: 0 6px 20px rgba(31,41,55,0.10); }
    table { width: 100%; border-collapse: collapse; font-size: 0.95rem; }
    th { background: #f9fafb; font-weight: 700; position: sticky; top: 0; border-bottom: 2px solid #e5e7eb; padding: 14px 12px; text-align: left; }
    td { padding: 12px; border-bottom: 1px solid #f3f4f6; }
    tbody tr:hover { background: #fffbf0; }
    td.date { font-size: 0.9rem; color: #6b7280; font-family: monospace; }
    td.amount { font-family: 'Courier New', monospace; font-weight: 600; }
    td.category-cell { min-width: 140px; }
    select { width: 100%; padding: 6px 8px; border: 1px solid #d8d3c7; border-radius: 6px; font-family: inherit; font-size: inherit; background: white; cursor: pointer; }
    select:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 2px rgba(15,118,110,0.1); }
    input.note-input { width: 100%; padding: 6px 8px; border: 1px solid #d8d3c7; border-radius: 6px; font-family: inherit; font-size: inherit; }
    input.note-input:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 2px rgba(15,118,110,0.1); }
    .note-display { cursor: pointer; padding: 6px 0; }
    .note-display:hover { color: var(--accent); }
    .success-banner { background: #ecfdf5; border-left: 4px solid var(--success); padding: 16px; border-radius: 6px; margin-bottom: 20px; color: #065f46; font-size: 0.95rem; display: none; }
  </style>
  <script>
    const CATEGORY_OPTIONS = {category_options};
    
    function setupCategoryDropdowns() {
      const categoryHeader = Array.from(document.querySelectorAll('th')).find(th => th.textContent === 'Category');
      if (!categoryHeader) return;
      
      const categoryColumnIndex = Array.from(categoryHeader.parentNode.children).indexOf(categoryHeader);
      const cells = document.querySelectorAll('tbody tr td:nth-child(' + (categoryColumnIndex + 1) + ')');
      
      cells.forEach((cell, idx) => {
        const currentValue = cell.textContent;
        cell.addEventListener('click', function(e) {
          if (e.target.tagName === 'SELECT') return;
          const select = document.createElement('select');
          select.innerHTML = CATEGORY_OPTIONS;
          select.value = currentValue;
          cell.innerHTML = '';
          cell.appendChild(select);
          select.focus();
          
          const saveCategory = () => {
            cell.textContent = select.value;
          };
          
          select.addEventListener('blur', saveCategory);
          select.addEventListener('change', saveCategory);
        });
      });
    }
    
    function setupNoteEdits() {
      const noteHeader = Array.from(document.querySelectorAll('th')).find(th => th.textContent === 'Note');
      if (!noteHeader) return;
      
      const noteColumnIndex = Array.from(noteHeader.parentNode.children).indexOf(noteHeader);
      const cells = document.querySelectorAll('tbody tr td:nth-child(' + (noteColumnIndex + 1) + ')');
      
      cells.forEach((cell) => {
        const value = cell.textContent;
        cell.classList.add('note-display');
        cell.addEventListener('click', function(e) {
          if (e.target.tagName === 'INPUT') return;
          const input = document.createElement('input');
          input.type = 'text';
          input.className = 'note-input';
          input.value = value;
          cell.innerHTML = '';
          cell.appendChild(input);
          input.focus();
          input.select();
          
          const saveNote = () => {
            cell.textContent = input.value;
            cell.classList.add('note-display');
          };
          
          input.addEventListener('blur', saveNote);
          input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') this.blur();
            if (e.key === 'Escape') {
              cell.textContent = value;
              cell.classList.add('note-display');
            }
          });
        });
      });
    }
    
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
      const headers = Array.from(document.querySelectorAll('table th')).map(th => th.textContent);
      const csv = [headers.map(h => '"' + h.replace(/"/g, '""') + '"').join(',')];
      data.forEach(row => {
        csv.push(headers.map(h => '"' + String(row[h] || '').replace(/"/g, '""') + '"').join(','));
      });
      const blob = new Blob([csv.join('\n')], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'cashew-export.csv';
      link.click();
      URL.revokeObjectURL(url);
      
      // Show success banner
      const banner = document.querySelector('.success-banner');
      banner.style.display = 'block';
      setTimeout(() => banner.style.display = 'none', 3000);
    }
    
    window.addEventListener('load', () => {
      setupCategoryDropdowns();
      setupNoteEdits();
    });
  </script>
</head>
<body>
<main>
  <div class="container">
    <div class="header">
      <h1>✓ Conversion Complete</h1>
      <p class="subtitle">Review, edit, and download your transactions</p>
      <div class="stats">
        <span>📊 {row_count} transactions processed</span>
      </div>
    </div>
    
    <div class="success-banner">✓ CSV downloaded successfully!</div>
    
    <div class="controls">
      <button onclick="downloadEdited()">⬇ Download CSV</button>
      <div class="divider"></div>
      <form action="/" method="get" style="margin:0; display:inline;">
        <button type="submit" class="secondary">+ Convert Another</button>
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
    preview = preview.replace("{category_options}", json.dumps(CATEGORY_OPTIONS))
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
