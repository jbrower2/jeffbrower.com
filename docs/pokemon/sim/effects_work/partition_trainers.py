#!/usr/bin/env python3
"""Partition uncovered trainers into cohesive by-type batches with a kind hint. -> trainer_batches.json"""
import os, sys, json
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import trainer_effects as TE

HERE = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(os.path.join(os.path.dirname(os.path.dirname(HERE)), 'deckgen', 'trainers.json')))


def tool_kind(txt):
    t = txt.lower()
    if 'more hp' in t or 'gets +' in t and 'hp' in t:
        return 'tool_hp'
    if 'less damage' in t or 'reduced' in t:
        return 'tool_dr'
    if 'damaged by an attack' in t or 'is knocked out' in t:
        return 'tool_ondamaged'
    if 'more damage' in t:
        return 'tool_attack_buff'
    if 'retreat' in t:
        return 'tool_retreat'
    return 'tool_hp'   # default; agent verifies/repicks


def kind_of(v):
    tt = v.get('trainerType')
    if tt == 'Item':
        return 'item'
    if tt == 'Supporter':
        return 'supporter'
    if tt == 'Stadium':
        return 'stadium'
    return tool_kind(v.get('effect', ''))


groups = defaultdict(list)
for nm, v in T.items():
    key = TE.normalize(v.get('effect', ''))
    if key in TE.TRAINER_EFFECTS:
        continue
    tt = v.get('trainerType', '?')
    groups[tt].append({'name': nm, 'text': v.get('effect', ''), 'ttype': tt, 'kind': kind_of(v)})

batches = []
for tt in ['Item', 'Supporter', 'Stadium', 'Tool']:
    xs = sorted(groups.get(tt, []), key=lambda x: x['name'])
    for i in range(0, len(xs), 14):
        batches.append({'id': f"tr_{tt.lower()}_{i//14}", 'ttype': tt, 'trainers': xs[i:i + 14]})

json.dump({'total_distinct': sum(len(g) for g in groups.values()), 'batches': batches},
          open(os.path.join(HERE, 'trainer_batches.json'), 'w'), indent=1)
print(f"{sum(len(g) for g in groups.values())} uncovered trainers -> {len(batches)} batches")
for b in batches:
    print(f"   {b['id']:20} {len(b['trainers']):2} {b['ttype']}")
