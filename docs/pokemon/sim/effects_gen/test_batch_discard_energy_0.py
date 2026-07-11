#!/usr/bin/env python3
"""Unit tests for effect batch discard_energy_0. Each effect asserts the returned damage AND the key
state change (energy moved to/from a Pokémon or the discard pile, snipe damage, buffs), covering both
branches where a condition/coin/gate is involved. heads=0.0 / tails=0.9 via the scripted RNG."""
from collections import Counter
from effects_testkit import mk, run, runner, BK
from engine import Mon
import attack_effects as AE
import effects_gen.batch_discard_energy_0  # noqa: F401  (registers the batch)


def _fire(text, ctx):
    return AE.ATTACK_EFFECTS[AE.normalize(text)](ctx)


# non-VANILLA cards used to exercise type/ex-gated effects. The test attacker is VANILLA (Bulbasaur,
# Grass), so a defender weak to Grass gets the ×2 KO-check multiplier and one weak to anything else does not.
DRAGON = next(c for c in BK.values() if c.ptype == 'Dragon' and c.stage == 0)
LIGHTNING = next(c for c in BK.values() if c.ptype == 'Lightning')
EX = next(c for c in BK.values() if c.is_ex)
BEEFY = next(c for c in BK.values() if 160 <= c.hp <= 300 and c.weakness != 'Grass')
HUGE = next(c for c in BK.values() if c.hp > 300 and c.weakness != 'Grass')            # mult=1, base+150 can't KO
WEAKG = next(c for c in BK.values() if c.weakness == 'Grass' and 150 < c.hp <= 300)     # mult=2: base 150 already KOs

TESTS = []
def test(fn): TESTS.append(fn); return fn


# ---------------------------------------------------------------- discard from opponent's Active
@test
def t_discard_opp_energy():
    d, ctx, at, df, me, opp = run("Discard an Energy from your opponent's Active Pokémon.",
                                  base=30, def_energy={'Water': 2})
    assert d == 30 and df.total_energy() == 1 and opp.disc_energy['Water'] == 1, (d, df.energy)


@test
def t_discard_opp_special():
    # has a Special Energy -> removed (name + pips), basic Water stays
    ctx, at, df, me, opp = mk(base=30, def_special=('Prism Energy',),
                              def_energy={'Wild': 1, 'Water': 1})
    d = _fire("Discard a Special Energy from your opponent's Active Pokémon.", ctx)
    assert d == 30 and df.special == [] and df.energy.get('Wild', 0) == 0 and df.energy.get('Water') == 1, (d, df.special, df.energy)
    # no Special Energy -> nothing removed
    ctx2, _, df2, *_ = mk(base=30, def_energy={'Water': 2})
    d2 = _fire("Discard a Special Energy from your opponent's Active Pokémon.", ctx2)
    assert d2 == 30 and df2.total_energy() == 2, (d2, df2.energy)


@test
def t_discard_opp_fire():
    ctx, at, df, me, opp = mk(base=0, def_energy={'Fire': 2, 'Water': 1})
    d = _fire("Discard a {R} Energy from your opponent's Active Pokémon.", ctx)
    assert d == 0 and df.energy.get('Fire') == 1 and df.energy.get('Water') == 1 and opp.disc_energy['Fire'] == 1
    # no Fire to discard -> untouched
    ctx2, _, df2, *_ = mk(base=0, def_energy={'Water': 2})
    _fire("Discard a {R} Energy from your opponent's Active Pokémon.", ctx2)
    assert df2.energy.get('Water') == 2 and df2.energy.get('Fire', 0) == 0


@test
def t_discard_opp_ex_energy():
    # non-ex Active -> nothing happens
    ctx, at, df, me, opp = mk(base=0, def_energy={'Water': 2})
    assert not df.card.is_ex
    d = _fire("Discard an Energy from your opponent's Active Pokémon ex.", ctx)
    assert d == 0 and df.total_energy() == 2
    # ex Active -> one Energy discarded
    ctx2, at2, df2, me2, opp2 = mk(base=0)
    exmon = Mon(EX); exmon.energy = Counter({'Water': 2}); opp2.active = exmon
    ctx2.defender = exmon
    d2 = _fire("Discard an Energy from your opponent's Active Pokémon ex.", ctx2)
    assert d2 == 0 and exmon.total_energy() == 1 and opp2.disc_energy['Water'] == 1


