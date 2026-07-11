#!/usr/bin/env python3
"""Unit tests for batch heal_0. Asserts returned Active damage AND the key state change
(self-heal, one-of-mine / each-of-mine heal, typed & Ancient bench heal, attach-then-heal,
heal + self can't-retreat, and the healed-this-turn damage rider). Covers both branches."""
from collections import Counter
from effects_testkit import mk, run, runner
import attack_effects as AE
import effects_gen.batch_heal_0  # noqa: F401  (registers the effects)
from engine import Mon
from cards import load_cards

_BK, _BN = load_cards()
MELOETTA = _BN['Meloetta'][0]        # Psychic Basic  — for the Benched {P} heal
SCREAM = _BN['Scream Tail'][0]       # Psychic Ancient Basic — for the Benched Ancient heal
SCREAM_EX = _BN['Scream Tail ex'][0]  # Psychic Ancient Basic ex — must ALSO count as Ancient
LEAFEON = _BN['Leafeon'][0]          # Stage-1 (non-Basic) — for the "each Basic" negative

K_SELF10 = "Heal 10 damage from this Pokémon."
K_SAME = "Heal from this Pokémon the same amount of damage you did to your opponent's Active Pokémon."
K_ONE30 = "Heal 30 damage from 1 of your Pokémon."
K_SELF40 = "Heal 40 damage from this Pokémon."
K_LEAFEON = "Attach a Basic {G} Energy card from your hand to 1 of your Benched Pokémon. If you do, heal all damage from that Pokémon."
K_SNORLAX = "Attach an Energy card from your hand to this Pokémon. If you do, heal 60 damage from this Pokémon."
K_SELF50NR = "Heal 50 damage from this Pokémon. During your next turn, this Pokémon can't retreat."
K_SELF60NR = "Heal 60 damage from this Pokémon. During your next turn, this Pokémon can't retreat."
K_EACH10 = "Heal 10 damage from each of your Pokémon."
K_EACHBASIC100 = "Heal 100 damage from each of your Basic Pokémon."
K_HEALEDRIDER = "If this Pokémon was healed during this turn, this attack does 100 more damage."
K_BENCHP120 = "Heal 120 damage from 1 of your Benched {P} Pokémon."
K_ONE40 = "Heal 40 damage from 1 of your Pokémon."
K_BENCHANCIENT100 = "Heal 100 damage from 1 of your Benched Ancient Pokémon."


def _fn(key):
    return AE.ATTACK_EFFECTS[AE.normalize(key)]


# 1) Heal 10 from self; returns base. Clamps at 0.
def t_self_10():
    ctx, at, df, me, opp = mk(text=K_SELF10, base=10)
    at.damage = 30
    assert _fn(K_SELF10)(ctx) == 10
    assert at.damage == 20, at.damage
    ctx, at, df, me, opp = mk(text=K_SELF10, base=10)
    at.damage = 5
    _fn(K_SELF10)(ctx)
    assert at.damage == 0, at.damage        # heal clamps (no negative damage)


# 2) Heal self by the amount dealt (= base); returns base.
def t_same_as_dealt():
    ctx, at, df, me, opp = mk(text=K_SAME, base=50)
    at.damage = 50
    assert _fn(K_SAME)(ctx) == 50
    assert at.damage == 0, at.damage
    ctx, at, df, me, opp = mk(text=K_SAME, base=30)
    at.damage = 100
    assert _fn(K_SAME)(ctx) == 30
    assert at.damage == 70, at.damage       # healed exactly base (30)


# 3) Heal 30 from the most-damaged one of my Pokémon; returns base (0). No-op when nothing hurt.
def t_one_30():
    ctx, at, df, me, opp = mk(text=K_ONE30, base=0, my_bench=1)
    me.active.damage = 50
    me.bench[0].damage = 10
    assert _fn(K_ONE30)(ctx) == 0
    assert me.active.damage == 20, me.active.damage      # most-damaged (active) healed
    assert me.bench[0].damage == 10, me.bench[0].damage  # the other is untouched
    ctx, at, df, me, opp = mk(text=K_ONE30, base=0)      # nothing damaged -> no-op, no crash
    assert _fn(K_ONE30)(ctx) == 0
    assert me.active.damage == 0


