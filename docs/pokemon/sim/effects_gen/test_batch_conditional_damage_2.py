#!/usr/bin/env python3
"""Unit tests for batch conditional_damage_2. These effects are condition/count driven, so state is
set explicitly (energy, hand size, defender ex/damage/status/retreat, discard, board attrs). Each
test asserts the returned damage AND the key state, covering met/unmet branches wherever the engine
model can represent both (conditions the engine keeps no state for are conservative single-branch)."""
from collections import Counter
from types import SimpleNamespace
from effects_testkit import mk, run, runner
from cards import load_cards
import attack_effects as AE
import effects_gen.batch_conditional_damage_2   # noqa: F401  (registers the effects)

BK, BN = load_cards()
EXCARD = next(c for c in BK.values() if c.is_ex)                 # a Pokémon ex
S1 = next(c for c in BK.values() if c.stage == 1)               # an Evolution (Stage 1)
ROUND = BN['Tympole'][0]                                        # has a 'Round' attack
HIRETREAT = next(c for c in BK.values() if c.retreat >= 2)      # Retreat Cost >= {C}{C}
LORETREAT = next(c for c in BK.values() if c.retreat <= 1)      # Retreat Cost < {C}{C}

TESTS = []
def test(fn): TESTS.append(fn); return fn


def _call(text, ctx):
    return AE.ATTACK_EFFECTS[AE.normalize(text)](ctx)


# ============================================================ per-each scaling (× / +)

@test
def t_dewott_x30_per_energy():
    T = "This attack does 30 damage for each Energy attached to this Pokémon."
    assert run(T, base=30, atk_energy={'Water': 4})[0] == 120       # 4 energy
    assert run(T, base=30, atk_energy={'Colorless': 2})[0] == 60    # 2 energy
    assert run(T, base=30, atk_energy={'Water': 2, 'Wild': 1})[0] == 90  # special-energy (Wild) pips count too
    ctx, at, *_ = mk(text=T, base=30)
    at.energy = Counter()                                           # 0 energy -> 0 (× floor)
    assert _call(T, ctx) == 0


@test
def t_tympole_x20_per_round():
    T = "This attack does 20 damage for each of your Pokémon in play that has the Round attack."
    ctx, at, df, me, opp = mk(text=T, base=20, my_bench=1)
    assert _call(T, ctx) == 0                                       # VANILLA: no Round
    at.card = ROUND; me.bench[0].card = ROUND
    assert _call(T, ctx) == 40                                      # 2 Round mons


@test
def t_seismitoad_x70_per_round():
    T = "This attack does 70 damage for each of your Pokémon in play that has the Round attack."
    ctx, at, df, me, opp = mk(text=T, base=70, my_bench=1)
    assert _call(T, ctx) == 0
    at.card = ROUND
    assert _call(T, ctx) == 70                                      # only the attacker
    me.bench[0].card = ROUND
    assert _call(T, ctx) == 140                                     # attacker + bench


@test
def t_tirtouga_x30_per_item():
    T = "This attack does 30 damage for each Item card in your opponent's discard pile."
    ctx, at, df, me, opp = mk(text=T, base=30)
    assert _call(T, ctx) == 0                                       # empty discard
    opp.discard = [('T', {'name': 'Nest Ball', 'trainerType': 'Item'}),
                   ('T', {'name': 'Boss', 'trainerType': 'Supporter'}),   # not an Item
                   ('P', object())]                                        # not a Trainer
    assert _call(T, ctx) == 30                                      # 1 Item only
    opp.discard.append(('T', {'name': 'Ultra Ball', 'trainerType': 'Item'}))
    assert _call(T, ctx) == 60


@test
def t_cinccino_x70_per_special():
    T = "This attack does 70 damage for each Special Energy card attached to this Pokémon."
    ctx, at, df, me, opp = mk(text=T, base=70)
    assert _call(T, ctx) == 0                                       # no special energy
    at.special = ['Prism Energy', 'Mist Energy']
    assert _call(T, ctx) == 140                                     # 2 special cards


@test
def t_darumaka_plus20_per_fire():
    T = "This attack does 20 more damage for each {R} Energy attached to this Pokémon."
    assert run(T, base=10, atk_energy={'Fire': 3})[0] == 70         # 10 + 3*20
    assert run(T, base=10, atk_energy={'Water': 3})[0] == 10        # no Fire -> base


@test
def t_darmanitan_plus40_per_fire():
    T = "This attack does 40 more damage for each {R} Energy attached to this Pokémon."
    assert run(T, base=40, atk_energy={'Fire': 2})[0] == 120        # 40 + 2*40
    assert run(T, base=40, atk_energy={'Colorless': 2})[0] == 40    # Colorless != Fire


