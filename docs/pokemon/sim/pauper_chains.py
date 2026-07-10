#!/usr/bin/env python3
"""Evolution-chain abstraction for the fully-pauper (Common/Uncommon only) deck lab.

A CHAIN is one C/U evolution line — basic (→ stage1 (→ stage2)) — built from the cheapest legal
printing per species (preferring the ability-bearing printing). Each chain knows the energy its
TOP stage's attacks require (excluding Colorless), so a colorless-attacking chain fits ANY deck
(rule 4). Chains are the unit of deck-building and of the chain-based mutation operators.

`cat == 'cat-green'` is the pauper legality gate (printings.json is already reg H/I/J-clean).
"""
import json, os, re
from collections import defaultdict
from cards import load_cards

HERE = os.path.dirname(os.path.abspath(__file__))
BY_KEY, BY_NAME = load_cards()
TYPES = ['Grass', 'Fire', 'Water', 'Lightning', 'Psychic', 'Fighting', 'Darkness', 'Metal']
L2T = {'G': 'Grass', 'R': 'Fire', 'W': 'Water', 'L': 'Lightning', 'P': 'Psychic',
       'F': 'Fighting', 'D': 'Darkness', 'M': 'Metal'}
ACCEL_ABILITIES = {'Dynamotor', 'Inferno Fandango', 'Electric Streamer', 'Golden Flame',
                   'Metal Maker', 'Stone Arms', 'Wash Out', 'Metal Road', 'Energized Steps'}


def _cu(name):
    return [c for c in BY_NAME.get(name, []) if c.cat == 'cat-green']


def _dps(c):
    return max((a['dmg'] / max(1, len(a['cost'])) for a in c.attacks if a['dmg'] > 0), default=0)


def _rep(name, stage):
    """Best C/U printing of `name` at `stage`: prefer one with an ability, else best damage/energy."""
    opts = [c for c in _cu(name) if c.stage == stage]
    if not opts:
        return None
    withab = [c for c in opts if c.abilities]
    return max(withab or opts, key=_dps)


def _attack_energy(card):
    """Non-colorless energy letters this card's attacks require."""
    need = set()
    for a in card.attacks:
        for ltr in a['cost']:
            if ltr in L2T:
                need.add(ltr)
    return need


def _tags(cards):
    tags = set()
    top = cards[-1]
    for c in cards:
        for ab in c.abilities:
            n = ab['name']; t = ab['text'].lower()
            if n in ACCEL_ABILITIES or ('attach' in t and 'energy' in t):
                tags.add('accel')
            if 'draw' in t or 'search your deck' in t:
                tags.add('engine')
            if 'more damage' in t and 'your' in t:
                tags.add('buff')
            if 'less damage' in t or "can't be" in t or 'prevent' in t:
                tags.add('wall')
            if ab:
                tags.add('ability')
    txt = ' '.join(a['text'].lower() for a in top.attacks)
    if re.search(r'damage to (each|1|2|3) of your opponent', txt):
        tags.add('spread')
    if 'is now asleep' in txt or 'is now poisoned' in txt or 'is now paralyzed' in txt or 'is now confused' in txt:
        tags.add('status')
    if _dps(top) >= 35:
        tags.add('attacker')
    return sorted(tags)


def load_chains():
    """Return list of chain dicts. Each: id, top, stages[(name,key,stage)], energy(set of letters),
    hp, dps, abilities[names], tags[], length."""
    chains = []
    seen_as_evo = set()
    # index C/U stage1/stage2 by what they evolve from
    evo = defaultdict(list)
    for name, plist in BY_NAME.items():
        for c in plist:
            if c.cat == 'cat-green' and c.stage in (1, 2) and c.evolves_from:
                evo[c.evolves_from].append(c)
    for name in BY_NAME:
        basic = _rep(name, 0)
        if basic is None:
            continue
        line = [basic]
        s1s = [c for c in evo.get(basic.name, [])]
        if s1s:
            s1 = max(s1s, key=lambda c: (bool(c.abilities), _dps(c)))
            line.append(_rep(s1.name, 1) or s1)
            seen_as_evo.add(s1.name)
            s2s = [c for c in evo.get(line[-1].name, [])]
            if s2s:
                s2 = max(s2s, key=lambda c: (bool(c.abilities), _dps(c)))
                line.append(_rep(s2.name, 2) or s2)
                seen_as_evo.add(s2.name)
        top = line[-1]
        energy = set()
        for c in line:                                   # union across the line, but rule uses top attacks
            pass
        energy = _attack_energy(top)                     # top-stage attack requirement (∅ = colorless, fits any)
        chains.append({'id': basic.name, 'top': top.name,
                       'stages': [(c.name, c.key, c.stage) for c in line],
                       'energy': sorted(energy), 'hp': top.hp, 'dps': round(_dps(top), 1),
                       'abilities': [ab['name'] for c in line for ab in c.abilities],
                       'tags': _tags(line), 'length': len(line)})
    # drop chains whose basic is itself a mid/late evolution of another line (avoid dupes)
    chains = [c for c in chains if c['id'] not in seen_as_evo]
    return chains


if __name__ == '__main__':
    chains = load_chains()
    json.dump(chains, open(os.path.join(HERE, 'pauper_chains.json'), 'w'), indent=0)
    print(f"{len(chains)} C/U evolution chains extracted -> pauper_chains.json")
    by_energy = defaultdict(int)
    for c in chains:
        key = 'Colorless' if not c['energy'] else '/'.join(L2T[e] for e in c['energy'])
        by_energy[key] += 1
    print("by energy requirement (top-stage attacks):")
    for k, v in sorted(by_energy.items(), key=lambda x: -x[1])[:14]:
        print(f"  {k:20} {v}")
    print(f"\ncolorless-compatible (fit any deck): {sum(1 for c in chains if not c['energy'])}")
    print(f"chains with an ability: {sum(1 for c in chains if 'ability' in c['tags'])}")
    print("\nsample INTERESTING chains (ability engines / buffs / spread):")
    for c in sorted(chains, key=lambda x: -x['dps']):
        if {'accel', 'engine', 'buff', 'spread'} & set(c['tags']):
            eng = 'Col' if not c['energy'] else '/'.join(c['energy'])
            print(f"  [{eng:5}] {c['top'][:24]:24} L{c['length']} {c['hp']}HP dps{c['dps']:4} {c['tags']} ab:{c['abilities'][:2]}")
