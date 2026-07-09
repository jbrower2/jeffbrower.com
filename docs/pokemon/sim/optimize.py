#!/usr/bin/env python3
"""Coevolutionary hill-climb optimizer for the decks.

Materializes each archetype into an explicit 60-card list, then repeatedly proposes
small legal on-theme mutations and keeps the ones that raise win% vs a gauntlet.
Persists optimized lists + a full change history for manual review.

Card refs (serializable): ('P', 'set:id') | ('E', 'Type') | ('T', 'Name').
A decklist is a Counter{ref: count} plus an ace ref-key. The premium (≤$1) and the
two ≤$0.50 support cards are the deck's identity and are held fixed; mutations only
touch the "free" pool (Common/Uncommon Pokémon, C/U Trainers, basic energy).
"""
import json, os, random, sys, time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from cards import load_cards
from decks_build import (parse_decks, build_spec, TRAINERS, backup_attackers,
                         deck_types, preevo_chain, support_card, trainer_package, _family_of, L2T)
from engine import run_match, Game
import special_energy as SE

HERE = os.path.dirname(os.path.abspath(__file__))
BY_KEY, BY_NAME = load_cards()
BASIC_ENERGY_TYPES = ['Grass', 'Fire', 'Water', 'Lightning', 'Psychic', 'Fighting', 'Darkness', 'Metal']


# ---------------- refs <-> engine items ----------------
def ref_of(item):
    if isinstance(item, str):
        return ('E', item)
    if isinstance(item, dict):
        if 'special_energy' in item:
            return ('S', item['special_energy'])
        return ('T', item['name'])
    return ('P', item.key)

def item_of(ref):
    if ref[0] == 'E':
        return ref[1]
    if ref[0] == 'T':
        return dict(TRAINERS[ref[1]], name=ref[1])
    if ref[0] == 'S':
        return {'special_energy': ref[1]}
    return BY_KEY[ref[1]]

def ref_name(ref):
    if ref[0] == 'E':
        return ref[1] + ' Energy'
    if ref[0] in ('T', 'S'):                         # trainer / special-energy names are literal
        return ref[1]
    return BY_KEY[ref[1]].name

def ref_cat_price(ref):
    """(cat, price): 'green'/'yellow'/'red'. Basic energy & C/U Trainers are free; special
    energy carry their own cat/price so the money-slot rule applies to them too."""
    if ref[0] in ('E', 'T'):
        return ('green', 0.0)                        # basic energy + C/U Trainers: free
    if ref[0] == 'S':
        e = SE.SPECIAL_ENERGY[ref[1]]
        return (e['cat'], e['price'])
    c = BY_KEY[ref[1]]
    return (c.cat.replace('cat-', ''), c.price or 0.0)

def ser(ref):
    return '|'.join(ref)

def deser(s):
    return tuple(s.split('|', 1))


# ---------------- materialize ----------------
def materialize(deck):
    """archetype dict -> (Counter{ref:count}, ace_ref) via decks_build."""
    spec, ace = build_spec(deck)
    counts = Counter()
    for n, item in spec:
        counts[ref_of(item)] += n
    return counts, ('P', ace.key)

def counts_to_spec(counts):
    """Counter{ref:count} -> engine spec [(count, item)]."""
    return [(n, item_of(ref)) for ref, n in counts.items() if n > 0]

def as_deck(counts, ace_ref):
    """-> engine deck tuple (spec, ace_key)."""
    return (counts_to_spec(counts), ace_ref[1])


# ---------------- legality ----------------
def is_legal(counts):
    if sum(counts.values()) != 60:
        return False
    byname = Counter()
    prices = []
    for ref, n in counts.items():
        if n < 0:
            return False
        if ref[0] == 'E':
            continue
        byname[ref_name(ref)] += n
        cat, price = ref_cat_price(ref)
        if cat in ('yellow', 'red'):
            prices += [price] * n
    if any(v > 4 for v in byname.values()):          # ≤4 copies by name (non-basic-energy)
        return False
    prices.sort(reverse=True)                        # money-slot rule
    if len(prices) > 3:
        return False
    if prices and prices[0] > 1.0:
        return False
    if len(prices) > 1 and any(p > 0.50 for p in prices[1:]):
        return False
    return True


# ---------------- candidate pools + mutations ----------------
GENERIC_EXTRAS = {"Judge", "Poké Pad", "Fennel", "Energy Search", "Nest Ball", "Ultra Ball"}
THRESH = 1.0          # min win% gain over baseline to accept a mutation


