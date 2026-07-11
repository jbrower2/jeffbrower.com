#!/usr/bin/env python3
"""Unit tests for trainer batch tr_item_3. Each Item runs through a TrainerCtx over real
Player/Game objects built by the shared harness; assertions check the concrete state change."""
from collections import Counter
from effects_testkit import mk, runner, BN, VANILLA
import trainer_effects as TE
import trainers_gen.batch_tr_item_3 as B


def fn(text):
    return TE.TRAINER_EFFECTS[TE.normalize(text)]['fn']


def ctx(**kw):
    """Return (TrainerCtx, me, opp) for an Item test."""
    c, at, df, me, opp = mk(**kw)
    return TE.TrainerCtx(me, opp, c.game), me, opp


def SUP(name='Prof'):
    return ('T', {'name': name, 'trainerType': 'Supporter'})


def TOOL(name='Rescue Board'):
    return ('T', {'name': name, 'trainerType': 'Tool'})


TESTS = []
def test(f): TESTS.append(f); return f


# ---------------------------------------------------------------- deck-look / search
@test
def t_pokegear_hit():
    t, me, opp = ctx()
    me.deck = [('E', 'Colorless')] * 3 + [SUP()] + [('E', 'Colorless')] * 3   # Supporter in top 7
    assert fn(B.POKEGEAR)(t) is True
    assert any(x[0] == 'T' and x[1]['trainerType'] == 'Supporter' for x in me.hand)
    assert not any(_is_sup(x) for x in me.deck) and len(me.deck) == 6


@test
def t_pokegear_miss():
    t, me, opp = ctx()
    me.deck = [('E', 'Colorless')] * 7                                        # no Supporter
    assert fn(B.POKEGEAR)(t) is False and len(me.hand) == 0


@test
def t_pokegear_only_one():
    t, me, opp = ctx()
    me.deck = [SUP('A'), ('E', 'Colorless'), SUP('B')]                        # two in top 7
    assert fn(B.POKEGEAR)(t) is True
    assert sum(1 for x in me.hand if _is_sup(x)) == 1                         # reveals at most ONE
    assert sum(1 for x in me.deck if _is_sup(x)) == 1


@test
def t_pokegear_depth_limited():
    t, me, opp = ctx()
    me.deck = [SUP()] + [('E', 'Colorless')] * 7                             # Supporter is the 8th card
    assert fn(B.POKEGEAR)(t) is False                                        # below the top 7 -> not seen


@test
def t_roto_stick_multi():
    t, me, opp = ctx()
    me.deck = [('E', 'Colorless')] * 4 + [SUP('A'), ('E', 'Colorless'), SUP('B'), ('E', 'Colorless')]
    assert fn(B.ROTO_STICK)(t) is True
    assert sum(1 for x in me.hand if _is_sup(x)) == 2                        # ANY number in top 4
    assert not any(_is_sup(x) for x in me.deck)


@test
def t_tm_machine():
    t, me, opp = ctx()
    tm = ('T', {'name': 'Technical Machine: Evolution', 'trainerType': 'Tool'})
    me.deck = [('E', 'Colorless')] * 5 + [TOOL('Rescue Board')] + [tm, tm, tm]
    assert fn(B.TM_MACHINE)(t) is True
    assert sum(1 for x in me.hand if x[0] == 'T' and 'Technical Machine' in x[1]['name']) == 3
    assert any(x[0] == 'T' and x[1]['name'] == 'Rescue Board' for x in me.deck)   # non-TM stays


@test
def t_tm_machine_none():
    t, me, opp = ctx()
    me.deck = [('E', 'Colorless')] * 6 + [TOOL('Rescue Board')]
    assert fn(B.TM_MACHINE)(t) is False


@test
def t_sacred_ash():
    t, me, opp = ctx()
    me.discard = [('P', VANILLA)] * 7
    d0 = len(me.deck)
    assert fn(B.SACRED_ASH)(t) is True
    assert len(me.discard) == 2 and len(me.deck) == d0 + 5                   # up to 5 back


@test
def t_sacred_ash_empty():
    t, me, opp = ctx()
    me.discard = []
    assert fn(B.SACRED_ASH)(t) is False


# ---------------------------------------------------------------- switch / gust
@test
def t_catcher_heads():
    # heads (0.0): active Bulbasaur (G, Bind Down 10) drags up a near-dead benched target it can KO.
    t, me, opp = ctx(flips=(0.0,), atk_energy={'Grass': 1}, opp_bench=1)
    tgt = opp.bench[0]
    tgt.damage = tgt.card.hp - 10                                            # hp_left = 10
    assert fn(B.POKEMON_CATCHER)(t) is True
    assert opp.active is tgt                                                 # switched in


@test
def t_catcher_tails():
    t, me, opp = ctx(flips=(0.9,), atk_energy={'Grass': 1})
    tgt = opp.bench[0]; tgt.damage = tgt.card.hp - 10
    before = opp.active
    assert fn(B.POKEMON_CATCHER)(t) is False and opp.active is before        # tails -> nothing


