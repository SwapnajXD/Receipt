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
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root { --ink: #1a1a1a; --paper: #faf9f7; --paper-dark: #f0ede8; --muted: #6b6b6b; --muted-light: #9a9a9a; --border: #e5e2dc; --accent: #c9553d; --accent-dark: #a3432d; --accent-light: #fdf4f2; --success: #2d8659; --error: #c9302c; --shadow-sm: 0 1px 2px rgba(0,0,0,0.04); --shadow-md: 0 4px 12px rgba(0,0,0,0.08); --shadow-lg: 0 12px 32px rgba(0,0,0,0.12); --radius-sm: 6px; --radius-md: 10px; --radius-lg: 16px; }
    body { font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif; background: var(--paper); color: var(--ink); min-height: 100vh; line-height: 1.5; }
    body::before { content: ''; position: fixed; inset: 0; background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E"); opacity: 0.03; pointer-events: none; z-index: -1; }
    .upload-page { min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 24px; }
    .upload-container { width: 100%; max-width: 520px; animation: fadeIn 0.6s ease-out; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
    .logo { text-align: center; margin-bottom: 32px; }
    .logo h1 { font-family: 'Instrument Serif', Georgia, serif; font-size: clamp(2.5rem, 6vw, 3.25rem); font-weight: 400; letter-spacing: -0.02em; color: var(--ink); }
    .logo h1 span { font-style: italic; color: var(--accent); }
    .logo p { color: var(--muted); margin-top: 8px; font-size: 1.05rem; }
    .upload-card { background: #fff; border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 32px; box-shadow: var(--shadow-md); }
    .dropzone { border: 2px dashed var(--border); border-radius: var(--radius-md); padding: 40px 24px; text-align: center; cursor: pointer; transition: all 0.25s ease; background: var(--paper); position: relative; overflow: hidden; }
    .dropzone::before { content: ''; position: absolute; inset: 0; background: linear-gradient(135deg, transparent 40%, rgba(201,85,61,0.03) 100%); opacity: 0; transition: opacity 0.25s; }
    .dropzone:hover, .dropzone.dragover { border-color: var(--accent); background: var(--accent-light); }
    .dropzone:hover::before, .dropzone.dragover::before { opacity: 1; }
    .dropzone-icon { width: 48px; height: 48px; margin: 0 auto 16px; background: var(--accent-light); border-radius: 50%; display: flex; align-items: center; justify-content: center; }
    .dropzone-icon svg { width: 24px; height: 24px; stroke: var(--accent); }
    .dropzone h3 { font-size: 1.1rem; font-weight: 600; margin-bottom: 4px; }
    .dropzone p { color: var(--muted); font-size: 0.9rem; }
    .dropzone input[type="file"] { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
    .file-status { display: none; margin-top: 16px; padding: 12px 16px; background: var(--paper-dark); border-radius: var(--radius-sm); font-size: 0.9rem; align-items: center; gap: 10px; }
    .file-status.visible { display: flex; }
    .file-status svg { flex-shrink: 0; }
    .file-name { font-weight: 500; color: var(--ink); }
    .file-size { color: var(--muted); font-size: 0.85rem; }
    .form-group { margin-top: 24px; }
    .form-group label { display: block; font-weight: 600; font-size: 0.9rem; margin-bottom: 8px; color: var(--ink); }
    .form-group input[type="text"] { width: 100%; padding: 14px 16px; border: 1px solid var(--border); border-radius: var(--radius-sm); font-size: 1rem; font-family: inherit; background: #fff; transition: border-color 0.2s, box-shadow 0.2s; }
    .form-group input[type="text"]:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-light); }
    .form-hint { margin-top: 6px; font-size: 0.85rem; color: var(--muted); }
    .submit-btn { width: 100%; margin-top: 28px; padding: 16px 24px; background: var(--accent); color: #fff; border: none; border-radius: var(--radius-sm); font-size: 1rem; font-weight: 600; font-family: inherit; cursor: pointer; transition: all 0.2s ease; display: flex; align-items: center; justify-content: center; gap: 8px; }
    .submit-btn:hover { background: var(--accent-dark); transform: translateY(-1px); box-shadow: 0 4px 12px rgba(201,85,61,0.3); }
    .submit-btn:active { transform: translateY(0); }
    .submit-btn svg { width: 18px; height: 18px; }
    .message { margin-top: 20px; padding: 14px 16px; border-radius: var(--radius-sm); font-size: 0.9rem; display: none; }
    .message.visible { display: block; animation: fadeIn 0.3s ease-out; }
    .message.error { background: #fef2f2; color: var(--error); border-left: 3px solid var(--error); }
    .message.success { background: #f0fdf4; color: var(--success); border-left: 3px solid var(--success); }
    .features { margin-top: 32px; padding-top: 24px; border-top: 1px solid var(--border); }
    .features h4 { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted-light); margin-bottom: 16px; }
    .feature-list { display: grid; gap: 12px; }
    .feature-item { display: flex; align-items: flex-start; gap: 12px; font-size: 0.9rem; color: var(--muted); }
    .feature-item svg { width: 18px; height: 18px; stroke: var(--accent); flex-shrink: 0; margin-top: 2px; }
  </style>
</head>
<body>
<form method="post" enctype="multipart/form-data" class="upload-page" id="upload-form" style="display:none;">
  <div class="upload-container">
    <div class="logo">
      <h1>Cashew<span>Converter</span></h1>
      <p>Transform bank statements into structured data</p>
    </div>

    <div class="upload-card">
      <div class="dropzone" id="dropzone">
        <div class="dropzone-icon">
          <svg fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
          </svg>
        </div>
        <h3>Drop your statement here</h3>
        <p>or click to browse files</p>
        <input type="file" name="statement" accept=".xlsx,.csv" required>
      </div>

      <div class="file-status" id="file-status">
        <svg fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" style="width:20px;height:20px;color:var(--success)">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span class="file-name" id="file-name"></span>
        <span class="file-size" id="file-size"></span>
      </div>

      <div class="form-group">
        <label for="account">Account name</label>
        <input type="text" id="account" name="account" value="{account_value}" maxlength="64" placeholder="e.g., SBI, HDFC, Chase">
        <p class="form-hint">This label identifies your transactions</p>
      </div>

      <button type="submit" class="submit-btn">
        <svg fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
        </svg>
        Convert & Preview
      </button>

      <div class="message" id="message">{message_html}</div>

      <div class="features">
        <h4>What you can do</h4>
        <div class="feature-list">
          <div class="feature-item">
            <svg fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
            <span>Edit transactions inline — click any field to modify</span>
          </div>
          <div class="feature-item">
            <svg fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" /><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
            <span>Bulk edit — select multiple rows and update at once</span>
          </div>
          <div class="feature-item">
            <svg fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" /></svg>
            <span>Download CSV ready for Cashew import</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</form>

<script>
document.getElementById('upload-form').style.display = 'flex';
const dropzone = document.getElementById('dropzone');
const fileInput = dropzone.querySelector('input[type="file"]');
const fileStatus = document.getElementById('file-status');
const fileName = document.getElementById('file-name');
const fileSize = document.getElementById('file-size');

['dragenter', 'dragover'].forEach(evt => {
  dropzone.addEventListener(evt, e => { e.preventDefault(); dropzone.classList.add('dragover'); });
});
['dragleave', 'drop'].forEach(evt => {
  dropzone.addEventListener(evt, e => { e.preventDefault(); dropzone.classList.remove('dragover'); });
});
dropzone.addEventListener('drop', e => {
  if (e.dataTransfer.files.length) { fileInput.files = e.dataTransfer.files; updateFileStatus(e.dataTransfer.files[0]); }
});
fileInput.addEventListener('change', () => { if (fileInput.files.length) updateFileStatus(fileInput.files[0]); });
function updateFileStatus(file) {
  fileName.textContent = file.name;
  const size = file.size / 1024;
  fileSize.textContent = size > 1024 ? (size / 1024).toFixed(1) + ' MB' : size.toFixed(0) + ' KB';
  fileStatus.classList.add('visible');
}
</script>
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
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root { --ink: #1a1a1a; --paper: #faf9f7; --paper-dark: #f0ede8; --muted: #6b6b6b; --muted-light: #9a9a9a; --border: #e5e2dc; --accent: #c9553d; --accent-dark: #a3432d; --accent-light: #fdf4f2; --success: #2d8659; --error: #c9302c; --shadow-sm: 0 1px 2px rgba(0,0,0,0.04); --shadow-md: 0 4px 12px rgba(0,0,0,0.08); --shadow-lg: 0 12px 32px rgba(0,0,0,0.12); --radius-sm: 6px; --radius-md: 10px; --radius-lg: 16px; }
    body { font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif; background: var(--paper); color: var(--ink); min-height: 100vh; line-height: 1.5; }
    body::before { content: ''; position: fixed; inset: 0; background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E"); opacity: 0.03; pointer-events: none; z-index: -1; }
    .preview-page { min-height: 100vh; padding: 32px 24px; animation: fadeIn 0.5s ease-out; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes slideUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
    .preview-container { max-width: 1400px; margin: 0 auto; }
    .preview-header { margin-bottom: 28px; }
    .preview-header h1 { font-family: 'Instrument Serif', Georgia, serif; font-size: 2.25rem; font-weight: 400; letter-spacing: -0.01em; }
    .preview-header h1 span { color: var(--accent); font-style: italic; }
    .preview-subtitle { color: var(--muted); margin-top: 4px; }
    .header-row { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 24px; }
    .header-stats { display: flex; align-items: center; gap: 20px; font-size: 0.9rem; color: var(--muted); }
    .stat-badge { display: flex; align-items: center; gap: 6px; padding: 6px 12px; background: var(--paper-dark); border-radius: 20px; }
    .stat-badge svg { width: 16px; height: 16px; }
    .action-buttons { display: flex; gap: 10px; }
    .btn { padding: 10px 18px; border-radius: var(--radius-sm); font-size: 0.9rem; font-weight: 600; font-family: inherit; cursor: pointer; transition: all 0.2s ease; display: inline-flex; align-items: center; gap: 8px; border: none; }
    .btn svg { width: 16px; height: 16px; }
    .btn-primary { background: var(--accent); color: #fff; }
    .btn-primary:hover { background: var(--accent-dark); box-shadow: 0 4px 12px rgba(201,85,61,0.25); }
    .btn-secondary { background: var(--paper-dark); color: var(--ink); }
    .btn-secondary:hover { background: var(--border); }
    .btn-ghost { background: transparent; color: var(--muted); border: 1px solid var(--border); }
    .btn-ghost:hover { background: var(--paper-dark); color: var(--ink); }
    .bulk-panel { background: #fff; border: 1px solid var(--border); border-radius: var(--radius-md); padding: 16px 20px; margin-bottom: 20px; display: none; align-items: center; flex-wrap: wrap; gap: 12px; box-shadow: var(--shadow-sm); }
    .bulk-panel.visible { display: flex; animation: fadeIn 0.3s ease-out; }
    .bulk-label { font-size: 0.85rem; color: var(--muted); font-weight: 500; }
    .bulk-select, .bulk-input { padding: 8px 12px; border: 1px solid var(--border); border-radius: var(--radius-sm); font-size: 0.9rem; font-family: inherit; background: #fff; min-width: 140px; }
    .bulk-select:focus, .bulk-input:focus { outline: none; border-color: var(--accent); }
    .bulk-actions { display: flex; gap: 8px; margin-left: auto; }
    .bulk-actions .btn { padding: 8px 14px; font-size: 0.85rem; }
    .table-wrapper { background: #fff; border: 1px solid var(--border); border-radius: var(--radius-md); overflow: hidden; box-shadow: var(--shadow-md); }
    .table-scroll { max-height: 75vh; overflow-y: auto; }
    table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
    thead { position: sticky; top: 0; z-index: 10; }
    th { background: var(--paper-dark); padding: 14px 12px; text-align: left; font-weight: 600; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); border-bottom: 2px solid var(--border); white-space: nowrap; }
    th.selector-col { width: 48px; text-align: center; }
    td { padding: 12px; border-bottom: 1px solid var(--border); vertical-align: middle; }
    td.selector-col { text-align: center; }
    tbody tr { transition: background 0.15s; animation: slideUp 0.4s ease-out backwards; }
    tbody tr:hover { background: var(--accent-light); }
    tbody tr.selected { background: var(--accent-light); }
    input[type="checkbox"] { width: 16px; height: 16px; accent-color: var(--accent); cursor: pointer; }
    .cell-input, .cell-select { width: 100%; padding: 8px 10px; border: 1px solid transparent; border-radius: 4px; font-size: 0.9rem; font-family: inherit; background: transparent; transition: all 0.2s; }
    .cell-input:hover, .cell-select:hover { border-color: var(--border); background: #fff; }
    .cell-input:focus, .cell-select:focus { outline: none; border-color: var(--accent); background: #fff; box-shadow: 0 0 0 2px var(--accent-light); }
    .cell-input.amount { font-family: 'DM Sans', monospace; font-weight: 600; }
    .cell-input.date { font-family: 'DM Sans', monospace; color: var(--muted); }
    .cell-select { cursor: pointer; min-width: 120px; }
    .income-badge { display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
    .income-badge.income { background: #dcfce7; color: #166534; }
    .income-badge.expense { background: #fee2e2; color: #991b1b; }
    .toast { position: fixed; bottom: 24px; right: 24px; padding: 14px 20px; background: var(--ink); color: #fff; border-radius: var(--radius-sm); font-size: 0.9rem; font-weight: 500; box-shadow: var(--shadow-lg); transform: translateY(100px); opacity: 0; transition: all 0.3s ease; z-index: 1000; }
    .toast.visible { transform: translateY(0); opacity: 1; }
    .toast.success { background: var(--success); }
    .toast.error { background: var(--error); }
    @media (max-width: 768px) { .header-row { flex-direction: column; align-items: stretch; } .header-stats { justify-content: center; } .action-buttons { justify-content: center; } .bulk-panel { flex-direction: column; align-items: stretch; } .bulk-actions { margin-left: 0; justify-content: stretch; } .bulk-actions .btn { flex: 1; } .table-scroll { max-height: 60vh; } th, td { padding: 10px 8px; font-size: 0.85rem; } }
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
  <div class="preview-page">
    <div class="preview-container">
      <div class="preview-header">
        <h1>Conversion <span>Complete</span></h1>
        <p class="preview-subtitle">Review, edit, and export your transactions</p>
      </div>

      <div class="header-row">
        <div class="header-stats">
          <div class="stat-badge">
            <svg fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" /></svg>
            <span>{row_count} transactions</span>
          </div>
        </div>

        <div class="action-buttons">
          <button class="btn btn-primary" id="download-btn">
            <svg fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" /></svg>
            Download CSV
          </button>
          <button class="btn btn-secondary" id="learn-btn">
            <svg fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" /></svg>
            Learn Rules
          </button>
          <button class="btn btn-ghost" onclick="location.href='/'">+ New</button>
        </div>
      </div>

      <div class="bulk-panel" id="bulk-panel">
        <span class="bulk-label">Bulk edit:</span>
        <select class="bulk-select" id="bulk-field">
          <option value="category name">Category</option>
          <option value="subcategory name">Subcategory</option>
          <option value="income">Income/Expense</option>
          <option value="note">Note</option>
        </select>
        <input type="text" class="bulk-input" id="bulk-value" placeholder="Enter value...">
        <div class="bulk-actions">
          <button class="btn btn-secondary" onclick="applyBulkEdit(false)">Apply Selected</button>
          <button class="btn btn-secondary" onclick="applyBulkEdit(true)">Apply All</button>
          <button class="btn btn-ghost" onclick="selectAllRows(false)">Clear</button>
        </div>
      </div>

      <div class="table-wrapper">
        <div class="table-scroll">
          <table>
            <thead><tr>{table_headers}</tr></thead>
            <tbody>{table_rows}</tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="toast" id="toast"></div>
  </div>
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

    form = UPLOAD_FORM.replace("{message_html}", message_html).replace("{account_value}", "Sbi")
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
