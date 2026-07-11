#!/usr/bin/env python3
"""Unit tests for the trainer registry proof batch. Item/Supporter/Stadium actions run through a
TrainerCtx over real Player/Game objects; Tool effects are exercised via their hook signature."""
from effects_testkit import mk, runner
import trainer_effects as TE


def action(text, **kw):
    ctx, at, df, me, opp = mk(**kw)
    e = TE.TRAINER_EFFECTS[TE.normalize(text)]
    return e['fn'](TE.TrainerCtx(me, opp, ctx.game)), me, opp, at, df


TESTS = []
def test(f): TESTS.append(f); return f


@test
def t_draw3():
    did, me, *_ = action("- Draw 3 cards.")
    assert did and len(me.hand) == 3


@test
def t_iono():
    did, me, opp, *_ = action("- Each player shuffles their hand into their deck. Then, you draw 5 cards and your opponent draws 4 cards.")
    assert did and len(me.hand) == 5 and len(opp.hand) == 4


@test
def t_potion():
    ctx, at, df, me, opp = mk()
    at.damage = 50
    TE.TRAINER_EFFECTS[TE.normalize("- Heal 30 damage from 1 of your Pokémon.")]['fn'](TE.TrainerCtx(me, opp, ctx.game))
    assert at.damage == 20


@test
def t_pokeball():
    did, me, *_ = action("- Search your deck for a Pokémon, reveal it, and put it into your hand. Then, shuffle your deck.")
    assert did and any(t[0] == 'P' for t in me.hand)


@test
def t_tool_hp():
    ctx, at, df, me, opp = mk()
    f = TE.TRAINER_EFFECTS[TE.normalize("- The Pokémon this card is attached to gets +20 HP.")]['fn']
    assert f(at, me, ctx.game) == 20


@test
def t_tool_dr():
    ctx, at, df, me, opp = mk()
    f = TE.TRAINER_EFFECTS[TE.normalize("- The Pokémon this Pokémon Tool is attached to takes 30 less damage from attacks from your opponent's Pokémon (after applying Weakness and Resistance).")]['fn']
    assert f(100, at, df, opp, ctx.game) == 70


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f"{p} passed, {f} failed  ({len(TE.TRAINER_EFFECTS)} trainer effects registered)")
    raise SystemExit(1 if f else 0)
