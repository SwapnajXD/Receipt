# Cashew Converter

Convert a bank statement exported as `.xlsx` or `.csv` into the Cashew import CSV format.

## Current scope

- Supports the workbook format in `bstate.xlsx`.
- Reads CSV statements with common `Date`, `Details`, `Debit`, `Credit`, and `Balance` columns.
- Emits a Cashew-compatible CSV using the same column order as the sample export.
- Includes a local web upload UI for quick file conversion.

## CLI usage

```bash
python -m cashew_converter /path/to/statement.xlsx --output /path/to/output.csv
```

You can also import a CSV statement:

```bash
python -m cashew_converter /path/to/statement.csv --output /path/to/output.csv
```

## Web UI

Start the upload page with:

```bash
python -m cashew_converter.web
```

Or use the installed script:

```bash
cashew-converter-web
```

Then open `http://127.0.0.1:8000` in your browser, upload a statement, and download the generated Cashew CSV.

## Notes

- Debit amounts become negative values.
- Credit amounts become positive values.
- The rule engine now maps more common merchant keywords into useful Cashew categories before falling back to `Transfers`.
