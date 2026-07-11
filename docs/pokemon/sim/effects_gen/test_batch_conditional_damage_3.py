#!/usr/bin/env python3
"""Unit tests for batch conditional_damage_3. Asserts the returned Active damage for each effect,
covering both branches of every condition (met vs unmet) and the correct per-count multipliers."""
from collections import Counter
from effects_testkit import mk, run, runner, VANILLA
import attack_effects as AE
import effects_gen.batch_conditional_damage_3  # noqa: F401  (registers the effects)
from effects_gen.batch_conditional_damage_3 import _is_ex_or_v
from engine import Mon
from cards import load_cards

_BK, _BN = load_cards()
EX = next(c for c in _BK.values() if c.is_ex)                       # any Pokémon ex (for ex-gated tests)
IRON = _BN['Iron Hands'][0]                                        # a Future ('Iron ___') Pokémon
DARTRIX = next(c for c in _BN['Dartrix'] if any(a['name'] == 'United Wings' for a in c.attacks))
HONEDGE, DOUBLADE, AEGIS = _BN['Honedge'][0], _BN['Doublade'][0], _BN['Aegislash'][0]
RT2 = next(c for c in _BK.values() if c.retreat == 2)              # Retreat Cost {C}{C}
RT0 = next(c for c in _BK.values() if c.retreat == 0)              # Retreat Cost 0
S1 = next(c for c in _BK.values() if c.stage == 1)                 # a non-Basic (Stage 1) Pokémon


def _fn(key):
    return AE.ATTACK_EFFECTS[AE.normalize(key)]


# ---------------------------------------------------------------- exact effect keys
K_REVEAL = "Reveal any number of Honedge, Doublade, and Aegislash from your hand, and this attack does 60 damage for each card you revealed in this way."
K_SELFCTR = "This attack does 20 damage for each damage counter on this Pokémon."
K_OPPSPEC = "This attack does 40 damage for each Special Energy attached to all of your opponent's Pokémon."
K_UW = "This attack does 20 damage for each Pokémon in your discard pile that has the United Wings attack."
K_MYBASIC = "This attack does 20 damage for each of your Basic Pokémon in play."
K_RETREAT = "This attack does 50 damage for each {C} in your opponent's Active Pokémon's Retreat Cost."
K_OPPNRG = "This attack does 40 more damage for each Energy attached to your opponent's Active Pokémon."
K_SELFR = "This attack does 80 more damage for each {R} Energy attached to this Pokémon."
K_SELFD = "This attack does 40 more damage for each {D} Energy attached to this Pokémon."
K_OPPCTR = "This attack does 50 more damage for each damage counter on your opponent's Active Pokémon."
K_OPPEX = "If your opponent's Active Pokémon is a Pokémon ex, this attack does 50 more damage."
K_OPPEXV = "If your opponent's Active Pokémon is a Pokémon ex or Pokémon V, this attack does 80 more damage."
K_MOREPRIZE = "If you have more Prize cards remaining than your opponent, this attack does 90 more damage."
K_LE2PRIZE = "If your opponent has 2 or fewer Prize cards remaining, this attack does 100 more damage."
K_FUTURE = "If your opponent has any Future Pokémon in play, this attack does 120 more damage."
K_3NRG = "If you have 3 or more Energy in play, this attack does 70 more damage. This attack's damage isn't affected by Weakness."
K_PRIZE2 = "During your next turn, if the Defending Pokémon is Knocked Out, take 2 more Prize cards."
K_COSTRED = "If this Pokémon has any damage counters on it, this attack can be used for {F}."
K_MYSTAD = "If you have a Stadium in play, this attack does 50 more damage."
K_ANYSTAD = "If a Stadium is in play, this attack does 60 more damage. Then, discard that Stadium."
K_OPPSTAD = "If your opponent has a Stadium in play, discard it. If you do, your opponent can't play any Stadium cards from their hand during their next turn."
K_FORMRANK = "If this Pokémon used Form Ranks during your last turn, this attack does 90 more damage."
K_EVOLVE = "If this Pokémon evolved from Gimmighoul during this turn, this attack does 90 more damage."
K_ANCIENT = "If 1 of your other Ancient Pokémon used an attack during your last turn, this attack does 150 more damage."


