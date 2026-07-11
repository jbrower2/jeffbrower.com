#!/usr/bin/env python3
"""Unit tests for effect batch status_0 (Special Conditions + condition-gated damage).

mk() defaults: base=50, game.turn=3, heads=0.0/tails=0.9, opp_prizes=my_prizes=6,
attacker/defender = VANILLA (Bulbasaur, one 10-dmg attack 'Bind Down'), atk_energy={'Colorless':3},
def_energy={'Colorless':2}, def_special=(), me/opp hands empty, my_bench=opp_bench=1.
ctx.status() respects the Mist/Rocky/Bubbly effect-shield via Mon.effect_immune().
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # ensure sim/ importable
from effects_testkit import mk, run, runner
import attack_effects as AE
import effects_gen.batch_status_0  # noqa: F401  (registers the effects)


def _fn(text):
    return AE.ATTACK_EFFECTS[AE.normalize(text)]


def _dmg_with_status(key, base, kind, present):
    """Resolve `key` with the defender's Active carrying (or not) Special Condition `kind`."""
    ctx, at, df, me, opp = mk(base=base, text=key)
    if present:
        df.status[kind] = True
    return _fn(key)(ctx)


# ---------------------------------------------------------------- single condition (opponent Active)
def t_burn():
    d, ctx, at, df, me, opp = run("Your opponent's Active Pokémon is now Burned.", base=20)
    assert d == 20 and df.status.get('Burned'), (d, df.status)


def t_burn_shielded():
    # Bubbly Water on the defender blocks the condition (effect_immune) -> Burned does not land.
    d, ctx, at, df, me, opp = run("Your opponent's Active Pokémon is now Burned.", base=20,
                                  def_special=('Bubbly Water Energy',))
    assert d == 20 and not df.status.get('Burned'), (d, df.status)


# ---------------------------------------------------------------- single condition (self)
def t_self_confuse():
    d, ctx, at, df, me, opp = run("This Pokémon is now Confused.", base=130)
    assert d == 130 and at.status.get('Confused') and not df.status.get('Confused'), (d, at.status, df.status)


def t_self_sleep():
    d, ctx, at, df, me, opp = run("This Pokémon is now Asleep.", base=160)
    assert d == 160 and at.status.get('Asleep') and not df.status.get('Asleep'), (d, at.status)


def t_self_sleep_heal30():
    key = "This Pokémon is now Asleep. Heal 30 damage from it."
    ctx, at, df, me, opp = mk(base=0, text=key)
    at.damage = 50
    d = _fn(key)(ctx)
    assert d == 0 and at.status.get('Asleep') and at.damage == 20, (d, at.status, at.damage)


# ---------------------------------------------------------------- combined conditions (opponent Active)
def t_burn_confuse():
    d, ctx, at, df, me, opp = run("Your opponent's Active Pokémon is now Burned and Confused.", base=90)
    assert d == 90 and df.status.get('Burned') and df.status.get('Confused'), (d, df.status)


def t_sleep_poison():
    d, ctx, at, df, me, opp = run("Your opponent's Active Pokémon is now Asleep and Poisoned.", base=100)
    assert d == 100 and df.status.get('Asleep') and df.status.get('Poisoned'), (d, df.status)


def t_burn_confuse_poison():
    key = "Your opponent's Active Pokémon is now Burned, Confused, and Poisoned."
    d, ctx, at, df, me, opp = run(key, base=0)
    assert d == 0 and df.status.get('Burned') and df.status.get('Confused') and df.status.get('Poisoned'), df.status


# ---------------------------------------------------------------- condition + can't-retreat rider
def t_confuse_noretreat():
    key = ("Your opponent's Active Pokémon is now Confused. During your opponent's next turn, "
           "that Pokémon can't retreat.")
    d, ctx, at, df, me, opp = run(key, base=80)
    assert d == 80 and df.status.get('Confused') and 'CantRetreat' in df.status, (d, df.status)