# named free "engine" Pokémon (from CLAUDE.md) — the plan of the decks that run them
KNOWN_ENGINES = {'Eelektrik', 'Magneton', 'Barbaracle', 'Grumpig', 'Aromatisse', 'Dusclops',
                 'Metang', 'Dewgong', 'Chansey', 'Fan Rotom', "Larry's Komala", 'Rabsca', 'Bibarel'}


def _free_money_slots(counts):
    used = sum(n for r, n in counts.items() if ref_cat_price(r)[0] in ('yellow', 'red'))
    return 3 - used


def special_candidates(ace, sups, types, arch, counts):
    """Standard-legal special energy worth offering this deck: Prism (universal fixer),
    Team Rocket's Energy (TR decks), Spiky (Fighting/Lycanroc), and — only if a money slot
    is free — the Rare typed special energy matching the deck's type."""
    out = [('S', 'Prism Energy')]
    if _family_of([arch.get('premium', '')] + arch.get('supports', [])) == "Team Rocket's":
        out.append(('S', "Team Rocket's Energy"))
    if 'Fighting' in types:
        out.append(('S', 'Spiky Energy'))
    if counts is not None and _free_money_slots(counts) > 0:
        for t in types:
            if t in SE.TYPED_SPECIAL:
                out.append(('S', SE.TYPED_SPECIAL[t]))
    return out


def candidates(arch, ace_ref, counts=None):
    """On-theme add pool for a deck: its Trainer package + generic staples, C/U backup
    attackers of the deck's types, basic energy, and legal special energy."""
    ace = BY_KEY[ace_ref[1]]
    sups = [c for c in (support_card(s) for s in arch.get('supports', [])) if c]
    types = deck_types(ace, sups)
    tnames = {d['name'] for _, d in trainer_package(arch, ace, sups)} | GENERIC_EXTRAS
    add_t = [('T', n) for n in sorted(tnames) if n in TRAINERS]
    excl = {ace.name} | {s.name for s in sups} | {p.name for p in preevo_chain(ace)}
    add_p = [('P', c.key) for c in backup_attackers(types, excl, k=12)]
    add_e = [('E', t) for t in types]
    add_s = special_candidates(ace, sups, types, arch, counts)
    return add_t + add_p + add_e + add_s, types


def protected_refs(counts, ace_ref, arch):
    """Refs the mutator must NOT remove: the ace's evolution line, free ability-engines, and
    named-family synergy pieces — so consistency tuning can't strand a deck's core plan."""
    ace = BY_KEY[ace_ref[1]]
    prot = {('P', pre.key) for pre in preevo_chain(ace)}
    fam = _family_of([arch.get('premium', '')] + arch.get('supports', []))
    for r in counts:
        if r[0] != 'P':
            continue
        c = BY_KEY[r[1]]
        if c.name in KNOWN_ENGINES or (c.cat == 'cat-green' and c.abilities):
            prot.add(r)
        elif fam and c.name.startswith(fam) and (c.abilities or any(a['scaling'] for a in c.attacks)):
            prot.add(r)
    return prot


def canon(counts):
    """Composition-only key for deduping / comparing deck versions."""
    return tuple(sorted((ser(r), n) for r, n in counts.items() if n > 0))


def _pdmg(ref):
    return max((a['dmg'] for a in BY_KEY[ref[1]].attacks), default=0) if ref[0] == 'P' else 0


