#!/usr/bin/env python3
"""Unit tests for ability batch ab_energy_accel_0. Each registered lambda is exercised directly
against real engine Mon/Player/Game objects (built by the shared testkit)."""
from collections import Counter
from effects_testkit import mk, runner, BK, BN, VANILLA
from engine import Mon
import ability_effects as AB
import abilities_gen.batch_ab_energy_accel_0  # noqa: F401  (registers the batch)


def fn(key):
    return AB.ABILITY_EFFECTS[AB.normalize(key)]['fn']


# real typed cards for tests that need a specific Pokémon type
WATER = next(c for c in BK.values() if c.ptype == 'Water' and c.stage == 0 and c.hp > 0 and c.cat != 'cat-red')
LIGHT = next(c for c in BK.values() if c.ptype == 'Lightning' and c.stage == 0 and c.hp > 0 and c.cat != 'cat-red')
FIGHT = next(c for c in BK.values() if c.ptype == 'Fighting' and c.stage == 0 and c.hp > 0 and c.cat != 'cat-red')
EVO = next(c for c in BK.values() if c.stage >= 1 and c.hp > 0)
LARRY = next(c for c in BK.values() if c.name.startswith("Larry's") and c.stage == 0 and c.hp > 0)
IRON_TREADS = BN['Iron Treads'][0]                       # printed Metal; Dual Core adds {F}=Fighting via the Capsule
FIGHT_WEAK = next(c for c in BK.values() if c.weakness == 'Fighting')
METAL_WEAK = next(c for c in BK.values() if c.weakness == 'Metal')
GRASS_WEAK = next(c for c in BK.values() if c.weakness == 'Grass')

DYNAMOTOR = "- Once during your turn, you may attach a Basic {L} Energy card from your discard pile to 1 of your Benched Pokémon."
OVERVOLT = "- Once during your turn, you may attach up to 3 Basic Energy cards from your discard pile to your {L} Pokémon in any way you like. If you use this Ability, this Pokémon is Knocked Out."
EVOGUIDE = "- Once during your turn, if this Pokémon has any Energy attached, you may use this Ability. Search your deck for an Evolution Pokémon, reveal it, and put it into your hand. Then, shuffle your deck."
FERMENTED = "- Once during your turn, if this Pokémon has any {G} Energy attached, you may use this Ability. Heal 30 damage from 1 of your Pokémon."
BOISTEROUS = "- Once during your turn, you may use this Ability. Flip a coin. If heads, put an Energy attached to your opponent's Active Pokémon into their hand."
ENERGIZED = "- Once during your turn, when you play this Pokémon from your hand to evolve 1 of your Pokémon, you may use this Ability. Look at the top 4 cards of your deck and attach any number of Basic Energy cards you find there to your Pokémon in any way you like. Shuffle the other cards back into your deck."
METALMAKER = "- Once during your turn, you may look at the top 4 cards of your deck and attach any number of Basic {M} Energy cards you find there to your Pokémon in any way you like. Shuffle the other cards and put them on the bottom of your deck."
STONEARMS = "- Once during your turn, you may use this Ability. Attach a Basic {F} Energy card from your hand to 1 of your {F} Pokémon."
FRILLED = "- Once during your turn, if you played Canari from your hand this turn, you may use this Ability. Search your deck for up to 2 Basic {L} Energy cards and attach them to this Pokémon. Then, shuffle your deck."
LETHARGIC = "- Once during your turn, if this Pokémon is on your Bench, you may use this Ability. Attach an Energy card from your hand to your Active Larry's Pokémon."
DUALCORE = "- As long as this Pokémon has a Future Booster Energy Capsule attached, it is {F} and {M} type."
DIVERS = "- When 1 of your {W} Pokémon is Knocked Out by damage from an attack from your opponent's Pokémon, you may put all Basic {W} Energy attached to that Pokémon into your hand instead of the discard pile."


def actx(ctx, me, opp, mon):
    return AB.ActivatedCtx(me, opp, mon, ctx.game)


