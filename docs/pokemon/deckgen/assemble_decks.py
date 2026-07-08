#!/usr/bin/env python3
"""Stitch the per-section deck source files into ../decks.md.

Sources (edit these, not decks.md directly): decks_<TYPE>.txt, plus optional
decks_<TYPE>_extra.txt and decks_<TYPE>_new.txt overflow files, concatenated in
order under each section header.

Run:  python3 assemble_decks.py
"""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
POKE = os.path.dirname(HERE)
OUT = os.path.join(POKE, 'decks.md')
ORDER = [('G', 'Grass'), ('R', 'Fire'), ('W', 'Water'), ('L', 'Lightning'), ('P', 'Psychic'),
         ('F', 'Fighting'), ('D', 'Darkness'), ('M', 'Metal'), ('C', 'Colorless'),
         ('MULTI', 'Multi (2–3 energy types)'), ('TR', "Team Rocket's")]

INTRO = '''# Deck ideas

A large, expanding catalog of *cohesive* budget/pauper decks — roughly ten per type — meant as candidates to run through a game simulator and optimize. Every deck fits the three "money" slots:

- **1 premium** (≤ $1.00) — the ex/Mega-ex centerpiece.
- **2 support slots** (≤ $0.50 each) — rares that specifically amplify the centerpiece (two copies of one card, written "×2", uses both slots).
- **everything else** is common/uncommon pokemon + basic energy (unlimited).

The paid cards should pull in the same direction, and the free common/uncommon backbone should enable them, so each deck lists its slots and the synergy that ties them together. Within each type, decks are ordered roughly strongest → most experimental; the tail options are deliberately greedier or more situational (flagged where so) to give the simulator a wider field to compare.

**Free (common/uncommon) engines worth building around:**

- **Eelektrik** — Dynamotor attaches a {L} from your discard every turn (repeatable). The backbone of Lightning.
- **Magneton** — dumps up to 3 basic energy from discard onto a {L} pokemon, but it *Knocks itself Out* doing so — a one-shot burst, not an engine.
- **Barbaracle** (Stone Arms, a {F} from hand each turn) · **Grumpig** (attach basics off the top 4 on evolve) · **Metang** (Metal Maker, attach {M} off the top 4) · **Dusclops** (snipe 5 counters anywhere, KOs itself) · **Chansey** (Lucky Attachment) · **Larry's Komala** (any energy from hand to an active Larry's) · **Fan Rotom** (turn-1 search for 3 colorless pokemon).

**Strong enablers that cost a support slot (they're rare):** Cinderace (Turbo Flare — 3 energy of *any* type), Emboar (Inferno Fandango — unlimited fire from hand), Meganium (Wild Growth — doubles grass), Toxtricity (Sinister Surge — dark from deck), Magearna (Auto Heal — 90 per attach), Dewgong (Wash Out — shuttle water to the active), Terapagos (Prism Charge — 3 basic energy of different types).

---
'''

parts = [INTRO]
missing = []
for key, title in ORDER:
    p = os.path.join(HERE, f'decks_{key}.txt')
    if not os.path.exists(p):
        missing.append(key); continue
    body = open(p).read().strip()
    for suf in ('_extra', '_new'):
        xp = os.path.join(HERE, f'decks_{key}{suf}.txt')
        if os.path.exists(xp):
            body += '\n\n' + open(xp).read().strip()
    parts.append(f'\n## {title}\n\n{body}\n')

parts.append('''
---

*Built on printing-level card data (1,836 distinct printings): where a Pokémon has two different cards under the same name, the deck names the exact printing it wants (e.g. "the SV06 Palafin," "the ASH Miraidon ex," "the SV09 Reshiram ex"). Prices are the cheapest legal printing at time of writing and drift constantly — re-check before building. Where a deck names a rare pre-evolution as a support (Meganium, Emboar, Feraligatr, the Serperior/Cynthia lines, etc.), remember it eats one of your two ≤$0.50 slots. This catalog is input to a deck simulator — the next step is encoding these as full 60-card lists and comparing win rates.*
''')
open(OUT, 'w').write('\n'.join(parts))
print('wrote', OUT)
if missing:
    print('MISSING sections:', missing)
