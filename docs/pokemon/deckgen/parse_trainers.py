#!/usr/bin/env python3
"""Extract the Common/Uncommon Trainer pool from carddata/*.json -> trainers.json.

Trainers are legal in the format under the same "rest must be Common/Uncommon" rule,
so rarity alone gates legality (C/U = free, unlimited up to 4). Each record has name,
trainerType (Supporter/Item/Stadium/Tool), rarity, regulationMark, and full effect text.
Higher-rarity Trainers (Ultra/ACE SPEC/etc.) are excluded — they'd need a money slot.
"""
import json, glob, os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
POKE = os.path.dirname(HERE)
CU = ('Common', 'Uncommon')


def load_all_trainers():
    rows = {}
    for f in glob.glob(os.path.join(POKE, 'carddata', '*.json')):
        d = json.load(open(f))
        cards = d if isinstance(d, list) else d.get('cards') or next((v for v in d.values() if isinstance(v, list)), [])
        for c in cards:
            if c.get('category') != 'Trainer':
                continue
            nm = c['name']; r = c.get('rarity') or ''
            rec = {'name': nm, 'trainerType': c.get('trainerType'), 'rarity': r,
                   'reg': c.get('regulationMark'), 'effect': (c.get('effect') or '').strip()}
            prev = rows.get(nm)
            # prefer the C/U printing (and the one with effect text) if a name repeats
            if prev is None or (r in CU and prev['rarity'] not in CU) or (not prev['effect'] and rec['effect']):
                rows[nm] = rec
    return rows


def cu_trainers():
    return {n: r for n, r in load_all_trainers().items() if r['rarity'] in CU}


if __name__ == '__main__':
    cu = cu_trainers()
    json.dump(cu, open(os.path.join(HERE, 'trainers.json'), 'w'), indent=0)
    byt = Counter(v['trainerType'] for v in cu.values())
    print(f"{len(cu)} Common/Uncommon Trainers -> trainers.json  {dict(byt)}")
