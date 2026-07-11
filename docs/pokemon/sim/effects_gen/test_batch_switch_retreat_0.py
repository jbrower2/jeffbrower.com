#!/usr/bin/env python3
"""Unit tests for batch switch_retreat_0. Each effect is exercised against real engine Mon/Player
objects (scripted RNG), asserting the returned damage AND the key state change, covering both branches
(switch fires / doesn't, condition met / unmet) where relevant.
Run: python3 effects_gen/test_batch_switch_retreat_0.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # ensure sim/ importable
from collections import Counter
from effects_testkit import mk, run, runner
import attack_effects as AE
import effects_gen.batch_switch_retreat_0        # registers this batch's effects
import effects
from engine import Mon
from cards import load_cards

BK, BN = load_cards()
LIGHT = next(c for c in BK.values() if c.ptype == 'Lightning' and c.stage == 0)   # a benched {L} target
WEAKG = next(c for c in BK.values() if c.stage == 0 and c.weakness == 'Grass')     # a Grass-weak basic (Weakness ×2)

# --- exact registry keys under test ---
SELF_ANY   = "Switch this Pokémon with 1 of your Benched Pokémon."
SELF_L     = "Switch this Pokémon with 1 of your Benched {L} Pokémon."
GUST_ONLY  = "Switch in 1 of your opponent's Benched Pokémon to the Active Spot."
GUST_20    = "Switch in 1 of your opponent's Benched Pokémon to the Active Spot. This attack does 20 damage to the new Active Pokémon."
GUST_30    = "Switch in 1 of your opponent's Benched Pokémon to the Active Spot. This attack does 30 damage to the new Active Pokémon."
GUST_40    = "Switch in 1 of your opponent's Benched Pokémon to the Active Spot. This attack does 40 damage to the new Active Pokémon."
GUST_70    = "Switch in 1 of your opponent's Benched Pokémon to the Active Spot. This attack does 70 damage to the new Active Pokémon."
XEROSIC    = "Switch in 1 of your opponent's Benched Pokémon to the Active Spot. If you do, this attack does 120 damage to the new Active Pokémon. If you didn't play Xerosic's Machinations from your hand during this turn, this attack does nothing."
MAY_OUT    = "You may switch out your opponent's Active Pokémon to the Bench. (Your opponent chooses the new Active Pokémon.)"
IRON_BUNDLE = "Switch this Pokémon with 1 of your Benched Pokémon. If you do, switch out your opponent's Active Pokémon to the Bench. (Your opponent chooses the new Active Pokémon.)"
STUNFISK   = "During your opponent's next turn, the Defending Pokémon can't retreat. During your next turn, the Defending Pokémon takes 100 more damage from attacks (after applying Weakness and Resistance)."


def call(text, ctx):
    return AE.ATTACK_EFFECTS[AE.normalize(text)](ctx)


TESTS = []
def test(fn): TESTS.append(fn); return fn


# ---------------------------------------------------------------- self-pivot
@test
def t_switch_self_any_fires():
    ctx, at, df, me, opp = mk(base=30, text=SELF_ANY, my_bench=1)
    benched = me.bench[0]
    d = call(SELF_ANY, ctx)
    assert d == 30, d                       # printed damage to opponent's Active
    assert me.active is benched, "benched mon should be promoted"
    assert at in me.bench, "attacker should be sent to the bench"
    assert opp.active is df, "opponent's Active must be untouched by a SELF switch"


@test
def t_switch_self_any_no_bench():
    ctx, at, df, me, opp = mk(base=30, text=SELF_ANY, my_bench=0)
    d = call(SELF_ANY, ctx)
    assert d == 30 and me.active is at, (d, me.active is at)   # no bench -> no switch, still deals base


@test
def t_switch_self_lightning_fires_only_on_L():
    # Lightning bench mon -> eligible, switch happens
    ctx, at, df, me, opp = mk(base=90, text=SELF_L, my_bench=0)
    me.bench = [Mon(LIGHT)]
    lmon = me.bench[0]
    d = call(SELF_L, ctx)
    assert d == 90 and me.active is lmon, (d, me.active.card.name)


@test
def t_switch_self_lightning_skips_non_L():
    # default bench mon is Grass (Bulbasaur) -> not an eligible {L} target -> no switch, still 90
    ctx, at, df, me, opp = mk(base=90, text=SELF_L, my_bench=1)
    d = call(SELF_L, ctx)
    assert d == 90 and me.active is at, (d, me.active is at)


# ---------------------------------------------------------------- gust (attacker chooses)
@test
def t_gust_only():
    ctx, at, df, me, opp = mk(base=0, text=GUST_ONLY, opp_bench=1)
    benched = opp.bench[0]
    d = call(GUST_ONLY, ctx)
    assert d == 0, d
    assert opp.active is benched, "benched opponent mon dragged into Active"
    assert df in opp.bench, "old Active pushed to the Bench"


@test
def t_gust_only_no_bench():
    ctx, at, df, me, opp = mk(base=0, text=GUST_ONLY, opp_bench=0)
    d = call(GUST_ONLY, ctx)
    assert d == 0 and opp.active is df, (d, opp.active is df)   # nothing to drag up


def _gust_dmg_case(text, amount):
    ctx, at, df, me, opp = mk(base=0, text=text, opp_bench=1)
    benched = opp.bench[0]
    d = call(text, ctx)
    # return value is 0 (damage is applied inline to the NEW Active, not the returned defender)
    assert d == 0, (text, d)
    assert opp.active is benched, (text, "gust must promote the benched mon")
    # attacker is Grass, benched is Fire-weak Bulbasaur -> no Weakness -> exactly `amount`
    assert opp.active.damage == amount, (text, opp.active.damage, amount)
    assert df in opp.bench and df.damage == 0, (text, "old Active benched, undamaged")


@test
def t_gust_dmg_20(): _gust_dmg_case(GUST_20, 20)
@test
def t_gust_dmg_30(): _gust_dmg_case(GUST_30, 30)
@test
def t_gust_dmg_40(): _gust_dmg_case(GUST_40, 40)
@test
def t_gust_dmg_70(): _gust_dmg_case(GUST_70, 70)


@test
def t_gust_dmg_no_bench_hits_unchanged_active():
    # No opponent bench -> no switch, but the fixed damage still lands on the (unchanged) Active.
    ctx, at, df, me, opp = mk(base=0, text=GUST_30, opp_bench=0)
    d = call(GUST_30, ctx)
    assert d == 0 and opp.active is df and df.damage == 30, (d, opp.active is df, df.damage)


@test
def t_gust_dmg_applies_weakness_to_new_active():
    # New Active is weak to the attacker's (Grass) type -> the printed N doubles on the promoted mon.
    # Exercises the ONLY Weakness ×2 path in _damage_active (every other gust test uses a non-weak target).
    ctx, at, df, me, opp = mk(base=0, text=GUST_30, opp_bench=0)
    opp.bench = [Mon(WEAKG)]                             # a Grass-weak basic to drag up
    wk = opp.bench[0]
    assert wk.card.weakness == at.card.ptype == 'Grass', (wk.card.weakness, at.card.ptype)
    d = call(GUST_30, ctx)
    assert d == 0, d
    assert opp.active is wk, "grass-weak mon gusted into the Active Spot"
    assert opp.active.damage == 60, opp.active.damage   # 30 doubled by Weakness
    assert df in opp.bench and df.damage == 0, "old Active benched, undamaged"


@test
def t_xerosic_gated_on_played_trainer():
    # Did NOT play Xerosic's Machinations this turn -> "this attack does nothing": no switch, no damage.
    ctx, at, df, me, opp = mk(base=0, text=XEROSIC, opp_bench=1)
    d = call(XEROSIC, ctx)
    assert d == 0, d
    assert opp.active is df, "no switch"
    assert df.damage == 0 and all(b.damage == 0 for b in opp.bench), "no damage anywhere"
    # Played Xerosic's Machinations from hand this turn -> gust up the benched mon and deal 120 to it.
    ctx2, at2, df2, me2, opp2 = mk(base=0, text=XEROSIC, opp_bench=1, played=["Xerosic's Machinations"])
    benched = opp2.bench[0]
    d2 = call(XEROSIC, ctx2)
    assert d2 == 0, d2                                   # 120 is applied inline to the NEW Active
    assert opp2.active is benched, "benched mon gusted into the Active Spot"
    assert opp2.active.damage == 120, opp2.active.damage
    assert df2 in opp2.bench and df2.damage == 0, "old Active benched, undamaged"


# ---------------------------------------------------------------- opponent-chosen switch-out
@test
def t_may_switch_out_fires_when_downgrading():
    # default: Active has 2 energy, bench mon has 0 -> switching downgrades their Active -> do it
    ctx, at, df, me, opp = mk(base=20, text=MAY_OUT, opp_bench=1)
    d = call(MAY_OUT, ctx)
    assert d == 20 and opp.active is not df, (d, opp.active is df)


@test
def t_may_switch_out_skips_when_no_gain():
    # bench mon MORE charged than the Active -> switching would upgrade their Active -> decline
    ctx, at, df, me, opp = mk(base=20, text=MAY_OUT, opp_bench=1)
    opp.bench[0].energy = Counter({'Colorless': 5})
    d = call(MAY_OUT, ctx)
    assert d == 20 and opp.active is df, (d, opp.active is df)


# ---------------------------------------------------------------- Iron Bundle: self-pivot + gate
@test
def t_iron_bundle_both_switches():
    ctx, at, df, me, opp = mk(base=60, text=IRON_BUNDLE, my_bench=1, opp_bench=1)
    my_benched = me.bench[0]
    d = call(IRON_BUNDLE, ctx)
    assert d == 60, d
    assert me.active is my_benched, "attacker pivoted to our bench mon"
    assert opp.active is not df, "opponent's Active bumped after a successful self-switch"


@test
def t_iron_bundle_gate_no_self_bench():
    # "If you do" -> no self-switch (no bench) means the opponent's Active is NOT switched out either.
    ctx, at, df, me, opp = mk(base=60, text=IRON_BUNDLE, my_bench=0, opp_bench=1)
    d = call(IRON_BUNDLE, ctx)
    assert d == 60 and me.active is at and opp.active is df, (d, me.active is at, opp.active is df)


# ---------------------------------------------------------------- Stunfisk: trap + vulnerability
@test
def t_stunfisk_marks_trap_and_vulnerability():
    ctx, at, df, me, opp = mk(base=30, text=STUNFISK)
    d = call(STUNFISK, ctx)
    assert d == 30, d
    assert 'CantRetreat' in df.status, "defender locked in next turn"
    assert df.dr_amount == -100, df.dr_amount
    assert df.dr_turn == ctx.game.turn + 1, (df.dr_turn, ctx.game.turn)


@test
def t_stunfisk_extra_100_only_on_attacker_next_turn():
    ctx, at, df, me, opp = mk(base=30, text=STUNFISK)
    call(STUNFISK, ctx)
    g = ctx.game
    # opponent's in-between turn (dr_turn, i.e. game.turn+1): debuff NOT yet live
    g.turn = df.dr_turn
    assert effects.incoming_damage(200, at, df, opp, g) == 200, "no bonus on the opponent's turn"
    # attacker's next turn (dr_turn+1 == game.turn+2): +100 applies, after Weakness
    g.turn = df.dr_turn + 1
    assert effects.incoming_damage(200, at, df, opp, g) == 300, "defender takes 100 more"
    # and it lapses afterward
    g.turn = df.dr_turn + 2
    assert effects.incoming_damage(200, at, df, opp, g) == 200, "one-turn only"


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
