#!/usr/bin/env python3
"""Tests for batch ab_other_1. Each ability's registered fn is exercised directly against real
Mon/Player objects built by the shared test kit. Run: python3 -m abilities_gen.test_batch_ab_other_1
"""
from effects_testkit import mk, runner
import ability_effects as AB
import abilities_gen.batch_ab_other_1  # noqa: F401  (import registers the batch)
from engine import Mon
from cards import load_cards

BK, BN = load_cards()
SHELMET = next(c for c in BN['Shelmet'] if c.abilities)      # the WHT printing with Stimulated Evolution
ACCELGOR = BN['Accelgor'][0]                                 # evolves from Shelmet, stage 1
KARRABLAST = BN['Karrablast'][0]
CARBINK = BN['Carbink'][0]                                   # printed Fighting, weak Grass
KYUREM = next(c for c in BN['Kyurem'] if c.abilities)
GENESECT = next(c for c in BN['Genesect'] if c.abilities)
WK_PSY = next(c for c in BK.values() if c.weakness == 'Psychic')
WK_FIG = next(c for c in BK.values() if c.weakness == 'Fighting')
WK_GRS = next(c for c in BK.values() if c.weakness == 'Grass')

STIM = "- If you have Karrablast in play, this Pokémon can evolve during your first turn or the turn you play it."
PLASMA = ('- If your opponent has any cards in their discard pile that have "Colress" in the name, '
          'this Pokémon can use the Trifrost attack for {C}.')
ACE = "- If this Pokémon has a Pokémon Tool attached, your opponent can't play any ACE SPEC cards from their hand."
DBL = "- As long as this Pokémon is in play, it is {F} and {P} type."


def fn_of(key):
    return AB.ABILITY_EFFECTS[AB.normalize(key)]['fn']


TESTS = []
def test(f): TESTS.append(f); return f


# ---- 1) Stimulated Evolution --------------------------------------------------------------------
@test
def t_stim_evolves_with_karrablast():
    ctx, at, df, me, opp = mk()
    holder = Mon(SHELMET); holder.turns = 0             # the turn it was played
    holder.damage = 30; holder.energy['Water'] = 2      # in-place evolve must carry damage + energy over
    me.active = holder
    me.bench = [Mon(KARRABLAST)]                        # Karrablast in play
    me.hand = [('P', ACCELGOR)]
    assert fn_of(STIM)(AB.ActivatedCtx(me, opp, holder, ctx.game)) is True
    assert me.active is holder                          # SAME Mon object (evolved in place, not replaced)
    assert holder.card.name == 'Accelgor'              # evolved in place
    assert holder.damage == 30 and holder.energy['Water'] == 2   # damage + energy preserved across evolution
    assert ('P', ACCELGOR) not in me.hand              # evolution card consumed


@test
def t_stim_no_karrablast_noop():
    ctx, at, df, me, opp = mk()
    holder = Mon(SHELMET); holder.turns = 0
    me.active = holder
    me.bench = []                                       # no Karrablast in play
    me.hand = [('P', ACCELGOR)]
    assert fn_of(STIM)(AB.ActivatedCtx(me, opp, holder, ctx.game)) is False
    assert holder.card.name == 'Shelmet'
    assert ('P', ACCELGOR) in me.hand


@test
def t_stim_already_aged_noop():
    ctx, at, df, me, opp = mk()
    holder = Mon(SHELMET); holder.turns = 1            # not the turn it was played -> engine path handles it
    me.active = holder
    me.bench = [Mon(KARRABLAST)]
    me.hand = [('P', ACCELGOR)]
    assert fn_of(STIM)(AB.ActivatedCtx(me, opp, holder, ctx.game)) is False
    assert holder.card.name == 'Shelmet'


@test
def t_stim_no_evo_in_hand_noop():
    ctx, at, df, me, opp = mk()
    holder = Mon(SHELMET); holder.turns = 0
    me.active = holder
    me.bench = [Mon(KARRABLAST)]
    me.hand = []                                        # nothing to evolve into
    assert fn_of(STIM)(AB.ActivatedCtx(me, opp, holder, ctx.game)) is False
    assert holder.card.name == 'Shelmet'


@test
def t_stim_wrong_card_in_hand_noop():
    # A non-matching Pokémon in hand must NOT satisfy the evolves_from/stage predicate (guards the
    # branch an empty hand can't exercise). Carbink is a Basic that doesn't evolve from Shelmet.
    ctx, at, df, me, opp = mk()
    holder = Mon(SHELMET); holder.turns = 0
    me.active = holder
    me.bench = [Mon(KARRABLAST)]
    me.hand = [('P', CARBINK)]                          # present but not Shelmet's evolution
    assert fn_of(STIM)(AB.ActivatedCtx(me, opp, holder, ctx.game)) is False
    assert holder.card.name == 'Shelmet'
    assert ('P', CARBINK) in me.hand                    # unrelated card left untouched


# ---- 2) Plasma Bane (cost reducer -> 0 damage buff) ---------------------------------------------
@test
def t_plasma_bane_never_a_damage_buff():
    ctx, at, df, me, opp = mk()
    attacker = Mon(KYUREM)
    trifrost = next(a for a in KYUREM.attacks if a['name'] == 'Trifrost')
    # Even with the condition satisfied (a "Colress" card in the opponent's discard), a cost
    # reduction is never a damage bonus.
    opp.discard = [('T', {'name': "Colress's Experiment"})]
    assert fn_of(PLASMA)(attacker, df, trifrost, ctx.game) == 0
    opp.discard = []                                    # condition unmet -> still 0
    assert fn_of(PLASMA)(attacker, df, trifrost, ctx.game) == 0


# ---- 3) ACE Nullifier (out-of-pool lock -> never disables an ability) ---------------------------
@test
def t_ace_nullifier_never_locks():
    ctx, at, df, me, opp = mk()
    holder = Mon(GENESECT)
    # lock signature: fn(mon, owner, opp, game) -> bool; must stay False (ACE SPEC card-play lock,
    # not an ability-lock; Tool + ACE SPEC both unmodeled).
    assert fn_of(ACE)(holder, me, opp, ctx.game) is False


# ---- 4) Double Type (Weakness to the added type) ------------------------------------------------
@test
def t_double_type_doubles_vs_added_type_weak():
    ctx, at, df, me, opp = mk()
    carbink = Mon(CARBINK)                              # printed Fighting -> added type is Psychic
    atk = {'dmg': 70, 'text': '', 'cost': 'FFC', 'name': 'Counter Jewel'}
    dfn = Mon(WK_PSY)                                   # Weak to Psychic (the added type)
    assert fn_of(DBL)(carbink, dfn, atk, ctx.game) == 70   # +base simulates the extra ×2


@test
def t_double_type_no_bonus_otherwise():
    ctx, at, df, me, opp = mk()
    carbink = Mon(CARBINK)
    atk = {'dmg': 70, 'name': 'Counter Jewel'}
    f = fn_of(DBL)
    # Weak to the printed type (Fighting): the engine already doubles that -> no extra here.
    assert f(carbink, Mon(WK_FIG), atk, ctx.game) == 0
    # Weak to neither {F} nor {P}: no bonus.
    assert f(carbink, Mon(WK_GRS), atk, ctx.game) == 0
    # No defender: no bonus.
    assert f(carbink, None, atk, ctx.game) == 0
    # A status attack (no base damage) grants no spurious damage even vs an added-type-Weak defender.
    assert f(carbink, Mon(WK_PSY), {'dmg': 0, 'name': 'Status'}, ctx.game) == 0


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