@test
def t_discard_opp_tools_and_special():
    ctx, at, df, me, opp = mk(base=30, def_special=('Prism Energy', 'Mist Energy'),
                              def_energy={'Wild': 1, 'Colorless': 1, 'Water': 1},
                              def_tools=['Lucky Helmet', 'Rescue Board'])
    d = _fire("Before doing damage, discard all Pokémon Tools and Special Energy from your opponent's Active Pokémon.", ctx)
    assert d == 30 and df.special == [] and df.tools == [] and df.energy.get('Wild', 0) == 0 \
        and df.energy.get('Colorless', 0) == 0 and df.energy.get('Water') == 1, (d, df.special, df.tools, df.energy)
    # a defender with no Tool attached is handled cleanly (nothing to discard)
    ctx2, at2, df2, me2, opp2 = mk(base=30, def_special=('Prism Energy',), def_energy={'Wild': 1})
    d2 = _fire("Before doing damage, discard all Pokémon Tools and Special Energy from your opponent's Active Pokémon.", ctx2)
    assert d2 == 30 and df2.special == [] and df2.tools == []


# ---------------------------------------------------------------- discard from this Pokémon
@test
def t_discard_all_energy_self():
    ctx, at, df, me, opp = mk(base=220, atk_energy={'Fire': 2, 'Metal': 1})
    d = _fire("Discard all Energy from this Pokémon.", ctx)
    assert d == 220 and at.total_energy() == 0 and me.disc_energy['Fire'] == 2 and me.disc_energy['Metal'] == 1


@test
def t_discard_all_energy_self_clears_special():
    # Special Energy (Prism -> Wild on a Basic) is stripped too; basic Fire routes to disc_energy
    ctx, at, df, me, opp = mk(base=60, atk_energy={'Wild': 1, 'Fire': 2})
    at.special = ['Prism Energy']
    d = _fire("Discard all Energy from this Pokémon.", ctx)
    assert d == 60 and at.total_energy() == 0 and at.special == [] and me.disc_energy['Fire'] == 2 \
        and me.disc_energy.get('Wild', 0) == 0, (d, at.energy, at.special, me.disc_energy)


@test
def t_discard_self_3():
    ctx, at, df, me, opp = mk(base=260, atk_energy={'Fighting': 4})
    d = _fire("Discard 3 Energy from this Pokémon.", ctx)
    assert d == 260 and at.total_energy() == 1 and me.disc_energy['Fighting'] == 3


@test
def t_discard_self_lightning():
    ctx, at, df, me, opp = mk(base=150, atk_energy={'Lightning': 2, 'Colorless': 1})
    d = _fire("Discard a {L} Energy from this Pokémon.", ctx)
    assert d == 150 and at.energy.get('Lightning') == 1 and me.disc_energy['Lightning'] == 1


@test
def t_discard_self_grass():
    ctx, at, df, me, opp = mk(base=40, atk_energy={'Grass': 2})
    d = _fire("Discard a {G} Energy from this Pokémon.", ctx)
    assert d == 40 and at.energy.get('Grass') == 1 and me.disc_energy['Grass'] == 1


@test
def t_galvantula_discharge():
    # 50 per {L} discarded: 3 Lightning -> 150
    ctx, at, df, me, opp = mk(base=50, atk_energy={'Lightning': 3})
    d = _fire("Discard all {L} Energy from this Pokémon. This attack does 50 damage for each card you discarded in this way.", ctx)
    assert d == 150 and at.energy.get('Lightning', 0) == 0 and me.disc_energy['Lightning'] == 3
    # no Lightning -> 0
    ctx2, at2, *_ = mk(base=50, atk_energy={'Colorless': 2})
    d2 = _fire("Discard all {L} Energy from this Pokémon. This attack does 50 damage for each card you discarded in this way.", ctx2)
    assert d2 == 0


@test
def t_donphan_heavy_impact():
    ctx, at, df, me, opp = mk(base=120, atk_energy={'Fighting': 2, 'Colorless': 1})
    d = _fire("Discard 2 Energy from this Pokémon. During your opponent's next turn, this Pokémon takes 100 less damage from attacks (after applying Weakness and Resistance).", ctx)
    assert d == 120 and at.total_energy() == 1 and at.dr_amount == 100 and at.dr_turn == ctx.game.turn


