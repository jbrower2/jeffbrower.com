#!/usr/bin/env python3
"""Unit tests for batch bench_spread_0. Each effect asserts the returned Active damage AND the key
state change (bench snipe/spread, own-bench self-spread, ×-scaling off bench, bench-condition
bonuses, energy/counter relocation, put-onto-bench, shuffle-away). Branches (condition met/unmet,
Active-hit vs Bench-snipe) are both covered."""
from collections import Counter
from effects_testkit import mk, run, runner
import attack_effects as AE
import effects_gen.batch_bench_spread_0  # noqa: F401  (registers the effects)
from engine import Mon
from cards import load_cards

BK, BN = load_cards()
DUSKULL = BN['Duskull'][0]
LUNATONE = BN['Lunatone'][0]
MIGHTYENA = BN['Mightyena'][0]
CUBONE = BN['Cubone'][0]
RATTATA = BN['Rattata'][0]
CYNTHIA = BN["Cynthia's Spiritomb"][0]
NIDOKING = BN["Team Rocket's Nidoking ex"][0]
CROBAT = BN['Crobat'][0]                                   # Stage 2, Darkness
METAL = next(c for c in BK.values() if c.ptype == 'Metal')
VANILLA = BN['Bulbasaur'][0]

K_also30b1 = "This attack also does 30 damage to 1 of your opponent's Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)"
K_also20b1 = "This attack also does 20 damage to 1 of your opponent's Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)"
K_also10be = "This attack also does 10 damage to each of your opponent's Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)"
K_snipe50 = "This attack does 50 damage to 1 of your opponent's Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)"
K_snipe10 = "This attack does 10 damage to 1 of your opponent's Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)"
K_snipe50x2 = "This attack does 50 damage to 2 of your opponent's Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)"
K_all30 = "This attack does 30 damage to each of your opponent's Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)"
K_50dmg = "This attack does 50 damage to each Pokémon that has any damage counters on it (both yours and your opponent's), except for this Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)"
K_own30e = "This attack also does 30 damage to each of your Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)"
K_own10e = "This attack also does 10 damage to each of your Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)"
K_own10one = "This attack also does 10 damage to 1 of your Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)"
K_all20b = "This attack also does 20 damage to each Benched Pokémon (both yours and your opponent's). (Don't apply Weakness and Resistance for Benched Pokémon.)"
K_20xbench = "This attack does 20 damage for each of your Benched Pokémon."
K_cynthia = "This attack does 10 damage for each damage counter on all of your Benched Cynthia's Pokémon. This attack's damage isn't affected by Weakness."
K_rattata = "This attack does 40 damage for each damage counter on all of your Benched Rattata."
K_metal = "If you have any {M} Pokémon on your Bench, this attack does 80 more damage."
K_nidoking = "If a Pokémon that has \"Nidoking\" in its name is on your Bench, this attack does 120 more damage."
K_cubone = "If any of your Benched Cubone have any damage counters on them, this attack does 120 more damage."
K_tera = "If you have any Tera Pokémon on your Bench, this attack does 100 more damage."
K_mightyena = "If Mightyena is on your Bench, this attack does 90 more damage."
K_stage2dark = "If you have any Stage 2 {D} Pokémon on your Bench, this attack does 70 more damage."
K_lunatone = "If you don't have Lunatone on your Bench, this attack does nothing. This attack's damage isn't affected by Weakness or Resistance."
K_moveenergy = "Move an Energy from this Pokémon to 1 of your Benched Pokémon."
K_movecounters = "Move all damage counters from 1 of your Benched Pokémon to your opponent's Active Pokémon."
K_gather = "You may move any number of damage counters from your opponent's Benched Pokémon to their Active Pokémon."
K_duskull = "Put up to 3 Duskull from your discard pile onto your Bench."
K_lickitung = "Your opponent reveals their hand. Put up to 2 Basic Pokémon you find there onto your opponent's Bench."
K_shiftry = "Choose 3 of your opponent's Benched Pokémon. If you do, shuffle all of your opponent's Benched Pokémon that you didn't choose, and all cards attached to those Pokémon, into their deck."


def _fn(key):
    return AE.ATTACK_EFFECTS[AE.normalize(key)]


# ---------------------------------------------------------------- opponent-bench snipe (base + bench)
def t_also30b1():
    d, ctx, at, df, me, opp = run(K_also30b1, base=50, opp_bench=1)
    assert d == 50 and opp.bench[0].damage == 30 and df.damage == 0, (d, opp.bench[0].damage)
    # targets the lowest-HP-remaining Benched Pokémon
    ctx, at, df, me, opp = mk(text=K_also30b1, base=50, opp_bench=2)
    opp.bench[1].damage = 60                              # hp_left 20 < 80 -> chosen
    _fn(K_also30b1)(ctx)
    assert opp.bench[1].damage == 90 and opp.bench[0].damage == 0, [b.damage for b in opp.bench]