@test
def t_repel():
    t, me, opp = ctx(opp_bench=1)
    old, bench = opp.active, opp.bench[0]
    assert fn(B.REPEL)(t) is True
    assert opp.active is bench and old in opp.bench                          # forced to a new active


@test
def t_switch():
    t, me, opp = ctx()
    old = me.active
    old.energy = Counter()                                                  # active has no energy
    me.bench[0].energy = Counter({'Fighting': 3})                           # bench is readier
    assert fn(B.SWITCH)(t) is True
    assert me.active is not old and me.active.total_energy() == 3


# ---------------------------------------------------------------- evolve / devolve
@test
def t_rare_candy():
    t, me, opp = ctx()
    me.active.card = VANILLA                                                 # Bulbasaur (Basic)
    me.active.turns = 1                                                      # in play a turn
    mv = next(c for c in BN['Mega Venusaur ex'] if c.stage == 2)
    me.hand = [('P', mv)]
    assert fn(B.RARE_CANDY)(t) is True
    assert me.active.card.name == 'Mega Venusaur ex'


@test
def t_strange_timepiece():
    t, me, opp = ctx()
    cle = next(c for c in BN['Clefable'] if c.stage == 1 and c.ptype == 'Psychic')
    me.active.card = cle                                                     # evolved Psychic
    assert fn(B.STRANGE_TIMEPIECE)(t) is True
    assert me.active.card.name == 'Clefairy'                                 # devolved one stage
    assert any(x[0] == 'P' and x[1].name == 'Clefable' for x in me.hand)     # evo card to hand
    assert me.active.turns == 0                                              # can't re-evolve this turn


@test
def t_strange_timepiece_no_target():
    t, me, opp = ctx()                                                       # active/bench are Grass Basics
    assert fn(B.STRANGE_TIMEPIECE)(t) is False


# ---------------------------------------------------------------- heal
@test
def t_super_potion():
    t, me, opp = ctx(atk_energy={'Fighting': 2})
    me.active.damage = 100
    assert fn(B.SUPER_POTION)(t) is True
    assert me.active.damage == 40                                            # healed 60
    assert me.active.total_energy() == 1 and me.disc_energy['Fighting'] == 1  # 1 energy discarded


@test
def t_super_potion_undamaged():
    t, me, opp = ctx(atk_energy={'Fighting': 2})
    me.active.damage = 0
    assert fn(B.SUPER_POTION)(t) is False and me.active.total_energy() == 2   # no heal -> no discard


# ---------------------------------------------------------------- prize / hand disruption
@test
def t_redeemable_ticket():
    t, me, opp = ctx()
    me.prizes = [('E', 'Fire')] * 6                                          # distinct marker
    d0 = len(me.deck)
    assert fn(B.REDEEMABLE_TICKET)(t) is True
    assert len(me.prizes) == 6 and len(me.deck) == d0                        # counts preserved
    assert all(p == ('E', 'Colorless') for p in me.prizes)                  # new prizes off the top
    assert me.deck[:6] == [('E', 'Fire')] * 6                                # old prizes to the bottom


@test
def t_special_red_card_gated_on():
    t, me, opp = ctx(opp_prizes=3)                                           # <=3 prizes remaining
    opp.hand = [('E', 'Fire')] * 4
    assert fn(B.SPECIAL_RED_CARD)(t) is True
    assert len(opp.hand) == 3 and all(x == ('E', 'Colorless') for x in opp.hand)   # drew 3 fresh
    assert opp.deck[:4] == [('E', 'Fire')] * 4                               # old hand to the bottom


@test
def t_special_red_card_gated_off():
    t, me, opp = ctx(opp_prizes=6)                                           # too many prizes
    opp.hand = [('E', 'Fire')] * 4
    assert fn(B.SPECIAL_RED_CARD)(t) is False and len(opp.hand) == 4          # unplayable -> no change


@test
def t_bother_bot():
    t, me, opp = ctx()
    opp.hand = [('E', 'Fire')]
    opp.prizes = [('E', 'Colorless')] * 6
    assert fn(B.BOTHER_BOT)(t) is True
    assert opp.hand[0] == ('E', 'Colorless') and opp.prizes[0] == ('E', 'Fire')   # hand<->prize swap


@test
def t_bother_bot_empty_hand():
    t, me, opp = ctx()
    opp.hand = []
    assert fn(B.BOTHER_BOT)(t) is False


# ---------------------------------------------------------------- turn-scoped buff (rider)
@test
def t_premium_power_pro():
    t, me, opp = ctx()
    assert fn(B.PREMIUM_POWER_PRO)(t) is True
    assert me.premium_power_pro_turn == t.game.turn                          # turn-stamped for wiring


# ---------------------------------------------------------------- shared helper
def _is_sup(tok):
    return tok[0] == 'T' and tok[1].get('trainerType') == 'Supporter'


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