@test
def t_metagross_metallic_hammer():
    key = "You may discard 3 {M} Energy from this Pokémon and have this attack do 150 more damage."
    # conversion: beefy defender (base 150 can't KO, 300 can) + 3 {M} -> pay, return 300
    ctx, at, df, me, opp = mk(base=150, atk_energy={'Metal': 4})
    beefy = Mon(BEEFY); opp.active = beefy; ctx.defender = beefy
    assert 150 < beefy.hp_left <= 300
    d = _fire(key, ctx)
    assert d == 300 and at.energy.get('Metal') == 1, (d, beefy.hp_left, at.energy)
    # base already KOs the small VANILLA Active -> don't waste energy
    ctx2, at2, df2, me2, opp2 = mk(base=150, atk_energy={'Metal': 4})
    d2 = _fire(key, ctx2)
    assert d2 == 150 and at2.energy.get('Metal') == 4
    # insufficient {M} -> just base
    ctx3, at3, df3, me3, opp3 = mk(base=150, atk_energy={'Metal': 2})
    b3 = Mon(BEEFY); opp3.active = b3; ctx3.defender = b3
    d3 = _fire(key, ctx3)
    assert d3 == 150 and at3.energy.get('Metal') == 2
    # +150 STILL can't KO a huge defender (hp>300, mult=1) -> don't waste the 3 {M}
    ctx4, at4, df4, me4, opp4 = mk(base=150, atk_energy={'Metal': 4})
    huge = Mon(HUGE); opp4.active = huge; ctx4.defender = huge
    assert huge.hp_left > 300
    d4 = _fire(key, ctx4)
    assert d4 == 150 and at4.energy.get('Metal') == 4, (d4, huge.hp_left, at4.energy)
    # Weakness feeds the KO check: a Grass-weak defender (mult=2) is already KO'd by base 150 -> don't pay.
    # (A mult-ignoring bug would see 150 < hp <= 300, pay, and return 300 with only 1 {M} left.)
    ctx5, at5, df5, me5, opp5 = mk(base=150, atk_energy={'Metal': 4})
    wk = Mon(WEAKG); opp5.active = wk; ctx5.defender = wk
    assert wk.card.weakness == 'Grass' and 150 < wk.hp_left <= 300
    d5 = _fire(key, ctx5)
    assert d5 == 150 and at5.energy.get('Metal') == 4, (d5, wk.hp_left, at5.energy)


# ---------------------------------------------------------------- discard from hand (gated / scaling)
@test
def t_mawile_double_eater():
    key = "Discard up to 2 Energy cards from your hand, and this attack does 60 damage for each card you discarded in this way."
    ctx, at, df, me, opp = mk(base=60)
    me.hand = [('E', 'Fire'), ('E', 'Water'), ('E', 'Grass')]
    d = _fire(key, ctx)
    assert d == 120 and len([t for t in me.hand if t[0] == 'E']) == 1 and me.disc_energy['Fire'] == 1 and me.disc_energy['Water'] == 1
    # only 1 energy in hand -> 60
    ctx2, at2, df2, me2, opp2 = mk(base=60)
    me2.hand = [('E', 'Grass')]
    assert _fire(key, ctx2) == 60 and not me2.hand
    # no energy in hand -> 0
    ctx3, at3, df3, me3, opp3 = mk(base=60)
    me3.hand = []
    assert _fire(key, ctx3) == 0


@test
def t_decidueye_razor_leaf():
    key = "Discard a Basic {G} Energy card from your hand. If you can't, this attack does nothing."
    ctx, at, df, me, opp = mk(base=170)
    me.hand = [('E', 'Grass')]
    d = _fire(key, ctx)
    assert d == 170 and not me.hand and me.disc_energy['Grass'] == 1
    # no basic Grass in hand -> attack does nothing
    ctx2, at2, df2, me2, opp2 = mk(base=170)
    me2.hand = [('E', 'Fire')]
    assert _fire(key, ctx2) == 0 and me2.hand == [('E', 'Fire')]


@test
def t_lurantis_solar_blade():
    key = "Discard 2 Basic {G} Energy cards from your hand. If you can't discard 2 cards in this way, this attack does nothing."
    ctx, at, df, me, opp = mk(base=130)
    me.hand = [('E', 'Grass'), ('E', 'Grass'), ('E', 'Fire')]
    d = _fire(key, ctx)
    assert d == 130 and me.disc_energy['Grass'] == 2 and me.hand == [('E', 'Fire')]
    # only 1 Grass -> nothing, and nothing discarded
    ctx2, at2, df2, me2, opp2 = mk(base=130)
    me2.hand = [('E', 'Grass'), ('E', 'Fire')]
    assert _fire(key, ctx2) == 0 and me2.hand == [('E', 'Grass'), ('E', 'Fire')] and me2.disc_energy['Grass'] == 0


