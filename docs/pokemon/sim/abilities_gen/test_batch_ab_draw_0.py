#!/usr/bin/env python3
"""Unit tests for ability batch ab_draw_0 (card-draw activated abilities)."""
from collections import Counter
from effects_testkit import mk, runner
import ability_effects as AB
import abilities_gen.batch_ab_draw_0  # noqa: F401 (registers the batch's abilities on import)

HURRIED_GAIT = "- Once during your turn, you may draw a card."
PSYCHIC_DRAW = ("- Once during your turn, when you play this Pokémon from your hand to evolve 1 of your "
                "Pokémon, you may use this Ability. Draw 2 cards.")
RECONSTITUTE = ("- You must discard 2 cards from your hand in order to use this Ability. Once during "
                "your turn, you may draw a card.")
ALLURING_WINGS = ("- Once during your turn, if this Pokémon is in the Active Spot, you may use this "
                  "Ability. Each player draws a card.")
UP_TEMPO = ("- You must put a card from your hand on the bottom of your deck in order to use this "
            "Ability. Once during your turn, you may draw cards until you have 5 cards in your hand.")
SHADOWY_ENVOY = ("- Once during your turn, if you played Janine's Secret Art from your hand this turn, "
                 "you may draw cards until you have 8 cards in your hand.")
GRAND_WING = ("- Once during your turn, you may use this Ability. Your opponent shuffles their hand and "
              "puts it on the bottom of their deck. If they put any cards on the bottom of their deck "
              "in this way, they draw 4 cards.")

ALL_KEYS = [HURRIED_GAIT, PSYCHIC_DRAW, RECONSTITUTE, ALLURING_WINGS, UP_TEMPO, SHADOWY_ENVOY, GRAND_WING]


def _entry(key):
    return AB.ABILITY_EFFECTS[AB.normalize(key)]


def _fn(key):
    return _entry(key)['fn']


def _actx(me, opp, mon, game):
    return AB.ActivatedCtx(me, opp, mon, game)


# ---------------------------------------------------------------- registration
def t_all_registered_as_activated():
    for k in ALL_KEYS:
        assert _entry(k)['kind'] == 'activated', k


# ---------------------------------------------------------------- Hurried Gait (draw 1)
def t_hurried_gait_draws_one():
    ctx, at, df, me, opp = mk()
    n0 = len(me.hand)
    assert _fn(HURRIED_GAIT)(_actx(me, opp, at, ctx.game)) is True
    assert len(me.hand) == n0 + 1


def t_hurried_gait_empty_deck_noop():
    ctx, at, df, me, opp = mk()
    me.deck = []
    assert _fn(HURRIED_GAIT)(_actx(me, opp, at, ctx.game)) is False
    assert me.hand == []


# ---------------------------------------------------------------- Psychic Draw (draw 2 on evolve)
def t_psychic_draw_draws_two():
    ctx, at, df, me, opp = mk()
    n0 = len(me.hand)
    assert _fn(PSYCHIC_DRAW)(_actx(me, opp, at, ctx.game)) is True
    assert len(me.hand) == n0 + 2


def t_psychic_draw_empty_deck_noop():
    ctx, at, df, me, opp = mk()
    me.deck = []
    assert _fn(PSYCHIC_DRAW)(_actx(me, opp, at, ctx.game)) is False
    assert me.hand == []


def t_psychic_draw_partial_deck_draws_what_it_can():
    # "Draw 2 cards" draws up to 2 — one when only one remains — and still counts as used.
    ctx, at, df, me, opp = mk()
    me.deck = [('E', 'Colorless')]
    assert _fn(PSYCHIC_DRAW)(_actx(me, opp, at, ctx.game)) is True
    assert len(me.hand) == 1 and me.deck == []


# ---------------------------------------------------------------- Reconstitute (discard 2, draw 1)
def t_reconstitute_discards_two_draws_one():
    ctx, at, df, me, opp = mk()
    me.hand = [('E', 'Fire'), ('E', 'Water'), ('P', df.card)]   # 3 cards
    me.deck = [('E', 'Colorless')]                              # exactly one to draw
    assert _fn(RECONSTITUTE)(_actx(me, opp, at, ctx.game)) is True
    # net: 3 - 2 discarded + 1 drawn = 2 in hand
    assert len(me.hand) == 2
    # the two discarded (popped from the end): the Pokémon token -> discard pile, Water -> disc_energy
    assert me.discard == [('P', df.card)]
    assert me.disc_energy['Water'] == 1
    assert me.deck == []                                        # the one card was drawn


def t_reconstitute_needs_two_cards():
    ctx, at, df, me, opp = mk()
    me.hand = [('E', 'Fire')]                                   # only 1 card -> can't pay the cost
    before = list(me.hand)
    assert _fn(RECONSTITUTE)(_actx(me, opp, at, ctx.game)) is False
    assert me.hand == before
    assert me.disc_energy == Counter()


def t_reconstitute_empty_deck_wont_pay():
    ctx, at, df, me, opp = mk()
    me.hand = [('E', 'Fire'), ('E', 'Water'), ('P', df.card)]
    me.deck = []                                                # never pay 2 for a 0-card draw
    before = list(me.hand)
    assert _fn(RECONSTITUTE)(_actx(me, opp, at, ctx.game)) is False
    assert me.hand == before                                    # nothing discarded
    assert me.discard == []


