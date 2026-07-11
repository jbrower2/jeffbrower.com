#!/usr/bin/env python3
"""Unit tests for effect batch damage_reduction_0.

Covers: flat self-reduction next turn (wired end-to-end through incoming_damage), immediate
"N less for each X" scaling (floored at 0), KO->wall, and the intent-recorded conditional/threshold
preventions + defender outgoing-attack debuffs. A coverage test asserts every batch key is registered.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # ensure sim/ importable
from effects_testkit import mk, run, runner, BK
import attack_effects as AE
import effects
import effects_gen.batch_damage_reduction_0 as BATCH  # noqa: F401  (registers the effects)

_WALL = BATCH._WALL


def call(key, ctx):
    """Invoke the registered effect for `key` against an already-prepared ctx."""
    return AE.ATTACK_EFFECTS[AE.normalize(key)](ctx)


# ---------------------------------------------------------------- A. flat self-reduction
def t_flat_self_reduction_all_amounts():
    for n in (10, 20, 30, 40, 50, 60):
        key = (f"During your opponent's next turn, this Pokémon takes {n} less damage from attacks "
               "(after applying Weakness and Resistance).")
        d, ctx, at, df, me, opp = run(key, base=50)
        assert d == 50, (n, d)                                  # deals its printed base damage
        assert at.dr_amount == n, (n, at.dr_amount)            # schedules the flat reduction
        assert at.dr_turn == ctx.game.turn, (n, at.dr_turn, ctx.game.turn)


def t_flat_self_reduction_zero_base():
    # Seedot-style printing has base 0: it still schedules the reduction but deals no damage.
    key = ("During your opponent's next turn, this Pokémon takes 30 less damage from attacks "
           "(after applying Weakness and Resistance).")
    d, ctx, at, df, me, opp = run(key, base=0)
    assert d == 0 and at.dr_amount == 30


def t_flat_self_reduction_wired_end_to_end():
    # The reduction really lands during the opponent's NEXT turn, then lapses.
    key = ("During your opponent's next turn, this Pokémon takes 30 less damage from attacks "
           "(after applying Weakness and Resistance).")
    d, ctx, at, df, me, opp = run(key, base=50)
    ctx.game.turn = at.dr_turn                                  # SAME turn it was set -> not yet active
    assert effects.incoming_damage(100, df, at, me, ctx.game) == 100
    ctx.game.turn = at.dr_turn + 1                              # opponent's next turn -> applies
    assert effects.incoming_damage(100, df, at, me, ctx.game) == 70
    ctx.game.turn = at.dr_turn + 2                              # turn after -> lapsed
    assert effects.incoming_damage(100, df, at, me, ctx.game) == 100


# ---------------------------------------------------------------- E. immediate "N less for each X"
def t_minus_10_per_own_counter():
    key = "This attack does 10 less damage for each damage counter on this Pokémon."
    ctx, at, df, me, opp = mk(base=150); at.damage = 50        # 5 counters -> -50
    assert call(key, ctx) == 100
    ctx, at, df, me, opp = mk(base=150); at.damage = 0         # no counters -> full
    assert call(key, ctx) == 150
    ctx, at, df, me, opp = mk(base=150); at.damage = 200       # 20 counters -> floored at 0
    assert call(key, ctx) == 0


def t_minus_30_per_retreat():
    key = "This attack does 30 less damage for each {C} in your opponent's Active Pokémon's Retreat Cost."
    assert run(key, base=120)[0] == 60                         # VANILLA retreat 2 -> -60
    assert run(key, base=40)[0] == 0                           # floored at 0
    # Magnetic Metal Energy zeroes the defender's retreat cost -> no reduction (full damage).
    assert run(key, base=120, def_special=('Magnetic Metal Energy',))[0] == 120


def t_minus_50_per_retreat():
    key = "This attack does 50 less damage for each {C} in your opponent's Active Pokémon's Retreat Cost."
    assert run(key, base=200)[0] == 100                        # retreat 2 -> -100
    assert run(key, base=80)[0] == 0                           # floored at 0
    assert run(key, base=200, def_special=('Magnetic Metal Energy',))[0] == 200  # retreat 0 -> full


def t_minus_60_per_opp_energy():
    key = "This attack does 60 less damage for each Energy attached to your opponent's Active Pokémon."
    assert run(key, base=240, def_energy={'Water': 1})[0] == 180
    assert run(key, base=240, def_energy={'Colorless': 2})[0] == 120
    # counts ALL attached Energy across every type (basic + Colorless + special/Wild pseudo-types)
    assert run(key, base=240, def_energy={'Water': 1, 'Colorless': 1, 'Wild': 1})[0] == 60  # 3 -> -180
    assert run(key, base=240, def_energy={'Water': 5})[0] == 0  # floored at 0


# ---------------------------------------------------------------- F. KO -> unconditional wall
def t_ko_then_wall():
    key = ("If your opponent's Pokémon is Knocked Out by damage from this attack, during your "
           "opponent's next turn, prevent all damage from and effects of attacks done to this Pokémon.")
    # KO case: defender's remaining HP <= this attack's damage -> wall scheduled.
    ctx, at, df, me, opp = mk(base=60)
    df.damage = df.max_hp - 10                                  # hp_left = 10 <= 60 -> KO
    assert call(key, ctx) == 60
    assert at.dr_amount == _WALL and at.dr_turn == ctx.game.turn
    ctx.game.turn = at.dr_turn + 1
    assert effects.incoming_damage(300, df, at, me, ctx.game) == 0   # wall prevents all next turn
    # Exact-boundary KO: damage == hp_left still KOs (>= comparison, not strictly greater).
    ctx, at, df, me, opp = mk(base=30)
    df.damage = df.max_hp - 30                                  # hp_left = 30 == base
    assert call(key, ctx) == 30
    assert at.dr_amount == _WALL and at.dr_turn == ctx.game.turn
    # No-KO case: defender survives -> no wall.
    ctx, at, df, me, opp = mk(base=30)
    df.damage = 0                                              # hp_left = 80 > 30 -> not KO
    assert call(key, ctx) == 30
    assert at.dr_amount == 0 and at.dr_turn == -9


def t_ko_then_wall_weakness_branch():
    # _ko_predicted MUST apply Weakness ×2: a hit that would NOT KO at printed base DOES KO once the
    # defender's Weakness doubles it -> the wall is scheduled. (Untested previously: default test Mons
    # are Grass attacker vs Fire-Weak defender, so Weakness never triggered.)
    key = ("If your opponent's Pokémon is Knocked Out by damage from this attack, during your "
           "opponent's next turn, prevent all damage from and effects of attacks done to this Pokémon.")
    fire = next(c for c in BK.values() if c.ptype == 'Fire' and c.stage == 0)  # matches VANILLA's Fire Weakness
    # Weakness matches -> 50 base doubles to 100 >= 80 HP -> KO -> wall.
    ctx, at, df, me, opp = mk(base=50)
    at.card = fire
    assert df.card.weakness == at.card.ptype == 'Fire'         # sanity: Weakness applies
    assert df.hp_left == 80 and 50 < 80                        # base ALONE would not KO
    assert call(key, ctx) == 50                               # still deals printed base damage
    assert at.dr_amount == _WALL, at.dr_amount                # 50*2=100 >= 80 -> KO predicted -> wall
    # Same base, NO Weakness match (Grass attacker) -> 50 < 80 -> survives -> no wall.
    ctx, at, df, me, opp = mk(base=50)
    assert df.card.weakness != at.card.ptype                  # Grass attacker vs Fire-Weak defender
    assert call(key, ctx) == 50
    assert at.dr_amount == 0, at.dr_amount


# ---------------------------------------------------------------- B. conditional prevent-by-class
def t_prevent_by_class():
    cases = [
        ("During your opponent's next turn, prevent all damage done to this Pokémon by attacks from "
         "Basic Pokémon.", 'PreventDmgFromBasic', 30),
        ("During your opponent's next turn, prevent all damage done to this Pokémon by attacks from "
         "Pokémon that have an Ability.", 'PreventDmgFromAbility', 80),
        ("During your opponent's next turn, prevent all damage done to this Pokémon by attacks from "
         "Ancient Pokémon.", 'PreventDmgFromAncient', 120),
    ]
    for key, marker, base in cases:
        d, ctx, at, df, me, opp = run(key, base=base)
        assert d == base, (key, d)                             # deals printed base damage
        assert at.status.get(marker) == ctx.game.turn, (key, at.status)
        assert at.dr_amount == 0, (key, at.dr_amount)          # NOT an unconditional flat wall


# ---------------------------------------------------------------- C. conditional prevent-by-threshold
def t_prevent_by_threshold():
    cases = [
        ("During your opponent's next turn, prevent all damage done to this Pokémon by attacks if "
         "that damage is 40 or less.", 'PreventDmgIfLE40'),
        ("During your opponent's next turn, prevent all damage done to this Pokémon by attacks if "
         "that damage is 60 or less.", 'PreventDmgIfLE60'),
    ]
    for key, marker in cases:
        d, ctx, at, df, me, opp = run(key, base=0)
        assert d == 0, (key, d)
        assert at.status.get(marker) == ctx.game.turn, (key, at.status)
        assert at.dr_amount == 0, (key, at.dr_amount)          # threshold != flat reduction


# ---------------------------------------------------------------- G. team Future-vs-ex prevention
def t_prevent_future_from_ex():
    key = ("During your opponent's next turn, prevent all damage done to each of your Future Pokémon "
           "by attacks from Pokémon ex. If this Pokémon is no longer your Active Pokémon, this effect ends.")
    d, ctx, at, df, me, opp = run(key, base=40)
    assert d == 40
    assert at.status.get('PreventFutureFromEx') == ctx.game.turn
    assert at.dr_amount == 0


# ---------------------------------------------------------------- D. defender outgoing-attack debuff
def t_defender_attack_debuff():
    cases = [
        ("During your opponent's next turn, attacks used by the Defending Pokémon do 20 less damage "
         "(before applying Weakness and Resistance).", 20, 0),
        ("During your opponent's next turn, attacks used by the Defending Pokémon do 30 less damage "
         "(before applying Weakness and Resistance).", 30, 70),
        ("During your opponent's next turn, attacks used by the Defending Pokémon do 40 less damage "
         "(before applying Weakness and Resistance).", 40, 0),
        ("During your opponent's next turn, attacks used by the Defending Pokémon do 100 less damage "
         "(before applying Weakness and Resistance).", 100, 100),
    ]
    for key, amt, base in cases:
        d, ctx, at, df, me, opp = run(key, base=base)
        assert d == base, (key, d)                             # attacker deals its printed base damage
        assert df.next_atk_penalty == amt, (key, getattr(df, 'next_atk_penalty', None))
        assert df.next_atk_penalty_turn == ctx.game.turn, key
        assert at.dr_amount == 0, key                          # debuff is on the DEFENDER, not self-reduction


# ---------------------------------------------------------------- coverage: every batch key registered
def t_all_batch_keys_registered():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'effects_work', 'batches.json')
    batch = next(b for b in json.load(open(path))['batches'] if b['id'] == 'damage_reduction_0')
    for e in batch['effects']:
        assert AE.normalize(e['key']) in AE.ATTACK_EFFECTS, f"missing registration: {e['key']!r}"
    assert len(batch['effects']) == 21, len(batch['effects'])


TESTS = [
    t_flat_self_reduction_all_amounts,
    t_flat_self_reduction_zero_base,
    t_flat_self_reduction_wired_end_to_end,
    t_minus_10_per_own_counter,
    t_minus_30_per_retreat,
    t_minus_50_per_retreat,
    t_minus_60_per_opp_energy,
    t_ko_then_wall,
    t_ko_then_wall_weakness_branch,
    t_prevent_by_class,
    t_prevent_by_threshold,
    t_prevent_future_from_ex,
    t_defender_attack_debuff,
    t_all_batch_keys_registered,
]

if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