# ---------------------------------------------------------------- discard-self + snipe / doom
@test
def t_ns_darmanitan_flare_blitz():
    key = "Discard all Energy from this Pokémon, and this attack also does 90 damage to 1 of your opponent's Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)"
    ctx, at, df, me, opp = mk(base=90, atk_energy={'Fire': 3}, opp_bench=1)
    d = _fire(key, ctx)
    assert d == 90 and at.total_energy() == 0 and me.disc_energy['Fire'] == 3 and opp.bench[0].damage == 90


@test
def t_honchkrow_night_slash():
    key = "Discard 2 Energy from this Pokémon, and this attack does 120 damage to 1 of your opponent's Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)"
    ctx, at, df, me, opp = mk(base=0, atk_energy={'Darkness': 3}, opp_bench=1)
    d = _fire(key, ctx)
    # Active (80 HP) is KO-able -> hit it (returned), Bench untouched; 2 energy discarded
    assert d == 120 and at.energy.get('Darkness') == 1 and opp.bench[0].damage == 0
    # Active NOT KO-able (190 HP) but the Benched Pokémon IS -> snipe the Bench: return 0 (no Active
    # damage), Bench takes 120 directly (bypasses W&R). Exercises the return-0 branch of _snipe_opp_any.
    ctx2, at2, df2, me2, opp2 = mk(base=0, atk_energy={'Darkness': 3}, opp_bench=1)
    big = Mon(BEEFY); opp2.active = big; ctx2.defender = big
    d2 = _fire(key, ctx2)
    assert d2 == 0 and opp2.bench[0].damage == 120 and big.damage == 0 and at2.energy.get('Darkness') == 1, \
        (d2, big.damage, opp2.bench[0].damage, at2.energy)


@test
def t_kyurem_trifrost():
    key = "Discard all Energy from this Pokémon. This attack does 110 damage to 3 of your opponent's Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)"
    ctx, at, df, me, opp = mk(base=0, atk_energy={'Water': 2, 'Metal': 2, 'Colorless': 1}, opp_bench=3)
    d = _fire(key, ctx)
    # 3 targets: Active (returned 110) + 2 Bench (direct 110 each)
    assert d == 110 and at.total_energy() == 0 and sum(1 for b in opp.bench if b.damage == 110) == 2


@test
def t_dartrix_razor_leaf():
    key = "Discard all Energy from this Pokémon, and this attack does 90 damage to 1 of your opponent's Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)"
    ctx, at, df, me, opp = mk(base=0, atk_energy={'Grass': 3}, opp_bench=1)
    d = _fire(key, ctx)
    assert d == 90 and at.total_energy() == 0 and me.disc_energy['Grass'] == 3


@test
def t_pinsir_doom():
    key = "Discard all Energy from this Pokémon. At the end of your opponent's next turn, the Defending Pokémon will be Knocked Out."
    ctx, at, df, me, opp = mk(base=0, atk_energy={'Grass': 2})
    d = _fire(key, ctx)
    # discard-all-energy cost is modeled; the delayed KO is not (no engine timer) -> 0 damage now
    assert d == 0 and at.total_energy() == 0 and me.disc_energy['Grass'] == 2


# ---------------------------------------------------------------- x-scaling off discard-pile / deck
@test
def t_30x_opp_discard_basic_energy():
    key = "This attack does 30 damage for each Basic Energy card in your opponent's discard pile."
    ctx, at, df, me, opp = mk(base=30)
    opp.disc_energy = Counter({'Fire': 2, 'Water': 1, 'Wild': 5})   # Wild pseudo-type is NOT a basic Energy card
    d = _fire(key, ctx)
    assert d == 90, d
    # empty discard -> 0
    ctx2, *_rest, opp2 = mk(base=30)
    assert _fire(key, ctx2) == 0


@test
def t_avalugg_iceberg_breaker():
    key = "Discard the top 6 cards of your deck, and this attack does 60 damage for each Basic {W} Energy card you discarded in this way."
    ctx, at, df, me, opp = mk(base=60)
    me.deck = [('E', 'Water')] * 3 + [('E', 'Fire')] * 3     # top 6 = 3 Water
    d = _fire(key, ctx)
    assert d == 180 and me.disc_energy['Water'] == 3 and not me.deck
    # fewer than 6 cards, 2 of them Water -> 120
    ctx2, at2, df2, me2, opp2 = mk(base=60)
    me2.deck = [('E', 'Water'), ('E', 'Water')]
    assert _fire(key, ctx2) == 120