# 4) Heal 40 from self.
def t_self_40():
    ctx, at, df, me, opp = mk(text=K_SELF40, base=0)
    at.damage = 100
    assert _fn(K_SELF40)(ctx) == 0
    assert at.damage == 60, at.damage


# 5) Leafeon: attach a basic Grass from hand to a Benched Pokémon, then full-heal it.
def t_leafeon():
    ctx, at, df, me, opp = mk(text=K_LEAFEON, base=0, my_bench=1)
    me.hand = [('E', 'Grass')]
    me.bench[0].damage = 70
    assert _fn(K_LEAFEON)(ctx) == 0
    assert me.bench[0].damage == 0, me.bench[0].damage         # all damage healed
    assert me.bench[0].energy.get('Grass', 0) == 1, me.bench[0].energy
    assert me.hand == [], me.hand                              # energy consumed
    # no Grass in hand -> no attach, no heal
    ctx, at, df, me, opp = mk(text=K_LEAFEON, base=0, my_bench=1)
    me.hand = [('E', 'Water')]
    me.bench[0].damage = 70
    assert _fn(K_LEAFEON)(ctx) == 0
    assert me.bench[0].damage == 70 and me.hand == [('E', 'Water')]


# 6) Snorlax: attach an Energy from hand to self, then heal 60.
def t_snorlax():
    ctx, at, df, me, opp = mk(text=K_SNORLAX, base=0, atk_energy={'Colorless': 1})
    me.hand = [('E', 'Water')]
    at.damage = 100
    assert _fn(K_SNORLAX)(ctx) == 0
    assert at.energy.get('Water', 0) == 1, at.energy
    assert at.damage == 40, at.damage
    assert me.hand == [], me.hand
    # empty hand -> no attach, no heal
    ctx, at, df, me, opp = mk(text=K_SNORLAX, base=0)
    at.damage = 100
    assert _fn(K_SNORLAX)(ctx) == 0
    assert at.damage == 100, at.damage


# 7) Heal 50 from self + self can't retreat next turn (turn-stamped marker).
def t_self_50_no_retreat():
    ctx, at, df, me, opp = mk(text=K_SELF50NR, base=0)
    at.damage = 80
    assert _fn(K_SELF50NR)(ctx) == 0
    assert at.damage == 30, at.damage
    assert at.status.get('CantRetreat') == ctx.game.turn == 3, at.status


# 8) Heal 60 from self + self can't retreat.
def t_self_60_no_retreat():
    ctx, at, df, me, opp = mk(text=K_SELF60NR, base=0)
    at.damage = 80
    assert _fn(K_SELF60NR)(ctx) == 0
    assert at.damage == 20, at.damage
    assert at.status.get('CantRetreat') == 3, at.status


# 9) Heal 10 from EACH of my Pokémon; returns base (20).
def t_each_10():
    ctx, at, df, me, opp = mk(text=K_EACH10, base=20, my_bench=1)
    me.active.damage = 30
    me.bench[0].damage = 25
    assert _fn(K_EACH10)(ctx) == 20
    assert me.active.damage == 20, me.active.damage
    assert me.bench[0].damage == 15, me.bench[0].damage


# 10) Heal 100 from each of my BASIC Pokémon only (Stage-1 bench mon untouched).
def t_each_basic_100():
    ctx, at, df, me, opp = mk(text=K_EACHBASIC100, base=0)
    me.active.damage = 100                     # VANILLA (Basic) -> healed
    stage1 = Mon(LEAFEON); stage1.damage = 100  # Stage 1 -> NOT healed
    me.bench = [stage1]
    assert _fn(K_EACHBASIC100)(ctx) == 0
    assert me.active.damage == 0, me.active.damage
    assert me.bench[0].damage == 100, me.bench[0].damage


