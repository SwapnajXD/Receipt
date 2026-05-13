# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Cashew Converter converts bank statements (XLSX or CSV) into Cashew-compatible CSV format for import. It includes a CLI tool and a web-based UI for previewing and editing transactions before export.

## Common Commands

```bash
# CLI conversion
python -m cashew_converter <input_file> --output <output_file> --account <account_name>

# Web UI (starts on http://127.0.0.1:8000)
python -m cashew_converter.web
# or
cashew-converter-web
```

## Architecture

The converter operates as a pipeline: `statement.py` handles file loading (CSV or XLSX via `xlsx.py`), parses rows into `StatementTransaction` objects, applies category classification via `rules.py`, and outputs `CashewRow` objects.

**Core modules:**
- `models.py` - Defines `CashewRow`, `StatementTransaction`, and `CategoryStyle` dataclasses. Contains `CASHEW_COLUMNS` field list and formatting helpers.
- `statement.py` - Main conversion logic. Handles header synonym detection, date parsing (multiple formats), amount parsing from debit/credit columns, and row filtering for ignorable content.
- `rules.py` - Category classification. Uses regex patterns (RULES list) for merchant detection and loads persistent mappings from `learned_rules.json`. The `learn_from_rows()` function saves edited categories from the web UI.
- `xlsx.py` - Pure Python XLSX parser using `zipfile` and `xml.etree`. Detects the best sheet and header row by scoring against known column names.
- `web.py` - WSGI application with inline HTML templates. Provides upload form, preview table with inline editing, bulk edit panel, and CSV download. The `/learn` endpoint persists category edits.

**Utility scripts** (`scripts/`):
- `categorize_misc.py` - Matches new.csv transactions against old.csv by date+amount to suggest categories for Miscellaneous entries
- `update_categories.py` - Applies matched categories and pattern-based heuristics to remaining uncategorized transactions
- `list_categories.py` - Lists available categories

## Data Flow

1. User uploads XLSX/CSV via CLI or web
2. `load_statement_rows()` detects format and parses to list of dicts
3. Each row becomes a `StatementTransaction` (date, description, amount, income flag)
4. `classify()` matches description against regex rules and learned rules to produce `CategoryStyle`
5. `CashewRow` combines transaction data with style info
6. Web UI allows inline editing and saves changes via `/learn` endpoint to `learned_rules.json`

## File Formats

- **Input**: XLSX (any sheet, auto-detected header) or CSV (auto-detected delimiter)
- **Output**: CSV with columns: account, amount, currency, title, note, date, income, type, category name, subcategory name, color, icon, emoji, budget, objective
- **Learned rules**: JSON file at `cashew_converter/learned_rules.json` stores merchant-to-category mappings