#!/usr/bin/env python3
"""Build a catalog of ~100 fully-pauper (Common/Uncommon only) decks around interesting chains.

Each deck = a small set of evolution chains (the core attacker/engine + compatible supports) +
a generic C/U Trainer consistency shell + basic energy, sized toward the 20 Pokémon / 25 Trainer /
15 energy target. No ace, no ex, no special/rare cards. Colorless-attacking chains (rule 4) can be
paired into any type. Output: pauper_decklists.json = {name: {cards: {refstr: count}}}.
"""
import json, os, re
from collections import Counter, defaultdict
from cards import load_cards
from pauper_chains import load_chains, L2T

HERE = os.path.dirname(os.path.abspath(__file__))
BY_KEY, BY_NAME = load_cards()
TRAINERS = json.load(open(os.path.join(os.path.dirname(HERE), 'deckgen', 'trainers.json')))
TYPES = ['Grass', 'Fire', 'Water', 'Lightning', 'Psychic', 'Fighting', 'Darkness', 'Metal']

# a generic C/U consistency shell (name, count) — all verified present in trainers.json (~23 cards)
SHELL = [("Professor's Research", 2), ("Cheren", 2), ("Boss's Orders", 2), ("Ultra Ball", 2),
         ("Poké Ball", 2), ("Buddy-Buddy Poffin", 2), ("Earthen Vessel", 2), ("Switch", 2),
         ("Pokégear 3.0", 2), ("Night Stretcher", 1), ("Judge", 1), ("Professor Turo's Scenario", 1),
         ("Carmine", 1), ("Ciphermaniac's Codebreaking", 1)]

# Targeted MULTI-energy decks around the pool's 2-type Dragon chains (they pay with two other-typed
# energies since no basic Dragon energy exists). (deck name, core top, two-letter energy combo);
# same-combo Dragons are auto-added as supports, the rest padded on-theme.
MULTI_GROUPS = [
    ("Eon Dragons", "Latios", ['P', 'W']),        # + Sliggoo — Latios 130HP basic, 130 for WPC
    ("Ember Dragons", "Druddigon", ['R', 'W']),   # + Shelgon, Tatsugiri — three R/W dragons
    ("Frost Dragons", "Altaria", ['M', 'W']),     # + Kyurem — Altaria 100 for WM, Kyurem spread
    ("Storm Dragons", "Dragonair", ['L', 'W']),   # Dragonair self-accelerates (accel/engine ability)
    ("Iron Dragons", "Fraxure", ['F', 'M']),      # Fraxure 80 for FM, wall ability
    ("Dusk Dragons", "Noivern", ['D', 'P']),      # Noivern 70 for PD + colorless fallback
    ("Phantom Dragons", "Drakloak", ['P', 'R']),  # Drakloak 70 for RP, ability
]


def ser(ref):
    return '|'.join(ref)


def _shell(has_stage2):
    out = Counter()
    for nm, n in SHELL:
        if nm in TRAINERS:
            out[('T', nm)] += n
    if has_stage2 and 'Rare Candy' in TRAINERS:
        out[('T', 'Rare Candy')] += 3
    return out


def _line(chain, counts_by_stage):
    """Emit (ref, count) for a chain given a per-stage count list (basic, stage1, stage2)."""
    out = []
    for (name, key, stage), n in zip(chain['stages'], counts_by_stage):
        if n > 0:
            out.append((('P', key), n))
    return out


def _npoke(counts):
    return sum(v for r, v in counts.items() if r[0] == 'P')


def _chain_refs(ch):
    """Pokémon refs for every member of a chain (used as a deck's no-trade / core-identity list)."""
    return [('P', key) for (nm, key, st) in ch['stages']]


def build_deck(name, core, supports, energy_type, pad_pool, pad_usage=None):
    """core/supports are chain dicts; pad_pool is compatible attacker chains used to reach ~20 Pokémon.
    pad_usage (a shared Counter) round-robins padding across decks so no fill line lands in nearly all."""
    counts = Counter()
    has_s2 = core['length'] == 3
    for ref, n in _line(core, [4, 3, 2][:core['length']]):
        counts[ref] += n
    for sup in supports:
        for ref, n in _line(sup, [3, 2, 1][:sup['length']]):
            counts[ref] += n
        has_s2 = has_s2 or sup['length'] == 3
    used = {core['id']} | {s['id'] for s in supports}
    # pad Pokémon toward ~20 with the least-globally-used compatible lines (spread, not the same top pick)
    pool = pad_pool if pad_usage is None else sorted(pad_pool, key=lambda ch: (pad_usage.get(ch['id'], 0), -_interest(ch)))
    for pad in pool:
        if _npoke(counts) >= 20:
            break
        if pad['id'] in used:
            continue
        used.add(pad['id'])
        if pad_usage is not None:
            pad_usage[pad['id']] += 1
        for ref, n in _line(pad, [3, 2, 1][:pad['length']]):
            counts[ref] += n
    for r in list(counts):                                   # ≤4 of any card
        counts[r] = min(4, counts[r])
    counts += _shell(has_s2)                                 # ~23–26 trainers
    n_poke = _npoke(counts)
    n_tr = sum(v for r, v in counts.items() if r[0] == 'T')
    counts[('E', energy_type)] = max(8, 60 - n_poke - n_tr)  # ~15 energy
    total = sum(counts.values())                             # exact 60 via energy
    counts[('E', energy_type)] += (60 - total)
    if counts[('E', energy_type)] <= 0:
        del counts[('E', energy_type)]
    return counts


