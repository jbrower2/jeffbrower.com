# -*- coding: utf-8 -*-
"""Unit tests for trainer batch tr_tool_1 (Pokémon Tools). Each Tool is exercised through its
registered hook signature (tool_ondamaged / tool_dr / tool_attack_buff / tool_hp / tool_retreat).

Hook-arg convention: the HOLDER is `dfn_mon` for on_damaged/dr, `atk_mon` for attack_buff, and
`mon` for hp/retreat; the fourth/second arg is the holder's Player."""
from collections import Counter
from effects_testkit import mk, runner
import trainer_effects as TE
import trainers_gen.batch_tr_tool_1          # noqa: F401  (registers the effects)
from cards import Card
from engine import Mon

# exact registration texts
HEAVY_BATON = "If the Pokémon this card is attached to has a Retreat Cost of exactly 4, is in the Active Spot, and is Knocked Out by damage from an attack from your opponent's Pokémon, move up to 3 Basic Energy cards from that Pokémon to your Benched Pokémon in any way you like."
HOPS_BAND = "Attacks used by the Hop's Pokémon this card is attached to cost {C} less and do 30 more damage to your opponent's Active Pokémon (before applying Weakness and Resistance)."
LIGHT_BALL = "Attacks used by the Pikachu ex this card is attached to do 50 more damage to your opponent's Active Pokémon ex (before applying Weakness and Resistance)."
LILLIES_PEARL = "If the Lillie's Pokémon this card is attached to is Knocked Out by damage from an attack from your opponent's Pokémon, that player takes 1 fewer Prize card."
LUCKY_HELMET = "If the Pokémon this card is attached to is in the Active Spot and is damaged by an attack from your opponent's Pokémon (even if this Pokémon is Knocked Out), draw 2 cards."
OCCA = "If the Pokémon this card is attached to is damaged by an attack from your opponent's {R} Pokémon, it takes 60 less damage (after applying Weakness and Resistance), and discard this card."
PASSHO = "If the Pokémon this card is attached to is damaged by an attack from your opponent's {W} Pokémon, it takes 60 less damage (after applying Weakness and Resistance), and discard this card."
PAYAPA = "If the Pokémon this card is attached to is damaged by an attack from your opponent's {P} Pokémon, it takes 60 less damage (after applying Weakness and Resistance), and discard this card."
POWERGLASS = "At the end of your turn (after your attack), if the Pokémon this card is attached to is in the Active Spot, you may attach a Basic Energy card from your discard pile to it."
PUNK_HELMET = "If the {D} Pokémon this card is attached to is in the Active Spot and is damaged by an attack from your opponent's Pokémon (even if this Pokémon is Knocked Out), place 4 damage counters on the Attacking Pokémon."
RESCUE_BOARD = "The Retreat Cost of the Pokémon this card is attached to is {C} less. If that Pokémon's remaining HP is 30 or less, it has no Retreat Cost."
SACRED_CHARM = "The Pokémon this card is attached to takes 30 less damage from attacks from your opponent's Pokémon that have an Ability (after applying Weakness and Resistance)."
TR_HYPNOTIZER = "If the Team Rocket's Pokémon this card is attached to is in the Active Spot and is damaged by an attack from your opponent's Pokémon (even if this Team Rocket's Pokémon is Knocked Out), the Attacking Pokémon is now Asleep."
TM_FLUORITE = "The Pokémon this card is attached to can use the attack on this card. (You still need the necessary Energy to use this attack.) If this card is attached to 1 of your Pokémon, discard it at the end of your turn."

ATTACK = {'name': 'TestAtk', 'dmg': 50, 'cost': [], 'text': ''}


def fn(text):
    return TE.TRAINER_EFFECTS[TE.normalize(text)]['fn']


def _mkcard(name='Dummy', hp=100, ptype='Colorless', retreat=1, is_ex=False, abilities=(), stage=0):
    c = Card.__new__(Card)
    c.name = name; c.set = 'X'; c.id = '0'; c.cat = 'cat-green'; c.price = 0.0; c.is_ex = is_ex
    c.energy = []; c.hp = hp; c.stage = stage; c.evolves_from = None; c.ptype = ptype
    c.weakness = None; c.retreat = retreat; c.attacks = []; c.abilities = list(abilities)
    return c


def _mon(**kw):
    return Mon(_mkcard(**kw))


TESTS = []
def test(f): TESTS.append(f); return f