TESTS = []
def test(f): TESTS.append(f); return f


@test
def t_dynamotor():
    ctx, at, df, me, opp = mk(my_bench=1)
    me.disc_energy['Lightning'] = 2
    f = fn(DYNAMOTOR)
    assert f(actx(ctx, me, opp, at)) is True
    assert me.bench[0].energy['Lightning'] == 1
    assert at.energy.get('Lightning', 0) == 0        # goes to a BENCHED mon, never the (active) holder
    assert me.disc_energy['Lightning'] == 1          # pulled from discard
    # no {L} in discard -> no-op
    c2, a2, d2, m2, o2 = mk(my_bench=1)
    assert f(actx(c2, m2, o2, a2)) is False
    # no bench -> no-op
    c3, a3, d3, m3, o3 = mk(my_bench=0)
    m3.disc_energy['Lightning'] = 2
    assert f(actx(c3, m3, o3, a3)) is False


@test
def t_overvolt_discharge():
    ctx, at, df, me, opp = mk(my_bench=1)
    me.bench[0] = Mon(LIGHT)                          # a {L} attacker to dump onto
    me.disc_energy.update({'Lightning': 2, 'Fighting': 1})
    f = fn(OVERVOLT)
    assert f(actx(ctx, me, opp, at)) is True
    assert me.bench[0].total_energy() == 3
    assert me.bench[0].energy['Lightning'] == 2      # target's needs pulled first
    assert at.damage == at.max_hp                    # holder self-KO'd
    # no {L} Pokémon (other than none) -> no-op, no self-KO
    c2, a2, d2, m2, o2 = mk(my_bench=1)
    m2.disc_energy['Lightning'] = 3
    assert f(actx(c2, m2, o2, a2)) is False
    assert a2.damage == 0
    # no energy in discard -> no-op
    c3, a3, d3, m3, o3 = mk(my_bench=1)
    m3.bench[0] = Mon(LIGHT)
    assert f(actx(c3, m3, o3, a3)) is False
    # "up to 3": abundant discard energy moves at most 3, then holder self-KOs
    c4, a4, d4, m4, o4 = mk(my_bench=1)
    m4.bench[0] = Mon(LIGHT)
    m4.disc_energy.update({'Lightning': 5})
    assert f(actx(c4, m4, o4, a4)) is True
    assert m4.bench[0].energy['Lightning'] == 3       # capped at 3
    assert m4.disc_energy['Lightning'] == 2           # only 3 pulled from the 5
    assert a4.damage == a4.max_hp


@test
def t_evolutionary_guidance():
    ctx, at, df, me, opp = mk()
    me.deck.append(('P', EVO))
    n0 = len(me.hand)
    f = fn(EVOGUIDE)
    assert f(actx(ctx, me, opp, at)) is True          # holder has default energy attached
    assert len(me.hand) == n0 + 1
    assert any(t[0] == 'P' and t[1].stage >= 1 for t in me.hand)
    # no energy attached -> gated off
    c2, a2, d2, m2, o2 = mk()
    a2.energy = Counter()
    m2.deck.append(('P', EVO))
    assert f(actx(c2, m2, o2, a2)) is False
    # energy but no Evolution in deck -> nothing to find
    c3, a3, d3, m3, o3 = mk()
    m3.deck = [('E', 'Colorless')] * 5
    assert f(actx(c3, m3, o3, a3)) is False


@test
def t_fermented_juice():
    ctx, at, df, me, opp = mk()
    at.energy = Counter({'Grass': 1})
    at.damage = 50
    f = fn(FERMENTED)
    assert f(actx(ctx, me, opp, at)) is True
    assert at.damage == 20                            # healed 30
    # no {G} energy -> gated off
    c2, a2, d2, m2, o2 = mk()
    a2.energy = Counter({'Fire': 1}); a2.damage = 50
    assert f(actx(c2, m2, o2, a2)) is False
    assert a2.damage == 50
    # {G} energy but nothing damaged -> no-op
    c3, a3, d3, m3, o3 = mk()
    a3.energy = Counter({'Grass': 1})
    assert f(actx(c3, m3, o3, a3)) is False


