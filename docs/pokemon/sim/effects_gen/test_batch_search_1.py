#!/usr/bin/env python3
"""Unit tests for effect batch search_1. Each effect is exercised against real engine Mon/Player
objects (via effects_testkit.mk) with specific cards injected into the deck, then its returned
damage AND the resulting board/hand/deck/energy state are asserted. Run:
    python3 effects_gen/test_batch_search_1.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # ensure sim/ importable
from collections import Counter
from effects_testkit import mk, run, runner
from engine import Mon
from cards import load_cards
import attack_effects as AE
import effects_gen.batch_search_1  # noqa: F401  (registers the effects)

_BK, _BN = load_cards()


def card(name, **filt):
    """A Card by name, optionally filtered (e.g. ptype='Grass'). Falls back to the first printing."""
    lst = _BN[name]
    for c in lst:
        if all(getattr(c, k) == v for k, v in filt.items()):
            return c
    return lst[0]


def fire(key, ctx):
    return AE.ATTACK_EFFECTS[AE.normalize(key)](ctx)


def mk0(key, **kw):
    """mk() defaulting base=0 — these search attacks print no damage (real dmg=0)."""
    kw.setdefault('base', 0)
    return mk(text=key, **kw)


TESTS = []
def test(fn): TESTS.append(fn); return fn


# ---------------------------------------------------------------- bench-put (Basic)

@test
def t_rotom_bench():
    key = 'You may search your deck for any number of Pokémon that have "Rotom" in their name and put them onto your Bench. Then, shuffle your deck.'
    ctx, at, df, me, opp = mk0(key, my_bench=1)
    me.deck += [('P', card('Rotom')), ('P', card('Rotom'))]
    d = fire(key, ctx)
    assert d == 0
    assert sum(1 for m in me.bench if 'Rotom' in m.card.name) == 2, [m.card.name for m in me.bench]


@test
def t_froakie_bench():
    key = "Search your deck for up to 2 Froakie and put them onto your Bench. Then, shuffle your deck."
    ctx, at, df, me, opp = mk0(key)
    me.deck += [('P', card('Froakie'))] * 3          # only up to 2 should come out
    d = fire(key, ctx)
    assert d == 0 and sum(1 for m in me.bench if m.card.name == 'Froakie') == 2


@test
def t_grubbin_bench():
    key = "Search your deck for up to 2 Grubbin and put them onto your Bench. Then, shuffle your deck."
    ctx, at, df, me, opp = mk0(key)
    me.deck += [('P', card('Grubbin'))] * 2
    d = fire(key, ctx)
    assert d == 0 and sum(1 for m in me.bench if m.card.name == 'Grubbin') == 2


@test
def t_lillies_bench():
    key = "You may search your deck for any number of Basic Lillie's Pokémon and put them onto your Bench. Then, shuffle your deck."
    ctx, at, df, me, opp = mk0(key)
    me.deck += [('P', card("Lillie's Comfey"))] * 2
    d = fire(key, ctx)
    assert d == 0 and sum(1 for m in me.bench if m.card.name.startswith("Lillie's ")) == 2


# ---------------------------------------------------------------- bench-put (Stage-1 direct)

@test
def t_charjabug_bench_stage1():
    key = "Search your deck for up to 3 Charjabug and put them onto your Bench. Then, shuffle your deck."
    ctx, at, df, me, opp = mk0(key, my_bench=0)
    cj = card('Charjabug')
    assert cj.stage == 1                              # sanity: it really is a Stage-1
    me.deck += [('P', cj)] * 3
    d = fire(key, ctx)
    assert d == 0 and sum(1 for m in me.bench if m.card.name == 'Charjabug') == 3


@test
def t_maushold_bench_stage1():
    key = "Search your deck for up to 2 in any combination of Maushold and Maushold ex and put them onto your Bench. Then, shuffle your deck."
    ctx, at, df, me, opp = mk0(key, my_bench=0)
    ms = card('Maushold')
    assert ms.stage == 1
    me.deck += [('P', ms)] * 3
    d = fire(key, ctx)
    assert d == 0 and sum(1 for m in me.bench if m.card.name == 'Maushold') == 2


@test
def t_charjabug_bench_cap():
    # 5-Bench cap respected: start with 4 benched, only 1 Charjabug fits.
    key = "Search your deck for up to 3 Charjabug and put them onto your Bench. Then, shuffle your deck."
    ctx, at, df, me, opp = mk0(key, my_bench=4)
    me.deck += [('P', card('Charjabug'))] * 3
    fire(key, ctx)
    assert len(me.bench) == 5 and sum(1 for m in me.bench if m.card.name == 'Charjabug') == 1


# ---------------------------------------------------------------- search-to-hand

@test
def t_dark_pokemon_hand():
    key = "Search your deck for up to 3 {D} Pokémon, reveal them, and put them into your hand. Then, shuffle your deck."
    ctx, at, df, me, opp = mk0(key)
    me.deck.append(('P', card('Purrloin')))          # a Darkness Pokémon
    d = fire(key, ctx)
    assert d == 0 and any(t[0] == 'P' and t[1].name == 'Purrloin' for t in me.hand)


@test
def t_fire_mix_hand():
    key = "Search your deck for up to 3 in any combination of {R} Pokémon and Basic {R} Energy cards, reveal them, and put them into your hand. Then, shuffle your deck."
    ctx, at, df, me, opp = mk0(key)
    me.deck += [('P', card('Heatmor')), ('E', 'Fire')]
    d = fire(key, ctx)
    assert d == 0
    assert any(t[0] == 'P' and t[1].name == 'Heatmor' for t in me.hand)
    assert ('E', 'Fire') in me.hand


@test
def t_fennel_hand():
    key = "You may search your deck for any number of Fennel cards, reveal them, and put them into your hand. Then, shuffle your deck."
    ctx, at, df, me, opp = mk0(key)
    fennel = {'name': 'Fennel', 'trainerType': 'Item', 'effect': ''}
    me.deck += [('T', fennel), ('T', fennel)]
    d = fire(key, ctx)
    assert d == 0 and sum(1 for t in me.hand if t[0] == 'T' and t[1].get('name') == 'Fennel') == 2


@test
def t_basic_energy_3_hand():
    key = "Search your deck for up to 3 Basic Energy cards, reveal them, and put them into your hand. Then, shuffle your deck."
    ctx, at, df, me, opp = mk0(key)          # deck already has ('E','Colorless') basics
    d = fire(key, ctx)
    assert d == 0 and sum(1 for t in me.hand if t[0] == 'E') == 3


@test
def t_energy_4_hand_includes_special():
    key = "Search your deck for up to 4 Energy cards, reveal them, and put them into your hand. Then, shuffle your deck."
    ctx, at, df, me, opp = mk0(key)
    spec = ('S', {'special_energy': 'Prism Energy'})
    me.deck.append(spec)                         # appended last -> grabbed first
    d = fire(key, ctx)
    assert d == 0
    assert spec in me.hand                        # Special Energy counts as an Energy card
    assert sum(1 for t in me.hand if t[0] in ('E', 'S')) == 4


@test
def t_stadium_hand():
    key = "Search your deck for a Stadium card, reveal it, and put it into your hand. Then, shuffle your deck."
    ctx, at, df, me, opp = mk0(key)
    stad = {'name': 'Town Store', 'trainerType': 'Stadium', 'effect': ''}
    me.deck.append(('T', stad))
    d = fire(key, ctx)
    assert d == 0 and any(t[0] == 'T' and t[1].get('trainerType') == 'Stadium' for t in me.hand)


@test
def t_fighting_resistance_data_gap_noop():
    # No resistance data exists -> the search grabs nothing (never over-grabs arbitrary Pokémon).
    key = "Search your deck for up to 2 Pokémon with {F} Resistance, reveal them, and put them into your hand. Then, shuffle your deck."
    ctx, at, df, me, opp = mk0(key)
    me.deck.append(('P', card('Purrloin')))
    hand_before = len(me.hand)
    d = fire(key, ctx)
    assert d == 0 and len(me.hand) == hand_before   # nothing moved to hand


# ---------------------------------------------------------------- energy accel (attach)

@test
def t_shaymin_accel_benched_grass():
    key = "Search your deck for an Energy card and attach it to 1 of your Benched {G} Pokémon. Then, shuffle your deck."
    ctx, at, df, me, opp = mk0(key)
    grass = card('Shaymin', ptype='Grass')
    me.bench = [Mon(grass)]
    me.deck.append(('E', 'Grass'))
    d = fire(key, ctx)
    assert d == 0 and me.bench[0].energy.get('Grass', 0) == 1
    assert at.energy.get('Grass', 0) == 0            # the Active did NOT get it


@test
def t_shaymin_accel_no_benched_grass_noop():
    key = "Search your deck for an Energy card and attach it to 1 of your Benched {G} Pokémon. Then, shuffle your deck."
    ctx, at, df, me, opp = mk0(key)
    me.bench = [Mon(card('Fletchling'))]          # a Colorless benched Pokémon -> no {G} target
    me.deck.append(('E', 'Grass'))
    grass_in_deck = sum(1 for t in me.deck if t == ('E', 'Grass'))
    d = fire(key, ctx)
    assert d == 0
    assert sum(1 for t in me.deck if t == ('E', 'Grass')) == grass_in_deck   # not pulled
    assert all(m.energy.get('Grass', 0) == 0 for m in me.all_mons())


@test
def t_bewear_self_accel():
    key = "Search your deck for a Basic Energy card and attach it to this Pokémon. Then, shuffle your deck."
    ctx, at, df, me, opp = mk(text=key, base=30)
    before = at.total_energy()
    me.deck.append(('E', 'Grass'))
    d = fire(key, ctx)
    assert d == 30 and at.total_energy() == before + 1
    assert at.energy.get('Grass', 0) == 1


@test
def t_joltik_g2_l2_any():
    key = "Search your deck for up to 2 Basic {G} Energy cards and up to 2 Basic {L} Energy cards and attach them to your Pokémon in any way you like. Then, shuffle your deck."
    ctx, at, df, me, opp = mk0(key)
    me.deck += [('E', 'Grass'), ('E', 'Grass'), ('E', 'Lightning'), ('E', 'Lightning')]
    d = fire(key, ctx)
    assert d == 0
    got = sum(m.energy.get('Grass', 0) + m.energy.get('Lightning', 0) for m in me.all_mons())
    assert got == 4, got


@test
def t_boltund_l2_benched():
    key = "Search your deck for up to 2 Basic {L} Energy cards and attach them to your Benched Pokémon in any way you like. Then, shuffle your deck."
    ctx, at, df, me, opp = mk(text=key, base=50, my_bench=1)
    me.deck += [('E', 'Lightning'), ('E', 'Lightning')]
    d = fire(key, ctx)
    assert d == 50
    assert sum(m.energy.get('Lightning', 0) for m in me.bench) == 2
    assert at.energy.get('Lightning', 0) == 0        # Active is not a valid target


@test
def t_ogerpon_fighting():
    key = "Search your deck for a Basic {F} Energy card and attach it to 1 of your Pokémon. Then, shuffle your deck."
    ctx, at, df, me, opp = mk0(key)
    me.deck.append(('E', 'Fighting'))
    d = fire(key, ctx)
    assert d == 0 and sum(m.energy.get('Fighting', 0) for m in me.all_mons()) == 1


@test
def t_ogerpon_fighting_no_energy_noop():
    key = "Search your deck for a Basic {F} Energy card and attach it to 1 of your Pokémon. Then, shuffle your deck."
    ctx, at, df, me, opp = mk0(key)               # deck has only Colorless basics
    d = fire(key, ctx)
    assert d == 0 and sum(m.energy.get('Fighting', 0) for m in me.all_mons()) == 0


@test
def t_ogerpon_fire():
    key = "Search your deck for a Basic {R} Energy card and attach it to 1 of your Pokémon. Then, shuffle your deck."
    ctx, at, df, me, opp = mk0(key)
    me.deck.append(('E', 'Fire'))
    d = fire(key, ctx)
    assert d == 0 and sum(m.energy.get('Fire', 0) for m in me.all_mons()) == 1


@test
def t_ogerpon_grass():
    key = "Search your deck for a Basic {G} Energy card and attach it to 1 of your Pokémon. Then, shuffle your deck."
    ctx, at, df, me, opp = mk0(key)
    me.deck.append(('E', 'Grass'))
    d = fire(key, ctx)
    assert d == 0 and sum(m.energy.get('Grass', 0) for m in me.all_mons()) == 1


@test
def t_ogerpon_water():
    key = "Search your deck for a Basic {W} Energy card and attach it to 1 of your Pokémon. Then, shuffle your deck."
    ctx, at, df, me, opp = mk0(key)
    me.deck.append(('E', 'Water'))
    d = fire(key, ctx)
    assert d == 0 and sum(m.energy.get('Water', 0) for m in me.all_mons()) == 1


# ---------------------------------------------------------------- evolve-from-deck

@test
def t_evolve_one_of_yours():
    key = "Search your deck for a card that evolves from 1 of your Pokémon and put it onto that Pokémon to evolve it. Then, shuffle your deck."
    ctx, at, df, me, opp = mk0(key)
    me.bench = [Mon(card('Grubbin'))]
    me.bench[0].energy = Counter({'Lightning': 1}); me.bench[0].damage = 20; me.bench[0].turns = 2
    me.deck.append(('P', card('Charjabug')))
    d = fire(key, ctx)
    assert d == 0
    assert me.bench[0].card.name == 'Charjabug'
    assert me.bench[0].energy.get('Lightning', 0) == 1 and me.bench[0].damage == 20  # carried over
    assert not any(t[0] == 'P' and t[1].name == 'Charjabug' for t in me.deck)         # pulled from deck


@test
def t_evolve_noop_when_no_evolution_in_deck():
    key = "Search your deck for a card that evolves from 1 of your Pokémon and put it onto that Pokémon to evolve it. Then, shuffle your deck."
    ctx, at, df, me, opp = mk0(key)
    me.bench = [Mon(card('Grubbin'))]                # Charjabug NOT in deck
    d = fire(key, ctx)
    assert d == 0 and me.bench[0].card.name == 'Grubbin'


# ---------------------------------------------------------------- recycle-self + search

@test
def t_eldegoss_recycle_search3():
    key = "Put this Pokémon and all attached cards into your deck. If you do, search your deck for up to 3 cards and put them into your hand. Then, shuffle your deck."
    ctx, at, df, me, opp = mk0(key, atk_energy={'Grass': 2}, my_bench=1)
    d = fire(key, ctx)
    assert d == 0
    assert at not in me.all_mons()                   # this Pokémon left play
    assert me.active is not None and me.active is not at   # a Bench mon was promoted
    assert len(me.hand) == 3                          # searched up to 3 cards
    assert sum(1 for t in me.hand if t == ('E', 'Grass')) == 2   # its 2 attached Energy came back


@test
def t_eldegoss_recycle_typed_special_no_dup():
    # A typed Special Energy (Growing Grass stamps a real {G} pip into `energy`) must return as
    # exactly ONE card — the special itself — never ALSO a phantom basic {G} Energy (duplication).
    key = "Put this Pokémon and all attached cards into your deck. If you do, search your deck for up to 3 cards and put them into your hand. Then, shuffle your deck."
    ctx, at, df, me, opp = mk0(key, my_bench=1)
    at.energy = Counter({'Grass': 1})            # the single pip Growing Grass provided
    at.special = ['Growing Grass Energy']
    fire(key, ctx)
    allz = me.deck + me.hand                       # everywhere the returned cards could be
    grass_basic = sum(1 for t in allz if t == ('E', 'Grass'))
    gg = sum(1 for t in allz if t[0] == 'S' and t[1].get('special_energy') == 'Growing Grass Energy')
    assert grass_basic == 0, grass_basic          # no phantom basic energy conjured
    assert gg == 1                                # the special energy card returns exactly once


@test
def t_eldegoss_recycle_mixed_basic_and_typed_special():
    # 1 real basic {G} + 1 Growing Grass (both show as {G} pips) -> exactly 1 basic {G} card back
    # plus the 1 special card; the typed-special pip is not double-counted as a basic.
    key = "Put this Pokémon and all attached cards into your deck. If you do, search your deck for up to 3 cards and put them into your hand. Then, shuffle your deck."
    ctx, at, df, me, opp = mk0(key, my_bench=1)
    at.energy = Counter({'Grass': 2})            # one basic {G} pip + one Growing Grass {G} pip
    at.special = ['Growing Grass Energy']
    fire(key, ctx)
    allz = me.deck + me.hand
    assert sum(1 for t in allz if t == ('E', 'Grass')) == 1      # only the genuine basic returns
    assert sum(1 for t in allz if t[0] == 'S') == 1              # + the special, once


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
