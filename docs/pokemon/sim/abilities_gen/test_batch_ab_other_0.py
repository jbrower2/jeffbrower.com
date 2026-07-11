#!/usr/bin/env python3
"""Unit tests for ability batch ab_other_0. Each registered lambda is exercised directly against real
engine Mon/Player/Game objects built by the shared test kit. Run:
    python3 -m abilities_gen.test_batch_ab_other_0
"""
from effects_testkit import mk, runner
import ability_effects as AB
import abilities_gen.batch_ab_other_0  # noqa: F401 (import registers the batch via @ability decorators)


def fn(key):
    return AB.ABILITY_EFFECTS[AB.normalize(key)]['fn']


def kind(key):
    return AB.ABILITY_EFFECTS[AB.normalize(key)]['kind']


# ---- keys (exact text) --------------------------------------------------------------------------
K_EXPERT = "- If any damage is done to this Pokémon by attacks, flip a coin. If heads, prevent that damage."
K_STURDY = "- If this Pokémon has full HP and would be Knocked Out by damage from an attack, it is not Knocked Out, and its remaining HP becomes 10."
K_NEEDLES = "- If this Pokémon is in the Active Spot and is Knocked Out by damage from an attack from your opponent's Pokémon, put 6 damage counters on the Attacking Pokémon."
K_HUSK = "- If this Pokémon is Knocked Out by damage from an attack from your opponent's Pokémon ex, your opponent can't take any Prize cards for it."
K_BOOSTED = "- As long as this Pokémon is in the Active Spot, it can evolve during your first turn or the turn you play it."
K_FOODPREP = "- Attacks used by this Pokémon cost {C} less for each Kofu card in your discard pile."
K_GLARE = "- As long as this Pokémon is in the Active Spot, your opponent can't play any Pokémon that has an Ability from their hand, except for Team Rocket's Pokémon."
K_HOLES = "- Whenever your opponent's Active Pokémon moves to the Bench during their turn, place 2 damage counters on that Pokémon."
K_IMPULSE = "- Whenever your opponent plays a Pokémon from their hand to evolve 1 of their Pokémon, put 4 damage counters on that Pokémon. The effect of Darkest Impulse doesn't stack."
K_BUBBLES = "- If you have any Tera Pokémon in play, this Pokémon can use the Double-Edge attack for {P}."
K_ROAR = "- If your opponent's Active Pokémon is a Pokémon ex, this Pokémon can evolve during your first turn or the turn you play it."
K_STIM = "- If you have Shelmet in play, this Pokémon can evolve during your first turn or the turn you play it."
K_DROP = "- During your opponent's turn, if this Pokémon is discarded from your deck by an effect of an attack or Ability from your opponent's Pokémon, or by an effect of your opponent's Item or Supporter cards, discard the top 8 cards of your opponent's deck."
K_UNNERVE = "- Whenever your opponent plays an Item or Supporter card from their hand, prevent all effects of that card done to this Pokémon."

IMMUNE_NOOPS = [K_BOOSTED, K_FOODPREP, K_GLARE, K_HOLES, K_IMPULSE,
                K_BUBBLES, K_ROAR, K_STIM, K_DROP, K_UNNERVE]

TESTS = []
def test(f): TESTS.append(f); return f


# ============================================================ Expert Hider (passive_dr, coin-flip)
@test
def t_expert_hider_heads():
    ctx, at, df, me, opp = mk(flips=(0.0,))          # heads -> prevent all
    assert kind(K_EXPERT) == 'passive_dr'
    assert fn(K_EXPERT)(100, at, df, opp, ctx.game) == 0


@test
def t_expert_hider_tails():
    ctx, at, df, me, opp = mk(flips=(0.9,))          # tails -> unchanged
    assert fn(K_EXPERT)(100, at, df, opp, ctx.game) == 100


# ============================================================ Sturdy (passive_dr, survive at 10)
@test
def t_sturdy_full_hp_lethal():
    ctx, at, df, me, opp = mk()
    assert df.damage == 0                            # full HP
    mh = df.max_hp
    assert fn(K_STURDY)(mh + 50, at, df, opp, ctx.game) == mh - 10   # lethal -> capped, survives at 10


@test
def t_sturdy_full_hp_nonlethal():
    ctx, at, df, me, opp = mk()
    mh = df.max_hp
    assert fn(K_STURDY)(mh - 30, at, df, opp, ctx.game) == mh - 30   # would not KO -> unchanged


@test
def t_sturdy_not_full_hp():
    ctx, at, df, me, opp = mk()
    df.damage = 10                                   # already damaged -> Sturdy inactive
    mh = df.max_hp
    assert fn(K_STURDY)(mh + 50, at, df, opp, ctx.game) == mh + 50   # unchanged


