#!/usr/bin/env python3
"""Unit tests for batch bench_spread_2. Asserts returned Active damage AND the key state change
(bench snipe, self-bench spread, energy move, damage-counter relocation, deck/bench conditionals)."""
from effects_testkit import mk, run, runner, VANILLA
import attack_effects as AE
import effects_gen.batch_bench_spread_2  # noqa: F401  (registers the effects)
from engine import Mon
from cards import load_cards

_BK, _BN = load_cards()
GREAT_TUSK = _BN['Great Tusk'][0]        # an Ancient Basic, for the counter-move test
SCREAM_TAIL_EX = _BN['Scream Tail ex'][0]  # a Psychic Ancient ex (regression: was missing from ANCIENT)

K1 = "This attack does 40 damage to 1 of your opponent's Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)"
K2 = "This attack does 40 damage to 1 of your opponent's Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)"
K3 = "This attack also does 50 damage to 1 of your opponent's Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)"
K4 = "This attack also does 20 damage to each of your Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)"
K5 = "Move a {W} Energy from this Pokémon to 1 of your Benched Pokémon."
K6 = "This attack does 20 damage to 1 of your opponent's Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)"
K7 = "Move all Energy from this Pokémon to your Benched Pokémon in any way you like."
K8 = "If your Benched Pokémon have any damage counters on them, this attack does 80 more damage."
K9 = "Move all damage counters from 1 of your Benched Ancient Pokémon to your opponent's Active Pokémon."
K10 = "If there are 3 or fewer cards in your deck, this attack also does 120 damage to 2 of your opponent's Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)"


def _fn(key):
    return AE.ATTACK_EFFECTS[AE.normalize(key)]


# 1) 40 to one opponent Benched Pokémon; nothing to the Active.
def t_bench_snipe_40():
    d, ctx, at, df, me, opp = run(K1, base=0, opp_bench=1)
    assert d == 0, d
    assert opp.bench[0].damage == 40, opp.bench[0].damage
    assert df.damage == 0, df.damage
    # no bench -> no target, no crash, still 0 to Active
    d2, *_ = run(K1, base=0, opp_bench=0)
    assert d2 == 0


# 2) 40 to any 1 opponent Pokémon: snipe bench when it exists, else hit the Active.
def t_snipe_any_40():
    d, ctx, at, df, me, opp = run(K2, base=0, opp_bench=1)   # no KO -> snipe the bench
    assert d == 0 and opp.bench[0].damage == 40 and df.damage == 0, (d, opp.bench[0].damage)
    d2, ctx, at, df, me, opp = run(K2, base=0, opp_bench=0)  # no bench -> hit the Active
    assert d2 == 40 and df.damage == 0, (d2, df.damage)


# 2b) KO-priority policy for "1 of your opponent's Pokémon" (Active OR Bench, player's choice):
#   (i)  a Benched KO the Active hit can't reach -> snipe the bench (return 0), and
#   (ii) when the Active is ALSO KO-able, prefer KOing the Active (return the amount; bench untouched).
def t_snipe_any_40_bench_ko():
    # (i) bench KO-able, Active NOT KO-able -> snipe the bench; nothing to the Active.
    ctx, at, df, me, opp = mk(text=K2, base=0, opp_bench=1)
    opp.bench[0].damage = 50          # VANILLA 80 HP -> hp_left 30 <= 40 -> KO-able on the bench
    assert df.hp_left == 80 and df.card.weakness != at.card.ptype   # Active (full-HP) is NOT KO-able by 40
    d = _fn(K2)(ctx)
    assert d == 0 and opp.bench[0].damage == 90, (d, opp.bench[0].damage)
    # (ii) Active AND bench both KO-able -> take the Active KO (return 40); the bench is left alone.
    ctx, at, df, me, opp = mk(text=K2, base=0, opp_bench=1)
    df.damage = 50                    # Active hp_left 30 <= 40 -> KO-able
    opp.bench[0].damage = 50          # bench also KO-able
    d = _fn(K2)(ctx)
    assert d == 40 and opp.bench[0].damage == 50, (d, opp.bench[0].damage)


# 3) base to Active + 50 to one opponent Benched Pokémon.
def t_also_bench_snipe_50():
    d, ctx, at, df, me, opp = run(K3, base=50, opp_bench=1)
    assert d == 50, d
    assert opp.bench[0].damage == 50, opp.bench[0].damage


# 4) base to Active + 20 to EACH of MY OWN Benched Pokémon.
def t_also_own_bench_20_each():
    d, ctx, at, df, me, opp = run(K4, base=140, my_bench=2)
    assert d == 140, d
    assert all(m.damage == 20 for m in me.bench), [m.damage for m in me.bench]
    assert len(me.bench) == 2


# 5) move one Water Energy from the attacker to a Benched Pokémon.
def t_move_w_to_bench():
    d, ctx, at, df, me, opp = run(K5, base=90, atk_energy={'Water': 2, 'Colorless': 1}, my_bench=1)
    assert d == 90, d
    assert at.energy.get('Water', 0) == 1, at.energy
    assert me.bench[0].energy.get('Water', 0) == 1, me.bench[0].energy
    # no Water attached -> nothing to move
    d2, ctx, at, df, me, opp = run(K5, base=90, atk_energy={'Colorless': 3}, my_bench=1)
    assert d2 == 90 and me.bench[0].energy.get('Water', 0) == 0, (d2, me.bench[0].energy)