@test
def t_reuniclus_plus40_per_evolution():
    T = "This attack does 40 more damage for each of your Evolution Pokémon in play."
    ctx, at, df, me, opp = mk(text=T, base=40, my_bench=1)
    assert _call(T, ctx) == 40                                      # all Basic -> +0
    at.card = S1; me.bench[0].card = S1
    assert _call(T, ctx) == 120                                     # 40 + 2*40


# ============================================================ if-condition flat bonus (+)

@test
def t_stoutland_plus100_if_special():
    T = "If this Pokémon has any Special Energy attached, this attack does 100 more damage."
    ctx, at, df, me, opp = mk(text=T, base=100)
    assert _call(T, ctx) == 100
    at.special = ['Prism Energy']
    assert _call(T, ctx) == 200


@test
def t_ferrothorn_plus70_if_special():
    T = "If this Pokémon has any Special Energy attached, this attack does 70 more damage."
    ctx, at, *_ = mk(text=T, base=70)
    assert _call(T, ctx) == 70
    at.special = ['Prism Energy']
    assert _call(T, ctx) == 140


@test
def t_galvantula_plus80_if_lightning():
    T = "If this Pokémon has any {L} Energy attached, this attack does 80 more damage."
    assert run(T, base=50, atk_energy={'Lightning': 1})[0] == 130
    assert run(T, base=50, atk_energy={'Colorless': 3})[0] == 50


@test
def t_stunfisk_plus20_if_fighting():
    T = "If this Pokémon has any {F} Energy attached, this attack does 20 more damage."
    assert run(T, base=20, atk_energy={'Fighting': 2})[0] == 40
    assert run(T, base=20, atk_energy={'Water': 2})[0] == 20        # {F}=Fighting, not Water


@test
def t_marnies_purrloin_plus40_if_ex():
    T = "If your opponent's Active Pokémon is a Pokémon ex, this attack does 40 more damage."
    ctx, at, df, me, opp = mk(text=T, base=20)
    assert _call(T, ctx) == 20                                      # VANILLA not ex
    df.card = EXCARD
    assert _call(T, ctx) == 60


@test
def t_swanna_plus90_if_ex_or_v():
    T = "If your opponent's Active Pokémon is a Pokémon ex or Pokémon V, this attack does 90 more damage."
    ctx, at, df, *_ = mk(text=T, base=20)
    assert _call(T, ctx) == 20
    df.card = EXCARD
    assert _call(T, ctx) == 110
    df.card = SimpleNamespace(is_ex=False, name='Zapdos V')         # the Pokémon V branch (name-detected)
    assert _call(T, ctx) == 110
    df.card = SimpleNamespace(is_ex=False, name='Zapdos')           # neither ex nor V -> no bonus
    assert _call(T, ctx) == 20


@test
def t_golurk_plus120_if_ex_or_v():
    T = "If your opponent's Active Pokémon is a Pokémon ex or Pokémon V, this attack does 120 more damage."
    ctx, at, df, *_ = mk(text=T, base=120)
    assert _call(T, ctx) == 120
    df.card = EXCARD
    assert _call(T, ctx) == 240
    df.card = SimpleNamespace(is_ex=False, name='Regigigas V')      # Pokémon V branch
    assert _call(T, ctx) == 240
    df.card = SimpleNamespace(is_ex=False, name='Regigigas')        # neither -> no bonus
    assert _call(T, ctx) == 120


@test
def t_amoonguss_plus120_if_condition():
    T = "If your opponent's Active Pokémon is affected by a Special Condition, this attack does 120 more damage."
    ctx, at, df, *_ = mk(text=T, base=30)
    assert _call(T, ctx) == 30                                      # no condition
    df.status['CantRetreat'] = 3
    assert _call(T, ctx) == 30                                      # CantRetreat is NOT a condition
    df.status['Poisoned'] = True
    assert _call(T, ctx) == 150


@test
def t_larrys_rufflet_plus80_if_damaged():
    T = "If your opponent's Active Pokémon already has any damage counters on it, this attack does 80 more damage."
    ctx, at, df, *_ = mk(text=T, base=20)
    assert _call(T, ctx) == 20
    df.damage = 10
    assert _call(T, ctx) == 100


@test
def t_boldore_plus50_if_fighting_resistance():
    T = "If your opponent's Active Pokémon has {F} Resistance, this attack does 50 more damage."
    ctx, at, df, *_ = mk(text=T, base=30)
    assert _call(T, ctx) == 30                                      # resistance unmodeled -> off
    df.resistance = 'Fighting'
    assert _call(T, ctx) == 80
    df.resistance = 'Water'
    assert _call(T, ctx) == 30                                      # wrong Resistance type