# ---------------------------------------------------------------- Alluring Wings (each player draws 1)
def t_alluring_wings_both_draw_when_active():
    ctx, at, df, me, opp = mk()
    mn, on = len(me.hand), len(opp.hand)
    assert _fn(ALLURING_WINGS)(_actx(me, opp, at, ctx.game)) is True   # at IS me.active
    assert len(me.hand) == mn + 1
    assert len(opp.hand) == on + 1


def t_alluring_wings_bench_noop():
    ctx, at, df, me, opp = mk()
    holder = me.bench[0]                                        # not the Active Spot
    assert _fn(ALLURING_WINGS)(_actx(me, opp, holder, ctx.game)) is False
    assert me.hand == [] and opp.hand == []


def t_alluring_wings_empty_own_deck_noop():
    # With our own deck empty we'd draw 0 while still handing the opponent a card — a pure gift.
    # Never fire it for zero self-benefit; the opponent's hand must stay untouched.
    ctx, at, df, me, opp = mk()
    me.deck = []                                                # at IS me.active, but we can't draw
    on = len(opp.hand)
    assert _fn(ALLURING_WINGS)(_actx(me, opp, at, ctx.game)) is False
    assert me.hand == [] and len(opp.hand) == on


# ---------------------------------------------------------------- Up-Tempo (bury 1, draw to 5)
def t_up_tempo_refills_to_five():
    ctx, at, df, me, opp = mk()
    me.hand = [('P', df.card), ('E', 'Fire')]                  # 2 cards
    assert _fn(UP_TEMPO)(_actx(me, opp, at, ctx.game)) is True
    assert len(me.hand) == 5                                   # bury 1 -> 1, draw 4 -> 5
    assert me.deck[0] == ('E', 'Fire')                         # last hand card buried on the bottom


def t_up_tempo_no_draw_when_already_full():
    ctx, at, df, me, opp = mk()
    marker = ('T', {'name': 'BURIED'})
    me.hand = [('E', 'Fire')] * 5 + [marker]                   # 6 cards
    deck0 = len(me.deck)
    assert _fn(UP_TEMPO)(_actx(me, opp, at, ctx.game)) is True
    assert len(me.hand) == 5                                   # bury 1 -> 5, draw 0
    assert me.deck[0] == marker
    assert len(me.deck) == deck0 + 1                            # nothing drawn, just the buried card added


def t_up_tempo_empty_hand_noop():
    ctx, at, df, me, opp = mk()
    me.hand = []
    assert _fn(UP_TEMPO)(_actx(me, opp, at, ctx.game)) is False


# ---------------------------------------------------------------- Shadowy Envoy (Janine gate -> draw to 8)
def t_shadowy_envoy_noop_without_tracker():
    ctx, at, df, me, opp = mk()
    assert _fn(SHADOWY_ENVOY)(_actx(me, opp, at, ctx.game)) is False   # no played-tracker on the engine
    assert me.hand == []


def t_shadowy_envoy_fires_with_janine():
    ctx, at, df, me, opp = mk()
    me.played_this_turn = {"Janine's Secret Art"}
    me.deck = [('E', 'Colorless')] * 20                        # plenty to reach 8
    assert _fn(SHADOWY_ENVOY)(_actx(me, opp, at, ctx.game)) is True
    assert len(me.hand) == 8


def t_shadowy_envoy_other_trainer_noop():
    ctx, at, df, me, opp = mk()
    me.played_this_turn = {"Professor's Research"}             # wrong card -> no fire
    assert _fn(SHADOWY_ENVOY)(_actx(me, opp, at, ctx.game)) is False
    assert me.hand == []


# ---------------------------------------------------------------- Grand Wing (opp hand -> bottom, draw 4)
def t_grand_wing_resets_opponent_hand():
    ctx, at, df, me, opp = mk()
    moved = [('T', {'name': 'X1'}), ('T', {'name': 'X2'}), ('P', df.card)]
    opp.hand = list(moved)
    d0 = len(opp.deck)
    assert _fn(GRAND_WING)(_actx(me, opp, at, ctx.game)) is True
    assert len(opp.hand) == 4                                  # redrew exactly 4 from the top
    assert opp.deck[:3] == moved                               # old hand buried on the bottom (front)
    assert len(opp.deck) == d0 + 3 - 4


def t_grand_wing_empty_hand_noop():
    ctx, at, df, me, opp = mk()
    opp.hand = []
    d0 = len(opp.deck)
    assert _fn(GRAND_WING)(_actx(me, opp, at, ctx.game)) is False
    assert opp.hand == []
    assert len(opp.deck) == d0                                  # deck untouched


TESTS = [
    t_all_registered_as_activated,
    t_hurried_gait_draws_one,
    t_hurried_gait_empty_deck_noop,
    t_psychic_draw_draws_two,
    t_psychic_draw_empty_deck_noop,
    t_psychic_draw_partial_deck_draws_what_it_can,
    t_reconstitute_discards_two_draws_one,
    t_reconstitute_needs_two_cards,
    t_reconstitute_empty_deck_wont_pay,
    t_alluring_wings_both_draw_when_active,
    t_alluring_wings_bench_noop,
    t_alluring_wings_empty_own_deck_noop,
    t_up_tempo_refills_to_five,
    t_up_tempo_no_draw_when_already_full,
    t_up_tempo_empty_hand_noop,
    t_shadowy_envoy_noop_without_tracker,
    t_shadowy_envoy_fires_with_janine,
    t_shadowy_envoy_other_trainer_noop,
    t_grand_wing_resets_opponent_hand,
    t_grand_wing_empty_hand_noop,
]

if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
