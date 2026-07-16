# Cashew Converter

Convert a bank statement (`.xlsx` or `.csv`) into a CSV ready to import into
[Cashew](https://cashewapp.web.app/) — and have it get better at categorizing
your transactions every time you use it.

## Features

- **Two ways in**: a CLI for quick batch conversion, and a local web UI for
  reviewing and correcting rows before you export.
- **Learns from your corrections.** Fix a category in the web UI and hit
  "Learn Rules" — that mapping is saved to `learned_rules.json` and applied
  automatically on every future conversion, before falling back to the
  built-in regex rules.
- **Pure Python, zero dependencies.** The XLSX reader is hand-rolled on top
  of `zipfile` and `xml.etree` — no `pandas`, no `openpyxl`. `pip install`
  has nothing to fetch.
- **Handles messy real-world spreadsheets**: auto-detects the correct sheet
  and header row, supports multiple date formats (including native Excel
  date cells, not just text dates), and normalizes debit/credit/amount
  columns regardless of which one your bank uses.

## Install

Requires Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e .
```

## Web UI (recommended)

```bash
python -m cashew_converter.web
# or, once installed:
cashew-converter-web
```

Open `http://127.0.0.1:8000`, drop in your statement, and you'll get an
editable preview with:

- inline editing of every field (date, amount, category, subcategory, note)
- a search box to filter rows by note, category, or amount
- category color dots for a quick visual scan
- live income / expense / net totals that update as you edit
- a bulk-edit bar to apply a change to selected or all visible (filtered) rows
- **Learn Rules** — save your corrections for next time
- **Download CSV** — export the edited table, ready for Cashew import

## CLI

```bash
python -m cashew_converter /path/to/statement.xlsx --output /path/to/output.csv
```

Also works with CSV input:

```bash
python -m cashew_converter /path/to/statement.csv --output /path/to/output.csv
```

Flags:

| Flag | Description |
| --- | --- |
| `--output`, `-o` | *(required)* Path to the generated Cashew CSV |
| `--account` | Cashew account name to write into the export (default: `Sbi`) |
| `--quiet`, `-q` | Only print the transaction count, skip the category/income summary |

By default the CLI also prints an income/expense/net summary and a
per-category breakdown after each conversion.

## How categorization works

1. Income transactions are tagged directly.
2. Everything else is checked against **learned rules** first — an exact
   match, then a substring match against the transaction's normalized
   description — so your manual corrections always take priority.
3. If nothing learned matches, it falls back to the built-in **regex rules**
   in `cashew_converter/rules.py` (merchant patterns, UPI reference formats,
   recurring bills, etc.).
4. If neither matches, the transaction is categorized as `Transfers` /
   uncategorized.

Learned rules are stored at `cashew_converter/learned_rules.json` and persist
across runs.

## Notes

- Debit amounts become negative values, credit amounts become positive.
- Everything runs locally — no statement data is ever sent anywhere.

## Running the tests

```bash
python -m unittest discover -s tests -v
```

You should see 10 tests, with 6 skipped — those need a real bank statement
fixture (`res/bstate.xlsx`) that isn't committed to the repo for privacy.
The core parsing logic (including XLSX edge cases like native date cells and
alternate writer formats) is covered by separate, self-contained tests that
don't need that fixture.
