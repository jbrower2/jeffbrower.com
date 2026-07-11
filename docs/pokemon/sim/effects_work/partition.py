#!/usr/bin/env python3
"""Partition the uncovered attack effects into cohesive mechanic-groups with per-effect context,
so each workflow agent gets a self-contained, implementable batch. Writes effects_work/batches.json."""
import os, sys, json
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cards import load_cards
import attack_effects as AE

BK, BN = load_cards()
HERE = os.path.dirname(os.path.abspath(__file__))

# gather uncovered distinct effects with example context
info = {}
for c in BK.values():
    if c.cat != 'cat-green':
        continue
    for a in c.attacks:
        key = AE.normalize(a.get('text'))
        if not key or key in AE.ATTACK_EFFECTS:
            continue
        e = info.setdefault(key, {'key': key, 'count': 0, 'raw': a['text'], 'examples': []})
        e['count'] += 1
        if len(e['examples']) < 3:
            e['examples'].append({'card': c.name, 'set': c.set, 'id': c.id,
                                  'cost': ''.join(a['cost']), 'dmg': a['dmg'], 'raw': a['text']})


def mechanic(k):
    t = k.lower()
    if 'coin' in t and ('for each heads' in t or 'more damage' in t or 'does 10' in t or 'does 20' in t):
        return 'coinflip_damage'
    if 'coin' in t and ('does nothing' in t):
        return 'coinflip_gate'
    if 'coin' in t:
        return 'coinflip_effect'
    if 'search your deck' in t:
        return 'search'
    if 'draw' in t and 'card' in t:
        return 'draw'
    if any(s in t for s in ('asleep', 'poisoned', 'burned', 'paralyzed', 'confused')):
        return 'status'
    if 'heal' in t:
        return 'heal'
    if 'damage to itself' in t:
        return 'self_damage'
    if 'discard' in t and 'energy' in t:
        return 'discard_energy'
    if "opponent's deck" in t or 'top card' in t:
        return 'mill'
    if 'less damage' in t or 'prevent all damage' in t or "reduce" in t:
        return 'damage_reduction'
    if 'switch' in t or "can't retreat" in t or 'to the bench' in t:
        return 'switch_retreat'
    if 'benched' in t or 'each of your opponent' in t or 'bench' in t:
        return 'bench_spread'
    if 'tool' in t:
        return 'tool'
    if 'more damage' in t or 'plus' in t or 'for each' in t or 'if this' in t or 'if your' in t or "if the defending" in t:
        return 'conditional_damage'
    return 'misc'


groups = defaultdict(list)
for e in info.values():
    groups[mechanic(e['key'])].append(e)

# split any oversized mechanic into <=28-effect sub-batches; sort effects by count desc within a group
batches = []
for mech, effs in sorted(groups.items()):
    effs.sort(key=lambda x: -x['count'])
    for i in range(0, len(effs), 28):
        chunk = effs[i:i + 28]
        batches.append({'id': f"{mech}_{i//28}", 'mechanic': mech, 'effects': chunk})

out = {'total_uncovered_distinct': len(info),
       'total_uncovered_instances': sum(e['count'] for e in info.values()),
       'batches': batches}
json.dump(out, open(os.path.join(HERE, 'batches.json'), 'w'), indent=1)
print(f"{len(info)} distinct uncovered effects -> {len(batches)} batches")
for b in batches:
    print(f"   {b['id']:24} {len(b['effects']):3} effects")