def t_poison_noretreat_that():
    key = ("Your opponent's Active Pokémon is now Poisoned. During your opponent's next turn, "
           "that Pokémon can't retreat.")
    d, ctx, at, df, me, opp = run(key, base=50)
    assert d == 50 and df.status.get('Poisoned') and 'CantRetreat' in df.status, (d, df.status)


def t_poison_noretreat_defending():
    key = ("Your opponent's Active Pokémon is now Poisoned. During your opponent's next turn, "
           "the Defending Pokémon can't retreat.")
    d, ctx, at, df, me, opp = run(key, base=0)
    assert d == 0 and df.status.get('Poisoned') and 'CantRetreat' in df.status, (d, df.status)


def t_burn_noretreat():
    key = ("Your opponent's Active Pokémon is now Burned. During your opponent's next turn, "
           "that Pokémon can't retreat.")
    d, ctx, at, df, me, opp = run(key, base=50)
    assert d == 50 and df.status.get('Burned') and 'CantRetreat' in df.status, (d, df.status)


# ---------------------------------------------------------------- discard-energy / recoil + condition
def t_discardall_paralyze():
    key = "Discard all Energy from this Pokémon. Your opponent's Active Pokémon is now Paralyzed."
    ctx, at, df, me, opp = mk(base=70, text=key, atk_energy={'Water': 2, 'Fire': 1})
    assert at.total_energy() == 3
    d = _fn(key)(ctx)
    assert d == 70 and at.total_energy() == 0 and df.status.get('Paralyzed'), (d, at.total_energy(), df.status)
    assert me.disc_energy['Water'] == 2 and me.disc_energy['Fire'] == 1, dict(me.disc_energy)


def t_self70_paralyze_poison():
    key = ("This Pokémon also does 70 damage to itself. Your opponent's Active Pokémon is now "
           "Paralyzed and Poisoned.")
    d, ctx, at, df, me, opp = run(key, base=100)
    assert d == 100 and at.damage == 70, (d, at.damage)
    assert df.status.get('Paralyzed') and df.status.get('Poisoned'), df.status


# ---------------------------------------------------------------- self-switch + condition
def t_confuse_poison_selfswitch():
    key = ("Your opponent's Active Pokémon is now Confused and Poisoned. Switch this Pokémon with "
           "1 of your Benched Pokémon.")
    ctx, at, df, me, opp = mk(base=70, text=key, my_bench=1)
    benched = me.bench[0]
    d = _fn(key)(ctx)
    assert d == 70 and df.status.get('Confused') and df.status.get('Poisoned'), (d, df.status)
    assert me.active is benched and me.active is not at and at in me.bench, (me.active is benched, at in me.bench)


def t_confuse_poison_selfswitch_no_bench():
    key = ("Your opponent's Active Pokémon is now Confused and Poisoned. Switch this Pokémon with "
           "1 of your Benched Pokémon.")
    ctx, at, df, me, opp = mk(base=70, text=key, my_bench=0)
    d = _fn(key)(ctx)
    assert d == 70 and me.active is at, (d, me.active is at)   # empty bench -> no switch, no crash
    assert df.status.get('Confused') and df.status.get('Poisoned'), df.status


def t_confuse_poison_selfswitch_readiest():
    # With multiple benched Pokémon the self-switch promotes the READIEST attacker (most energy, then
    # HP — engine.Player.promote's ordering), not simply bench[0].
    key = ("Your opponent's Active Pokémon is now Confused and Poisoned. Switch this Pokémon with "
           "1 of your Benched Pokémon.")
    ctx, at, df, me, opp = mk(base=70, text=key, my_bench=2)
    me.bench[1].energy['Water'] = 2               # make the 2nd benched Pokémon the readiest (most energy)
    ready = me.bench[1]
    d = _fn(key)(ctx)
    assert d == 70 and me.active is ready and at in me.bench, (d, me.active is ready, at in me.bench)
    assert df.status.get('Confused') and df.status.get('Poisoned'), df.status