@test
def t_boisterous_wind():
    ctx, at, df, me, opp = mk(flips=(0.0,), def_energy={'Lightning': 2})
    f = fn(BOISTEROUS)
    assert f(actx(ctx, me, opp, at)) is True          # heads
    assert opp.active.energy['Lightning'] == 1        # one pip bounced
    assert ('E', 'Lightning') in opp.hand
    # tails -> no effect
    c2, a2, d2, m2, o2 = mk(flips=(0.9,), def_energy={'Lightning': 2})
    assert f(actx(c2, m2, o2, a2)) is False
    assert o2.active.energy['Lightning'] == 2
    # heads but opponent active has no energy -> no-op
    c3, a3, d3, m3, o3 = mk(flips=(0.0,), def_energy={})
    o3.active.energy = Counter()
    assert f(actx(c3, m3, o3, a3)) is False


@test
def t_energized_steps():
    ctx, at, df, me, opp = mk()
    me.deck = me.deck + [('E', 'Fire'), ('E', 'Water')]     # top-2 are basic energy
    before = sum(m.energy.get('Fire', 0) + m.energy.get('Water', 0) for m in me.all_mons())
    f = fn(ENERGIZED)
    assert f(actx(ctx, me, opp, at)) is True
    after = sum(m.energy.get('Fire', 0) + m.energy.get('Water', 0) for m in me.all_mons())
    assert after - before == 2
    # Colorless filler is NOT a basic energy type -> nothing to attach
    c2, a2, d2, m2, o2 = mk()
    m2.deck = [('E', 'Colorless')] * 4
    assert f(actx(c2, m2, o2, a2)) is False


@test
def t_metal_maker():
    ctx, at, df, me, opp = mk()
    me.deck = [('P', VANILLA)] * 3 + [('E', 'Grass'), ('E', 'Metal'), ('E', 'Metal'), ('E', 'Grass')]
    f = fn(METALMAKER)
    assert f(actx(ctx, me, opp, at)) is True
    assert sum(m.energy.get('Metal', 0) for m in me.all_mons()) == 2
    assert me.deck[0][1] == 'Grass' and me.deck[1][1] == 'Grass'   # non-metal put on the bottom
    # only {G} in top4, no {M} -> no-op
    c2, a2, d2, m2, o2 = mk()
    m2.deck = [('E', 'Grass')] * 4
    assert f(actx(c2, m2, o2, a2)) is False


@test
def t_stone_arms():
    ctx, at, df, me, opp = mk(my_bench=1)
    me.bench[0] = Mon(FIGHT)
    me.hand.append(('E', 'Fighting'))
    f = fn(STONEARMS)
    assert f(actx(ctx, me, opp, at)) is True
    assert me.bench[0].energy['Fighting'] == 1
    assert ('E', 'Fighting') not in me.hand
    # no {F} energy in hand -> no-op
    c2, a2, d2, m2, o2 = mk(my_bench=1)
    m2.bench[0] = Mon(FIGHT)
    assert f(actx(c2, m2, o2, a2)) is False
    # no {F} Pokémon -> no-op, energy stays in hand
    c3, a3, d3, m3, o3 = mk(my_bench=1)
    m3.hand.append(('E', 'Fighting'))
    assert f(actx(c3, m3, o3, a3)) is False
    assert ('E', 'Fighting') in m3.hand


