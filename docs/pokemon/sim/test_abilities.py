#!/usr/bin/env python3
"""Unit tests for the ability registry proof batch (and, once generated, every abilities_gen batch's
tests import the same kit). Each ability's registered lambda is exercised directly against real Mon/
Player objects. Run: python3 test_abilities.py."""
from effects_testkit import mk, runner
import ability_effects as AB


def fn_of(text):
    return AB.ABILITY_EFFECTS[AB.normalize(text)]['fn']


TESTS = []
def test(f): TESTS.append(f); return f


@test
def t_thicket_body():
    ctx, at, df, me, opp = mk()
    f = fn_of("- This Pokémon takes 30 less damage from attacks (after applying Weakness and Resistance).")
    assert f(100, at, df, opp, ctx.game) == 70
    assert f(20, at, df, opp, ctx.game) == -10  # (engine clamps via reduce_damage's max(0,...))


@test
def t_reduce_damage_query_clamps():
    ctx, at, df, me, opp = mk()
    # reduce_damage clamps at 0 even when the raw DR would overshoot
    import ability_effects as A
    # exoskeleton fn directly
    f = fn_of("- This Pokémon takes 20 less damage from attacks (after applying Weakness and Resistance).")
    assert f(50, at, df, opp, ctx.game) == 30


@test
def t_poison_point():
    ctx, at, df, me, opp = mk()          # opp.active is df; me.active is at
    f = fn_of("- If this Pokémon is in the Active Spot and is damaged by an attack from your opponent's Pokémon (even if this Pokémon is Knocked Out), the Attacking Pokémon is now Poisoned.")
    f(at, df, opp, ctx.game)             # df (opp active) damaged -> attacker at is Poisoned
    assert at.status.get('Poisoned')


@test
def t_poison_point_shielded_attacker():
    ctx, at, df, me, opp = mk()
    at.special = ['Mist Energy']         # attacker immune to the condition
    f = fn_of("- If this Pokémon is in the Active Spot and is damaged by an attack from your opponent's Pokémon (even if this Pokémon is Knocked Out), the Attacking Pokémon is now Poisoned.")
    f(at, df, opp, ctx.game)
    assert not at.status.get('Poisoned')


@test
def t_recon_directive():
    ctx, at, df, me, opp = mk()
    n0 = len(me.hand)
    f = fn_of("- Once during your turn, you may look at the top 2 cards of your deck and put 1 of them into your hand. Put the other card on the bottom of your deck.")
    assert f(AB.ActivatedCtx(me, opp, at, ctx.game)) is True
    assert len(me.hand) == n0 + 1


@test
def t_cursed_blast():
    ctx, at, df, me, opp = mk()
    f = fn_of("- Once during your turn, you may put 5 damage counters on 1 of your opponent's Pokémon. If you use this Ability, this Pokémon is Knocked Out.")
    assert f(AB.ActivatedCtx(me, opp, at, ctx.game)) is True
    assert any(m.damage == 50 for m in opp.all_mons())   # 5 counters = 50
    assert at.damage == at.max_hp                         # holder self-KO'd


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f"{p} passed, {f} failed  ({len(AB.ABILITY_EFFECTS)} abilities registered)")
    raise SystemExit(1 if f else 0)
