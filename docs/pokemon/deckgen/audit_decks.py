#!/usr/bin/env python3
"""Verify every deck's paid slots against printing-level data.

For each deck in decks_*.txt: the Premium must have an ex printing <= $1.00, and
each Support must have a cat-yellow (rare) printing <= $0.50. Reports:
  - HARD ERRORS: no legal printing exists for the claimed slot (must fix).
  - ambiguous: a legal printing exists but the NAME has >1 distinct-mechanic
    printing at that slot -> confirm the deck names the intended printing.

Run:  python3 parse_printings.py && python3 audit_decks.py
"""
import json, re, glob, os
HERE = os.path.dirname(os.path.abspath(__file__))
byname = json.load(open(os.path.join(HERE, 'printings.json')))['byname']
bolds = re.compile(r'\*\*([^*]+)\*\*')

def norm(b):
    b = re.sub(r'\s*[×x]\s*\d+$', '', b.strip())
    b = re.sub(r'\s*\(.*$', '', b)
    return b.replace('’', "'").strip(' *')

hard = []; ambig = []; ok = 0; total = 0; premiums = []
for path in sorted(glob.glob(os.path.join(HERE, 'decks_*.txt'))):
    T = os.path.basename(path).replace('decks_', '').replace('.txt', '')
    deck = None
    for line in open(path):
        l = line.rstrip('\n')
        if l.startswith('**') and not l.startswith('- '):
            m = bolds.search(l); deck = m.group(1) if m else l[:30]
        elif l.strip().startswith('- Premium:'):
            m = bolds.findall(l)
            if not m: continue
            name = norm(m[0]); total += 1; premiums.append((T, name))
            qual = [p for p in byname.get(name, []) if p['ex'] and p['price'] is not None and p['price'] <= 1.0]
            if not qual: hard.append((T, deck, 'PREMIUM', name, 'no ex <=$1 printing'))
            else:
                ok += 1
                if len({tuple(p['sig']) for p in qual}) > 1: ambig.append((T, deck, 'premium', name))
        elif l.strip().startswith('- Supports:'):
            for b in bolds.findall(l):
                name = norm(b); total += 1
                qual = [p for p in byname.get(name, []) if p['cat'] == 'cat-yellow' and p['price'] is not None and p['price'] <= 0.50]
                if not qual: hard.append((T, deck, 'SUPPORT', name, 'no rare <=$0.50 printing'))
                else:
                    ok += 1
                    if len({tuple(p['sig']) for p in qual}) > 1: ambig.append((T, deck, 'support', name))

print(f'slot-cards: {total} | legal printing exists: {ok} | HARD ERRORS: {len(hard)} | ambiguous: {len(ambig)}')
for t in hard: print('  HARD', t)
