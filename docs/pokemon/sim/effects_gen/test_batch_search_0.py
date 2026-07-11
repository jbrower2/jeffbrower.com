#!/usr/bin/env python3
"""Unit tests for effect batch search_0 (deck-search attacks)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # ensure sim/ importable
from collections import Counter
from effects_testkit import mk, run, runner
from cards import load_cards
import attack_effects as AE
import effects_gen.batch_search_0  # noqa: F401  (registers the effects)

BK, BN = load_cards()

# Real cards for evolve / named-subset tests:
BULBASAUR = BK['ME01:#001/132']   # VANILLA in the testkit — Grass Basic
IVYSAUR   = BK['ME01:#002/132']   # Stage 1, evolves from Bulbasaur
EKANS     = BK['SV05:#100/162']   # Darkness Basic
ARBOK     = BK['SV05:#101/162']   # Stage 1, evolves from Ekans
STEVEN_B  = BN["Steven's Baltoy"][0]
MISTY_P   = BN["Misty's Psyduck"][0]

# In mk(): me.hand empty; me.deck = 6 Basic Pokémon (Bulbasaur) + 10 Colorless energy;
# me.bench has my_bench mons; attacker energy defaults to {'Colorless':3}. heads=0.0, tails=0.9.


def _fn(text):
    return AE.ATTACK_EFFECTS[AE.normalize(text)]


def _sup(name='SupX'):
    return {'name': name, 'trainerType': 'Supporter', 'effect': ''}


def _item(name='ItemX'):
    return {'name': name, 'trainerType': 'Item', 'effect': ''}


def _tool(name='ToolX'):
    return {'name': name, 'trainerType': 'Tool', 'effect': ''}


def _stadium(name='StadX'):
    return {'name': name, 'trainerType': 'Stadium', 'effect': ''}


# ================================================================ bench-fill

def t_bench_2_basic():
    d, ctx, at, df, me, opp = run(
        "Search your deck for up to 2 Basic Pokémon and put them onto your Bench. Then, shuffle your deck.")
    assert d == 50, d                              # returns printed base
    assert len(me.bench) == 3, len(me.bench)       # started at 1, +2


def t_bench_1_basic():
    d, ctx, at, df, me, opp = run(
        "Search your deck for a Basic Pokémon and put it onto your Bench. Then, shuffle your deck.")
    assert len(me.bench) == 2, len(me.bench)


def t_bench_3_basic():
    d, ctx, at, df, me, opp = run(
        "Search your deck for up to 3 Basic Pokémon and put them onto your Bench. Then, shuffle your deck.")
    assert len(me.bench) == 4, len(me.bench)       # 1 + 3


def t_bench_2_steven():
    key = "Search your deck for up to 2 Basic Steven's Pokémon and put them onto your Bench. Then, shuffle your deck."
    ctx, at, df, me, opp = mk(text=key, my_bench=0)
    me.deck = [('P', STEVEN_B)] * 2 + [('P', BULBASAUR)] * 3 + [('E', 'Colorless')] * 3
    _fn(key)(ctx)
    assert len(me.bench) == 2, len(me.bench)       # only the 2 Steven's, NOT the Bulbasaurs
    assert all(m.card.name.startswith("Steven's") for m in me.bench), [m.card.name for m in me.bench]


def t_bench_2_basic_first_turn():
    d, ctx, at, df, me, opp = run(
        "If you go first, you can use this attack during your first turn. Search your deck for up to 2 "
        "Basic Pokémon and put them onto your Bench. Then, shuffle your deck.")
    assert len(me.bench) == 3, len(me.bench)


def t_bench_1_move_energy_moves():
    key = ("Search your deck for a Basic Pokémon and put it onto your Bench. Then, shuffle your deck. "
           "If you put any Pokémon onto your Bench in this way, move an Energy from this Pokémon to the "
           "new Benched Pokémon.")
    d, ctx, at, df, me, opp = run(key, atk_energy={'Water': 2}, my_bench=1)
    assert len(me.bench) == 2, len(me.bench)                       # one basic benched
    assert me.bench[-1].energy['Water'] == 1, me.bench[-1].energy  # moved onto the new mon
    assert at.energy['Water'] == 1, at.energy                      # taken off the attacker


def t_bench_1_move_energy_no_basic():
    # No Basic Pokémon to fetch -> nothing benched -> no energy moved.
    key = ("Search your deck for a Basic Pokémon and put it onto your Bench. Then, shuffle your deck. "
           "If you put any Pokémon onto your Bench in this way, move an Energy from this Pokémon to the "
           "new Benched Pokémon.")
    ctx, at, df, me, opp = mk(text=key, atk_energy={'Water': 2}, my_bench=1)
    me.deck = [('E', 'Colorless')] * 4                            # no Pokémon in deck
    before = len(me.bench)
    _fn(key)(ctx)
    assert len(me.bench) == before, len(me.bench)
    assert at.energy['Water'] == 2, at.energy                    # unchanged


# ================================================================ search Pokémon into hand

def t_hand_3_poke():
    d, ctx, at, df, me, opp = run(
        "Search your deck for up to 3 Pokémon, reveal them, and put them into your hand. Then, shuffle your deck.")
    assert len(me.hand) == 3, len(me.hand)
    assert all(t[0] == 'P' for t in me.hand), me.hand


def t_hand_1_poke():
    d, ctx, at, df, me, opp = run(
        "Search your deck for a Pokémon, reveal it, and put it into your hand. Then, shuffle your deck.")
    assert len(me.hand) == 1 and me.hand[0][0] == 'P', me.hand


def t_hand_3_misty():
    key = "Search your deck for up to 3 Misty's Pokémon, reveal them, and put them into your hand. Then, shuffle your deck."
    ctx, at, df, me, opp = mk(text=key)
    me.deck = [('P', MISTY_P)] * 3 + [('P', BULBASAUR)] * 3       # Bulbasaur is a decoy (not Misty's)
    _fn(key)(ctx)
    assert len(me.hand) == 3, len(me.hand)
    assert all(t[1].name.startswith("Misty's") for t in me.hand), [t[1].name for t in me.hand]


# ================================================================ search Trainer into hand

def t_hand_supporter():
    key = "Search your deck for a Supporter card, reveal it, and put it into your hand. Then, shuffle your deck."
    ctx, at, df, me, opp = mk(text=key)
    me.deck = [('T', _item()), ('T', _sup())]                    # Item decoy + the Supporter
    _fn(key)(ctx)
    assert len(me.hand) == 1, me.hand
    assert me.hand[0][1]['trainerType'] == 'Supporter', me.hand


def t_hand_item():
    key = "Search your deck for an Item card, reveal it, and put it into your hand. Then, shuffle your deck."
    ctx, at, df, me, opp = mk(text=key)
    # Item at the front; a Supporter AND a Pokémon Tool sit AFTER it (searched first) and must both be
    # skipped -- an "Item" search must NOT grab a Pokémon Tool (distinct SV-era Trainer categories).
    me.deck = [('T', _item()), ('T', _sup()), ('T', _tool())]
    _fn(key)(ctx)
    assert len(me.hand) == 1 and me.hand[0][1]['trainerType'] == 'Item', me.hand


def t_hand_tool():
    key = "Search your deck for a Pokémon Tool card, reveal it, and put it into your hand. Then, shuffle your deck."
    ctx, at, df, me, opp = mk(text=key)
    # Tool at the front; an Item sits AFTER it (searched first) and must be skipped -- a Pokémon Tool
    # search must NOT grab a plain Item card.
    me.deck = [('T', _tool()), ('T', _item())]
    _fn(key)(ctx)
    assert len(me.hand) == 1 and me.hand[0][1]['trainerType'] == 'Tool', me.hand


def t_hand_2_tome():
    key = "Search your deck for up to 2 Transformation Tome cards, reveal them, and put them into your hand. Then, shuffle your deck."
    ctx, at, df, me, opp = mk(text=key)
    me.deck = [('T', _item('Transformation Tome'))] * 2 + [('T', _item('Great Ball'))]
    _fn(key)(ctx)
    assert len(me.hand) == 2, me.hand                            # only the two Tomes
    assert all(t[1]['name'] == 'Transformation Tome' for t in me.hand), me.hand


def t_hand_3_grass_or_stadium():
    key = ("Search your deck for up to 3 in any combination of {G} Pokémon and Stadium cards, reveal them, "
           "and put them into your hand. Then, shuffle your deck.")
    ctx, at, df, me, opp = mk(text=key)
    me.deck = [('P', BULBASAUR), ('T', _stadium()), ('P', EKANS), ('E', 'Colorless')]  # Ekans(Dark)+energy = decoys
    _fn(key)(ctx)
    assert len(me.hand) == 2, me.hand
    kinds = sorted((t[0] for t in me.hand))
    assert kinds == ['P', 'T'], kinds                           # one Grass Pokémon + one Stadium
    poke = next(t for t in me.hand if t[0] == 'P')
    assert poke[1].ptype == 'Grass', poke[1].name               # Ekans (Dark) was not taken


# ================================================================ search any card(s) into hand

def t_hand_2_any():
    d, ctx, at, df, me, opp = run(
        "You may search your deck for up to 2 cards and put them into your hand. Then, shuffle your deck.", base=70)
    assert d == 70, d                                            # Noctowl's printed 70
    assert len(me.hand) == 2, len(me.hand)


def t_hand_1_any_first_turn():
    d, ctx, at, df, me, opp = run(
        "If you go first, you can use this attack during your first turn. Search your deck for a card and "
        "put it into your hand. Then, shuffle your deck.")
    assert len(me.hand) == 1, len(me.hand)


# ================================================================ search Basic Energy into hand

def t_hand_2_basic_energy():
    d, ctx, at, df, me, opp = run(
        "Search your deck for up to 2 Basic Energy cards, reveal them, and put them into your hand. Then, shuffle your deck.")
    assert len(me.hand) == 2, len(me.hand)
    assert all(t[0] == 'E' for t in me.hand), me.hand


def t_hand_1_basic_energy():
    d, ctx, at, df, me, opp = run(
        "Search your deck for a Basic Energy card, reveal it, and put it into your hand. Then, shuffle your deck.")
    assert len(me.hand) == 1 and me.hand[0][0] == 'E', me.hand


def t_hand_3_diff_energy():
    key = "Search your deck for up to 3 Basic Energy cards of different types, reveal them, and put them into your hand. Then, shuffle your deck."
    ctx, at, df, me, opp = mk(text=key)
    me.deck = [('E', 'Fire'), ('E', 'Fire'), ('E', 'Water'), ('E', 'Grass')]
    _fn(key)(ctx)
    assert len(me.hand) == 3, me.hand                            # one duplicate Fire skipped
    assert len({t[1] for t in me.hand}) == 3, me.hand           # three distinct types


def t_hand_3_diff_energy_all_same():
    # Deck of a single energy type -> only one card can be taken.
    d, ctx, at, df, me, opp = run(
        "Search your deck for up to 3 Basic Energy cards of different types, reveal them, and put them into your hand. Then, shuffle your deck.")
    assert len(me.hand) == 1, me.hand                            # deck is all Colorless


# ================================================================ search Basic Energy and attach

def t_attach_1_grass_self():
    key = "Search your deck for a Basic {G} Energy card and attach it to this Pokémon. Then, shuffle your deck."
    ctx, at, df, me, opp = mk(text=key, base=20)                 # Quilladin's 20
    me.deck = [('E', 'Grass')] * 2 + [('E', 'Colorless')] * 2
    d = _fn(key)(ctx)
    assert d == 20, d
    assert at.energy['Grass'] == 1, at.energy                   # exactly one attached
    assert me.deck.count(('E', 'Grass')) == 1, me.deck          # one Grass left in deck


def t_attach_2_psychic_self():
    key = "Search your deck for up to 2 Basic {P} Energy cards and attach them to this Pokémon. Then, shuffle your deck."
    ctx, at, df, me, opp = mk(text=key)
    me.deck = [('E', 'Psychic')] * 3
    _fn(key)(ctx)
    assert at.energy['Psychic'] == 2, at.energy
    assert me.deck.count(('E', 'Psychic')) == 1, me.deck


def t_attach_2_water_self():
    key = "Search your deck for up to 2 Basic {W} Energy cards and attach them to this Pokémon. Then, shuffle your deck."
    ctx, at, df, me, opp = mk(text=key)
    me.deck = [('E', 'Water')] * 2 + [('E', 'Colorless')]
    _fn(key)(ctx)
    assert at.energy['Water'] == 2, at.energy


def t_attach_2_psychic_bench():
    key = "Search your deck for up to 2 Basic {P} Energy cards and attach them to 1 of your Benched Pokémon. Then, shuffle your deck."
    ctx, at, df, me, opp = mk(text=key, my_bench=1)
    me.deck = [('E', 'Psychic')] * 2
    _fn(key)(ctx)
    assert me.bench[0].energy['Psychic'] == 2, me.bench[0].energy
    assert at.energy['Psychic'] == 0, at.energy                 # NOT the attacker


def t_attach_2_psychic_bench_no_bench():
    key = "Search your deck for up to 2 Basic {P} Energy cards and attach them to 1 of your Benched Pokémon. Then, shuffle your deck."
    ctx, at, df, me, opp = mk(text=key, my_bench=0)
    me.deck = [('E', 'Psychic')] * 2
    d = _fn(key)(ctx)                                            # no bench -> no crash, nothing attached
    assert d == 50, d
    assert me.deck.count(('E', 'Psychic')) == 2, me.deck        # energy stayed in deck


def t_attach_2_any_energy():
    key = "Search your deck for up to 2 Basic Energy cards and attach them to your Pokémon in any way you like. Then, shuffle your deck."
    ctx, at, df, me, opp = mk(text=key, my_bench=1)
    me.deck = [('E', 'Fire')] * 2 + [('E', 'Colorless')]
    _fn(key)(ctx)
    assert at.energy['Fire'] == 2, at.energy                    # attached to the ace (the funded attacker)
    assert me.deck == [('E', 'Colorless')], me.deck            # exactly 2 pulled; capped -> Colorless left behind


# ================================================================ evolve-search

def t_evolve_self():
    key = "Search your deck for a card that evolves from this Pokémon and put it onto this Pokémon to evolve it. Then, shuffle your deck."
    ctx, at, df, me, opp = mk(text=key, base=30)                 # Team Rocket's Pupitar's 30
    me.deck = [('P', IVYSAUR)] + [('E', 'Colorless')] * 3
    d = _fn(key)(ctx)
    assert d == 30, d
    assert me.active.card.name == 'Ivysaur', me.active.card.name
    assert me.active.total_energy() == 3, me.active.total_energy()   # attacker's energy carried over
    assert ctx.attacker is me.active, "ctx.attacker should follow the evolution"


def t_evolve_self_no_target():
    key = "Search your deck for a card that evolves from this Pokémon and put it onto this Pokémon to evolve it. Then, shuffle your deck."
    ctx, at, df, me, opp = mk(text=key)
    me.deck = [('E', 'Colorless')] * 3                          # nothing evolves from Bulbasaur here
    _fn(key)(ctx)
    assert me.active.card.name == 'Bulbasaur', me.active.card.name   # unchanged


def t_evolve_self_first_turn():
    key = ("If you go first, you can use this attack during your first turn. Search your deck for a card "
           "that evolves from this Pokémon and put it onto this Pokémon to evolve it. Then, shuffle your deck.")
    ctx, at, df, me, opp = mk(text=key)
    me.deck = [('P', IVYSAUR)]
    _fn(key)(ctx)
    assert me.active.card.name == 'Ivysaur', me.active.card.name


def t_evolve_all_bench():
    key = ("For each of your Benched Pokémon, search your deck for a card that evolves from that Pokémon and "
           "put it onto that Pokémon to evolve it. Then, shuffle your deck.")
    ctx, at, df, me, opp = mk(text=key, my_bench=2)             # two benched Bulbasaurs
    me.deck = [('P', IVYSAUR)]                                  # only ONE evolution available
    _fn(key)(ctx)
    # Each benched Pokémon gets its OWN independent deck search; the deck runs out after the first.
    assert me.bench[0].card.name == 'Ivysaur', me.bench[0].card.name        # first bench mon evolved
    assert me.bench[1].card.name == 'Bulbasaur', me.bench[1].card.name      # no card left -> left unevolved


def t_evolve_2_dark():
    key = ("Choose up to 2 of your {D} Pokémon. For each of those Pokémon, search your deck for a card that "
           "evolves from that Pokémon and put it onto that Pokémon to evolve it. Then, shuffle your deck.")
    # all_mons() order is [active, bench0, bench1, bench2]. A Grass mon between two Dark mons proves the
    # {D} filter; a 3rd Dark mon proves the "up to 2" cap stops it from evolving.
    ctx, at, df, me, opp = mk(text=key, my_bench=3)
    at.card = EKANS                 # active: Dark  -> evolves (1st)
    me.bench[0].card = BULBASAUR    # bench0: Grass -> skipped by the {D} filter (its Ivysaur stays in deck)
    me.bench[1].card = EKANS        # bench1: Dark  -> evolves (2nd)
    me.bench[2].card = EKANS        # bench2: Dark  -> NOT reached (cap of 2 already hit)
    me.deck = [('P', ARBOK), ('P', ARBOK), ('P', IVYSAUR)]
    _fn(key)(ctx)
    assert me.active.card.name == 'Arbok', me.active.card.name          # 1st Dark evolved
    assert me.bench[0].card.name == 'Bulbasaur', me.bench[0].card.name  # Grass mon left alone ({D} filter)
    assert me.bench[1].card.name == 'Arbok', me.bench[1].card.name      # 2nd Dark evolved
    assert me.bench[2].card.name == 'Ekans', me.bench[2].card.name      # 3rd Dark blocked by the "up to 2" cap
    assert ('P', IVYSAUR) in me.deck, me.deck                          # Grass evo untouched -> proves filter, not cap


TESTS = [
    t_bench_2_basic,
    t_bench_1_basic,
    t_bench_3_basic,
    t_bench_2_steven,
    t_bench_2_basic_first_turn,
    t_bench_1_move_energy_moves,
    t_bench_1_move_energy_no_basic,
    t_hand_3_poke,
    t_hand_1_poke,
    t_hand_3_misty,
    t_hand_supporter,
    t_hand_item,
    t_hand_tool,
    t_hand_2_tome,
    t_hand_3_grass_or_stadium,
    t_hand_2_any,
    t_hand_1_any_first_turn,
    t_hand_2_basic_energy,
    t_hand_1_basic_energy,
    t_hand_3_diff_energy,
    t_hand_3_diff_energy_all_same,
    t_attach_1_grass_self,
    t_attach_2_psychic_self,
    t_attach_2_water_self,
    t_attach_2_psychic_bench,
    t_attach_2_psychic_bench_no_bench,
    t_attach_2_any_energy,
    t_evolve_self,
    t_evolve_self_no_target,
    t_evolve_self_first_turn,
    t_evolve_all_bench,
    t_evolve_2_dark,
]

if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