# 11) +100 damage only if the attacker was healed this turn.
def t_healed_rider():
    ctx, at, df, me, opp = mk(text=K_HEALEDRIDER, base=20)
    assert _fn(K_HEALEDRIDER)(ctx) == 20            # not healed -> base only
    ctx, at, df, me, opp = mk(text=K_HEALEDRIDER, base=20)
    at.healed_this_turn = True
    assert _fn(K_HEALEDRIDER)(ctx) == 120           # healed -> +100


# 12) Heal 120 from a Benched {P} Pokémon (non-Psychic bench mon untouched).
def t_bench_psychic_120():
    ctx, at, df, me, opp = mk(text=K_BENCHP120, base=0)
    psy = Mon(MELOETTA); psy.damage = 120
    other = Mon(_BK[  # a Grass (non-Psychic) benched mon
        next(k for k, c in _BK.items() if c.ptype == 'Grass' and c.stage == 0)]); other.damage = 50
    me.bench = [psy, other]
    assert _fn(K_BENCHP120)(ctx) == 0
    assert me.bench[0].damage == 0, me.bench[0].damage      # Psychic healed
    assert me.bench[1].damage == 50, me.bench[1].damage     # non-Psychic untouched
    # no eligible Psychic bench mon -> no-op
    ctx, at, df, me, opp = mk(text=K_BENCHP120, base=0, my_bench=1)
    me.bench[0].damage = 60                                  # VANILLA (Grass)
    assert _fn(K_BENCHP120)(ctx) == 0
    assert me.bench[0].damage == 60


# 13) Heal 40 from 1 of my Pokémon.
def t_one_40():
    ctx, at, df, me, opp = mk(text=K_ONE40, base=0)
    me.active.damage = 40
    assert _fn(K_ONE40)(ctx) == 0
    assert me.active.damage == 0, me.active.damage


# 14) Heal 100 from a Benched Ancient Pokémon. Both base Scream Tail AND Scream Tail ex are Ancient;
#     a vanilla is not — even when the vanilla is the MOST-damaged mon, the Ancient predicate must skip
#     it and heal the most-damaged *Ancient* instead (proves the ex is in the allow-list & the filter wins).
def t_bench_ancient_100():
    ctx, at, df, me, opp = mk(text=K_BENCHANCIENT100, base=0)
    anc = Mon(SCREAM); anc.damage = 60
    ancx = Mon(SCREAM_EX); ancx.damage = 100                # Scream Tail EX -> must count as Ancient
    van = Mon(_BK[next(k for k, c in _BK.items() if c.cat == 'cat-green' and c.stage == 0)])
    van.damage = 120                                        # VANILLA, most damaged overall -> NOT Ancient
    me.bench = [anc, ancx, van]
    assert _fn(K_BENCHANCIENT100)(ctx) == 0
    assert me.bench[2].damage == 120, me.bench[2].damage    # non-Ancient untouched (despite most damage)
    assert me.bench[1].damage == 0, me.bench[1].damage      # Scream Tail ex is Ancient + most-damaged Ancient
    assert me.bench[0].damage == 60, me.bench[0].damage     # base Scream Tail untouched (less damaged)
    # no Ancient on bench -> no-op, no crash
    ctx, at, df, me, opp = mk(text=K_BENCHANCIENT100, base=0, my_bench=1)
    me.bench[0].damage = 100                                 # VANILLA (not Ancient)
    assert _fn(K_BENCHANCIENT100)(ctx) == 0
    assert me.bench[0].damage == 100


TESTS = [t_self_10, t_same_as_dealt, t_one_30, t_self_40, t_leafeon, t_snorlax,
         t_self_50_no_retreat, t_self_60_no_retreat, t_each_10, t_each_basic_100,
         t_healed_rider, t_bench_psychic_120, t_one_40, t_bench_ancient_100]

if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