# ---------------------------------------------------------------- attach basic Energy from discard
@test
def t_attach_basic_discard_1_bench():
    key = "Attach a Basic Energy card from your discard pile to 1 of your Benched Pokémon."
    ctx, at, df, me, opp = mk(base=30, my_bench=1)
    me.disc_energy = Counter({'Water': 2})
    d = _fire(key, ctx)
    assert d == 30 and me.bench[0].energy.get('Water') == 1 and me.disc_energy['Water'] == 1
    # empty discard -> nothing attached
    ctx2, at2, df2, me2, opp2 = mk(base=30, my_bench=1)
    me2.disc_energy = Counter()
    assert _fire(key, ctx2) == 30 and me2.bench[0].total_energy() == 0


@test
def t_attach_basic_discard_2_bench():
    key = "Attach up to 2 Basic Energy cards from your discard pile to 1 of your Benched Pokémon."
    ctx, at, df, me, opp = mk(base=0, my_bench=1)
    me.disc_energy = Counter({'Water': 3})
    d = _fire(key, ctx)
    assert d == 0 and me.bench[0].energy.get('Water') == 2 and me.disc_energy['Water'] == 1
    # only 1 in discard -> attach just 1
    ctx2, at2, df2, me2, opp2 = mk(base=0, my_bench=1)
    me2.disc_energy = Counter({'Water': 1})
    _fire(key, ctx2)
    assert me2.bench[0].energy.get('Water') == 1 and me2.disc_energy.get('Water', 0) == 0


@test
def t_druddigon_attach_fire_to_dragon():
    key = "Attach a Basic {R} Energy card from your discard pile to 1 of your {N} Pokémon."
    ctx, at, df, me, opp = mk(base=20, my_bench=1)
    me.bench = [Mon(DRAGON)]
    me.disc_energy = Counter({'Fire': 2})
    d = _fire(key, ctx)
    assert d == 20 and me.bench[0].energy.get('Fire') == 1 and me.disc_energy['Fire'] == 1
    # no Dragon Pokémon in play -> nothing attached
    ctx2, at2, df2, me2, opp2 = mk(base=20, my_bench=1)   # bench is VANILLA (Grass), no Dragon
    me2.disc_energy = Counter({'Fire': 2})
    assert _fire(key, ctx2) == 20 and me2.bench[0].total_energy() == 0 and me2.disc_energy['Fire'] == 2


@test
def t_lycanroc_attach_2f_bench():
    key = "Attach up to 2 Basic {F} Energy cards from your discard pile to your Benched Pokémon in any way you like."
    ctx, at, df, me, opp = mk(base=50, my_bench=1)
    me.disc_energy = Counter({'Fighting': 3})
    d = _fire(key, ctx)
    assert d == 50 and me.bench[0].energy.get('Fighting') == 2 and me.disc_energy['Fighting'] == 1
    # only 1 {F} in discard -> attach 1
    ctx2, at2, df2, me2, opp2 = mk(base=50, my_bench=1)
    me2.disc_energy = Counter({'Fighting': 1})
    _fire(key, ctx2)
    assert me2.bench[0].energy.get('Fighting') == 1


@test
def t_mudsdale_attach_f_each_bench():
    key = "Attach a Basic {F} Energy card from your discard pile to each of your Benched Pokémon."
    ctx, at, df, me, opp = mk(base=0, my_bench=3)
    me.disc_energy = Counter({'Fighting': 2})   # only 2 in discard, 3 on bench -> 2 get fed
    d = _fire(key, ctx)
    fed = sum(1 for m in me.bench if m.energy.get('Fighting', 0) == 1)
    assert d == 0 and fed == 2 and me.disc_energy.get('Fighting', 0) == 0


@test
def t_dedenne_energy_assist():
    key = "Choose Basic {L} Energy cards from your discard pile up to the amount of Energy attached to all of your opponent's Pokémon and attach them to your {L} Pokémon in any way you like."
    ctx, at, df, me, opp = mk(base=0, def_energy={'Psychic': 2}, opp_bench=1)   # opp total energy = 2
    me.bench = [Mon(LIGHTNING)]
    me.disc_energy = Counter({'Lightning': 5})
    d = _fire(key, ctx)
    assert d == 0 and me.bench[0].energy.get('Lightning') == 2 and me.disc_energy['Lightning'] == 3
    # capped by available Lightning in discard (only 1) even though opp has 2 energy
    ctx2, at2, df2, me2, opp2 = mk(base=0, def_energy={'Psychic': 2}, opp_bench=1)
    me2.bench = [Mon(LIGHTNING)]
    me2.disc_energy = Counter({'Lightning': 1})
    _fire(key, ctx2)
    assert me2.bench[0].energy.get('Lightning') == 1 and me2.disc_energy.get('Lightning', 0) == 0


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
