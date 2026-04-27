# Cashew Converter

Convert a bank statement exported as `.xlsx` or `.csv` into the Cashew import CSV format.

## Current scope

- Supports the workbook format in `bstate.xlsx`.
- Reads CSV statements with common `Date`, `Details`, `Debit`, `Credit`, and `Balance` columns.
- Emits a Cashew-compatible CSV using the same column order as the sample export.

## Usage

```bash
python -m cashew_converter /path/to/statement.xlsx --output /path/to/output.csv
```

You can also import a CSV statement:

```bash
python -m cashew_converter /path/to/statement.csv --output /path/to/output.csv
```

## Notes

- Debit amounts become negative values.
- Credit amounts become positive values.
- The current first-pass rules use transaction keywords to assign Cashew categories.
- Rows without a rule fall back to a generic transfer-style category so nothing is lost.
# Receipt