def t_also20b1():
    d, ctx, at, df, me, opp = run(K_also20b1, base=30, opp_bench=1)
    assert d == 30 and opp.bench[0].damage == 20, (d, opp.bench[0].damage)


def t_also10be():
    d, ctx, at, df, me, opp = run(K_also10be, base=90, opp_bench=2)
    assert d == 90 and all(b.damage == 10 for b in opp.bench), (d, [b.damage for b in opp.bench])


# ---------------------------------------------------------------- "N to 1/2/each opponent Pokémon"
def t_snipe50():
    d, _, _, df, _, _ = run(K_snipe50, base=0, opp_bench=0)   # no bench -> hit Active
    assert d == 50 and df.damage == 0, (d, df.damage)
    d, _, _, df, _, opp = run(K_snipe50, base=0, opp_bench=1)  # no KO -> snipe the bench threat
    assert d == 0 and opp.bench[0].damage == 50 and df.damage == 0, (d, opp.bench[0].damage)
    ctx, at, df, me, opp = mk(text=K_snipe50, base=0, opp_bench=1)  # bench KO available
    opp.bench[0].damage = 40                                  # hp_left 40 <= 50
    d = _fn(K_snipe50)(ctx)
    assert d == 0 and opp.bench[0].damage == 90, (d, opp.bench[0].damage)


def t_snipe10():
    d, _, _, df, _, _ = run(K_snipe10, base=0, opp_bench=0)
    assert d == 10 and df.damage == 0, (d, df.damage)
    d, _, _, df, _, opp = run(K_snipe10, base=0, opp_bench=1)
    assert d == 0 and opp.bench[0].damage == 10, (d, opp.bench[0].damage)


def t_snipe50x2():
    # two benched KOs available, Active not KO-able -> both hits land on the bench
    ctx, at, df, me, opp = mk(text=K_snipe50x2, base=0, opp_bench=2)
    opp.bench[0].damage = 40; opp.bench[1].damage = 40       # both hp_left 40 <= 50
    d = _fn(K_snipe50x2)(ctx)
    assert d == 0 and all(b.damage == 90 for b in opp.bench), (d, [b.damage for b in opp.bench])
    # Active + one Bench (no KOs) -> 50 returned for the Active, 50 onto the bench
    d, _, _, df, _, opp = run(K_snipe50x2, base=0, opp_bench=1)
    assert d == 50 and opp.bench[0].damage == 50, (d, opp.bench[0].damage)


def t_all30():
    d, _, _, df, _, opp = run(K_all30, base=0, opp_bench=2)
    assert d == 30 and all(b.damage == 30 for b in opp.bench), (d, [b.damage for b in opp.bench])


def t_50dmg():
    ctx, at, df, me, opp = mk(text=K_50dmg, base=0, opp_bench=1, my_bench=1)
    at.damage = 10                     # attacker is exempt
    me.bench[0].damage = 10
    opp.bench[0].damage = 10
    opp.active.damage = 20
    d = _fn(K_50dmg)(ctx)
    assert d == 50, d                                   # Active damaged -> hit it (return, Weakness later)
    assert at.damage == 10, at.damage                   # attacker exempt, untouched
    assert me.bench[0].damage == 60, me.bench[0].damage
    assert opp.bench[0].damage == 60, opp.bench[0].damage
    assert opp.active.damage == 20, opp.active.damage    # fn does NOT self-apply the Active hit
    # undamaged Active -> 0 returned, but still hits damaged bench
    ctx, at, df, me, opp = mk(text=K_50dmg, base=0, opp_bench=1)
    opp.bench[0].damage = 10; opp.active.damage = 0
    assert _fn(K_50dmg)(ctx) == 0 and opp.bench[0].damage == 60


# ---------------------------------------------------------------- own-bench / both-bench self-spread
def t_own30e():
    d, _, _, _, me, _ = run(K_own30e, base=140, my_bench=2)
    assert d == 140 and all(m.damage == 30 for m in me.bench), (d, [m.damage for m in me.bench])


def t_own10e():
    d, _, _, _, me, _ = run(K_own10e, base=120, my_bench=2)
    assert d == 120 and all(m.damage == 10 for m in me.bench), (d, [m.damage for m in me.bench])


