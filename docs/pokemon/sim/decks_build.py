#!/usr/bin/env python3
"""Turn each archetype in deckgen/decks_*.txt into a legal 60-card spec.

Parses the Premium and Supports of every deck, then auto-builds a decklist:
  - 1 copy of the premium (the ≤$1 card), plus its C/U pre-evolution line (4 basic, 3 each middle stage)
  - up to 2 support copies total (the ≤$0.50 cap), plus any support's C/U pre-evo line
  - C/U backup attacker lines of the deck's type (board presence / plan B)
  - a Common/Uncommon Trainer shell (trainer_package): draw, ball search, Boss's Orders
    gust, Switch, energy search, recovery, and Rare Candy for Stage-2 aces
  - basic energy of the type(s) the deck pays for, filling to exactly 60
Enforces exactly 60 cards and ≤4 copies of any non-basic-energy card.

Trainers come from deckgen/trainers.json (Common/Uncommon only — legal & unlimited).
Items are dicts; the engine expands them to ('T', dict) tokens. NEXT: per-deck Trainer
tech (named/type-specific/heal cards) instead of one generic shell.
"""
import os, re, glob, json
from collections import Counter
from cards import load_cards
BY_KEY, BY_NAME = load_cards()
DECKGEN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'deckgen')
TRAINERS = json.load(open(os.path.join(DECKGEN, 'trainers.json')))   # name -> {trainerType, rarity, effect}


FAMILIES = ["Team Rocket's", "Ethan's", "Arven's", "Hop's", "Marnie's", "Iono's",
            "Cynthia's", "Erika's", "Steven's", "Larry's", "Misty's", "Lillie's"]
# type -> best C/U energy-consistency card for a high-cost mono deck
TYPE_ENERGY = {'Grass': 'Bug Catching Set', 'Fire': 'Firebreather', 'Fighting': 'Fighting Gong',
               'Darkness': "Janine's Secret Art", 'Metal': 'Philippe', 'Water': 'Earthen Vessel',
               'Lightning': 'Earthen Vessel', 'Psychic': 'Earthen Vessel'}
# named family -> its signature engine (all Common/Uncommon, all implemented generically)
FAMILY_TECH = {"Ethan's": [("Ethan's Adventure", 3)], "Arven's": [("Arven's Sandwich", 2)],
               "Hop's": [("Hop's Bag", 2)], "Marnie's": [("Janine's Secret Art", 2)],
               "Team Rocket's": [("Team Rocket's Great Ball", 2), ("Team Rocket's Transceiver", 1)]}


def _family_of(names):
    for fam in FAMILIES:
        if any(n.startswith(fam + ' ') for n in names):
            return fam
    return None


def trainer_package(deck, ace, sup_cards):
    """Deep-research Trainer selector: a universal consistency core + tech chosen from the
    deck's structure (Stage-2 → Rare Candy + Dawn; Mega → Mega Signal; multi-color → Crispin;
    high-cost mono → type energy card; tanky → heal; named family → its engine)."""
    pkg = {}
    def addT(name, n):
        if TRAINERS.get(name):
            pkg[name] = min(4, pkg.get(name, 0) + n)

    # --- universal consistency core ---
    addT("Professor's Research", 2)   # draw 7
    addT("Cheren", 2)                 # draw 3
    addT("Boss's Orders", 2)          # gust for KOs
    addT("Buddy-Buddy Poffin", 2)     # small basics to bench
    addT("Poké Ball", 1)              # find a Pokémon
    addT("Switch", 1)                 # free pivot
    addT("Night Stretcher", 1)        # recover the ace / energy from discard
    addT("Earthen Vessel", 1)         # energy to hand

    types = deck_types(ace, sup_cards); prim = types[0] if types else 'Water'
    stage2 = ace.stage == 2 or any(s.stage == 2 for s in sup_cards)
    mega = ace.name.startswith('Mega ')
    multi = len(types) >= 2
    maxcost = max((len(a['cost']) for a in ace.attacks), default=2)

    # --- ace finders ---
    if mega:
        addT("Mega Signal", 2)        # tutor the singleton Mega-ex
    elif ace.is_ex:
        addT("Cyrano", 1)             # tutor Pokémon ex
    if stage2:
        addT("Rare Candy", 4)         # Basic -> Stage 2 skip (the key evolution enabler)
        addT("Dawn", 1)               # fetch a Basic + Stage 1 + Stage 2 at once

    # --- energy consistency ---
    if multi:
        addT("Crispin", 2)            # two basic energy of DIFFERENT types (fixes 2-color)
    elif maxcost >= 4:
        addT(TYPE_ENERGY.get(prim, 'Energy Search'), 2)

    # --- tanky decks want healing ---
    if ace.hp >= 310:
        addT("Pokémon Center Lady", 2)

    # --- named family engine ---
    for nm, n in FAMILY_TECH.get(_family_of([deck['premium']] + deck.get('supports', [])), []):
        addT(nm, n)

    return [(n, dict(TRAINERS[nm], name=nm)) for nm, n in pkg.items()]
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
    trainers = trainer_package(deck, ace, sup_cards)
    n_trainer = sum(n for n, _ in trainers)
    # backup attacker lines until Pokémon + Trainers ≈ 46 (leaving ~14 basic energy)
    exclude = {ace.name} | {s.name for s in sup_cards} | {p.name for p in preevo_chain(ace)}
    for b in backup_attackers(types, exclude, k=4):
        if sum(counts.values()) + n_trainer >= 46:
            break
        add(b, 4)
    spec = [(n, c) for c, n in counts.items()] + trainers
    n_energy = max(0, 60 - sum(n for n, _ in spec))
    merged = Counter()
    for i in range(n_energy):
        merged[types[i % len(types)]] += 1
    out = spec + [(n, t) for t, n in merged.items()]
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
    def label(it):
        if isinstance(it, str): return it + ' Energy'
        if isinstance(it, dict): return it['name'] + ' [T]'
        return it.name
    for n, item in sorted(spec, key=lambda x: (0 if not isinstance(x[1], (str, dict)) else 1, isinstance(x[1], str), -x[0])):
        print(f"  {n}x {label(item)}")
