#!/usr/bin/env python3
"""Coevolutionary optimizer for the fully-pauper deck lab (no ace, C/U only).

Score = win% vs the field MINUS a squared-distance composition penalty from the 20 Pokémon /
25 Trainer / 15 energy target (±4 slack, then strict). Candidate Pokémon are whole evolution
CHAINS that don't need energy the deck lacks (colorless chains fit anything). Mutation operators:
  (micro)  ±1 single-card swap among Pokémon / Trainer / energy  (kept from the old system)
  (a)      swap an entire chain in the deck for a compatible chain
  (b)      shift member quantities between two chains
  (c)      add or remove a whole chain, rebalancing energy/trainers to 60
  (d)      the ±1-2 trainer/energy rebalancing that a–c need for space
Everything is legality-checked (exactly 60, ≤4 by name, all C/U). Daemon/resume/archive-revert
infrastructure mirrors optimize.py.
"""
import json, os, random, sys, time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from cards import load_cards
from engine import run_match, Game
from pauper_chains import load_chains, L2T
import special_energy as SE

HERE = os.path.dirname(os.path.abspath(__file__))
BY_KEY, BY_NAME = load_cards()
TRAINERS = json.load(open(os.path.join(os.path.dirname(HERE), 'deckgen', 'trainers.json')))
CHAINS = load_chains()
CHAIN_BY_MEMBER = {('P', key): ch for ch in CHAINS for (nm, key, st) in ch['stages']}
T2L = {v: k for k, v in L2T.items()}
TARGET = {'P': 20, 'T': 25, 'E': 15}
SLACK, PEN_K = 4, 0.5
THRESH = 1.0
# Trainers that only do something if the deck runs a Stage-2 Pokémon: Rare Candy (Basic->Stage 2 skip)
# and Dawn (fetches a Basic+Stage 1+Stage 2). Never add them to a Stage-2-less deck — there they're
# dead cards. The mutation generator filters these out (and proposes removing any that got stranded).
STAGE2_TRAINERS = {'Rare Candy', 'Dawn'}
EPS = 2.5          # accept randomly among moves within this many score points of the best (exploration; breaks pile-on)
# diversity pressure: penalty (in score points) for holding a chain that sits in `freq` of the
# field, rising CUBICALLY — 5% share is a small nudge (~1.25), 10% is large (10), and anything
# near 35% is effectively forbidden (~430). Forces Pokémon lines to spread thin across the field.
# A deck's own no-trade core lines are exempt (see diversity_penalty).
DIV_AT10, DIV_REF = 10.0, 0.10


# ---------------- refs ----------------
def ser(ref):
    return '|'.join(ref)

def deser(s):
    return tuple(s.split('|', 1))

def ref_name(ref):
    if ref[0] == 'E':
        return ref[1] + ' Energy'
    if ref[0] in ('T', 'S'):                          # trainer / special-energy names are literal
        return ref[1]
    return BY_KEY[ref[1]].name

def item_of(ref):
    if ref[0] == 'E':
        return ref[1]
    if ref[0] == 'T':
        return dict(TRAINERS[ref[1]], name=ref[1])
    if ref[0] == 'S':
        return {'special_energy': ref[1]}
    return BY_KEY[ref[1]]

def counts_to_spec(counts):
    return [(n, item_of(r)) for r, n in counts.items() if n > 0]

def as_deck(counts):
    return (counts_to_spec(counts), None)          # no ace


# ---------------- composition + legality ----------------
def kind_counts(counts):
    c = {'P': 0, 'T': 0, 'E': 0}
    for r, n in counts.items():
        k = 'E' if r[0] in ('E', 'S') else r[0]           # special energy counts toward the energy bucket
        c[k] = c.get(k, 0) + n
    return c

def penalty(counts):
    kc = kind_counts(counts)
    pen = 0.0
    for k, tgt in TARGET.items():
        over = max(0, abs(kc.get(k, 0) - tgt) - SLACK)
        pen += over * over
    return PEN_K * pen