# ---------------------------------------------------------------- variable "×"
def t_reveal_sword_line():
    ctx, at, df, me, opp = mk(text=K_REVEAL, base=60)
    me.hand = [('P', HONEDGE), ('P', DOUBLADE), ('P', AEGIS), ('E', 'Fire'), ('P', VANILLA)]
    assert _fn(K_REVEAL)(ctx) == 180, "60 * 3 sword-line cards revealed"
    ctx, at, df, me, opp = mk(text=K_REVEAL, base=60)
    me.hand = [('P', HONEDGE), ('P', HONEDGE)]           # 2 copies of ONE name -> counts copies, not distinct
    assert _fn(K_REVEAL)(ctx) == 120, "must count duplicate copies (guard vs a set-based regression)"
    ctx, at, df, me, opp = mk(text=K_REVEAL, base=60)
    me.hand = [('E', 'Fire'), ('P', VANILLA)]           # none of the line -> 0
    assert _fn(K_REVEAL)(ctx) == 0


def t_20_per_self_counter():
    ctx, at, df, me, opp = mk(text=K_SELFCTR, base=20)
    at.damage = 30                                       # 3 counters
    assert _fn(K_SELFCTR)(ctx) == 60
    ctx, at, *_ = mk(text=K_SELFCTR, base=20)            # undamaged -> 0
    assert _fn(K_SELFCTR)(ctx) == 0


def t_40_per_opp_special():
    ctx, at, df, me, opp = mk(text=K_OPPSPEC, base=40, def_special=('Prism Energy',), opp_bench=1)
    opp.bench[0].special = ['Mist Energy']               # 2 Special Energy across opp's Pokémon
    assert _fn(K_OPPSPEC)(ctx) == 80
    ctx, at, df, me, opp = mk(text=K_OPPSPEC, base=40, opp_bench=1)   # none attached -> 0
    assert _fn(K_OPPSPEC)(ctx) == 0


def t_20_per_united_wings():
    ctx, at, df, me, opp = mk(text=K_UW, base=20)
    me.discard = [('P', DARTRIX), ('P', DARTRIX), ('E', 'Fire'), ('P', VANILLA)]
    assert _fn(K_UW)(ctx) == 40                          # 2 United-Wings Pokémon in discard
    ctx, at, df, me, opp = mk(text=K_UW, base=20)
    me.discard = [('P', VANILLA), ('E', 'Fire')]         # no United-Wings holder -> 0
    assert _fn(K_UW)(ctx) == 0


def t_20_per_my_basic():
    ctx, at, df, me, opp = mk(text=K_MYBASIC, base=20, my_bench=2)
    assert _fn(K_MYBASIC)(ctx) == 60                     # active + 2 Basic bench
    ctx, at, df, me, opp = mk(text=K_MYBASIC, base=20, my_bench=1)
    me.bench.append(Mon(S1))                             # a Stage-1 mon is NOT a Basic
    assert _fn(K_MYBASIC)(ctx) == 40                     # active + 1 Basic bench (Stage 1 excluded)


def t_50_per_opp_retreat():
    ctx, at, df, me, opp = mk(text=K_RETREAT, base=50)
    nd = Mon(RT2); ctx.defender = nd; opp.active = nd
    assert _fn(K_RETREAT)(ctx) == 100                    # 50 * 2 {C}
    ctx, at, df, me, opp = mk(text=K_RETREAT, base=50)
    nd = Mon(RT0); ctx.defender = nd; opp.active = nd
    assert _fn(K_RETREAT)(ctx) == 0                      # free retreat -> 0
    ctx, at, df, me, opp = mk(text=K_RETREAT, base=50)   # RT2 but Magnetic Metal zeroes eff_retreat -> 0
    nd = Mon(RT2); nd.special = ['Magnetic Metal Energy']; ctx.defender = nd; opp.active = nd
    assert _fn(K_RETREAT)(ctx) == 0


# ---------------------------------------------------------------- bonus "+" per count
def t_plus_40_per_opp_energy():
    ctx, at, df, me, opp = mk(text=K_OPPNRG, base=40, def_energy={'Colorless': 2})
    assert _fn(K_OPPNRG)(ctx) == 120                     # 40 + 40*2
    ctx, at, df, me, opp = mk(text=K_OPPNRG, base=40)
    df.energy = Counter()                                # no energy on defender
    assert _fn(K_OPPNRG)(ctx) == 40


def t_plus_80_per_self_fire():
    ctx, at, df, me, opp = mk(text=K_SELFR, base=40, atk_energy={'Fire': 2, 'Colorless': 1})
    assert _fn(K_SELFR)(ctx) == 200                      # 40 + 80*2 Fire (Colorless ignored)
    ctx, at, df, me, opp = mk(text=K_SELFR, base=40, atk_energy={'Colorless': 3})
    assert _fn(K_SELFR)(ctx) == 40