@test
def t_frilled_generator():
    # Canari played this turn -> pull up to 2 Basic {L} Energy from the deck onto Heliolisk (the holder).
    ctx, at, df, me, opp = mk(played=['Canari'])
    me.deck = [('P', VANILLA)] * 3 + [('E', 'Lightning')] * 3   # 3 available; the ability caps at 2
    at.energy = Counter()
    f = fn(FRILLED)
    assert f(actx(ctx, me, opp, at)) is True
    assert at.energy['Lightning'] == 2                          # up to 2 attached to this Pokémon
    assert me.deck.count(('E', 'Lightning')) == 1             # only 2 pulled from the 3
    # Canari NOT played this turn -> gate off, nothing attached
    c2, a2, d2, m2, o2 = mk()                                   # me.played defaults to []
    m2.deck = [('E', 'Lightning')] * 2; a2.energy = Counter()
    assert f(actx(c2, m2, o2, a2)) is False
    assert a2.energy.get('Lightning', 0) == 0
    # Canari played but no {L} energy in the deck -> no-op
    c3, a3, d3, m3, o3 = mk(played=['Canari'])
    m3.deck = [('P', VANILLA)] * 4; a3.energy = Counter()
    assert f(actx(c3, m3, o3, a3)) is False
    assert a3.energy.get('Lightning', 0) == 0


@test
def t_lethargic_charge():
    ctx, at, df, me, opp = mk(my_bench=1)
    me.active = Mon(LARRY)                             # Active Larry's Pokémon
    holder = Mon(LARRY)
    me.bench = [holder]
    me.hand.append(('E', 'Fighting'))
    f = fn(LETHARGIC)
    assert f(actx(ctx, me, opp, holder)) is True
    assert me.active.energy['Fighting'] == 1
    assert ('E', 'Fighting') not in me.hand
    # holder in the Active Spot (not Benched) -> gated off
    c2, a2, d2, m2, o2 = mk(my_bench=1)
    m2.active = Mon(LARRY); m2.hand.append(('E', 'Fighting'))
    assert f(actx(c2, m2, o2, m2.active)) is False
    # active is not a Larry's Pokémon -> no-op
    c3, a3, d3, m3, o3 = mk(my_bench=1)
    m3.hand.append(('E', 'Fighting'))
    assert f(actx(c3, m3, o3, m3.bench[0])) is False


@test
def t_dual_core():
    f = fn(DUALCORE)
    atk = {'dmg': 60, 'name': 'Wheel Pass'}
    # Capsule attached + defender Weak to the ADDED type (Fighting) -> +base simulates the extra Weakness ×2.
    iron = Mon(IRON_TREADS); iron.tools = ['Future Booster Energy Capsule']
    assert f(iron, Mon(FIGHT_WEAK), atk, None) == 60
    # No Capsule attached -> no bonus, even vs a Fighting-Weak defender.
    assert f(Mon(IRON_TREADS), Mon(FIGHT_WEAK), atk, None) == 0
    # Capsule attached but defender Weak to Metal = Iron Treads' PRINTED type (already doubled by the
    # engine) -> no extra here, so no double-count.
    assert f(iron, Mon(METAL_WEAK), atk, None) == 0
    # Capsule attached, defender Weak to neither added type -> 0.
    assert f(iron, Mon(GRASS_WEAK), atk, None) == 0
    # No defender -> 0.
    assert f(iron, None, atk, None) == 0


@test
def t_divers_catch():
    ctx, at, df, me, opp = mk()
    wmon = Mon(WATER); wmon.energy = Counter({'Water': 2}); wmon.damage = wmon.max_hp
    f = fn(DIVERS)
    f(at, wmon, me, ctx.game)
    assert me.hand.count(('E', 'Water')) == 2         # recovered to hand
    assert wmon.energy.get('Water', 0) == 0           # off the KO'd Pokémon
    # not KO'd -> energy stays attached
    c2, a2, d2, m2, o2 = mk()
    w2 = Mon(WATER); w2.energy = Counter({'Water': 2}); w2.damage = 10
    f(a2, w2, m2, c2.game)
    assert w2.energy.get('Water', 0) == 2
    assert m2.hand.count(('E', 'Water')) == 0
    # non-Water KO'd -> no recovery
    c3, a3, d3, m3, o3 = mk()
    g = Mon(VANILLA); g.energy = Counter({'Grass': 2}); g.damage = g.max_hp
    f(a3, g, m3, c3.game)
    assert m3.hand.count(('E', 'Water')) == 0


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
