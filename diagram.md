(# Cashew Converter — Architecture Diagram)

## Overview

Cashew Converter transforms bank statements (XLSX or CSV) into a Cashew-compatible CSV for import. The codebase is organized as a small pipeline: input parsing -> normalization -> classification -> output, with both a CLI and a lightweight web UI for preview and manual correction.

## High-level components

- Entry points
	- CLI: `cashew_converter.cli` (CLI parser and `main`) — batch conversion to CSV.
	- Web UI: `cashew_converter.web` — WSGI app that accepts uploads, previews rows for inline editing, persists learned mappings, and serves downloads.
- Parsing
	- `cashew_converter.xlsx` — lightweight XLSX reader that extracts sheet rows and picks the best table.
	- `cashew_converter.statement` — CSV/XLSX dispatcher, header synonym mapping, date parsing, amount extraction, and canonical `StatementTransaction` creation.
- Data & Models
	- `cashew_converter.models` — dataclasses: `StatementTransaction`, `CategoryStyle`, `CashewRow` and helpers for CSV formatting.
- Classification
	- `cashew_converter.rules` — regex RULES for merchant→category mapping, learned rules persistence (`learned_rules.json`), `classify()` and `learn_from_rows()`.
- Utilities & Scripts
	- `scripts/` — helper scripts for bulk categorization, listing categories and updating learned mappings.
	- `tests/test_converter.py` — unit tests for core conversion

## Dataflow (text + mermaid)

Below is a simplified flow showing how an uploaded/selected file is processed.

```mermaid
flowchart TD
	subgraph Input
		A[.xlsx / .csv file] -->|uploaded / path| B[Entry: CLI or Web UI]
	end

	B --> C{File type}
	C -->|XLSX| D[cashew_converter.xlsx: load_xlsx_table()]
	C -->|CSV| E[cashew_converter.statement: load_csv_table()]

	D --> F[rows: list[dict]]
	E --> F

	F --> G[statement.py: row_to_transaction()]
	G --> H[StatementTransaction(date, description, amount, income)]

	H --> I[rules.classify(transaction)]
	I -->|match RULES or learned| J[CategoryStyle(category, subcategory, color, icon, budget)]

	H --> K[statement.transaction_to_cashew()] 
	J --> K
	K --> L[CashewRow]
	L --> M[rows_to_csv_text() / CSV writer]
	M --> N[Downloadable Cashew CSV]

	subgraph Web
		B --> WebUI[cashew_converter.web: render preview table]
		WebUI -->|edits| Learn[POST /learn -> rules.learn_from_rows()]
		Learn --> rules.LEARNED_RULES_PATH (learned_rules.json)
		WebUI -->|download| M
	end

	style L fill:#fff4e6,stroke:#c96b4d
```

## Component responsibilities (file-level)

- `cashew_converter.__main__` and `cashew_converter.cli`
	- CLI entry point that parses arguments and writes out Cashew CSV using Python's `csv.DictWriter`.

- `cashew_converter.xlsx`
	- Pure-Python XLSX parser (uses `zipfile` and `xml.etree.ElementTree`) to extract sheets and shared strings, score sheet headers against `HEADER_HINTS` and return a list of row dicts.

- `cashew_converter.statement`
	- Central orchestrator for conversion. Detects file type, normalizes headers (via `HEADER_SYNONYMS`), parses dates using `DATE_FORMATS`, resolves amounts from debit/credit/amount columns, filters ignorable rows, converts rows into `StatementTransaction`, and then to `CashewRow` via `classify()`.

- `cashew_converter.models`
	- Domain dataclasses and CSV formatting utilities. `CashewRow.to_csv_row()` converts typed values into strings matching `CASHEW_COLUMNS`.

- `cashew_converter.rules`
	- Two-stage classification: 1) learned merchant->category mappings persisted in `learned_rules.json`; 2) regex-based RULES fallback. `extract_note()` tries to canonicalize merchant/UPI strings.

- `cashew_converter.web`
	- Minimal WSGI HTML app providing an upload form, a preview table with inline editing and bulk edits, a `/learn` endpoint to persist corrections using `rules.learn_from_rows()`, and a CSV download path (uses `rows_to_csv_text`). Contains the HTML templates inline and a simple development server runner.

## Persistence and learning

- Learned rules are stored at runtime in `cashew_converter/learned_rules.json` (path computed relative to `rules.py`). The web UI posts edited rows to `/learn`, which calls `learn_from_rows()`; that writes the JSON mapping used by future classifications.

## Error handling & heuristics

- Date parsing tries multiple formats (`DATE_FORMATS`) and rejects rows without parseable dates.
- Amount parsing prefers credit/debit columns, with fallbacks and error raising for ambiguous rows.
- XLSX sheet selection scores headers against `HEADER_HINTS` and chooses the best-scoring table.

## Runtime modes

- CLI: batch mode for scripted conversion (`python -m cashew_converter <input> --output <out.csv>`).
- Web: interactive mode for human review, editing, and learning (`python -m cashew_converter.web` or `cashew-converter-web`).

## Notes & extension points

- Add more RULES in `cashew_converter.rules` to improve automatic categorization.
- Improve `extract_note()` heuristics to handle more bank-specific formats.
- Persist learned rules to a configurable path for multi-user deployments.

---

Generated from repository inspection: key files include `cashew_converter/models.py`, `cashew_converter/statement.py`, `cashew_converter/rules.py`, `cashew_converter/xlsx.py`, and `cashew_converter/web.py`.