def _multi_compatible(chains, combo):
    """Attacker chains legal in a two-type deck (energy ⊆ combo), on-theme (uses a combo letter) first."""
    cs = set(combo)
    pool = [ch for ch in chains if set(ch['energy']) <= cs and 'attacker' in ch['tags']]
    pool.sort(key=lambda ch: (0 if set(ch['energy']) & cs else 1, -_interest(ch)))
    return pool


def build_multi_deck(name, core, supports, combo, pad_pool, pad_usage=None):
    """Two-type deck: core Dragon + same-combo Dragon supports, padded on-theme, energy split across both."""
    counts = Counter()
    has_s2 = core['length'] == 3
    for ref, n in _line(core, [4, 3, 2][:core['length']]):
        counts[ref] += n
    for sup in supports:
        for ref, n in _line(sup, [3, 2, 1][:sup['length']]):
            counts[ref] += n
        has_s2 = has_s2 or sup['length'] == 3
    used = {core['id']} | {s['id'] for s in supports}
    pool = pad_pool if pad_usage is None else sorted(pad_pool, key=lambda ch: (pad_usage.get(ch['id'], 0), -_interest(ch)))
    for pad in pool:                                        # pad toward ~20 Pokémon, least-used-globally first
        if _npoke(counts) >= 20:
            break
        if pad['id'] in used:
            continue
        used.add(pad['id'])
        if pad_usage is not None:
            pad_usage[pad['id']] += 1
        for ref, n in _line(pad, [3, 2, 1][:pad['length']]):
            counts[ref] += n
    for r in list(counts):
        counts[r] = min(4, counts[r])
    counts += _shell(has_s2)
    n_poke = _npoke(counts)
    n_tr = sum(v for r, v in counts.items() if r[0] == 'T')
    n_en = max(8, 60 - n_poke - n_tr)
    t1, t2 = L2T[combo[0]], L2T[combo[1]]                    # split energy across the two types
    counts[('E', t1)] += (n_en + 1) // 2
    counts[('E', t2)] += n_en // 2
    counts[('E', t1)] += (60 - sum(counts.values()))        # exact-60 fixup on the primary type
    if counts[('E', t1)] <= 0:
        counts.pop(('E', t1), None)
    return counts


def _interest(ch):
    """Rank a chain as a deck CORE: attackers by damage×hp, engines/buffs get a boost."""
    s = ch['dps'] * (1 + ch['hp'] / 200)
    if 'accel' in ch['tags'] or 'engine' in ch['tags']:
        s += 30
    if 'buff' in ch['tags']:
        s += 25
    if 'spread' in ch['tags'] or 'status' in ch['tags']:
        s += 15
    return s


def compatible(ch, tletter):
    """Chain fits a deck of energy-letter tletter if its attacks need only that letter (or colorless)."""
    return set(ch['energy']) <= {tletter}


def _pick_least_used(cands, pad_usage, exclude_ids):
    """Choose the least-globally-used candidate (tie-break by interest) so support slots spread too."""
    opts = [c for c in cands if c['id'] not in exclude_ids]
    return min(opts, key=lambda ch: (pad_usage.get(ch['id'], 0), -_interest(ch))) if opts else None