# ---------------------------------------------------------------- heavy poison / heavy confusion
def t_heavy_poison_2():
    key = ("Your opponent's Active Pokémon is now Poisoned. During Pokémon Checkup, put 2 damage "
           "counters on that Pokémon instead of 1.")
    d, ctx, at, df, me, opp = run(key, base=120)
    assert d == 120 and df.status.get('Poisoned') and df.poison_amt == 20, (d, df.status, df.poison_amt)
    # shielded: poison never lands, so the checkup override is NOT applied (stays default 10)
    d2, ctx2, at2, df2, me2, opp2 = run(key, base=120, def_special=('Bubbly Water Energy',))
    assert not df2.status.get('Poisoned') and df2.poison_amt == 10, (df2.status, df2.poison_amt)


def t_heavy_confuse_8():
    key = ("Your opponent's Active Pokémon is now Confused. Put 8 damage counters instead of 3 on "
           "that Pokémon for this Special Condition.")
    d, ctx, at, df, me, opp = run(key, base=0)
    assert d == 0 and df.status.get('Confused') and getattr(df, 'confuse_amt', None) == 80, (d, df.status)


# ---------------------------------------------------------------- next-turn offense buff (Komala)
def t_slumbering_smack():
    key = ("Both Active Pokémon are now Asleep. During your next turn, attacks used by this Pokémon "
           "do 100 more damage to your opponent's Active Pokémon (before applying Weakness and Resistance).")
    d, ctx, at, df, me, opp = run(key, base=30)
    assert d == 30 and at.status.get('Asleep') and df.status.get('Asleep'), (d, at.status, df.status)
    assert at.ramp.get('TestAtk') == 100, at.ramp                # +100 lands on the attack it will reuse
    assert all(at.ramp.get(a['name']) == 100 for a in at.card.attacks), at.ramp  # "attacks" (plural): every card attack buffed
    assert not df.ramp, df.ramp                                  # buff is attacker-only — the opponent never gets ramp
    # flat, not accumulating: a second resolution keeps it at 100 (no sleep-loop runaway)
    _fn(key)(ctx)
    assert at.ramp.get('TestAtk') == 100, at.ramp


# ---------------------------------------------------------------- spread + condition (Frosmoth)
def t_frosmoth_powder_snow():
    key = ("This attack does 20 damage to each of your opponent's Pokémon. (Don't apply Weakness and "
           "Resistance for Benched Pokémon.) Your opponent's Active Pokémon is now Asleep.")
    ctx, at, df, me, opp = mk(base=0, text=key, opp_bench=2)
    d = _fn(key)(ctx)
    assert d == 20 and df.status.get('Asleep'), (d, df.status)   # 20 to Active returned (engine applies Weakness)
    assert df.damage == 0, df.damage                             # effect must NOT self-apply the Active's 20 (engine does) nor let the bench spread hit the Active
    assert len(opp.bench) == 2 and all(b.damage == 20 for b in opp.bench), [b.damage for b in opp.bench]


# ---------------------------------------------------------------- condition-gated: does-nothing
def t_only_if_burned():
    key = "If your opponent's Active Pokémon isn't Burned, this attack does nothing."
    assert run(key, base=110)[0] == 0                            # not Burned -> nothing
    assert _dmg_with_status(key, 110, 'Burned', True) == 110     # Burned -> full


# ---------------------------------------------------------------- condition-gated: bonus damage
def t_plus50_if_poisoned():
    key = "If your opponent's Active Pokémon is Poisoned, this attack does 50 more damage."
    assert _dmg_with_status(key, 30, 'Poisoned', True) == 80
    assert _dmg_with_status(key, 30, 'Poisoned', False) == 30
    assert _dmg_with_status(key, 30, 'Burned', True) == 30       # a different condition must NOT trigger the Poison bonus


def t_plus60_if_poisoned():
    key = "If your opponent's Active Pokémon is Poisoned, this attack does 60 more damage."
    assert _dmg_with_status(key, 30, 'Poisoned', True) == 90
    assert _dmg_with_status(key, 30, 'Poisoned', False) == 30


def t_plus90_if_poisoned():
    key = "If your opponent's Active Pokémon is Poisoned, this attack does 90 more damage."
    assert _dmg_with_status(key, 90, 'Poisoned', True) == 180
    assert _dmg_with_status(key, 90, 'Poisoned', False) == 90


