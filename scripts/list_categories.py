#!/usr/bin/env python3
import csv
from collections import defaultdict
p='res/cashew-2025-12-31-21-09-30-327607.csv'
with open(p, newline='', encoding='utf-8') as f:
    r=csv.DictReader(f)
    d=defaultdict(set)
    for row in r:
        cat=(row.get('category name') or '').strip()
        sub=(row.get('subcategory name') or '').strip()
        if not cat:
            cat='(blank)'
        if not sub:
            sub='(blank)'
        d[cat].add(sub)
for c in sorted(d.keys()):
    print(c)
    for s in sorted(d[c]):
        print('  -', s)
