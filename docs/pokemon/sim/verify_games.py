#!/usr/bin/env python3
"""Run a few fully-logged games between decks stacked with TRICKY cards, so every move can be audited
against the card text. Prints a turn-by-turn trace. Run: python3 verify_games.py [seed]."""
import sys
from cards import load_cards
from engine import Game

BK, BN = load_cards()


def green(pred):
    return [c for c in BK.values() if c.cat == 'cat-green' and pred(c)]


def has_ab(c, name):
    return any(ab.get('name') == name for ab in c.abilities)


def atk_has(c, sub):
    return any(sub in (a.get('text') or '') for a in c.attacks)


def basic(pred):
    xs = green(lambda c: c.stage == 0 and pred(c))
    return xs[0] if xs else None


# ---- pick tricky cards (prefer Basics so they attack without an evolution line) ----
cram = next((c for c in BN.get("Hop's Cramorant", []) if any('Fickle' in a['name'] for a in c.attacks)), None)
coinflip = basic(lambda c: atk_has(c, 'for each heads') and c is not cram)
gate = basic(lambda c: atk_has(c, 'If tails, this attack does nothing'))
paralyze = basic(lambda c: atk_has(c, 'now Paralyzed'))
poison_atk = basic(lambda c: atk_has(c, 'now Poisoned'))
spread = basic(lambda c: atk_has(c, "Benched") and atk_has(c, 'damage'))
poison_point = basic(lambda c: has_ab(c, 'Poison Point'))
# a damage-reduction aura line (evolution) + its base, and a bench-immunity mon
dr_line = green(lambda c: has_ab(c, 'Thick Fat') or has_ab(c, 'Exoskeleton') or has_ab(c, 'Protective Bell'))
dr_evo = dr_line[0] if dr_line else None
dr_base = basic(lambda c: dr_evo and c.name == dr_evo.evolves_from) if dr_evo else None
immunity = basic(lambda c: has_ab(c, 'Spherical Shield') or (has_ab(c, 'So Submerged')))
vanilla = basic(lambda c: not c.abilities and c.attacks and 70 <= c.hp <= 90
                and 30 <= max((a['dmg'] for a in c.attacks), default=0) <= 50
                and min(len(a['cost']) for a in c.attacks) <= 2)          # moderate filler: games progress


def show(label, c):
    if c is None:
        print(f"   [{label}] (none found)")
        return
    atext = ' / '.join(f"{a['name']}[{''.join(a['cost']) or '-'}]{a['dmg']}" for a in c.attacks)
    ab = ' ABIL:' + ','.join(a['name'] for a in c.abilities) if c.abilities else ''
    print(f"   [{label:12}] {c.name} ({c.set}#{c.id}) {c.hp}HP  {atext}{ab}")


print("=== tricky cards selected ===")
for lbl, c in [('cramorant', cram), ('coinflip', coinflip), ('gate', gate), ('paralyze', paralyze),
               ('poison_atk', poison_atk), ('spread', spread), ('poison_point', poison_point),
               ('dr_base', dr_base), ('dr_evo', dr_evo), ('immunity', immunity), ('vanilla', vanilla)]:
    show(lbl, c)


def deck(cards, energy_types, n_energy=26):
    spec = []
    for c in cards:
        if c is not None:
            spec.append((3, c))
    # pad Pokémon count a little with the vanilla basic so setups are reliable
    spec.append((4, vanilla))
    per = n_energy // len(energy_types)
    for et in energy_types:
        spec.append((per, et))
    total = sum(n for n, _ in spec)
    spec.append((max(0, 60 - total), energy_types[0]))     # fill to 60 with the primary energy
    return (spec, None)


A = deck([cram, coinflip, gate, poison_point, immunity], ['Psychic', 'Water'])
B = deck([paralyze, poison_atk, spread, dr_base, dr_evo], ['Fire', 'Psychic'])

seed = int(sys.argv[1]) if len(sys.argv) > 1 else 7
print(f"\n=== GAME (seed {seed}) — Deck A vs Deck B, verbose ===")
g = Game(A, B, seed=seed, verbose=True)
g.play(max_turns=40)
w = g.winner()
print(f"=== result: winner={['A', 'B', 'draw'][w if w is not None else 2]} | "
      f"A prizes {g.players[0].prizes_taken}/6, B prizes {g.players[1].prizes_taken}/6 ===")