def mutations(counts, ace_ref, arch, cap=40, rng=random):
    """Enumerate small legal on-theme single-card swaps (rules a–e). The premium, the two
    ≤$0.50 supports, the ace's evolution line, free engines and named-family signatures are
    protected; basic energy won't be cut below a floor that keeps the ace powerable."""
    adds, _types = candidates(arch, ace_ref, counts)
    prot = protected_refs(counts, ace_ref, arch)
    free_pokes = [r for r in counts if r[0] == 'P' and BY_KEY[r[1]].cat == 'cat-green' and r not in prot]
    weak = sorted(free_pokes, key=_pdmg)[:5]                     # cheapest to cut
    strong = sorted(free_pokes, key=_pdmg, reverse=True)[:3]
    energies = sorted([r for r in counts if r[0] == 'E'], key=lambda r: -counts[r])
    most_e = energies[0] if energies else None
    total_e = sum(counts[r] for r in counts if r[0] == 'E')
    ace_cost = max((len(a['cost']) for a in BY_KEY[ace_ref[1]].attacks), default=2)
    e_floor = max(7, ace_cost + 4)                              # basic energy needed to fund the ace
    muts, seen = [], set()

    def addmut(rem, add):
        if rem is None or add is None or rem == add or (rem, add) in seen:
            return
        if counts.get(rem, 0) < 1 or rem in prot:
            return
        if rem[0] == 'E' and total_e <= e_floor:                # keep energy above the floor
            return
        if counts.get(add, 0) >= (60 if add[0] == 'E' else 4):
            return
        m = Counter(counts); m[rem] -= 1; m[add] += 1
        if m[rem] == 0:
            del m[rem]
        if not is_legal(m):
            return
        seen.add((rem, add))
        muts.append((f'-1 {ref_name(rem)} +1 {ref_name(add)}', m))

    for a in adds:
        if a[0] == 'E':
            for w in weak:                      # add energy by cutting a weak backup
                addmut(w, a)
        else:                                   # add Trainer/Pokémon by cutting energy or a weak line
            addmut(most_e, a)
            for w in weak[:2]:
                addmut(w, a)
    for s in strong:                            # redistribute counts toward strong existing cards
        addmut(most_e, s)
        for w in weak:
            addmut(w, s)
    rng.shuffle(muts)
    return muts[:cap]


# ---------------- parallel gauntlet evaluation ----------------
def _rebuild(cards):
    return [(n, item_of(deser(r))) for r, n in cards]


def _eval_pairing(task):
    """Worker: play `games` matches of A vs B; return (winsA, winsB, draws)."""
    a_cards, a_ace, b_cards, b_ace, games, seed = task
    res = run_match((_rebuild(a_cards), a_ace), (_rebuild(b_cards), b_ace),
                    games=games, base_seed=seed)
    return res[0], res[1], res[2]


def _stat_pairing(task):
    """Worker: play A vs B with telemetry on; aggregate deck-A ace stats over the games."""
    a_cards, a_ace, b_cards, b_ace, games, seed = task
    A = (_rebuild(a_cards), a_ace); B = (_rebuild(b_cards), b_ace)
    agg = Counter()
    for g in range(games):
        if g % 2 == 0:
            game = Game(A, B, seed=seed + g, stats=True); si = 0
        else:
            game = Game(B, A, seed=seed + g, stats=True); si = 1
        w = game.play(); s = game.stats[si]
        agg['games'] += 1
        agg['wins'] += 1 if w == si else 0
        agg['ace_play'] += s['ace_in_play']
        if s['ace_turn'] >= 0:
            agg['ace_turn_sum'] += s['ace_turn']; agg['ace_turn_n'] += 1
        agg['atk'] += s['ace_atk']; agg['dealt'] += s['ace_dmg_dealt']; agg['taken'] += s['ace_dmg_taken']
    return dict(agg)


def build_gauntlet(decks, exclude):
    """Serialized opponents (current best of every other deck) — the field to beat."""
    return [([(ser(r), c) for r, c in d['counts'].items()], d['ace'][1])
            for n, d in decks.items() if n != exclude]