# ---------------- tool_ondamaged ----------------
@test
def t_heavy_baton():
    ctx, at, df, me, opp = mk()
    holder = _mon(name='Tanky', hp=100, retreat=4)
    holder.energy = Counter({'Fire': 3, 'Water': 1}); holder.damage = 100   # KO'd
    opp.active = holder
    bench = opp.bench[0]; before = bench.total_energy()
    fn(HEAVY_BATON)(at, holder, opp, ctx.game)
    assert bench.total_energy() == before + 3                # up to 3 basic pips salvaged
    assert holder.total_energy() == 1                        # 4 -> 1 left on the KO'd holder
    # not KO'd -> no move
    ctx2, at2, df2, me2, opp2 = mk()
    h2 = _mon(name='Tanky', hp=100, retreat=4); h2.energy = Counter({'Fire': 3}); h2.damage = 0
    opp2.active = h2; b2 = opp2.bench[0].total_energy()
    fn(HEAVY_BATON)(at2, h2, opp2, ctx2.game)
    assert opp2.bench[0].total_energy() == b2 and h2.total_energy() == 3
    # wrong retreat cost -> no move
    ctx3, at3, df3, me3, opp3 = mk()
    h3 = _mon(name='Tanky', hp=100, retreat=2); h3.energy = Counter({'Fire': 3}); h3.damage = 100
    opp3.active = h3; b3 = opp3.bench[0].total_energy()
    fn(HEAVY_BATON)(at3, h3, opp3, ctx3.game)
    assert opp3.bench[0].total_energy() == b3


@test
def t_lillies_pearl():
    ctx, at, df, me, opp = mk()
    holder = _mon(name="Lillie's Clefairy ex", hp=100, is_ex=True); holder.damage = 100  # KO'd
    opp.active = holder
    fn(LILLIES_PEARL)(at, holder, opp, ctx.game)
    assert getattr(holder, 'prize_penalty', 0) == 1
    # non-Lillie's holder -> no penalty
    ctx2, at2, df2, me2, opp2 = mk()
    h2 = _mon(name='Clefairy', hp=100); h2.damage = 100; opp2.active = h2
    fn(LILLIES_PEARL)(at2, h2, opp2, ctx2.game)
    assert getattr(h2, 'prize_penalty', 0) == 0
    # Lillie's but not KO'd -> no penalty
    ctx3, at3, df3, me3, opp3 = mk()
    h3 = _mon(name="Lillie's Clefairy ex", hp=100); h3.damage = 10; opp3.active = h3
    fn(LILLIES_PEARL)(at3, h3, opp3, ctx3.game)
    assert getattr(h3, 'prize_penalty', 0) == 0


@test
def t_lucky_helmet():
    ctx, at, df, me, opp = mk()
    holder = _mon(hp=120); opp.active = holder
    before = len(opp.hand)
    fn(LUCKY_HELMET)(at, holder, opp, ctx.game)
    assert len(opp.hand) == before + 2                       # owner draws 2
    # not in the Active Spot -> no draw
    ctx2, at2, df2, me2, opp2 = mk()
    benched = _mon(hp=120)                                    # not opp2.active
    before2 = len(opp2.hand)
    fn(LUCKY_HELMET)(at2, benched, opp2, ctx2.game)
    assert len(opp2.hand) == before2


@test
def t_punk_helmet():
    ctx, at, df, me, opp = mk()
    holder = _mon(name='Dark', hp=120, ptype='Darkness'); opp.active = holder
    fn(PUNK_HELMET)(at, holder, opp, ctx.game)
    assert at.damage == 40                                   # 4 counters on the attacker
    # non-{D} holder -> no counters
    ctx2, at2, df2, me2, opp2 = mk()
    h2 = _mon(hp=120, ptype='Fire'); opp2.active = h2
    fn(PUNK_HELMET)(at2, h2, opp2, ctx2.game)
    assert at2.damage == 0
    # {D} but not Active -> no counters
    ctx3, at3, df3, me3, opp3 = mk()
    h3 = _mon(hp=120, ptype='Darkness')                      # not opp3.active
    fn(PUNK_HELMET)(at3, h3, opp3, ctx3.game)
    assert at3.damage == 0


@test
def t_tr_hypnotizer():
    ctx, at, df, me, opp = mk()
    holder = _mon(name="Team Rocket's Meowth", hp=90); opp.active = holder
    fn(TR_HYPNOTIZER)(at, holder, opp, ctx.game)
    assert at.status.get('Asleep') is True
    # non-Team Rocket's holder -> no sleep
    ctx2, at2, df2, me2, opp2 = mk()
    h2 = _mon(name='Meowth', hp=90); opp2.active = h2
    fn(TR_HYPNOTIZER)(at2, h2, opp2, ctx2.game)
    assert 'Asleep' not in at2.status
    # attacker with effect-immunity (Bubbly Water Energy) -> not put to sleep
    ctx3, at3, df3, me3, opp3 = mk()
    h3 = _mon(name="Team Rocket's Meowth", hp=90); opp3.active = h3
    at3.special = ['Bubbly Water Energy']
    fn(TR_HYPNOTIZER)(at3, h3, opp3, ctx3.game)
    assert 'Asleep' not in at3.status


# ---------------- tool_attack_buff ----------------
@test
def t_hops_choice_band():
    ctx, at, df, me, opp = mk()
    holder = _mon(name="Hop's Zacian", hp=120)               # attacker is the holder
    assert fn(HOPS_BAND)(holder, df, ATTACK, ctx.game) == 30
    plain = _mon(name='Zacian', hp=120)
    assert fn(HOPS_BAND)(plain, df, ATTACK, ctx.game) == 0


