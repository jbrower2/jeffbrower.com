#!/usr/bin/env python3
"""Turn each archetype in deckgen/decks_*.txt into a legal 60-card spec.

Parses the Premium and Supports of every deck, then auto-builds a decklist:
  - 1 copy of the premium (the ≤$1 card), plus its C/U pre-evolution line (4 basic, 3 each middle stage)
  - up to 2 support copies total (the ≤$0.50 cap), plus any support's C/U pre-evo line
  - a cheap C/U basic attacker of the deck's type as backup/bench fodder
  - basic energy of the type(s) the deck pays for, filling to exactly 60
Enforces exactly 60 cards and ≤4 copies of any non-energy card.

These are heuristic lists (no Trainer cards — the pool is Pokémon-only), meant as a
consistent baseline for the simulator, not tuned championship lists.
"""
import os, re, glob
from collections import Counter
from cards import load_cards
BY_KEY, BY_NAME = load_cards()
DECKGEN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'deckgen')
L2T = {'G': 'Grass', 'R': 'Fire', 'W': 'Water', 'L': 'Lightning', 'P': 'Psychic',
       'F': 'Fighting', 'D': 'Darkness', 'M': 'Metal'}
bolds = re.compile(r'\*\*([^*]+)\*\*')


def _norm(b):
    b = re.sub(r'\s*[×x]\s*\d+$', '', b.strip()); b = re.sub(r'\s*\(.*$', '', b)
    return b.replace('’', "'").strip(' *')


def parse_decks():
    """Yield dicts: {section, name, premium, supports:[...]}"""
    out = []
    for path in sorted(glob.glob(os.path.join(DECKGEN, 'decks_*.txt'))):
        sec = os.path.basename(path).replace('decks_', '').replace('.txt', '').split('_')[0]
        name = premium = None; supports = []
        for line in open(path):
            l = line.rstrip('\n')
            if l.startswith('**') and not l.startswith('- '):
                if name and premium:
                    out.append({'section': sec, 'name': name, 'premium': premium, 'supports': supports})
                m = bolds.search(l); name = m.group(1) if m else l[:30]; premium = None; supports = []
            elif l.strip().startswith('- Premium:'):
                m = bolds.findall(l); premium = _norm(m[0]) if m else None
            elif l.strip().startswith('- Supports:'):
                supports = [_norm(b) for b in bolds.findall(l)]
        if name and premium:
            out.append({'section': sec, 'name': name, 'premium': premium, 'supports': supports})
    return out


def _cheapest(name, pred):
    opts = [c for c in BY_NAME.get(name, []) if pred(c) and c.price is not None]
    return min(opts, key=lambda c: c.price) if opts else None


def premium_card(name):
    return _cheapest(name, lambda c: c.is_ex and c.price <= 1.0) or _cheapest(name, lambda c: c.price <= 1.0)


def support_card(name):
    return _cheapest(name, lambda c: c.cat == 'cat-yellow' and c.price <= 0.50)


def cu_printing(name):
    return _cheapest(name, lambda c: c.cat == 'cat-green') or _cheapest(name, lambda c: True)


def preevo_chain(card):
    """C/U pre-evolutions from basic up to (not incl.) card."""
    chain, cur, guard = [], card, 0
    while cur and cur.evolves_from and guard < 4:
        pre = cu_printing(cur.evolves_from)
        if not pre:
            break
        chain.append(pre); cur = pre; guard += 1
    return list(reversed(chain))


def deck_types(premium, supports):
    ts = set(L2T[ch] for ch in premium.energy if ch in L2T)
    for s in supports:
        if s:
            ts |= set(L2T[ch] for ch in s.energy if ch in L2T)
    return sorted(ts) or ['Water']   # colorless-only: any single basic energy pays it


def generic_basic(types):
    """A cheap C/U Basic attacker of one of the deck's types (backup/fodder)."""
    for c in BY_NAME:
        pass
    best = None
    for name, plist in BY_NAME.items():
        for c in plist:
            if c.cat == 'cat-green' and c.stage == 0 and c.hp >= 60 and c.energy and c.energy[0] in 'GRWLPFDM' \
               and L2T.get(c.energy[0]) in types and any(a['dmg'] >= 20 for a in c.attacks) and c.price is not None:
                if best is None or c.price < best.price:
                    best = c
    return best


def build_spec(deck):
    prem = premium_card(deck['premium'])
    if not prem:
        return None
    counts = Counter()   # Card -> count
    def add(card, n):
        if card:
            counts[card] = min(4, counts[card] + n)
    add(prem, 1)
    chain = preevo_chain(prem)
    for i, pre in enumerate(chain):
        add(pre, 4 if i == 0 else 3)
    # supports (<=2 physical copies total)
    sup_cards = [support_card(s) for s in deck['supports']]
    sup_cards = [c for c in sup_cards if c]
    budget = 2
    for i, sc in enumerate(sup_cards[:2]):
        n = 2 if len(sup_cards) == 1 else 1
        n = min(n, budget); budget -= n
        add(sc, n)
        for j, pre in enumerate(preevo_chain(sc)):
            add(pre, 3 if j == 0 else 2)
    types = deck_types(prem, [c for c in sup_cards])
    gb = generic_basic(types)
    add(gb, 3)
    # count pokemon, fill rest with basic energy split across types
    spec = [(n, c) for c, n in counts.items()]
    n_poke = sum(n for n, _ in spec)
    n_energy = max(0, 60 - n_poke)
    for i in range(n_energy):
        spec.append((1, types[i % len(types)]))
    # merge energy tokens of same type
    merged = {}
    out = []
    for n, item in spec:
        if isinstance(item, str):
            merged[item] = merged.get(item, 0) + n
        else:
            out.append((n, item))
    for t, n in merged.items():
        out.append((n, t))
    return out


def validate(spec):
    total = sum(n for n, _ in spec)
    over = [(_c, n) for n, _c in spec if not isinstance(_c, str) and n > 4]
    return total, over


if __name__ == '__main__':
    decks = parse_decks()
    print(f"parsed {len(decks)} decks")
    bad = 0
    for d in decks:
        spec = build_spec(d)
        if spec is None:
            print("  NO PREMIUM:", d['name']); bad += 1; continue
        total, over = validate(spec)
        if total != 60 or over:
            print(f"  BAD {d['name']}: total={total} over4={[(c.name,n) for c,n in over]}"); bad += 1
    print(f"{len(decks)-bad}/{len(decks)} decks build to a legal 60")
    # show one sample
    d = next(x for x in decks if x['premium'] == 'Mega Venusaur ex')
    print(f"\nsample — {d['name']} ({d['premium']}):")
    for n, item in sorted(build_spec(d), key=lambda x: (isinstance(x[1], str), -x[0])):
        print(f"  {n}x {item if isinstance(item, str) else item.name}")