def _run_map(fn, tasks, ex):
    if ex is None:
        return map(fn, tasks)
    return ex.map(fn, tasks, chunksize=max(1, len(tasks) // 32))


def evaluate(counts, ace, gaunt, games, ex, seed0):
    """Win% of a decklist vs the whole gauntlet. Uses the same per-opponent seeds every
    call (common random numbers) so a mutation's gain is measured against identical games."""
    a_cards = [(ser(r), n) for r, n in counts.items()]
    tasks = [(a_cards, ace[1], bc, ba, games, seed0 + i) for i, (bc, ba) in enumerate(gaunt)]
    wa = wb = 0
    for x, y, _ in _run_map(_eval_pairing, tasks, ex):
        wa += x; wb += y
    return 100.0 * wa / max(1, wa + wb)


# ---------------- persistence ----------------
def save_decklists(decks):
    out = {name: {'section': d['section'], 'ace': ser(d['ace']),
                  'cards': {ser(r): c for r, c in d['counts'].items() if c > 0}}
           for name, d in decks.items()}
    json.dump(out, open(os.path.join(HERE, 'decklists.json'), 'w'), indent=0)


def append_jsonl(path, rec):
    with open(path, 'a') as f:
        f.write(json.dumps(rec) + '\n')


def save_archive(decks):
    """Per-deck version history (Hall of Fame) for the archive-and-revert search."""
    out = {name: [{ser(r): c for r, c in ver.items() if c > 0} for ver in d.get('archive', [])]
           for name, d in decks.items()}
    json.dump(out, open(os.path.join(HERE, 'archive.json'), 'w'), indent=0)


def load_state(fresh=False):
    """decks: name -> {section, ace, counts, archive}; archs: name -> archetype dict."""
    archs = {d['name']: d for d in parse_decks()}
    path = os.path.join(HERE, 'decklists.json')
    apath = os.path.join(HERE, 'archive.json')
    archive = json.load(open(apath)) if (os.path.exists(apath) and not fresh) else {}
    decks = {}
    if os.path.exists(path) and not fresh:
        for name, e in json.load(open(path)).items():
            if name not in archs:
                continue
            counts = Counter({deser(k): v for k, v in e['cards'].items()})
            arc = [Counter({deser(k): v for k, v in ver.items()}) for ver in archive.get(name, [])]
            decks[name] = {'section': e['section'], 'ace': deser(e['ace']),
                           'counts': counts, 'archive': arc or [Counter(counts)]}
    else:
        for d in parse_decks():
            counts, ace = materialize(d)
            if is_legal(counts):
                decks[d['name']] = {'section': d['section'], 'ace': ace, 'counts': counts,
                                    'archive': [Counter(counts)]}
        save_decklists(decks)
    return decks, archs


# ---------------- telemetry snapshot ----------------
def collect_field_stats(decks, games, ex, seed0=1, out_name='stats.json'):
    out = {}
    for name, d in decks.items():
        gaunt = build_gauntlet(decks, name)
        a_cards = [(ser(r), c) for r, c in d['counts'].items()]
        tasks = [(a_cards, d['ace'][1], bc, ba, games, seed0 + i) for i, (bc, ba) in enumerate(gaunt)]
        tot = Counter()
        for a in _run_map(_stat_pairing, tasks, ex):
            tot.update(a)
        g = max(1, tot['games'])
        out[name] = {'section': d['section'],
                     'winrate': round(100 * tot['wins'] / g, 1),
                     'ace_play_rate': round(100 * tot['ace_play'] / g, 1),
                     'avg_ace_turn': round(tot['ace_turn_sum'] / max(1, tot['ace_turn_n']), 1),
                     'ace_atks_per_game': round(tot['atk'] / g, 2),
                     'ace_dmg_dealt_per_game': round(tot['dealt'] / g, 1),
                     'ace_dmg_taken_per_game': round(tot['taken'] / g, 1)}
    json.dump(out, open(os.path.join(HERE, out_name), 'w'), indent=1)
    return out


def leaderboard(decks, games, ex, rnd, seed0=1):
    board = []
    for name, d in decks.items():
        wr = evaluate(d['counts'], d['ace'], build_gauntlet(decks, name), games, ex, seed0)
        board.append([round(wr, 2), name, d['section']])
    board.sort(reverse=True)
    json.dump({'round': rnd, 'games_per_pairing': games, 'board': board},
              open(os.path.join(HERE, 'leaderboard.json'), 'w'), indent=1)
    return board


# ---------------- coevolutionary hill-climb ----------------
def run(names=None, section=None, games=20, rounds=1, cap=40, workers=1, seed0=1, resume=True):
    decks, archs = load_state()
    if section:
        names = [n for n in decks if decks[n]['section'] == section]
    names = [n for n in (names or list(decks)) if n in decks]
    ex = ProcessPoolExecutor(workers) if workers > 1 else None
    hist = os.path.join(HERE, 'history.jsonl')
    done = set()                                    # (round, deck) already processed
    donef = os.path.join(HERE, 'OPT_DONE')          # completion sentinel (for the daemon wrapper)
    if not resume:
        open(hist, 'w').close()                     # fresh: wipe the ledger
        try:
            os.remove(donef)
        except OSError:
            pass
    elif os.path.exists(hist):
        for l in open(hist):
            try:
                r = json.loads(l); done.add((r['round'], r['deck']))
            except Exception:
                pass
        if done:
            print(f"resuming: {len(done)} deck-rounds already recorded, skipping those", flush=True)
    t0 = time.time()
    print(f"optimizing {len(names)} decks | field={len(decks)} | {games} games/pairing | "
          f"cap={cap} muts | {rounds} round(s) | workers={workers or 1}", flush=True)
    try:
        for rnd in range(1, rounds + 1):
            accepts = 0
            for i, name in enumerate(names, 1):
                if (rnd, name) in done:             # resume: already optimized this deck-round
                    continue
                d = decks[name]
                gaunt = build_gauntlet(decks, name)                 # current best of the field
                base = evaluate(d['counts'], d['ace'], gaunt, games, ex, seed0)
                cur_key = canon(d['counts'])
                cands = list(mutations(d['counts'], d['ace'], archs[name], cap))
                for vi, av in enumerate(d.get('archive', [])):      # archive-and-revert candidates
                    if canon(av) != cur_key:
                        cands.append((f'revert->v{vi}', Counter(av)))
                best, seen_keys = None, {cur_key}
                for desc, mc in cands:                              # eval each unique candidate vs current field
                    k = canon(mc)
                    if k in seen_keys:
                        continue
                    seen_keys.add(k)
                    wr = evaluate(mc, d['ace'], gaunt, games, ex, seed0)
                    if best is None or wr > best[1]:
                        best = (desc, wr, mc)
                accepted = best is not None and best[1] > base + THRESH
                is_revert = accepted and best[0].startswith('revert')
                append_jsonl(hist, {'round': rnd, 'deck': name, 'section': d['section'],
                                    'base': round(base, 2),
                                    'best': round(best[1], 2) if best else None,
                                    'delta': round(best[1] - base, 2) if best else None,
                                    'mutation': best[0] if best else None, 'revert': is_revert,
                                    'n_cands': len(cands), 'accepted': accepted, 'ts': time.time()})
                if accepted:
                    d['counts'] = best[2]; accepts += 1
                    if canon(best[2]) not in {canon(a) for a in d['archive']}:
                        d['archive'].append(Counter(best[2]))       # remember this version
                        d['archive'] = d['archive'][-30:]
                    save_decklists(decks); save_archive(decks)      # checkpoint after every change
                el = time.time() - t0
                tag = ('REVERT' if is_revert else 'ACCEPT') if accepted else '  ----'
                print(f"[r{rnd} {i:3}/{len(names)} {el:6.0f}s] {tag} {name[:32]:32} "
                      f"{base:5.1f} -> {(best[1] if best else base):5.1f}  "
                      f"{(best[0] if accepted else '')}", flush=True)
            board = leaderboard(decks, games, ex, rnd, seed0)
            print(f"=== round {rnd} done: {accepts} changes | top: "
                  f"{board[0][1]} {board[0][0]}% | median "
                  f"{board[len(board) // 2][0]}% ===", flush=True)
        open(donef, 'w').write(str(time.time()))    # signal the wrapper: all rounds complete
        print("=== ALL ROUNDS COMPLETE ===", flush=True)
    finally:
        if ex:
            ex.shutdown()
    return decks


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='coevolutionary deck optimizer')
    ap.add_argument('--materialize', action='store_true', help='(re)build fresh decklists.json and exit')
    ap.add_argument('--fresh', action='store_true', help='reset decklists + wipe history, then optimize from scratch')
    ap.add_argument('--stats', action='store_true', help='telemetry-only pass -> stats.json')
    ap.add_argument('--games', type=int, default=20)
    ap.add_argument('--statgames', type=int, default=6)
    ap.add_argument('--rounds', type=int, default=1)
    ap.add_argument('--cap', type=int, default=40, help='max mutations tried per deck')
    ap.add_argument('--workers', type=int, default=1)
    ap.add_argument('--section', default=None)
    ap.add_argument('--decks', default=None, help='comma-separated deck names')
    a = ap.parse_args()

    if a.materialize:
        decks, _ = load_state(fresh=True)
        print(f"materialized {len(decks)} legal decklists -> decklists.json")
    elif a.stats:
        decks, _ = load_state()
        ex = ProcessPoolExecutor(a.workers) if a.workers > 1 else None
        try:
            st = collect_field_stats(decks, a.statgames, ex)
        finally:
            if ex:
                ex.shutdown()
        print(f"telemetry for {len(st)} decks -> stats.json ({a.statgames} games/pairing)")
    else:
        if a.fresh:
            load_state(fresh=True)                  # re-materialize decklists.json to baseline
        names = [n.strip() for n in a.decks.split(',')] if a.decks else None
        run(names=names, section=a.section, games=a.games, rounds=a.rounds,
            cap=a.cap, workers=a.workers, resume=not a.fresh)
