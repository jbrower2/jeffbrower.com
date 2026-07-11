#!/usr/bin/env python3
"""Partition uncovered abilities into cohesive kind-batches with context + a KIND HINT, for the
ability-implementation workflow. Writes effects_work/ability_batches.json."""
import os, sys, json
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cards import load_cards
import ability_effects as AB

BK, BN = load_cards()
HERE = os.path.dirname(os.path.abspath(__file__))

PRIORITY = ['passive_hp', 'passive_dr', 'immunity', 'attack_buff', 'retreat_mod', 'lock',
            'between_turns', 'on_damaged', 'energy_accel', 'search', 'draw', 'activated', 'other']


def kind_hint(t):
    tl = t.lower()
    if 'more hp' in tl or 'maximum hp' in tl:
        return 'passive_hp'
    if 'less damage' in tl or 'reduced by' in tl:
        return 'passive_dr'
    if 'prevent all damage' in tl or "can't be" in tl or "isn't affected" in tl or "aren't affected" in tl or 'no effect' in tl or "can't be affected" in tl:
        return 'immunity'
    if 'more damage' in tl and ('attacks' in tl or "this pokémon's attacks" in tl or 'your' in tl):
        return 'attack_buff'
    if 'retreat cost' in tl or 'has no retreat' in tl or 'free retreat' in tl:
        return 'retreat_mod'
    if 'lose any ability' in tl or 'stop working' in tl or "abilities on your opponent" in tl:
        return 'lock'
    if 'between turns' in tl or 'pokémon checkup' in tl or 'checkup' in tl:
        return 'between_turns'
    if 'is damaged by an attack' in tl or 'damaged by' in tl and 'attacking' in tl:
        return 'on_damaged'
    if 'attach' in tl and 'energy' in tl:
        return 'energy_accel'
    if 'search your deck' in tl:
        return 'search'
    if 'draw' in tl:
        return 'draw'
    if 'once during your turn' in tl or 'once during your first turn' in tl or 'you may' in tl:
        return 'activated'
    return 'other'


info = {}
for c in BK.values():
    if c.cat != 'cat-green':
        continue
    for ab in c.abilities:
        key = AB.normalize(ab['text'])
        if key in AB.ABILITY_EFFECTS:
            continue
        e = info.setdefault(key, {'key': ab['text'], 'count': 0, 'kind_hint': kind_hint(key), 'examples': []})
        e['count'] += 1
        if len(e['examples']) < 3:
            e['examples'].append({'card': c.name, 'ability': ab['name']})

groups = defaultdict(list)
for e in info.values():
    groups[e['kind_hint']].append(e)

batches = []
for k in PRIORITY:
    effs = sorted(groups.get(k, []), key=lambda x: -x['count'])
    for i in range(0, len(effs), 14):
        batches.append({'id': f"ab_{k}_{i//14}", 'kind_hint': k, 'abilities': effs[i:i + 14]})

json.dump({'total_distinct': len(info), 'batches': batches},
          open(os.path.join(HERE, 'ability_batches.json'), 'w'), indent=1)
print(f"{len(info)} distinct uncovered abilities -> {len(batches)} batches")
for b in batches:
    print(f"   {b['id']:26} {len(b['abilities']):2} abilities")