@test
def t_sturdy_exactly_lethal_boundary():
    # "would be Knocked Out" includes an exactly-lethal hit (dmg == max_hp): Sturdy fires.
    ctx, at, df, me, opp = mk()
    mh = df.max_hp
    assert fn(K_STURDY)(mh, at, df, opp, ctx.game) == mh - 10        # capped -> survives at 10
    # one below lethal at full HP: no KO to prevent -> the hit passes through untouched.
    assert fn(K_STURDY)(mh - 1, at, df, opp, ctx.game) == mh - 1


# ============================================================ Exploding Needles (on_damaged, KO)
@test
def t_exploding_needles_ko():
    ctx, at, df, me, opp = mk()                      # df is opp.active
    assert kind(K_NEEDLES) == 'on_damaged'
    df.damage = df.card.hp + 10                       # lethal hit already applied -> is_ko True
    fn(K_NEEDLES)(at, df, opp, ctx.game)
    assert at.damage == 60                            # 6 counters back on the attacker


@test
def t_exploding_needles_no_ko():
    ctx, at, df, me, opp = mk()
    df.damage = 0                                     # survived the hit
    fn(K_NEEDLES)(at, df, opp, ctx.game)
    assert at.damage == 0                             # no KO -> no counterattack


@test
def t_exploding_needles_benched_no_fire():
    ctx, at, df, me, opp = mk()
    opp.active = opp.bench[0]                          # a different Pokémon is Active
    opp.bench = [df]                                   # df is now on the Bench
    df.damage = df.card.hp + 100                       # KO'd, but not in the Active Spot
    fn(K_NEEDLES)(at, df, opp, ctx.game)
    assert at.damage == 0                              # Active-Spot condition fails -> no fire


@test
def t_exploding_needles_adds_not_sets():
    # 6 counters are ADDED to whatever damage the attacker already carries (not an assignment),
    # and go on raw (no effect_immune gate — matches the _counterattack_3 counter convention).
    ctx, at, df, me, opp = mk()
    at.damage = 30                                     # attacker already softened
    at.special = ['Mist Energy']                       # an effect-shield must NOT block ability counters
    df.damage = df.card.hp + 10                         # lethal -> is_ko True, df is Active
    fn(K_NEEDLES)(at, df, opp, ctx.game)
    assert at.damage == 90                              # 30 + 60, shield ignored


# ============================================================ Fragile Husk (on_damaged no-op)
@test
def t_fragile_husk_noop():
    ctx, at, df, me, opp = mk()
    assert kind(K_HUSK) == 'on_damaged'
    df.damage = df.card.hp + 10                        # KO'd
    before = (at.damage, len(opp.prizes), opp.prizes_taken, len(me.prizes))
    assert fn(K_HUSK)(at, df, opp, ctx.game) is None   # no prize-denial mechanism -> no state change
    assert (at.damage, len(opp.prizes), opp.prizes_taken, len(me.prizes)) == before


# ============================================================ immunity/False no-ops (no engine hook)
@test
def t_immunity_noops_all_false():
    for key in IMMUNE_NOOPS:
        ctx, at, df, me, opp = mk()
        assert kind(key) == 'immunity', key
        assert fn(key)(at, df, opp, ctx.game) is False, key


# individual per-ability no-op tests (one per key, so each exact-text key is covered on its own)
@test
def t_boosted_evolution_noop():
    ctx, at, df, me, opp = mk()
    assert fn(K_BOOSTED)(at, df, opp, ctx.game) is False


@test
def t_food_prep_noop():
    ctx, at, df, me, opp = mk()
    assert fn(K_FOODPREP)(at, df, opp, ctx.game) is False


@test
def t_potent_glare_noop():
    ctx, at, df, me, opp = mk()
    assert fn(K_GLARE)(at, df, opp, ctx.game) is False


@test
def t_holes_noop():
    ctx, at, df, me, opp = mk()
    assert fn(K_HOLES)(at, df, opp, ctx.game) is False


@test
def t_darkest_impulse_noop():
    ctx, at, df, me, opp = mk()
    assert fn(K_IMPULSE)(at, df, opp, ctx.game) is False


@test
def t_glistening_bubbles_noop():
    ctx, at, df, me, opp = mk()
    assert fn(K_BUBBLES)(at, df, opp, ctx.game) is False


@test
def t_fighting_roar_noop():
    ctx, at, df, me, opp = mk()
    assert fn(K_ROAR)(at, df, opp, ctx.game) is False


@test
def t_stimulated_evolution_noop():
    ctx, at, df, me, opp = mk()
    assert fn(K_STIM)(at, df, opp, ctx.game) is False


@test
def t_startling_drop_noop():
    ctx, at, df, me, opp = mk()
    assert fn(K_DROP)(at, df, opp, ctx.game) is False


@test
def t_unnerve_noop():
    ctx, at, df, me, opp = mk()
    assert fn(K_UNNERVE)(at, df, opp, ctx.game) is False


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