def is_legal(counts):
    if sum(counts.values()) != 60:
        return False
    byname = Counter()
    for r, n in counts.items():
        if n < 0:
            return False
        if r[0] == 'E':
            continue
        if r[0] == 'S' and SE.SPECIAL_ENERGY.get(r[1], {}).get('cat') != 'green':
            return False                                      # fully-pauper: only free special energy
        if r[0] == 'P' and BY_KEY[r[1]].cat != 'cat-green':   # pauper: C/U only
            return False
        byname[ref_name(r)] += n                              # special energy counts toward ≤4-by-name
    return all(v <= 4 for v in byname.values())

def canon(counts):
    return tuple(sorted((ser(r), n) for r, n in counts.items() if n > 0))


# ---------------- chains ----------------
def energy_letters(counts):
    return {T2L[r[1]] for r in counts if r[0] == 'E'}

def primary_etype(counts):
    es = [(r[1], n) for r, n in counts.items() if r[0] == 'E']
    return max(es, key=lambda x: x[1])[0] if es else 'Psychic'

def deck_chains(counts):
    """[(chain, {member_ref: count})] for chains present in the deck."""
    groups = defaultdict(dict)
    for r, n in counts.items():
        if r[0] == 'P' and r in CHAIN_BY_MEMBER:
            ch = CHAIN_BY_MEMBER[r]
            groups[ch['id']][r] = n
    return [(next(c for c in CHAINS if c['id'] == cid), mem) for cid, mem in groups.items()]

def chain_line(ch, base=(3, 2, 1)):
    return [(('P', key), n) for (nm, key, st), n in zip(ch['stages'], base[:ch['length']])]

def compatible_chains(counts):
    letters = energy_letters(counts)
    return [ch for ch in CHAINS if set(ch['energy']) <= letters]


def field_chain_freq(decks):
    """Fraction of decks in the current population that contain each chain (keyed by root id)."""
    freq = defaultdict(int)
    n = max(1, len(decks))
    for d in decks.values():
        for cid in {ch['id'] for ch, _ in deck_chains(d['counts'])}:
            freq[cid] += 1
    return {cid: c / n for cid, c in freq.items()}


def diversity_penalty(counts, chain_freq, notrade=frozenset()):
    """Squared-excess penalty for holding chains that already saturate the field (0 if under slack).
    A deck's own no-trade core lines are exempt — the penalty only pushes off incidental shared filler."""
    if not chain_freq:
        return 0.0
    pen = 0.0
    for ch, _ in deck_chains(counts):
        if any(('P', key) in notrade for (nm, key, st) in ch['stages']):
            continue
        pen += (chain_freq.get(ch['id'], 0.0) / DIV_REF) ** 3
    return DIV_AT10 * pen


def rebalance(counts, etype):
    """Adjust energy (then trainers) to bring the deck back to exactly 60 (operator d)."""
    diff = 60 - sum(counts.values())
    if diff > 0:
        counts[('E', etype)] += diff
    elif diff < 0:
        rem = -diff
        for pred in (lambda r: r[0] == 'E', lambda r: r[0] == 'T'):
            for r in sorted([r for r in counts if pred(r)], key=lambda r: -counts[r]):
                take = min(counts[r], rem); counts[r] -= take; rem -= take
                if counts[r] <= 0:
                    del counts[r]
                if rem == 0:
                    break
            if rem == 0:
                break
    if counts.get(('E', etype), 0) <= 0:
        counts.pop(('E', etype), None)
    return counts