def t_own10one():
    d, _, _, _, me, _ = run(K_own10one, base=30, my_bench=1)
    assert d == 30 and me.bench[0].damage == 10, (d, me.bench[0].damage)
    # picks the sturdiest (most HP left) of our bench
    ctx, at, df, me, opp = mk(text=K_own10one, base=30, my_bench=2)
    me.bench[0].damage = 30            # hp_left 50; bench[1] full (80) is sturdier
    _fn(K_own10one)(ctx)
    assert me.bench[1].damage == 10 and me.bench[0].damage == 30, [m.damage for m in me.bench]


def t_all20b():
    d, _, _, _, me, opp = run(K_all20b, base=20, opp_bench=1, my_bench=1)
    assert d == 20 and opp.bench[0].damage == 20 and me.bench[0].damage == 20, d


# ---------------------------------------------------------------- ×-scaling
def t_20xbench():
    assert run(K_20xbench, base=20, my_bench=3)[0] == 60
    assert run(K_20xbench, base=20, my_bench=0)[0] == 0


def t_cynthia():
    ctx, at, df, me, opp = mk(text=K_cynthia, base=10, my_bench=0)
    b1 = Mon(CYNTHIA); b1.damage = 30      # 3 counters
    b2 = Mon(CYNTHIA); b2.damage = 20      # 2 counters
    other = Mon(VANILLA); other.damage = 50  # not Cynthia's -> excluded
    me.bench = [b1, b2, other]
    # "isn't affected by Weakness" -> written straight to the Active's .damage, returns 0 (so the
    # engine can't double it on Weakness).
    assert _fn(K_cynthia)(ctx) == 0, 'no-Weakness damage bypasses the int return'
    assert df.damage == 50, ('expected 10*(3+2)=50 onto the Active', df.damage)
    # no benched Cynthia's damage -> 0 dealt
    ctx, at, df, me, opp = mk(text=K_cynthia, base=10)
    me.bench = [Mon(CYNTHIA)]
    assert _fn(K_cynthia)(ctx) == 0 and df.damage == 0


def t_rattata():
    ctx, at, df, me, opp = mk(text=K_rattata, base=40)
    r = Mon(RATTATA); r.damage = 40        # 4 counters
    me.bench = [r]
    assert _fn(K_rattata)(ctx) == 160, '40*4'
    ctx, at, df, me, opp = mk(text=K_rattata, base=40, my_bench=1)   # VANILLA bench, no Rattata
    assert _fn(K_rattata)(ctx) == 0


# ---------------------------------------------------------------- bench-condition bonuses
def t_metal():
    ctx, at, df, me, opp = mk(text=K_metal, base=60)
    me.bench = [Mon(METAL)]
    assert _fn(K_metal)(ctx) == 140
    ctx, at, df, me, opp = mk(text=K_metal, base=60, my_bench=1)     # VANILLA (Grass) bench
    assert _fn(K_metal)(ctx) == 60


def t_nidoking():
    ctx, at, df, me, opp = mk(text=K_nidoking, base=60)
    me.bench = [Mon(NIDOKING)]
    assert _fn(K_nidoking)(ctx) == 180
    ctx, at, df, me, opp = mk(text=K_nidoking, base=60, my_bench=1)
    assert _fn(K_nidoking)(ctx) == 60


def t_cubone():
    ctx, at, df, me, opp = mk(text=K_cubone, base=60)
    c = Mon(CUBONE); c.damage = 10
    me.bench = [c]
    assert _fn(K_cubone)(ctx) == 180
    ctx, at, df, me, opp = mk(text=K_cubone, base=60)                # Cubone present but undamaged
    me.bench = [Mon(CUBONE)]
    assert _fn(K_cubone)(ctx) == 60


def t_tera():
    # Tera subtype is not captured by the dataset (meta has no Tera token; Card.__slots__ has no
    # 'tera') -> _is_tera is always False -> condition never met -> no bonus (conservative floor,
    # never the forbidden unconditional +100).
    from effects_gen.batch_bench_spread_0 import _is_tera
    assert _is_tera(CROBAT) is False
    assert run(K_tera, base=100, my_bench=2)[0] == 100


def t_mightyena():
    ctx, at, df, me, opp = mk(text=K_mightyena, base=30)
    me.bench = [Mon(MIGHTYENA)]
    assert _fn(K_mightyena)(ctx) == 120
    ctx, at, df, me, opp = mk(text=K_mightyena, base=30, my_bench=1)
    assert _fn(K_mightyena)(ctx) == 30


def t_stage2dark():
    ctx, at, df, me, opp = mk(text=K_stage2dark, base=20)
    me.bench = [Mon(CROBAT)]                                          # Stage 2 Darkness
    assert _fn(K_stage2dark)(ctx) == 90
    ctx, at, df, me, opp = mk(text=K_stage2dark, base=20, my_bench=1)  # VANILLA (Basic Grass)
    assert _fn(K_stage2dark)(ctx) == 20


