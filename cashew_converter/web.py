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
from .rules import learn_from_rows
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

CATEGORY_CHOICES = [
  "Income",
  "Groceries",
  "Travel",
  "Bills & Fees",
  "Dining",
  "Personal Care",
  "Gifts",
  "Shopping",
  "Transfers",
]

SUBCATEGORY_CHOICES = [
  "FastFood",
  "Cafes",
  "Trains",
  "Recharge",
  "Toiletries",
  "Clothing",
]


def render_category_options(selected: str) -> str:
  return "\n".join(
    f'<option value="{escape(choice)}"{" selected" if choice == selected else ""}>{escape(choice)}</option>'
    for choice in CATEGORY_CHOICES
  )


def render_select_options(choices: list[str], selected: str) -> str:
  option_choices = [""] + [choice for choice in choices if choice]
  if selected and selected not in option_choices:
    option_choices = ["", selected, *[choice for choice in choices if choice and choice != selected]]

  return "\n".join(
    f'<option value="{escape(choice)}"{" selected" if choice == selected else ""}>{escape(choice) or "&nbsp;"}</option>'
    for choice in option_choices
  )


def display_cell_value(value: object) -> str:
  text = "" if value is None else str(value)
  return "" if text.lower() in {"none", "null"} else text


def display_date_value(value: object) -> str:
  text = display_cell_value(value)
  if len(text) >= 10:
    return text[:10]
  return text

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
    td.category-cell, td.subcategory-cell { min-width: 180px; }
    td.note-cell { min-width: 220px; }
    .cell-control { width: 100%; border: 1px solid #d8d3c7; border-radius: 6px; background: white; font: inherit; color: inherit; padding: 7px 8px; }
    .cell-control:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 2px rgba(15,118,110,0.1); }
    .cell-control.select-control { cursor: pointer; }
    .cell-control.input-control { min-width: 180px; }
    .selector-col { width: 44px; min-width: 44px; text-align: center; }
    .row-select, #select-all { width: 16px; height: 16px; accent-color: var(--accent); cursor: pointer; }
    .bulk-panel { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin-bottom: 14px; padding: 12px; border: 1px solid #d8d3c7; border-radius: 10px; background: #fffef9; }
    .bulk-panel label { font-size: 0.88rem; color: #6b7280; margin-right: 2px; }
    .bulk-panel .bulk-control { min-width: 160px; }
    .bulk-panel .bulk-actions { display: flex; gap: 8px; flex-wrap: wrap; }
    .bulk-panel button { padding: 8px 12px; border-radius: 8px; font-size: 0.9rem; }
    .bulk-panel button.ghost { background: #e5e7eb; color: #111827; }
    .success-banner { background: #ecfdf5; border-left: 4px solid var(--success); padding: 16px; border-radius: 6px; margin-bottom: 20px; color: #065f46; font-size: 0.95rem; display: none; }
  </style>
  <script>
    const DATA_COLUMNS = {data_columns};
    const CATEGORY_CHOICES = {category_choices};
    const SUBCATEGORY_CHOICES = {subcategory_choices};

    function collectTableData() {
      const rows = [];
      const table = document.querySelector('table');
      const bodyRows = table.querySelectorAll('tbody tr');
      bodyRows.forEach(tr => {
        const row = {};
        DATA_COLUMNS.forEach((header) => {
          const safeName = CSS.escape(header);
          const field = tr.querySelector('[name="' + safeName + '"]');
          if (!field) {
            row[header] = '';
          } else if (field.type === 'date' && field.value) {
            row[header] = field.value + ' 00:00:00.000';
          } else {
            row[header] = field.value;
          }
        });
        rows.push(row);
      });
      return rows;
    }

    function getSelectedRows() {
      return Array.from(document.querySelectorAll('tbody tr')).filter(row => {
        const cb = row.querySelector('.row-select');
        return cb && cb.checked;
      });
    }

    function updateBulkValueControl() {
      const field = document.getElementById('bulk-field').value;
      const input = document.getElementById('bulk-value-input');
      const select = document.getElementById('bulk-value-select');
      let options = null;

      if (field === 'category name') {
        options = CATEGORY_CHOICES;
      } else if (field === 'subcategory name') {
        options = [''].concat(SUBCATEGORY_CHOICES);
      } else if (field === 'income') {
        options = ['true', 'false'];
      }

      if (options) {
        input.style.display = 'none';
        select.style.display = 'inline-block';
        select.innerHTML = options.map(value => '<option value="' + String(value).replace(/"/g, '&quot;') + '">' + (value || ' ') + '</option>').join('');
      } else {
        select.style.display = 'none';
        input.style.display = 'inline-block';
      }
    }

    function getBulkValue() {
      const input = document.getElementById('bulk-value-input');
      const select = document.getElementById('bulk-value-select');
      if (select.style.display !== 'none') {
        return select.value;
      }
      return input.value;
    }

    function applyBulkEdit(applyToAll) {
      const field = document.getElementById('bulk-field').value;
      const value = getBulkValue();
      const rows = applyToAll ? Array.from(document.querySelectorAll('tbody tr')) : getSelectedRows();

      if (!rows.length) {
        showBanner('Select at least one row first.', true);
        return;
      }

      rows.forEach(row => {
        const safeName = CSS.escape(field);
        const control = row.querySelector('[name="' + safeName + '"]');
        if (!control) return;

        if (control.tagName === 'SELECT') {
          const exists = Array.from(control.options).some(o => o.value === value);
          if (!exists) {
            const option = document.createElement('option');
            option.value = value;
            option.textContent = value || ' ';
            control.appendChild(option);
          }
        }
        control.value = value;
      });

      showBanner('Bulk edit applied to ' + rows.length + ' row(s).', false);
    }

    function selectAllRows(checked) {
      document.querySelectorAll('.row-select').forEach(cb => {
        cb.checked = checked;
      });
      const master = document.getElementById('select-all');
      if (master) master.checked = checked;
    }

    function showBanner(message, isError) {
      const banner = document.querySelector('.success-banner');
      banner.textContent = message;
      banner.style.display = 'block';
      banner.style.background = isError ? '#fef2f2' : '#ecfdf5';
      banner.style.color = isError ? '#991b1b' : '#065f46';
      banner.style.borderLeftColor = isError ? '#f87171' : '#10b981';
      setTimeout(() => {
        banner.style.display = 'none';
      }, 3000);
    }

    async function learnCategoryRules() {
      const rows = collectTableData();
      try {
        const response = await fetch('/learn', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ rows }),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || 'Failed to learn rules.');
        }
        showBanner(data.message || 'Learned category rules.', false);
      } catch (error) {
        showBanner(String(error.message || error), true);
      }
    }

    window.downloadEdited = downloadEdited;
    window.learnCategoryRules = learnCategoryRules;
    
    function escapeCSV(field) {
      const str = String(field || '');
      if (str.includes(',') || str.includes('"') || str.includes('\n')) {
        return '"' + str.replace(/"/g, '""') + '"';
      }
      return str;
    }

    function downloadEdited() {
      const data = collectTableData();
      const allHeaders = Array.from(document.querySelectorAll('table th')).map(th => th.textContent);
      const headers = allHeaders.slice(1); // Skip first column (selector checkbox)
      const csv = [headers.map(h => escapeCSV(h)).join(',')];
      data.forEach(row => {
        csv.push(headers.map(h => escapeCSV(row[h])).join(','));
      });
      const blob = new Blob([csv.join('\\n')], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'cashew-export.csv';
      link.click();
      URL.revokeObjectURL(url);

      showBanner('CSV downloaded successfully.', false);
    }

    window.addEventListener('load', () => {
      updateBulkValueControl();
      const master = document.getElementById('select-all');
      if (master) {
        master.addEventListener('change', (event) => {
          selectAllRows(event.target.checked);
        });
      }

      const downloadButton = document.getElementById('download-btn');
      if (downloadButton) {
        downloadButton.addEventListener('click', downloadEdited);
      }

      const learnButton = document.getElementById('learn-btn');
      if (learnButton) {
        learnButton.addEventListener('click', learnCategoryRules);
      }
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
      <button id="download-btn" type="button">⬇ Download CSV</button>
      <button id="learn-btn" type="button">🧠 Learn Category Rules</button>
      <div class="divider"></div>
      <form action="/" method="get" style="margin:0; display:inline;">
        <button type="submit" class="secondary">+ Convert Another</button>
      </form>
    </div>

    <div class="bulk-panel">
      <label for="bulk-field">Bulk edit field</label>
      <select id="bulk-field" class="cell-control select-control bulk-control" onchange="updateBulkValueControl()">
        <option value="category name">category name</option>
        <option value="subcategory name">subcategory name</option>
        <option value="income">income</option>
        <option value="budget">budget</option>
        <option value="type">type</option>
        <option value="note">note</option>
      </select>

      <label for="bulk-value-input">Value</label>
      <input id="bulk-value-input" class="cell-control input-control bulk-control" type="text" placeholder="Enter value">
      <select id="bulk-value-select" class="cell-control select-control bulk-control" style="display:none;"></select>

      <div class="bulk-actions">
        <button type="button" onclick="applyBulkEdit(false)">Apply To Selected</button>
        <button type="button" onclick="applyBulkEdit(true)">Apply To All</button>
        <button type="button" class="ghost" onclick="selectAllRows(true)">Select All</button>
        <button type="button" class="ghost" onclick="selectAllRows(false)">Clear Selection</button>
      </div>
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

    if method == "GET" and path == "/":
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [render_upload_page()]

    if method == "POST" and path == "/learn":
        return learn_edited_rules(environ, start_response)

    if method != "POST" or path != "/":
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


def learn_edited_rules(environ, start_response):
    content_length = int(environ.get("CONTENT_LENGTH", 0) or 0)
    body = environ["wsgi.input"].read(content_length) if content_length else b""
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        start_response("400 Bad Request", [("Content-Type", "application/json; charset=utf-8")])
        return [json.dumps({"error": "Invalid JSON payload."}).encode("utf-8")]

    rows = payload.get("rows") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        start_response("400 Bad Request", [("Content-Type", "application/json; charset=utf-8")])
        return [json.dumps({"error": "Expected 'rows' as an array."}).encode("utf-8")]

    learned_count = learn_from_rows(rows)
    start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
    return [
        json.dumps(
            {
                "learned": learned_count,
                "message": f"Learned {learned_count} rule(s). Future conversions will use these mappings.",
            }
        ).encode("utf-8")
    ]


def render_preview_page(rows: list[CashewRow]) -> bytes:
  """Render an editable preview table of the converted transactions."""
  headers = '<th class="selector-col"><input id="select-all" type="checkbox" title="Select all rows"></th> '
  headers += " ".join(f"<th>{escape(col)}</th>" for col in CASHEW_COLUMNS)
  subcategory_choices = sorted(
    {
      *SUBCATEGORY_CHOICES,
      *{
        str(row.to_csv_row().get("subcategory name", "")).strip()
        for row in rows
        if str(row.to_csv_row().get("subcategory name", "")).strip()
      },
    }
  )

  table_rows_html = ""
  for row in rows:
    csv_row = row.to_csv_row()
    cell_html: list[str] = [
      '<td class="selector-col"><input class="row-select" type="checkbox" title="Select row"></td>'
    ]

    for col in CASHEW_COLUMNS:
      value = display_cell_value(csv_row.get(col, ""))
      if col == "category name":
        cell_html.append(
          '<td class="category-cell">'
          f'<select class="cell-control select-control" name="{escape(col)}" data-col="{escape(col)}">'
          f"{render_category_options(value)}"
          "</select>"
          "</td>"
        )
      elif col == "subcategory name":
        cell_html.append(
          '<td class="subcategory-cell">'
          f'<select class="cell-control select-control" name="{escape(col)}" data-col="{escape(col)}">'
          f"{render_select_options(subcategory_choices, value)}"
          "</select>"
          "</td>"
        )
      elif col == "note":
        cell_html.append(
          '<td class="note-cell">'
          f'<input class="cell-control input-control" type="text" name="{escape(col)}" data-col="{escape(col)}" value="{escape(value)}">'
          "</td>"
        )
      elif col == "date":
        cell_html.append(
          "<td>"
          f'<input class="cell-control input-control" type="date" name="{escape(col)}" data-col="{escape(col)}" value="{escape(display_date_value(csv_row.get(col, "")))}">'
          "</td>"
        )
      elif col == "income":
        cell_html.append(
          "<td>"
          f'<select class="cell-control select-control" name="{escape(col)}" data-col="{escape(col)}">'
          f'{render_select_options(["true", "false"], value.lower())}'
          "</select>"
          "</td>"
        )
      else:
        input_type = "number" if col == "amount" else "text"
        extra_attrs = ' step="any"' if col == "amount" else ""
        cell_html.append(
          "<td>"
          f'<input class="cell-control input-control" type="{input_type}" name="{escape(col)}" data-col="{escape(col)}" value="{escape(value)}"{extra_attrs}>'
          "</td>"
        )

    cells = " ".join(cell_html)
    table_rows_html += f"<tr>{cells}</tr>\n"

  preview = PREVIEW_FORM.replace("{row_count}", str(len(rows)))
  preview = preview.replace("{table_headers}", headers)
  preview = preview.replace("{table_rows}", table_rows_html)
  preview = preview.replace("{data_columns}", json.dumps(CASHEW_COLUMNS))
  preview = preview.replace("{category_choices}", json.dumps(CATEGORY_CHOICES))
  preview = preview.replace("{subcategory_choices}", json.dumps(subcategory_choices))
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