# ---------------- mutation generator ----------------
def mutations(counts, cap=200, rng=random, notrade=frozenset()):
    etype = primary_etype(counts)
    nt_active = [r for r in notrade if counts.get(r, 0) >= 1]   # core refs that must stay present
    compat = compatible_chains(counts)
    present = deck_chains(counts)
    present_ids = {ch['id'] for ch, _ in present}
    add_chains = [ch for ch in compat if ch['id'] not in present_ids]
    trainers = [r for r in counts if r[0] == 'T']
    energies = [r for r in counts if r[0] == 'E']
    pokes = [r for r in counts if r[0] == 'P']
    has_s2 = any(BY_KEY[r[1]].stage == 2 for r in pokes)          # deck runs a Stage-2 line?
    trainer_adds = [('T', n) for n in TRAINERS if has_s2 or n not in STAGE2_TRAINERS]
    muts, seen = [], set()

    def emit(m, desc):
        if (sum(v for v in m.values() if v > 0) and is_legal(m)
                and all(m.get(r, 0) >= 1 for r in nt_active)):     # never drop a no-trade core card
            k = canon(m)
            if k not in seen and k != canon(counts):
                seen.add(k); muts.append((desc, m))

    # ---- micro: single-card swaps among free cards (kept from old system) ----
    def micro(rem, add):
        if rem is None or add is None or rem == add or counts.get(rem, 0) < 1:
            return
        m = Counter(counts); m[rem] -= 1; m[add] += 1
        if m[rem] == 0:
            del m[rem]
        emit(m, f'-1 {ref_name(rem)} +1 {ref_name(add)}')
    for a in trainer_adds:                                    # swap energy/weak-poke -> a trainer
        micro(energies[0] if energies else None, a)
    for a in [('E', etype)]:                                  # add energy by cutting a trainer
        for t in trainers[:4]:
            micro(t, a)
    if not has_s2:                                            # strand-cleanup: dump dead Rare Candy / Dawn
        for t in trainers:
            if t[1] in STAGE2_TRAINERS:
                micro(t, ('E', etype))                        # -> primary basic energy (always at least as useful)
    for ch in add_chains[:20]:                                # +1 of a compatible chain's basic, -1 energy
        micro(energies[0] if energies else None, chain_line(ch)[0][0])
    for a in [('S', n) for n in SE.FREE_SPECIAL if n != "Team Rocket's Energy"]:
        micro(energies[0] if energies else None, a)           # basic energy -> a free special energy
    if any("Team Rocket's" in BY_KEY[r[1]].name for r in pokes):
        micro(energies[0] if energies else None, ('S', "Team Rocket's Energy"))   # TR-only: where it works
    for s in [r for r in counts if r[0] == 'S']:              # a special energy -> back to basic
        micro(s, ('E', etype))

    # ---- (a) swap a whole chain for a compatible chain ----
    for ch_in, members in present:
        if any(r in notrade for r in members):                # keep the core line — don't swap it out
            continue
        for ch_new in add_chains:
            m = Counter(counts)
            for r in list(members):
                del m[r]
            for ref, n in chain_line(ch_new, (4, 3, 2)):
                m[ref] += min(4, n)
            rebalance(m, etype)
            emit(m, f'swap chain {ch_in["top"]} -> {ch_new["top"]}')

    # ---- (b) shift member quantities between two chains ----
    for ch_x, mem_x in present:
        for ch_y, mem_y in present:
            if ch_x['id'] == ch_y['id']:
                continue
            rx = max(mem_x, key=lambda r: mem_x[r])           # bump the most-present member of X
            ry = min(mem_y, key=lambda r: mem_y[r])           # trim the least-present member of Y
            if counts.get(rx, 0) >= 4 or counts.get(ry, 0) < 1:
                continue
            m = Counter(counts); m[rx] += 1; m[ry] -= 1
            if m[ry] == 0:
                del m[ry]
            emit(m, f'+1 {ref_name(rx)} / -1 {ref_name(ry)}')

    # ---- (c) add a whole chain (rebalance), or remove a present chain (rebalance) ----
    for ch_new in add_chains:
        m = Counter(counts)
        for ref, n in chain_line(ch_new, (3, 2, 1)):
            m[ref] += min(4, n)
        rebalance(m, etype)
        emit(m, f'add chain {ch_new["top"]}')
    for ch_in, members in present:
        if len(present) <= 2 or any(r in notrade for r in members):
            continue                                          # keep at least a couple lines; never the core
        m = Counter(counts)
        for r in list(members):
            del m[r]
        rebalance(m, etype)
        emit(m, f'remove chain {ch_in["top"]}')

    rng.shuffle(muts)
    return muts[:cap]