@test
def t_talonflame_plus110_if_heavy_retreat():
    T = "If the Retreat Cost of your opponent's Active Pokémon is {C}{C} or more, this attack does 110 more damage."
    ctx, at, df, *_ = mk(text=T, base=110)
    df.card = HIRETREAT
    assert _call(T, ctx) == 220                                     # retreat >= 2
    df.card = LORETREAT
    assert _call(T, ctx) == 110                                     # retreat < 2
    # Magnetic Metal Energy zeroes effective retreat -> no bonus even on a heavy Pokémon
    ctx2, at2, df2, *_ = mk(text=T, base=110, def_special=('Magnetic Metal Energy',))
    df2.card = HIRETREAT
    assert _call(T, ctx2) == 110


@test
def t_krookodile_plus120_if_small_hand():
    T = "If your opponent has 3 or fewer cards in their hand, this attack does 120 more damage."
    ctx, at, df, me, opp = mk(text=T, base=120)
    opp.hand = []
    assert _call(T, ctx) == 240                                     # 0 <= 3
    opp.hand = [('E', 'Colorless')] * 3
    assert _call(T, ctx) == 240                                     # exactly 3
    opp.hand = [('E', 'Colorless')] * 4
    assert _call(T, ctx) == 120                                     # 4 > 3


@test
def t_mienshao_plus60_if_small_hand():
    T = "If your opponent has 5 or fewer cards in their hand, this attack does 60 more damage."
    ctx, at, df, me, opp = mk(text=T, base=30)
    opp.hand = [('E', 'Colorless')] * 5
    assert _call(T, ctx) == 90                                      # exactly 5
    opp.hand = [('E', 'Colorless')] * 6
    assert _call(T, ctx) == 30                                      # 6 > 5


@test
def t_vivillon_plus60_if_stadium():
    T = "If a Stadium is in play, this attack does 60 more damage."
    ctx, at, df, me, opp = mk(text=T, base=60)
    assert _call(T, ctx) == 60                                      # no Stadium -> base
    ctx2, *_ = mk(text=T, base=60, stadium='Prism Tower')
    assert _call(T, ctx2) == 120                                    # Stadium in play -> +60


# ============================================================ conditional "does nothing" gates

@test
def t_sawk_ex_only():
    T = ("If your opponent's Active Pokémon isn't a Pokémon ex, this attack does nothing. "
         "This attack's damage isn't affected by Weakness or Resistance.")
    ctx, at, df, *_ = mk(text=T, base=90)
    assert _call(T, ctx) == 0                                       # not ex -> nothing
    df.card = EXCARD
    assert _call(T, ctx) == 90


@test
def t_basculin_needs_damaged():
    T = ("If your opponent's Active Pokémon has no damage counters on it before this attack does "
         "damage, this attack does nothing.")
    ctx, at, df, *_ = mk(text=T, base=50)
    assert _call(T, ctx) == 0                                       # undamaged -> nothing
    df.damage = 20
    assert _call(T, ctx) == 50


# ============================================================ fixed base / cost / cross-turn gates

@test
def t_conkeldurr_cost_ignore():
    T = "If this Pokémon is affected by a Special Condition, ignore all Energy in this attack's cost."
    ctx, at, df, *_ = mk(text=T, base=250)
    assert _call(T, ctx) == 250                                     # cost-only clause; damage always base
    at.status['Asleep'] = True
    assert _call(T, ctx) == 250                                     # condition state doesn't change damage


@test
def t_bouffalant_retaliate():
    T = ("During your opponent's next turn, if this Pokémon is damaged by an attack (even if this "
         "Pokémon is Knocked Out), put 6 damage counters on the Attacking Pokémon.")
    ctx, at, df, me, opp = mk(text=T, base=40)
    assert _call(T, ctx) == 40                                      # fixed base this turn
    assert at.retaliate_counters == 6 and at.retaliate_turn == ctx.game.turn   # intent recorded


@test
def t_krookodile_comeback():
    T = ("If any of your Pokémon were Knocked Out by damage from an attack during your opponent's "
         "last turn, this attack does 160 more damage.")
    assert run(T, base=60)[0] == 60                                 # no KO last turn -> base
    assert run(T, base=60, ko_last=True)[0] == 220                  # a mon KO'd on opp's last turn -> +160


@test
def t_espurr_emma():
    T = "If you played Emma from your hand during this turn, this attack does 60 more damage."
    assert run(T, base=10)[0] == 10                                 # didn't play Emma -> base
    assert run(T, base=10, played=['Emma'])[0] == 70               # played Emma this turn -> +60


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
