#!/usr/bin/env python3
"""Find cards not yet used in decks.md, to spot deck-design gaps.

Lists legal ex premiums (<= $1) and rare ability-cards (<= $0.50) whose name does
not appear in ../decks.md. Useful for 'what else can we build'.

Run:  python3 coverage.py
"""
import json, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
POKE = os.path.dirname(HERE)
byname = json.load(open(os.path.join(HERE, 'printings.json')))['byname']
decks = open(os.path.join(POKE, 'decks.md')).read()

def used(name):
    return name in decks

print('=== LEGAL EX PREMIUMS (<=$1) not yet in any deck ===')
seen = set()
for name, ps in sorted(byname.items()):
    if not any(p['ex'] and p['price'] and p['price'] <= 1.0 for p in ps):
        continue
    if name in seen: continue
    seen.add(name)
    if not used(name):
        cheap = min((p for p in ps if p['ex'] and p['price'] and p['price'] <= 1.0), key=lambda p: p['price'])
        print(f"  ${cheap['price']:.2f} {name} ({cheap['set']}) [{cheap['energy'] or 'C'}]")

print('\n=== RARE ABILITY-CARDS (<=$0.50) not yet in any deck (potential supports) ===')
seen = set()
rows = []
for name, ps in byname.items():
    for p in ps:
        if p['cat'] == 'cat-yellow' and p['price'] is not None and p['price'] <= 0.50 and p['abils']:
            if name in seen: break
            if not used(name):
                seen.add(name)
                rows.append((p['price'], name, p['set'], p['energy'] or 'C', p['abils'][0]['name']))
            break
for pr, name, st, en, ab in sorted(rows):
    print(f"  ${pr:.2f} {name} ({st}) [{en}] — {ab}")
