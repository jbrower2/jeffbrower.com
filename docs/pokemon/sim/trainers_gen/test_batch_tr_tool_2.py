# -*- coding: utf-8 -*-
"""Unit tests for trainer batch tr_tool_2 (Pokémon Tools)."""
from effects_testkit import mk, runner
import trainer_effects as TE
import trainers_gen.batch_tr_tool_2          # noqa: F401  (registers the effects)
from cards import Card
from engine import Mon

# EXACT registration text (straight apostrophe, standard é).
THICK_SCALE = ("The {N} Pokémon this card is attached to takes 50 less damage from attacks from "
               "your opponent's {G}, {R}, {W}, or {L} Pokémon (after applying Weakness and Resistance).")


def fn(text):
    return TE.TRAINER_EFFECTS[TE.normalize(text)]['fn']


def _mkmon(ptype, hp=130):
    """A bare Mon of a chosen on-card type, for driving the tool_dr hook directly."""
    c = Card.__new__(Card)
    c.name = ptype + ' TestMon'; c.set = 'X'; c.id = '0'; c.cat = 'cat-green'; c.price = 0.0
    c.is_ex = False; c.energy = []; c.hp = hp; c.stage = 0; c.evolves_from = None
    c.ptype = ptype; c.weakness = None; c.retreat = 1; c.attacks = []; c.abilities = []
    return Mon(c)


TESTS = []
def test(f): TESTS.append(f); return f


@test
def t_thick_scale_reduces_vs_water():
    # Dragon holder, Water attacker: 100 -> 50 (-50).
    ctx, at, df, me, opp = mk()
    holder = _mkmon('Dragon')
    assert fn(THICK_SCALE)(100, _mkmon('Water'), holder, opp, ctx.game) == 50


@test
def t_thick_scale_all_four_trigger_types():
    # Each of {G}/{R}/{W}/{L} triggers the -50 on a Dragon holder.
    ctx, at, df, me, opp = mk()
    holder = _mkmon('Dragon')
    for typ in ('Grass', 'Fire', 'Water', 'Lightning'):
        assert fn(THICK_SCALE)(80, _mkmon(typ), holder, opp, ctx.game) == 30, typ


@test
def t_thick_scale_floors_at_zero():
    # 40 damage - 50 reduction never goes negative.
    ctx, at, df, me, opp = mk()
    holder = _mkmon('Dragon')
    assert fn(THICK_SCALE)(40, _mkmon('Fire'), holder, opp, ctx.game) == 0


@test
def t_thick_scale_wrong_attacker_type_unaffected():
    # Non-{G/R/W/L} attackers deal full damage even to a Dragon holder.
    ctx, at, df, me, opp = mk()
    holder = _mkmon('Dragon')
    for typ in ('Psychic', 'Fighting', 'Darkness', 'Metal', 'Colorless'):
        assert fn(THICK_SCALE)(100, _mkmon(typ), holder, opp, ctx.game) == 100, typ


@test
def t_thick_scale_non_dragon_holder_never_fires():
    # Attached to a non-Dragon Pokémon: no reduction, even from a Water attacker.
    ctx, at, df, me, opp = mk()
    for holder_type in ('Water', 'Metal', 'Colorless'):
        holder = _mkmon(holder_type)
        assert fn(THICK_SCALE)(100, _mkmon('Water'), holder, opp, ctx.game) == 100, holder_type


@test
def t_thick_scale_no_attacker_conservative_noop():
    # No identifiable attacker -> leave damage unchanged rather than firing blind.
    ctx, at, df, me, opp = mk()
    holder = _mkmon('Dragon')
    assert fn(THICK_SCALE)(100, None, holder, opp, ctx.game) == 100


@test
def t_thick_scale_registered_as_tool_dr():
    assert TE.TRAINER_EFFECTS[TE.normalize(THICK_SCALE)]['kind'] == 'tool_dr'


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
