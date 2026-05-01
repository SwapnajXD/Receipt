#!/usr/bin/env python3
"""
Compare old.csv and new.csv to find matching transactions and suggest categories.
"""

import csv
from pathlib import Path
from collections import defaultdict

# Read files
old_file = Path(__file__).parent.parent / "res" / "old.csv"
new_file = Path(__file__).parent.parent / "res" / "new.csv"

# Parse old.csv - this has proper categories
old_transactions = {}  # (date, amount) -> category
with open(old_file) as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['category name'] and row['category name'] != 'Miscellaneous':
            date = row['date'].split()[0]  # Get just the date part
            amount = float(row['amount'])
            key = (date, amount)
            # Store category info
            old_transactions[key] = {
                'category': row['category name'],
                'subcategory': row['subcategory name'],
                'note': row['note']
            }

# Parse new.csv - find Miscellaneous entries
misc_transactions = []
with open(new_file) as f:
    reader = csv.DictReader(f)
    for idx, row in enumerate(reader, 1):
        if row['category name'] == 'Miscellaneous':
            date = row['date'].split()[0]
            amount = float(row['amount'])
            misc_transactions.append({
                'row_idx': idx,
                'date': date,
                'amount': amount,
                'note': row['note'],
                'full_row': row
            })

print(f"Found {len(misc_transactions)} Miscellaneous transactions in new.csv")
print(f"Found {len(old_transactions)} categorized transactions in old.csv\n")

# Try to match by date and amount
matches = []
unmatched = []

for misc in misc_transactions:
    key = (misc['date'], misc['amount'])
    
    if key in old_transactions:
        old_data = old_transactions[key]
        matches.append({
            **misc,
            'suggested_category': old_data['category'],
            'suggested_subcategory': old_data['subcategory'],
            'old_note': old_data['note']
        })
    else:
        unmatched.append(misc)

print(f"Matched by date+amount: {len(matches)}")
print(f"Could not match: {len(unmatched)}\n")

# Group matches by suggested category
matches_by_category = defaultdict(list)
for match in matches:
    cat = match['suggested_category']
    matches_by_category[cat].append(match)

print("=" * 80)
print("SUGGESTED CATEGORIES FOR MISCELLANEOUS TRANSACTIONS")
print("=" * 80)

for category in sorted(matches_by_category.keys()):
    items = matches_by_category[category]
    print(f"\n{category}: {len(items)} transactions")
    print("-" * 40)
    for item in items[:5]:  # Show first 5
        print(f"  Row {item['row_idx']}: {item['date']} | ₹{item['amount']} | {item['note']} | Old note: {item['old_note']}")
    if len(items) > 5:
        print(f"  ... and {len(items) - 5} more")

# Also group unmatched by amount ranges to help identify patterns
print(f"\n\n{'=' * 80}")
print("UNMATCHED TRANSACTIONS (no exact date+amount match in old.csv)")
print(f"{'=' * 80}")
print(f"Total unmatched: {len(unmatched)}\n")

# Group by amount ranges
amount_groups = defaultdict(list)
for item in unmatched:
    # Group by rough amount (lower to nearest 10)
    amount_group = (int(item['amount'] / 50) * 50)
    amount_groups[amount_group].append(item)

print("Top amounts in unmatched transactions:")
for amount in sorted(amount_groups.keys(), reverse=True)[:10]:
    items = amount_groups[amount]
    if len(items) >= 2:  # Only show amounts with multiple entries
        print(f"\n₹{amount} range: {len(items)} transactions")
        for item in items[:3]:
            print(f"  {item['date']} | {item['amount']} | {item['note']}")
        if len(items) > 3:
            print(f"  ... and {len(items) - 3} more")

# Save detailed report
output_file = Path(__file__).parent.parent / "res" / "misc_categorization_report.csv"
with open(output_file, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['date', 'amount', 'note', 'suggested_category', 'suggested_subcategory', 'old_note', 'status'])
    writer.writeheader()
    
    for match in matches:
        writer.writerow({
            'date': match['date'],
            'amount': match['amount'],
            'note': match['note'],
            'suggested_category': match['suggested_category'],
            'suggested_subcategory': match['suggested_subcategory'],
            'old_note': match['old_note'],
            'status': 'MATCHED'
        })
    
    for item in unmatched:
        writer.writerow({
            'date': item['date'],
            'amount': item['amount'],
            'note': item['note'],
            'suggested_category': '',
            'suggested_subcategory': '',
            'old_note': '',
            'status': 'UNMATCHED'
        })

print(f"\n\nDetailed report saved to: {output_file}")
