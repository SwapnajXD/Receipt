#!/usr/bin/env python3
"""
Update new.csv with suggested categories based on old.csv matches.
"""

import csv
from pathlib import Path
from collections import defaultdict

old_file = Path(__file__).parent.parent / "res" / "old.csv"
new_file = Path(__file__).parent.parent / "res" / "new.csv"
output_file = Path(__file__).parent.parent / "res" / "new_categorized.csv"

# Build lookup from old.csv
old_transactions = {}
with open(old_file) as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['category name'] and row['category name'] != 'Miscellaneous':
            date = row['date'].split()[0]
            amount = float(row['amount'])
            key = (date, amount)
            old_transactions[key] = {
                'category': row['category name'],
                'subcategory': row['subcategory name'],
            }

# Read and update new.csv
rows = []
categorized = 0

# Analyze unmatched for patterns
unmatched_by_category = defaultdict(list)

with open(new_file) as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['category name'] == 'Miscellaneous':
            date = row['date'].split()[0]
            amount = float(row['amount'])
            key = (date, amount)
            
            if key in old_transactions:
                # Update with suggestion
                old_data = old_transactions[key]
                row['category name'] = old_data['category']
                row['subcategory name'] = old_data['subcategory']
                categorized += 1
            else:
                # Try to categorize by name patterns
                note = row['note'].lower()
                
                # Pattern-based categorization for common names/merchants
                if any(x in note for x in ['zomato', 'swiggy', 'dunzo', 'uber', 'ola', 'magicpin']):
                    row['category name'] = 'Dining'
                    row['subcategory name'] = 'Delivery'
                elif any(x in note for x in ['chai', 'coffee', 'tea', 'juice', 'shake', 'burger', 'pizza', 'food']):
                    row['category name'] = 'Dining'
                    row['subcategory name'] = 'Cafes'
                elif any(x in note for x in ['petrol', 'gas', 'fuel', 'bp', 'shell', 'relay']):
                    row['category name'] = 'Travel'
                elif any(x in note for x in ['metro', 'train', 'cab', 'taxi', 'auto', 'bus']):
                    row['category name'] = 'Travel'
                    row['subcategory name'] = 'Trains'
                elif any(x in note for x in ['movie', 'ticket', 'concert', 'game', 'show']):
                    row['category name'] = 'Entertainment'
                elif any(x in note for x in ['book', 'xerox', 'pen', 'pencil', 'paper', 'college']):
                    row['category name'] = 'Bills & Fees'
                    row['subcategory name'] = 'College'
                elif any(x in note for x in ['dress', 'shirt', 'pant', 'shoe', 'jersey', 'cloth', 'hanger']):
                    row['category name'] = 'Shopping'
                    row['subcategory name'] = 'Clothing'
                elif any(x in note for x in ['grocery', 'mart', 'shop', 'store', 'egg', 'dal', 'rice', 'vegetable']):
                    row['category name'] = 'Groceries'
                elif any(x in note for x in ['medicine', 'doctor', 'hospital', 'pharmacy', 'health', 'wash']):
                    row['category name'] = 'Personal Care'
                else:
                    # Try to guess by amount - very small amounts are usually social transfers
                    amount_abs = abs(amount)
                    if amount_abs <= 50:
                        row['category name'] = 'Gifts'  # Small casual transfers
                    elif 50 < amount_abs <= 150:
                        row['category name'] = 'Gifts'  # Medium transfers
                    else:
                        row['category name'] = 'Gifts'  # Larger transfers/payments to people
        
        rows.append(row)

# Write updated file
with open(output_file, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print(f"✓ Updated {categorized} transactions with old.csv matches")
print(f"✓ Applied pattern-based categorization to remaining unmatched")
print(f"✓ Output saved to: new_categorized.csv")

# Summary
from collections import Counter
new_categories = Counter(row.get('category name', '') for row in rows)
print(f"\n📊 Category distribution in updated file:")
for cat, count in sorted(new_categories.items(), key=lambda x: -x[1]):
    print(f"  {cat}: {count}")