def t_lunatone():
    ctx, at, df, me, opp = mk(text=K_lunatone, base=70)
    me.bench = [Mon(LUNATONE)]
    # Lunatone present -> 70 straight to the Active (no Weakness), returns 0.
    assert _fn(K_lunatone)(ctx) == 0 and df.damage == 70, ('70 onto the Active, no Weakness', df.damage)
    # no Lunatone -> does nothing (0 returned, nothing dealt)
    d, _, _, df2, _, _ = run(K_lunatone, base=70, my_bench=1)
    assert d == 0 and df2.damage == 0


# ---------------------------------------------------------------- energy / counter relocation
def t_moveenergy():
    d, _, at, _, me, _ = run(K_moveenergy, base=60, atk_energy={'Water': 2}, my_bench=1)
    assert d == 60 and at.energy.get('Water', 0) == 1 and me.bench[0].energy.get('Water', 0) == 1, at.energy
    # no bench -> energy stays put
    d, _, at, _, me, _ = run(K_moveenergy, base=60, atk_energy={'Water': 2}, my_bench=0)
    assert d == 60 and at.total_energy() == 2


def t_movecounters():
    ctx, at, df, me, opp = mk(text=K_movecounters, base=0, my_bench=1)
    me.bench[0].damage = 30; opp.active.damage = 0
    d = _fn(K_movecounters)(ctx)
    assert d == 0 and opp.active.damage == 30 and me.bench[0].damage == 0, (d, opp.active.damage)
    # nothing damaged on our bench -> no-op
    ctx, at, df, me, opp = mk(text=K_movecounters, base=0, my_bench=1)
    assert _fn(K_movecounters)(ctx) == 0 and opp.active.damage == 0


def t_gather():
    ctx, at, df, me, opp = mk(text=K_gather, base=0, opp_bench=2)
    opp.bench[0].damage = 20; opp.bench[1].damage = 30; opp.active.damage = 0
    d = _fn(K_gather)(ctx)
    assert d == 0 and opp.active.damage == 50, (d, opp.active.damage)
    assert all(b.damage == 0 for b in opp.bench), [b.damage for b in opp.bench]


# ---------------------------------------------------------------- put-onto-bench / shuffle-away
def t_duskull():
    ctx, at, df, me, opp = mk(text=K_duskull, base=0, my_bench=0)
    me.discard = [('P', DUSKULL)] * 4
    d = _fn(K_duskull)(ctx)
    assert d == 0 and len(me.bench) == 3, (d, len(me.bench))
    assert all(m.card.name == 'Duskull' for m in me.bench)
    assert sum(1 for t in me.discard if t[1].name == 'Duskull') == 1     # only 3 of 4 moved


def t_lickitung():
    ctx, at, df, me, opp = mk(text=K_lickitung, base=0, opp_bench=0)
    opp.hand = [('P', CROBAT), ('P', VANILLA), ('P', VANILLA)]           # Crobat is Stage 2 -> skipped
    d = _fn(K_lickitung)(ctx)
    assert d == 0 and len(opp.bench) == 2, (d, len(opp.bench))
    assert all(m.card.stage == 0 for m in opp.bench)
    assert ('P', CROBAT) in opp.hand                                     # evolution left in hand


def t_shiftry():
    ctx, at, df, me, opp = mk(text=K_shiftry, base=0, opp_bench=5)
    opp.bench[3].energy = Counter({'Water': 2})       # most-developed -> shuffled away
    opp.bench[4].energy = Counter({'Fire': 1})
    n0 = len(opp.deck)
    d = _fn(K_shiftry)(ctx)
    assert d == 0 and len(opp.bench) == 3, (d, len(opp.bench))
    assert all(b.total_energy() == 0 for b in opp.bench)                 # kept the 3 least-developed
    assert len(opp.deck) == n0 + 2 + 3, len(opp.deck)                    # 2 Pokémon + 3 Energy back
    # 3 or fewer on the bench -> nothing shuffled
    ctx, at, df, me, opp = mk(text=K_shiftry, base=0, opp_bench=3)
    n0 = len(opp.deck)
    assert _fn(K_shiftry)(ctx) == 0 and len(opp.bench) == 3 and len(opp.deck) == n0


TESTS = [t_also30b1, t_also20b1, t_also10be, t_snipe50, t_snipe10, t_snipe50x2, t_all30, t_50dmg,
         t_own30e, t_own10e, t_own10one, t_all20b, t_20xbench, t_cynthia, t_rattata, t_metal,
         t_nidoking, t_cubone, t_tera, t_mightyena, t_stage2dark, t_lunatone, t_moveenergy,
         t_movecounters, t_gather, t_duskull, t_lickitung, t_shiftry]

if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