def t_plus100_if_poisoned():
    key = "If your opponent's Active Pokémon is Poisoned, this attack does 100 more damage."
    assert _dmg_with_status(key, 30, 'Poisoned', True) == 130
    assert _dmg_with_status(key, 30, 'Poisoned', False) == 30


def t_plus40_if_burned():
    key = "If your opponent's Active Pokémon is Burned, this attack does 40 more damage."
    assert _dmg_with_status(key, 10, 'Burned', True) == 50
    assert _dmg_with_status(key, 10, 'Burned', False) == 10
    # Poison on the defender must NOT trigger the Burn bonus
    assert _dmg_with_status(key, 10, 'Poisoned', True) == 10


# ---------------------------------------------------------------- prize-gated condition (Togedemaru)
def t_paralyze_if_1_prize():
    key = "If you have exactly 1 Prize card remaining, your opponent's Active Pokémon is now Paralyzed."
    d, ctx, at, df, me, opp = run(key, base=30, my_prizes=1)
    assert d == 30 and df.status.get('Paralyzed'), (d, df.status)
    d2, ctx2, at2, df2, me2, opp2 = run(key, base=30, my_prizes=6)
    assert d2 == 30 and not df2.status.get('Paralyzed'), (d2, df2.status)
    d3, ctx3, at3, df3, me3, opp3 = run(key, base=30, my_prizes=2)   # 2 remaining also does not fire
    assert not df3.status.get('Paralyzed'), df3.status


# ---------------------------------------------------------------- tool discard -> conditional Paralysis
def t_tool_strip_paralyze():
    key = ("Before doing damage, discard all Pokémon Tools from your opponent's Active Pokémon. If you "
           "discarded a Pokémon Tool in this way, your opponent's Active Pokémon is now Paralyzed.")
    # no Tool on the defender -> nothing discarded -> no Paralysis
    d, ctx, at, df, me, opp = run(key, base=30)
    assert d == 30 and df.tools == [] and not df.status.get('Paralyzed'), (d, df.tools, df.status)
    # Tool attached -> stripped, and because a Tool WAS discarded the defender is now Paralyzed
    d2, ctx2, at2, df2, me2, opp2 = run(key, base=30, def_tools=['Lucky Helmet'])
    assert d2 == 30 and df2.tools == [] and df2.status.get('Paralyzed'), (d2, df2.tools, df2.status)


# ---------------------------------------------------------------- energy-attach lock rider (Glimmora)
def t_poison_no_energy_attach():
    key = ("Your opponent's Active Pokémon is now Poisoned. During your opponent's next turn, Energy "
           "cards can't be attached from your opponent's hand to that Pokémon.")
    d, ctx, at, df, me, opp = run(key, base=20)
    assert d == 20 and df.status.get('Poisoned'), (d, df.status)
    assert getattr(df, 'no_energy_attach_until', None) == ctx.game.turn + 1, getattr(df, 'no_energy_attach_until', None)


TESTS = [
    t_burn,
    t_burn_shielded,
    t_self_confuse,
    t_self_sleep,
    t_self_sleep_heal30,
    t_burn_confuse,
    t_sleep_poison,
    t_burn_confuse_poison,
    t_confuse_noretreat,
    t_poison_noretreat_that,
    t_poison_noretreat_defending,
    t_burn_noretreat,
    t_discardall_paralyze,
    t_self70_paralyze_poison,
    t_confuse_poison_selfswitch,
    t_confuse_poison_selfswitch_no_bench,
    t_confuse_poison_selfswitch_readiest,
    t_heavy_poison_2,
    t_heavy_confuse_8,
    t_slumbering_smack,
    t_frosmoth_powder_snow,
    t_only_if_burned,
    t_plus50_if_poisoned,
    t_plus60_if_poisoned,
    t_plus90_if_poisoned,
    t_plus100_if_poisoned,
    t_plus40_if_burned,
    t_paralyze_if_1_prize,
    t_tool_strip_paralyze,
    t_poison_no_energy_attach,
]

if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
