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


def backup_attackers(types, exclude, k=6):
    """C/U Basic attackers of the deck's types, ranked by damage-per-energy (best first).
    These give a trainerless deck board presence + a plan B when the ace is slow/prized."""
    cands = []
    for name, plist in BY_NAME.items():
        if name in exclude:
            continue
        for c in plist:
            if (c.cat == 'cat-green' and c.stage == 0 and c.price is not None and c.hp >= 60
                    and c.energy and c.energy[0] in 'GRWLPFDM' and L2T.get(c.energy[0]) in types):
                usable = [a for a in c.attacks if len(a['cost']) <= 3 and a['dmg'] > 0]
                if not usable:
                    break
                a = max(usable, key=lambda x: x['dmg'] / max(1, len(x['cost'])))
                cands.append((a['dmg'] / max(1, len(a['cost'])), a['dmg'], c))
                break
    cands.sort(key=lambda x: (-x[0], -x[1]))
    return [c for _, _, c in cands[:k]]


def build_spec(deck):
    """Return (spec, ace_card). spec is a list of (count, Card|energy_type_str), 60 cards,
    <=4 copies of any non-energy card. ace_card is the premium the AI builds toward."""
    ace = premium_card(deck['premium'])
    if not ace:
        return None, None
    counts = Counter()

    def add(card, n):
        if card:
            counts[card] = min(4, counts[card] + n)

    add(ace, 1)                                     # the singleton premium
    for i, pre in enumerate(preevo_chain(ace)):     # its C/U evolution line: 4 basic, 3 each above
        add(pre, 4 if i == 0 else 3)
    sup_cards = [c for c in (support_card(s) for s in deck['supports']) if c]
    budget = 2                                      # <=2 physical support copies total
    for sc in sup_cards[:2]:
        n = min(2 if len(sup_cards) == 1 else 1, budget); budget -= n
        add(sc, n)
        for j, pre in enumerate(preevo_chain(sc)):
            add(pre, 3 if j == 0 else 2)
    types = deck_types(ace, sup_cards)
    # backup attacker lines: enough to make the deck Pokémon-forward (target ~42 Pokémon,
    # leaving ~18 energy) so it stays consistent without Trainer search.
    exclude = {ace.name} | {s.name for s in sup_cards} | {p.name for p in preevo_chain(ace)}
    target_poke = 42
    for b in backup_attackers(types, exclude):
        if sum(counts.values()) >= target_poke:
            break
        add(b, 4)
    n_poke = sum(counts.values())
    n_energy = max(10, 60 - n_poke)                 # never fewer than ~10 energy
    # if we overshot 60 (rare), trim energy handled by fill loop below
    spec = [(n, c) for c, n in counts.items()]
    total_poke = sum(n for n, _ in spec)
    n_energy = 60 - total_poke if total_poke < 50 else 10
    merged = Counter()
    for i in range(max(0, n_energy)):
        merged[types[i % len(types)]] += 1
    out = [(n, c) for n, c in spec]
    out += [(n, t) for t, n in merged.items()]
    return out, ace


def validate(spec):
    total = sum(n for n, _ in spec)
    over = [(_c, n) for n, _c in spec if not isinstance(_c, str) and n > 4]
    return total, over


if __name__ == '__main__':
    decks = parse_decks()
    print(f"parsed {len(decks)} decks")
    bad = 0
    for d in decks:
        spec, ace = build_spec(d)
        if spec is None:
            print("  NO PREMIUM:", d['name']); bad += 1; continue
        total, over = validate(spec)
        if total != 60 or over:
            print(f"  BAD {d['name']}: total={total} over4={[(c.name,n) for c,n in over]}"); bad += 1
    print(f"{len(decks)-bad}/{len(decks)} decks build to a legal 60")
    # show one sample
    d = next(x for x in decks if x['premium'] == 'Mega Venusaur ex')
    spec, ace = build_spec(d)
    print(f"\nsample — {d['name']} (ace: {ace.name}):")
    for n, item in sorted(spec, key=lambda x: (isinstance(x[1], str), -x[0])):
        print(f"  {n}x {item if isinstance(item, str) else item.name}")
