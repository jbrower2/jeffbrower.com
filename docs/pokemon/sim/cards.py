#!/usr/bin/env python3
"""Data-derived card model for the simulator.

Loads deckgen/printings.json and turns each printing into a Card with the fields
the engine needs: HP, stage, evolves_from, types, weakness, retreat, is_ex, and
attacks (energy cost + parsed base damage + a scaling flag + raw text for effects).

Cards are identified by (set, id) so the two "Palafin" printings stay distinct.
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
PRINTINGS = os.path.join(os.path.dirname(HERE), 'deckgen', 'printings.json')

STAGE = {'Basic': 0, 'Stage1': 1, 'Stage2': 2}


def _parse_damage(atk):
    """Return (base_damage:int, scaling:str|None). Base is the printed number;
    scaling flags '×'/'+'/'-' attacks whose real damage depends on effect text."""
    txt = atk['text']
    m = re.match(r'\s*\[(\d+)\]', txt)          # fixed damage e.g. [240]
    if m:
        return int(m.group(1)), None
    m = re.match(r'\s*(\d+)\s*([×+\-])', txt)    # scaling e.g. 110× / 130+ / 290-
    if m:
        return int(m.group(1)), m.group(2)
    return 0, None                               # no damage (status/utility attack)


class Card:
    __slots__ = ('name', 'set', 'id', 'cat', 'price', 'is_ex', 'energy', 'hp',
                 'stage', 'evolves_from', 'ptype', 'weakness', 'retreat', 'attacks', 'abilities')

    def __init__(self, p):
        self.name = p['name']; self.set = p['set']; self.id = p['id']
        self.cat = p['cat']; self.price = p['price']; self.is_ex = p['ex']
        self.energy = p['energy']                # non-colorless energy this card pays for
        meta = p.get('meta', '')
        m = re.search(r'(\d+) HP', meta); self.hp = int(m.group(1)) if m else 0
        m = re.match(r'\s*(Basic|Stage1|Stage2)', meta); self.stage = STAGE.get(m.group(1), 0) if m else 0
        m = re.search(r'evolves from ([^·]+?)(?: ·|$)', meta); self.evolves_from = m.group(1).strip() if m else None
        # on-card type = token right after HP (e.g. "... 380 HP · Grass · ...")
        m = re.search(r'\d+ HP · ([A-Za-z]+)', meta); self.ptype = m.group(1) if m else None
        m = re.search(r'weak: (\w+)', meta); self.weakness = m.group(1) if m else None
        m = re.search(r'retreat (\d+)', meta); self.retreat = int(m.group(1)) if m else 0
        self.attacks = []
        for a in p['atks']:
            dmg, scaling = _parse_damage(a)
            self.attacks.append({'cost': a['cost'], 'name': a['name'], 'dmg': dmg,
                                 'scaling': scaling, 'text': a['text']})
        self.abilities = p['abilities'] if 'abilities' in p else p.get('abils', [])

    @property
    def key(self):
        return f"{self.set}:{self.id}"

    def is_basic_energy(self):
        return False

    def __repr__(self):
        return f"<{self.name} {self.set}#{self.id} {self.hp}HP S{self.stage}>"


def load_cards():
    """Return (by_key, by_name) indexes of Card objects."""
    data = json.load(open(PRINTINGS))['byname']
    by_key, by_name = {}, {}
    for name, plist in data.items():
        for p in plist:
            c = Card(p)
            by_key[c.key] = c
            by_name.setdefault(name, []).append(c)
    return by_key, by_name


if __name__ == '__main__':
    by_key, by_name = load_cards()
    print(f"loaded {len(by_key)} printings, {len(by_name)} names")
    for probe in ['Palafin', 'Mega Venusaur ex', 'Charmander']:
        print(f"\n{probe}:")
        for c in by_name.get(probe, []):
            atks = '; '.join(f"{a['cost'] or '-'} {a['name']} {a['dmg']}{a['scaling'] or ''}" for a in c.attacks)
            print(f"  {c.set}#{c.id} {c.hp}HP stage{c.stage} evo<-{c.evolves_from} weak:{c.weakness} rt:{c.retreat} ex:{c.is_ex} | {atks}")
