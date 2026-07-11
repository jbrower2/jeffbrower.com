#!/usr/bin/env python3
"""Unit tests for trainer batch tr_supporter_0 (14 Supporters)."""
from effects_testkit import mk, runner, BK, VANILLA
from engine import Mon
import trainer_effects as TE
import trainers_gen.batch_tr_supporter_0        # noqa: F401 — registers the effects

EX_CARD = next(c for c in BK.values() if c.is_ex)
LIGHT = next(c for c in BK.values() if c.ptype == 'Lightning' and c.stage == 0)

# exact printed texts (keyed via normalize)
T = {
    'az':     "Switch your Active Pokémon with 1 of your Benched Pokémon. If you moved a Pokémon ex to your Bench in this way, heal 80 damage from that Pokémon.",
    'acerola': "You can use this card only if your opponent has 2 or fewer Prize cards remaining.\n\nChoose 1 of your Pokémon in play. During your opponent's next turn, prevent all damage from and effects of attacks done to that Pokémon by your opponent's Pokémon ex.",
    'amarys': "Draw 4 cards. At the end of this turn, if you have 5 or more cards in your hand, discard your hand.",
    'anthea': "You can use this card only if you have N's Darmanitan, N's Zoroark ex, N's Vanilluxe, N's Klinklang, N's Reshiram, and N's Zekrom in play.\n\nDuring this turn, if your opponent's Active Pokémon is Knocked Out by damage from an attack used by your N's Pokémon, take 3 more Prize cards.",
    'bianca': "Heal all damage from 1 of your Pokémon that has 30 HP or less remaining.",
    'billy':  "Draw 2 cards. Then, if you have 10 or more cards in your hand, draw 2 more cards.",
    'blackbelt': "During this turn, attacks used by your Pokémon do 40 more damage to your opponent's Active Pokémon ex (before applying Weakness and Resistance).",
    'boss':   "Switch in 1 of your opponent's Benched Pokémon to the Active Spot.",
    'briar':  "You can use this card only if your opponent has exactly 2 Prize cards remaining.\n\nDuring this turn, if your opponent's Active Pokémon is Knocked Out by damage from an attack used by your Tera Pokémon, take 1 more Prize card.",
    'brock':  "Search your deck for up to 2 Basic Pokémon or 1 Evolution Pokémon, reveal them, and put them into your hand. Then, shuffle your deck.",
    'canari': "You can use this card only if you discard another card from your hand.\n\nSearch your deck for up to 4 {L} Pokémon, reveal them, and put them into your hand. Then, shuffle your deck.",
    'caretaker': "Draw 2 cards. If you drew any cards in this way and if Community Center is in play, shuffle this Caretaker into your deck instead of discarding it.",
    'carmine': "If you go first, you may use this card during your first turn.\n\nDiscard your hand and draw 5 cards.",
    'cassiopeia': "You can use this card only when it is the last card in your hand.\n\nSearch your deck for up to 2 cards and put them into your hand. Then, shuffle your deck.",
}


def fn(key):
    return TE.TRAINER_EFFECTS[TE.normalize(T[key])]['fn']


def action(key, **kw):
    ctx, at, df, me, opp = mk(**kw)
    did = fn(key)(TE.TrainerCtx(me, opp, ctx.game))
    return did, me, opp, ctx


TESTS = []
def test(f): TESTS.append(f); return f


@test
def t_az_tranquility():
    ctx, at, df, me, opp = mk()
    me.active = Mon(EX_CARD); me.active.damage = 100
    me.bench = [Mon(VANILLA)]
    did = fn('az')(TE.TrainerCtx(me, opp, ctx.game))
    assert did
    assert me.active.card is VANILLA and not me.active.card.is_ex   # promoted the bench mon
    assert me.bench[0].card.is_ex and me.bench[0].damage == 20      # ex benched + healed 80


@test
def t_acerola_mischief():
    # gate met: opponent at 2 prizes -> one-turn shield on our Active
    did, me, opp, ctx = action('acerola', opp_prizes=2)
    assert did and me.active.dr_amount == 10000 and me.active.dr_turn == ctx.game.turn
    # gate not met: opponent at 3 prizes -> no-op
    did2, me2, *_ = action('acerola', opp_prizes=3)
    assert not did2 and me2.active.dr_amount == 0