@test
def t_light_ball():
    ctx, at, df, me, opp = mk()
    pika = _mon(name='Pikachu ex', hp=200, is_ex=True)
    ex_target = _mon(name='Foe ex', hp=200, is_ex=True)
    non_ex = _mon(name='Foe', hp=90, is_ex=False)
    assert fn(LIGHT_BALL)(pika, ex_target, ATTACK, ctx.game) == 50   # vs an ex
    assert fn(LIGHT_BALL)(pika, non_ex, ATTACK, ctx.game) == 0       # vs a non-ex
    non_pika = _mon(name='Raichu ex', hp=200, is_ex=True)
    assert fn(LIGHT_BALL)(non_pika, ex_target, ATTACK, ctx.game) == 0  # holder isn't Pikachu ex


# ---------------- tool_dr ----------------
@test
def t_occa_berry():
    ctx, at, df, me, opp = mk()
    fire = _mon(name='Charmander', hp=90, ptype='Fire')      # {R} attacker
    holder = _mon(hp=120); holder.tools = ['Occa Berry']
    assert fn(OCCA)(100, fire, holder, opp, ctx.game) == 40  # -60
    assert 'Occa Berry' not in holder.tools                  # discarded
    assert ('T', {'name': 'Occa Berry'}) in opp.discard
    # non-{R} attacker -> unchanged, berry stays
    ctx2, at2, df2, me2, opp2 = mk()
    water = _mon(hp=90, ptype='Water'); h2 = _mon(hp=120); h2.tools = ['Occa Berry']
    assert fn(OCCA)(100, water, h2, opp2, ctx2.game) == 100
    assert h2.tools == ['Occa Berry']
    # over-reduction floors at 0 (no defender-heal)
    ctx3, at3, df3, me3, opp3 = mk()
    fire3 = _mon(name='Charmander', hp=90, ptype='Fire'); h3 = _mon(hp=120); h3.tools = ['Occa Berry']
    assert fn(OCCA)(50, fire3, h3, opp3, ctx3.game) == 0


@test
def t_passho_berry():
    ctx, at, df, me, opp = mk()
    water = _mon(name='Squirtle', hp=90, ptype='Water')
    holder = _mon(hp=120); holder.tools = ['Passho Berry']
    assert fn(PASSHO)(100, water, holder, opp, ctx.game) == 40
    assert 'Passho Berry' not in holder.tools
    fire = _mon(hp=90, ptype='Fire'); h2 = _mon(hp=120); h2.tools = ['Passho Berry']
    assert fn(PASSHO)(100, fire, h2, opp, ctx.game) == 100 and h2.tools == ['Passho Berry']


@test
def t_payapa_berry():
    ctx, at, df, me, opp = mk()
    psy = _mon(name='Abra', hp=90, ptype='Psychic')
    holder = _mon(hp=120); holder.tools = ['Payapa Berry']
    assert fn(PAYAPA)(100, psy, holder, opp, ctx.game) == 40
    assert 'Payapa Berry' not in holder.tools
    grass = _mon(hp=90, ptype='Grass'); h2 = _mon(hp=120); h2.tools = ['Payapa Berry']
    assert fn(PAYAPA)(100, grass, h2, opp, ctx.game) == 100 and h2.tools == ['Payapa Berry']


@test
def t_sacred_charm():
    ctx, at, df, me, opp = mk()
    ab_atk = _mon(hp=120, abilities=[{'name': 'Ab', 'text': 'x'}])   # has an Ability
    holder = _mon(hp=120)
    assert fn(SACRED_CHARM)(100, ab_atk, holder, opp, ctx.game) == 70   # -30
    plain = _mon(hp=120, abilities=[])                                  # no Ability
    assert fn(SACRED_CHARM)(100, plain, holder, opp, ctx.game) == 100
    assert fn(SACRED_CHARM)(20, ab_atk, holder, opp, ctx.game) == 0     # floors at 0 (no defender-heal)


# ---------------- tool_retreat ----------------
@test
def t_rescue_board():
    ctx, at, df, me, opp = mk()
    m = _mon(hp=100, retreat=3); m.damage = 0                # 100 HP left -> {C} less
    assert fn(RESCUE_BOARD)(m, opp, ctx.game) == -1
    m.damage = 80                                            # 20 HP left (<=30) -> no retreat cost
    assert fn(RESCUE_BOARD)(m, opp, ctx.game) == -3          # zeroes the printed retreat 3


# ---------------- tool_hp (conservative no-ops) ----------------
@test
def t_powerglass_noop():
    ctx, at, df, me, opp = mk()
    assert fn(POWERGLASS)(at, me, ctx.game) == 0             # grants no HP (accel unmodeled)


@test
def t_tm_fluorite_noop():
    ctx, at, df, me, opp = mk()
    assert fn(TM_FLUORITE)(at, me, ctx.game) == 0            # grants no HP (grant-attack unmodeled)


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f"{p} pass {f} fail")
    raise SystemExit(1 if f else 0)