def generate_catalog():
    chains = load_chains()
    for c in chains:
        c['eletter'] = c['energy'][0] if len(c['energy']) == 1 else ('' if not c['energy'] else None)
    catalog, notrade_map = {}, {}
    pad_usage = Counter()                                    # global fill-usage so padding round-robins across decks
    used_cores = set()
    for T in TYPES:
        tl = [k for k, v in L2T.items() if v == T][0]
        # cores that fit this type: mono-T attackers/engines (not pure colorless — those get their own pass)
        cores = sorted([c for c in chains if c['energy'] == [tl] and _interest(c) > 20],
                       key=_interest, reverse=True)
        # support pool: compatible engines + backup attackers (mono-T or colorless)
        engines = [c for c in chains if compatible(c, tl) and {'accel', 'engine', 'buff'} & set(c['tags'])]
        attackers = sorted([c for c in chains if compatible(c, tl) and 'attacker' in c['tags']],
                           key=_interest, reverse=True)
        made = 0
        for core in cores:
            if made >= 12 or core['top'] in used_cores:
                continue
            used_cores.add(core['top'])
            # pick a distinct engine support + backup attacker — least-used-globally so they spread
            eng = _pick_least_used(engines, pad_usage, {core['id']})
            bk = _pick_least_used(attackers, pad_usage, {core['id']} | ({eng['id']} if eng else set()))
            sups = [s for s in (eng, bk) if s]
            for s in sups:
                pad_usage[s['id']] += 1
            nm = f"{core['top']}"
            if nm in catalog:
                nm = f"{core['top']} ({T})"
            catalog[nm] = build_deck(nm, core, sups, T, attackers, pad_usage)
            pad_usage[core['id']] += 1                    # count the core so it isn't also padded everywhere
            notrade_map[nm] = _chain_refs(core)          # the namesake core line = the deck's identity
            made += 1
    # colorless-core decks: a strong colorless attacker + engine, splashed into a few types
    col_attackers = sorted([c for c in chains if c['energy'] == [] and 'attacker' in c['tags']],
                           key=_interest, reverse=True)
    for core in col_attackers[:14]:
        if core['top'] in used_cores:
            continue
        used_cores.add(core['top'])
        col_engines = [c for c in chains if c['energy'] == [] and {'engine', 'accel'} & set(c['tags'])]
        eng = _pick_least_used(col_engines, pad_usage, {core['id']})
        bk = _pick_least_used(col_attackers, pad_usage, {core['id']} | ({eng['id']} if eng else set()))
        sups = [s for s in (eng, bk) if s]
        for s in sups:
            pad_usage[s['id']] += 1
        nm = f"{core['top']} (Colorless)"
        catalog[nm] = build_deck(nm, core, sups, 'Psychic', col_attackers, pad_usage)
        pad_usage[core['id']] += 1
        notrade_map[nm] = _chain_refs(core)
    # multi-energy Dragon decks: cores needing two energy types (never selected by the mono passes)
    for dname, core_top, combo in MULTI_GROUPS:
        combo = sorted(combo)
        core = next((ch for ch in chains if ch['top'] == core_top and ch['energy'] == combo), None)
        if core is None:
            continue
        used_cores.add(core_top)
        sups = [ch for ch in chains if ch['energy'] == combo and ch['top'] != core_top][:2]
        catalog[dname] = build_multi_deck(dname, core, sups, combo, _multi_compatible(chains, combo), pad_usage)
        for _seed in (core, *sups):
            pad_usage[_seed['id']] += 1
        notrade_map[dname] = _chain_refs(core) + [r for s in sups for r in _chain_refs(s)]  # all the dragons
    # seed Team Rocket's Energy (2 wild each, TR-only) into the Team Rocket decks, keeping some basic
    for nm, counts in catalog.items():
        if "Team Rocket" in nm:
            ebasic = [r for r in counts if r[0] == 'E']
            if ebasic and counts[ebasic[0]] > 6:
                swap = min(4, counts[ebasic[0]] - 6)          # special energy is non-basic: ≤4 copies
                counts[ebasic[0]] -= swap
                counts[('S', "Team Rocket's Energy")] = swap
    return catalog, notrade_map


if __name__ == '__main__':
    cat, notrade = generate_catalog()
    out = {nm: {'cards': {ser(r): c for r, c in counts.items() if c > 0},
                'notrade': [ser(r) for r in notrade.get(nm, [])]} for nm, counts in cat.items()}
    json.dump(out, open(os.path.join(HERE, 'pauper_decklists.json'), 'w'), indent=0)
    # stats
    ratios = []
    for nm, e in out.items():
        p = sum(v for k, v in e['cards'].items() if k[0] == 'P')
        t = sum(v for k, v in e['cards'].items() if k[0] == 'T')
        en = sum(v for k, v in e['cards'].items() if k[0] == 'E')
        ratios.append((p, t, en, sum(e['cards'].values())))
    import statistics
    print(f"{len(out)} pauper decks -> pauper_decklists.json")
    print(f"avg composition: {statistics.mean(r[0] for r in ratios):.1f} Pokémon / "
          f"{statistics.mean(r[1] for r in ratios):.1f} Trainer / {statistics.mean(r[2] for r in ratios):.1f} energy "
          f"(target 20/25/15)")
    print(f"all exactly 60 cards: {all(r[3] == 60 for r in ratios)}")
    print("sample decks:", list(out)[:20])