# 6) 20 to any 1 opponent Pokémon: bench snipe vs Active hit.
def t_snipe_any_20():
    d, ctx, at, df, me, opp = run(K6, base=0, opp_bench=1)
    assert d == 0 and opp.bench[0].damage == 20, (d, opp.bench[0].damage)
    d2, ctx, at, df, me, opp = run(K6, base=0, opp_bench=0)
    assert d2 == 20 and df.damage == 0, (d2, df.damage)


# 7) move ALL energy from the attacker to a Benched Pokémon.
def t_move_all_to_bench():
    d, ctx, at, df, me, opp = run(K7, base=160, atk_energy={'Lightning': 2, 'Colorless': 1}, my_bench=1)
    assert d == 160, d
    assert at.total_energy() == 0, at.energy
    assert me.bench[0].total_energy() == 3, me.bench[0].energy
    # no bench -> energy stays put
    d2, ctx, at, df, me, opp = run(K7, base=160, atk_energy={'Lightning': 2, 'Colorless': 1}, my_bench=0)
    assert d2 == 160 and at.total_energy() == 3, (d2, at.total_energy())


# 8) +80 only if any of MY Benched Pokémon carry damage counters.
def t_plus_80_if_bench_damaged():
    ctx, at, df, me, opp = mk(text=K8, base=80, my_bench=1)
    me.bench[0].damage = 10
    assert _fn(K8)(ctx) == 160
    ctx, at, df, me, opp = mk(text=K8, base=80, my_bench=1)   # clean bench
    assert _fn(K8)(ctx) == 80


# 9) move all damage counters from a Benched Ancient Pokémon to the opponent's Active.
def t_move_counters_ancient():
    ctx, at, df, me, opp = mk(text=K9, base=0)
    src = Mon(GREAT_TUSK); src.damage = 50
    me.bench = [src]
    d = _fn(K9)(ctx)
    assert d == 0, d
    assert df.damage == 50, df.damage          # counters relocated onto the Active (no weakness)
    assert src.damage == 0, src.damage
    # non-Ancient benched Pokémon -> nothing moves
    ctx, at, df, me, opp = mk(text=K9, base=0, my_bench=1)
    me.bench[0].damage = 50                     # a VANILLA (Bulbasaur) — not Ancient
    d2 = _fn(K9)(ctx)
    assert d2 == 0 and df.damage == 0 and me.bench[0].damage == 50, (d2, df.damage)
    # mixed bench: an Ancient (30) beside a NON-Ancient carrying MORE counters (50). Only the Ancient is
    # a legal source -> exactly its 30 move; the bigger non-Ancient pile is never touched. (This fails if
    # the source filter picks max over the whole bench instead of over Ancient mons only.)
    ctx, at, df, me, opp = mk(text=K9, base=0)
    anc = Mon(GREAT_TUSK); anc.damage = 30
    van = Mon(VANILLA); van.damage = 50
    me.bench = [van, anc]
    d3 = _fn(K9)(ctx)
    assert d3 == 0 and df.damage == 30, (d3, df.damage)     # 30 (Ancient), NOT 50 (bigger non-Ancient)
    assert anc.damage == 0 and van.damage == 50, (anc.damage, van.damage)
    # a benched Ancient ex (Scream Tail ex is Psychic, a natural Flutter Mane partner) is a valid source.
    # Regression guard: 'Scream Tail ex' was missing from the ANCIENT allow-list.
    ctx, at, df, me, opp = mk(text=K9, base=0)
    ste = Mon(SCREAM_TAIL_EX); ste.damage = 40
    me.bench = [ste]
    d4 = _fn(K9)(ctx)
    assert d4 == 0 and df.damage == 40 and ste.damage == 0, (d4, df.damage, ste.damage)
    # an Ancient with NO counters -> nothing to move, no crash (empty-source guard), 0 to the Active.
    ctx, at, df, me, opp = mk(text=K9, base=0)
    me.bench = [Mon(GREAT_TUSK)]                 # 0 damage
    assert _fn(K9)(ctx) == 0 and df.damage == 0


# 10) mill finisher: 120 to 2 opponent Benched Pokémon only when deck has <=3 cards.
def t_mill_finisher():
    ctx, at, df, me, opp = mk(text=K10, base=20, opp_bench=2)
    me.deck = []                                # 0 cards left -> fires
    d = _fn(K10)(ctx)
    assert d == 20, d
    assert all(b.damage == 120 for b in opp.bench), [b.damage for b in opp.bench]
    ctx, at, df, me, opp = mk(text=K10, base=20, opp_bench=2)   # default deck (16 cards) -> no spread
    d2 = _fn(K10)(ctx)
    assert d2 == 20 and all(b.damage == 0 for b in opp.bench), (d2, [b.damage for b in opp.bench])


TESTS = [t_bench_snipe_40, t_snipe_any_40, t_snipe_any_40_bench_ko, t_also_bench_snipe_50,
         t_also_own_bench_20_each, t_move_w_to_bench, t_snipe_any_20, t_move_all_to_bench,
         t_plus_80_if_bench_damaged, t_move_counters_ancient, t_mill_finisher]

if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