@test
def t_amarys():
    did, me, opp, ctx = action('amarys')            # empty opening hand
    assert did and len(me.hand) == 4


@test
def t_anthea_concordia():
    did, me, opp, ctx = action('anthea')            # no N's Pokémon in play -> gate fails
    assert not did


@test
def t_biancas_devotion():
    ctx, at, df, me, opp = mk()
    me.active.damage = 60                            # VANILLA 80 HP -> 20 HP remaining (eligible)
    me.bench = [Mon(VANILLA)]; me.bench[0].damage = 40   # 40 HP remaining (NOT eligible)
    did = fn('bianca')(TE.TrainerCtx(me, opp, ctx.game))
    assert did and me.active.damage == 0 and me.bench[0].damage == 40


@test
def t_billy_onare():
    did, me, opp, ctx = action('billy')             # empty hand -> draw 2, no bonus
    assert did and len(me.hand) == 2
    ctx2, at2, df2, me2, opp2 = mk()
    me2.hand = [('E', 'Colorless')] * 8             # -> draw 2 to 10, then 2 more to 12
    fn('billy')(TE.TrainerCtx(me2, opp2, ctx2.game))
    assert len(me2.hand) == 12


@test
def t_black_belts_training():
    did, me, opp, ctx = action('blackbelt')         # offensive supporter buff: unmodeled no-op
    assert not did


@test
def t_bosss_orders():
    ctx, at, df, me, opp = mk(atk_energy={'Grass': 1}, opp_bench=1)
    opp.bench[0].damage = 75                         # hp_left 5 -> KO-able, so gust drags it up
    did = fn('boss')(TE.TrainerCtx(me, opp, ctx.game))
    assert did and opp.active.damage == 75


@test
def t_briar():
    did, me, opp, ctx = action('briar', opp_prizes=2)   # Tera unmodeled -> no-op
    assert not did


@test
def t_brocks_scouting():
    did, me, opp, ctx = action('brock')             # deck has Basic VANILLAs
    assert did and sum(1 for x in me.hand if x[0] == 'P') == 2


@test
def t_canari():
    ctx, at, df, me, opp = mk()
    me.hand = [('E', 'Colorless')]                   # a card to discard
    me.deck = me.deck + [('P', LIGHT)] * 2           # {L} Pokémon to fetch
    did = fn('canari')(TE.TrainerCtx(me, opp, ctx.game))
    assert did
    assert sum(1 for x in me.hand if x[0] == 'P' and x[1].ptype == 'Lightning') >= 1
    assert me.disc_energy['Colorless'] == 1          # the discarded card was routed to disc_energy
    # no {L} in deck -> don't pay the cost
    ctx2, at2, df2, me2, opp2 = mk()
    me2.hand = [('E', 'Colorless')]
    assert not fn('canari')(TE.TrainerCtx(me2, opp2, ctx2.game))
    assert me2.hand == [('E', 'Colorless')]          # cost not paid


@test
def t_caretaker():
    did, me, opp, ctx = action('caretaker')
    assert did and len(me.hand) == 2


@test
def t_carmine():
    ctx, at, df, me, opp = mk()
    me.hand = [('P', VANILLA), ('E', 'Colorless')]
    did = fn('carmine')(TE.TrainerCtx(me, opp, ctx.game))
    assert did and len(me.hand) == 5                 # discarded 2, drew 5
    assert ('P', VANILLA) in me.discard and me.disc_energy['Colorless'] == 1


@test
def t_cassiopeia():
    did, me, opp, ctx = action('cassiopeia')         # empty hand (it was the last card) -> search 2
    assert did and len(me.hand) == 2
    ctx2, at2, df2, me2, opp2 = mk()
    me2.hand = [('E', 'Colorless')]                  # not the last card -> gate fails
    assert not fn('cassiopeia')(TE.TrainerCtx(me2, opp2, ctx2.game))


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