def t_plus_40_per_self_dark():
    ctx, at, df, me, opp = mk(text=K_SELFD, base=20, atk_energy={'Darkness': 3})
    assert _fn(K_SELFD)(ctx) == 140                      # 20 + 40*3
    ctx, at, df, me, opp = mk(text=K_SELFD, base=20, atk_energy={'Colorless': 3})
    assert _fn(K_SELFD)(ctx) == 20


def t_plus_50_per_opp_counter():
    ctx, at, df, me, opp = mk(text=K_OPPCTR, base=50)
    df.damage = 40                                       # 4 counters
    assert _fn(K_OPPCTR)(ctx) == 250                     # 50 + 50*4
    ctx, at, df, me, opp = mk(text=K_OPPCTR, base=50)
    assert _fn(K_OPPCTR)(ctx) == 50


# ---------------------------------------------------------------- bonus "+" if condition
def t_plus_50_if_opp_ex():
    ctx, at, df, me, opp = mk(text=K_OPPEX, base=10)
    nd = Mon(EX); ctx.defender = nd; opp.active = nd
    assert _fn(K_OPPEX)(ctx) == 60
    ctx, at, df, me, opp = mk(text=K_OPPEX, base=10)     # VANILLA defender (not ex)
    assert _fn(K_OPPEX)(ctx) == 10


def t_plus_80_if_opp_ex_or_v():
    ctx, at, df, me, opp = mk(text=K_OPPEXV, base=80)
    nd = Mon(EX); ctx.defender = nd; opp.active = nd
    assert _fn(K_OPPEXV)(ctx) == 160
    ctx, at, df, me, opp = mk(text=K_OPPEXV, base=80)
    assert _fn(K_OPPEXV)(ctx) == 80
    # cover the dead-but-real Pokémon V branch of the helper (no V exists in the reg H/I/J pool)
    class _C:
        def __init__(self, name, is_ex): self.name, self.is_ex = name, is_ex
    assert _is_ex_or_v(_C('Zacian V', False))            # ' V'
    assert _is_ex_or_v(_C('Zamazenta VSTAR', False))     # ' VSTAR'
    assert _is_ex_or_v(_C('Eternatus VMAX', False))      # ' VMAX'
    assert _is_ex_or_v(_C('Charizard ex', True))         # ex still counts
    assert not _is_ex_or_v(_C('Pikachu', False))         # neither -> False


def t_plus_90_if_more_prizes():
    assert run(K_MOREPRIZE, base=50, my_prizes=5, opp_prizes=3)[0] == 140
    assert run(K_MOREPRIZE, base=50, my_prizes=3, opp_prizes=5)[0] == 50
    assert run(K_MOREPRIZE, base=50, my_prizes=4, opp_prizes=4)[0] == 50   # equal -> no bonus


def t_plus_100_if_opp_le2():
    assert run(K_LE2PRIZE, base=70, opp_prizes=2)[0] == 170
    assert run(K_LE2PRIZE, base=70, opp_prizes=1)[0] == 170
    assert run(K_LE2PRIZE, base=70, opp_prizes=3)[0] == 70


def t_plus_120_if_opp_future():
    ctx, at, df, me, opp = mk(text=K_FUTURE, base=20, opp_bench=1)
    opp.bench[0] = Mon(IRON)                              # a Future Pokémon on the opp bench
    assert _fn(K_FUTURE)(ctx) == 140
    ctx, at, df, me, opp = mk(text=K_FUTURE, base=20, opp_bench=1)   # all VANILLA (non-Future)
    assert _fn(K_FUTURE)(ctx) == 20


def t_plus_70_if_3_energy():
    ctx, at, df, me, opp = mk(text=K_3NRG, base=20, atk_energy={'Fighting': 3}, my_bench=0)
    assert _fn(K_3NRG)(ctx) == 90                         # 3 energy on the lone active -> +70
    ctx, at, df, me, opp = mk(text=K_3NRG, base=20, atk_energy={'Fighting': 2}, my_bench=0)
    assert _fn(K_3NRG)(ctx) == 20                         # only 2 -> no bonus
    ctx, at, df, me, opp = mk(text=K_3NRG, base=20, atk_energy={'Fighting': 1}, my_bench=1)
    me.bench[0].energy = Counter({'Water': 2})            # 1 + 2 across my Pokémon = 3 -> +70
    assert _fn(K_3NRG)(ctx) == 90