# ---------------- parallel gauntlet ----------------
def _rebuild(cards):
    return [(n, item_of(deser(r))) for r, n in cards]

def _eval_pairing(task):
    a_cards, b_cards, games, seed = task
    res = run_match((_rebuild(a_cards), None), (_rebuild(b_cards), None), games=games, base_seed=seed)
    return res[0], res[1], res[2]

def build_gauntlet(decks, exclude):
    return [[(ser(r), c) for r, c in d['counts'].items()] for n, d in decks.items() if n != exclude]

def _run_map(fn, tasks, ex):
    return map(fn, tasks) if ex is None else ex.map(fn, tasks, chunksize=max(1, len(tasks) // 32))

def winrate(counts, gaunt, games, ex, seed0):
    a = [(ser(r), n) for r, n in counts.items()]
    tasks = [(a, bc, games, seed0 + i) for i, bc in enumerate(gaunt)]
    wa = wb = 0
    for x, y, _ in _run_map(_eval_pairing, tasks, ex):
        wa += x; wb += y
    return 100.0 * wa / max(1, wa + wb)

def score(counts, gaunt, games, ex, seed0, chain_freq=None, notrade=frozenset()):
    return (winrate(counts, gaunt, games, ex, seed0) - penalty(counts)
            - diversity_penalty(counts, chain_freq, notrade))


# ---------------- persistence ----------------
def save(decks, path='pauper_decklists.json'):
    out = {n: {'cards': {ser(r): c for r, c in d['counts'].items() if c > 0},
               'notrade': [ser(r) for r in d.get('notrade', ())]} for n, d in decks.items()}
    json.dump(out, open(os.path.join(HERE, path), 'w'), indent=0)

def save_archive(decks):
    out = {n: [{ser(r): c for r, c in v.items() if c > 0} for v in d.get('archive', [])] for n, d in decks.items()}
    json.dump(out, open(os.path.join(HERE, 'pauper_archive.json'), 'w'), indent=0)

def append_jsonl(path, rec):
    with open(path, 'a') as f:
        f.write(json.dumps(rec) + '\n')

def load_state():
    raw = json.load(open(os.path.join(HERE, 'pauper_decklists.json')))
    apath = os.path.join(HERE, 'pauper_archive.json')
    archive = json.load(open(apath)) if os.path.exists(apath) else {}
    decks = {}
    for n, e in raw.items():
        counts = Counter({deser(k): v for k, v in e['cards'].items()})
        arc = [Counter({deser(k): v for k, v in v0.items()}) for v0 in archive.get(n, [])]
        decks[n] = {'counts': counts, 'archive': arc or [Counter(counts)],
                    'notrade': set(deser(k) for k in e.get('notrade', []))}
    return decks


def leaderboard(decks, games, ex, rnd, seed0=1):
    board = []
    for n, d in decks.items():
        wr = winrate(d['counts'], build_gauntlet(decks, n), games, ex, seed0)
        kc = kind_counts(d['counts'])
        board.append([round(wr - penalty(d['counts']), 2), round(wr, 2), n,
                      f"{kc['P']}/{kc['T']}/{kc['E']}"])
    board.sort(reverse=True)
    json.dump({'round': rnd, 'board': board}, open(os.path.join(HERE, 'pauper_leaderboard.json'), 'w'), indent=1)
    return board


# ---------------- run ----------------
def run(games=5, rounds=10, cap=200, workers=9, seed0=1):
    decks = load_state()
    names = list(decks)
    ex = ProcessPoolExecutor(workers) if workers > 1 else None
    hist = os.path.join(HERE, 'pauper_history.jsonl')
    donef = os.path.join(HERE, 'PAUPER_DONE')
    done = set()
    if os.path.exists(hist):
        for l in open(hist):
            try:
                r = json.loads(l); done.add((r['round'], r['deck']))
            except Exception:
                pass
    t0 = time.time()
    print(f"pauper-optimizing {len(names)} decks | {games} games/pairing | cap={cap} | {rounds} rounds | "
          f"target {TARGET['P']}/{TARGET['T']}/{TARGET['E']} penalty(slack {SLACK}, k {PEN_K}) | "
          f"diversity(cubic: 5%~{DIV_AT10*0.125:.2f}pt 10%={DIV_AT10:.0f}pt 20%={DIV_AT10*8:.0f}pt)", flush=True)
    try:
        for rnd in range(1, rounds + 1):
            accepts = 0
            for i, name in enumerate(names, 1):
                if (rnd, name) in done:
                    continue
                d = decks[name]
                chain_freq = field_chain_freq(decks)      # LIVE field frequency (recomputed per deck) — no lag, no pile-on oscillation
                gaunt = build_gauntlet(decks, name)
                base = score(d['counts'], gaunt, games, ex, seed0, chain_freq, d['notrade'])
                cands = list(mutations(d['counts'], cap, notrade=d['notrade']))
                for vi, av in enumerate(d.get('archive', [])):
                    if canon(av) != canon(d['counts']):
                        cands.append((f'revert->v{vi}', Counter(av)))
                scored, seen = [], {canon(d['counts'])}
                for desc, mc in cands:
                    k = canon(mc)
                    if k in seen:
                        continue
                    seen.add(k)
                    scored.append((desc, score(mc, gaunt, games, ex, seed0, chain_freq, d['notrade']), mc))
                # accept: pick RANDOMLY among moves within EPS of the best viable one — decks spread
                # instead of all piling onto the single highest-scoring line
                viable = [c for c in scored if c[1] > base + THRESH]
                if viable:
                    cutoff = max(c[1] for c in viable) - EPS
                    pick = random.choice([c for c in viable if c[1] >= cutoff]); accepted = True
                else:
                    pick = max(scored, key=lambda c: c[1]) if scored else None; accepted = False
                append_jsonl(hist, {'round': rnd, 'deck': name, 'base': round(base, 2),
                                    'best': round(pick[1], 2) if pick else None,
                                    'delta': round(pick[1] - base, 2) if pick else None,
                                    'mutation': pick[0] if pick else None,
                                    'divpen': round(diversity_penalty(d['counts'], chain_freq, d['notrade']), 2),
                                    'revert': bool(accepted and pick[0].startswith('revert')),
                                    'accepted': accepted, 'ts': time.time()})
                if accepted:
                    d['counts'] = pick[2]; accepts += 1
                    if canon(pick[2]) not in {canon(a) for a in d['archive']}:
                        d['archive'].append(Counter(pick[2])); d['archive'] = d['archive'][-25:]
                    save(decks); save_archive(decks)
                kc = kind_counts(d['counts'])
                tag = 'ACCEPT' if accepted else '  ----'
                print(f"[r{rnd} {i:3}/{len(names)} {time.time()-t0:6.0f}s] {tag} {name[:26]:26} "
                      f"{base:5.1f} -> {(pick[1] if pick else base):5.1f}  ({kc['P']}/{kc['T']}/{kc['E']})  "
                      f"{pick[0][:34] if accepted else ''}", flush=True)
            b = leaderboard(decks, games, ex, rnd, seed0)
            distinct = len({ch['top'] for d in decks.values() for ch, _ in deck_chains(d['counts'])})
            print(f"=== round {rnd} done: {accepts} changes | top {b[0][2]} {b[0][0]} | "
                  f"median {b[len(b)//2][0]} | {distinct} distinct chains ===", flush=True)
        open(donef, 'w').write(str(time.time()))
        print("=== ALL ROUNDS COMPLETE ===", flush=True)
    finally:
        if ex:
            ex.shutdown()


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--games', type=int, default=5)
    ap.add_argument('--rounds', type=int, default=10)
    ap.add_argument('--cap', type=int, default=200)
    ap.add_argument('--workers', type=int, default=9)
    a = ap.parse_args()
    run(games=a.games, rounds=a.rounds, cap=a.cap, workers=a.workers)