# ---------------------------------------------------------------- fixed [N] (rider unmodeled)
def t_fixed_take_2_more_prizes():
    assert run(K_PRIZE2, base=30)[0] == 30               # flat damage; prize rider has no engine hook


def t_fixed_cost_reduction():
    assert run(K_COSTRED, base=130)[0] == 130            # damage unconditional (cost gate, not damage)
    ctx, at, *_ = mk(text=K_COSTRED, base=130)
    at.damage = 20                                       # damaged -> still 130 (cost reduction only)
    assert _fn(K_COSTRED)(ctx) == 130


# ---------------------------------------------------------------- Stadium-gated (unmodeled -> base)
def t_plus_50_if_my_stadium():
    assert run(K_MYSTAD, base=30)[0] == 30               # no Stadium -> base
    ctx, at, df, me, opp = mk(text=K_MYSTAD, base=30, stadium='Prism Tower')
    assert _fn(K_MYSTAD)(ctx) == 80                       # Stadium in play -> +50


def t_plus_60_if_stadium_discard():
    assert run(K_ANYSTAD, base=60)[0] == 60              # no Stadium -> base, nothing discarded
    ctx, at, df, me, opp = mk(text=K_ANYSTAD, base=60, stadium='Prism Tower')
    assert _fn(K_ANYSTAD)(ctx) == 120                    # +60
    assert ctx.game.stadium is None                      # and the Stadium is discarded


def t_fixed_discard_opp_stadium():
    assert run(K_OPPSTAD, base=40)[0] == 40              # no Stadium -> flat damage, nothing discarded
    ctx, at, df, me, opp = mk(text=K_OPPSTAD, base=40, stadium='Prism Tower')
    assert _fn(K_OPPSTAD)(ctx) == 40                     # flat damage
    assert ctx.game.stadium is None                      # Stadium in play discarded


# ---------------------------------------------------------------- setup-gated (timing untracked -> base)
def t_form_ranks_base():
    assert run(K_FORMRANK, base=30)[0] == 30             # didn't use Form Ranks last turn -> base
    ctx, at, df, me, opp = mk(text=K_FORMRANK, base=30)
    at.last_atk = 'Form Ranks'; at.last_atk_turn = ctx.game.turn - 2   # used it on your PREVIOUS turn
    assert _fn(K_FORMRANK)(ctx) == 120                    # -> +90
    ctx2, at2, *_ = mk(text=K_FORMRANK, base=30)
    at2.last_atk = 'Form Ranks'; at2.last_atk_turn = ctx2.game.turn    # used THIS turn, not last -> base
    assert _fn(K_FORMRANK)(ctx2) == 30


def t_evolved_this_turn_base():
    assert run(K_EVOLVE, base=30)[0] == 30               # didn't evolve this turn -> base
    ctx, at, df, me, opp = mk(text=K_EVOLVE, base=30)
    at.evolved_turn = ctx.game.turn                       # evolved this turn
    assert _fn(K_EVOLVE)(ctx) == 120                       # -> +90
    ctx2, at2, *_ = mk(text=K_EVOLVE, base=30)
    at2.evolved_turn = ctx2.game.turn - 2                  # evolved a PRIOR turn -> no bonus
    assert _fn(K_EVOLVE)(ctx2) == 30


def t_ancient_attacked_base():
    assert run(K_ANCIENT, base=30)[0] == 30


TESTS = [
    t_reveal_sword_line, t_20_per_self_counter, t_40_per_opp_special, t_20_per_united_wings,
    t_20_per_my_basic, t_50_per_opp_retreat, t_plus_40_per_opp_energy, t_plus_80_per_self_fire,
    t_plus_40_per_self_dark, t_plus_50_per_opp_counter, t_plus_50_if_opp_ex, t_plus_80_if_opp_ex_or_v,
    t_plus_90_if_more_prizes, t_plus_100_if_opp_le2, t_plus_120_if_opp_future, t_plus_70_if_3_energy,
    t_fixed_take_2_more_prizes, t_fixed_cost_reduction, t_plus_50_if_my_stadium,
    t_plus_60_if_stadium_discard, t_fixed_discard_opp_stadium, t_form_ranks_base,
    t_evolved_this_turn_base, t_ancient_attacked_base,
]

if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
