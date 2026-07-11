#!/usr/bin/env python3
"""Unit tests for effect batch draw_0."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # ensure sim/ importable
from collections import Counter
from effects_testkit import mk, run, runner
import attack_effects as AE
import effects_gen.batch_draw_0  # noqa: F401  (registers the effects)

# In mk(): me.hand starts empty; me.deck has 16 cards (6 Pokémon + 10 Colorless energy);
# opp.hand starts empty; heads=0.0, tails=0.9.


def _fn(text):
    return AE.ATTACK_EFFECTS[AE.normalize(text)]


# ---------------------------------------------------------------- fixed-count draws

def t_draw_2():
    d, ctx, at, df, me, opp = run("[60] Draw 2 cards.", base=60)
    assert d == 60, d                     # returns printed base (Seaking's 60)
    assert len(me.hand) == 2, len(me.hand)


def t_draw_2_zero_base():
    d, ctx, at, df, me, opp = run("- Draw 2 cards.", base=0)   # Absol / Latias: no damage
    assert d == 0, d
    assert len(me.hand) == 2, len(me.hand)


def t_draw_3():
    d, ctx, at, df, me, opp = run("- Draw 3 cards.", base=0)
    assert d == 0 and len(me.hand) == 3, (d, len(me.hand))


def t_draw_4():
    d, ctx, at, df, me, opp = run("- Draw 4 cards.", base=0)
    assert d == 0 and len(me.hand) == 4, (d, len(me.hand))


# ---------------------------------------------------------------- refill to N in hand

def t_draw_until_5_from_empty():
    d, ctx, at, df, me, opp = run("[30] You may draw cards until you have 5 cards in your hand.", base=30)
    assert d == 30, d
    assert len(me.hand) == 5, len(me.hand)


def t_draw_until_6_from_empty():
    d, ctx, at, df, me, opp = run("[20] You may draw cards until you have 6 cards in your hand.", base=20)
    assert d == 20 and len(me.hand) == 6, (d, len(me.hand))


def t_draw_until_6_no_overdraw():
    # Hand already has more than 6 -> draw nothing (never discards down).
    ctx, at, df, me, opp = mk(text="You may draw cards until you have 6 cards in your hand.")
    me.hand = [('E', 'Colorless')] * 8
    deck_before = len(me.deck)
    _fn("You may draw cards until you have 6 cards in your hand.")(ctx)
    assert len(me.hand) == 8, len(me.hand)          # unchanged
    assert len(me.deck) == deck_before, len(me.deck)


def t_draw_until_6_partial_fill():
    # Hand already holds 2 -> TOP UP to exactly 6 (draw 4, NOT 6). Pins the
    # "until you have N" semantics vs a plain draw(N): draws target - len(hand).
    ctx, at, df, me, opp = mk(text="You may draw cards until you have 6 cards in your hand.")
    me.hand = [('P', 'x'), ('E', 'Colorless')]      # 2 cards already in hand
    deck_before = len(me.deck)                        # 16
    _fn("You may draw cards until you have 6 cards in your hand.")(ctx)
    assert len(me.hand) == 6, len(me.hand)           # topped up to exactly 6
    assert len(me.deck) == deck_before - 4, len(me.deck)  # drew exactly 4 (6-2), not 6


def t_draw_until_7_from_empty():
    d, ctx, at, df, me, opp = run("- Draw cards until you have 7 cards in your hand.", base=0)
    assert d == 0 and len(me.hand) == 7, (d, len(me.hand))


def t_draw_until_stops_on_empty_deck():
    # Deck too small to reach the target -> draws all it can, then stops (no crash).
    ctx, at, df, me, opp = mk(text="Draw cards until you have 7 cards in your hand.")
    me.hand = []
    me.deck = [('E', 'Colorless')] * 3
    _fn("Draw cards until you have 7 cards in your hand.")(ctx)
    assert len(me.hand) == 3 and len(me.deck) == 0, (len(me.hand), len(me.deck))


# ---------------------------------------------------------------- shuffle-hand redraws

def t_shuffle_draw_6():
    ctx, at, df, me, opp = mk(text="Shuffle your hand into your deck. Then, draw 6 cards.")
    me.hand = [('P', 'x'), ('E', 'Colorless')]      # 2-card hand shuffled away first
    deck_before = len(me.deck)                       # 16
    _fn("Shuffle your hand into your deck. Then, draw 6 cards.")(ctx)
    assert len(me.hand) == 6, len(me.hand)
    assert len(me.deck) == deck_before + 2 - 6, len(me.deck)   # 16 +2 hand -6 drawn = 12


def t_shuffle_draw_per_opp_hand():
    ctx, at, df, me, opp = mk(text="Shuffle your hand into your deck. Then, draw a card for each card in your opponent's hand.")
    me.hand = [('E', 'Colorless'), ('E', 'Colorless')]  # 2 cards, shuffled in
    opp.hand = [('P', 'a'), ('P', 'b'), ('P', 'c'), ('P', 'd')]  # opp has 4 -> draw 4
    _fn("Shuffle your hand into your deck. Then, draw a card for each card in your opponent's hand.")(ctx)
    assert len(me.hand) == 4, len(me.hand)
    assert len(opp.hand) == 4, len(opp.hand)         # opponent's hand untouched


def t_shuffle_draw_per_opp_hand_zero():
    # Opponent has an empty hand -> draw 0 after shuffling ours away.
    ctx, at, df, me, opp = mk(text="Shuffle your hand into your deck. Then, draw a card for each card in your opponent's hand.")
    me.hand = [('E', 'Colorless'), ('E', 'Colorless')]
    opp.hand = []
    _fn("Shuffle your hand into your deck. Then, draw a card for each card in your opponent's hand.")(ctx)
    assert len(me.hand) == 0, len(me.hand)


# ---------------------------------------------------------------- discard-to-draw (gated)

def t_discard_draw_2_with_card():
    ctx, at, df, me, opp = mk(text="Discard a card from your hand. If you do, draw 2 cards.", base=0)
    me.hand = [('E', 'Colorless')]                   # one card to discard
    d = _fn("Discard a card from your hand. If you do, draw 2 cards.")(ctx)
    assert d == 0, d
    assert len(me.hand) == 2, len(me.hand)           # -1 discard, +2 draw
    assert me.disc_energy['Colorless'] == 1, me.disc_energy   # energy routed to disc_energy


def t_discard_draw_2_empty_hand():
    # Empty hand -> nothing discarded -> "If you do" fails -> no draw.
    d, ctx, at, df, me, opp = run("- Discard a card from your hand. If you do, draw 2 cards.", base=0)
    assert d == 0, d
    assert len(me.hand) == 0, len(me.hand)
    assert me.discard == [], me.discard                     # gate held: nothing discarded
    assert sum(me.disc_energy.values()) == 0, me.disc_energy


def t_discard_draw_3_with_card():
    ctx, at, df, me, opp = mk(text="Discard a card from your hand. If you do, draw 3 cards.", base=0)
    me.hand = [('P', 'x')]                            # Pokémon card -> goes to discard pile
    d = _fn("Discard a card from your hand. If you do, draw 3 cards.")(ctx)
    assert d == 0, d
    assert len(me.hand) == 3, len(me.hand)           # -1 discard, +3 draw
    assert me.discard == [('P', 'x')], me.discard


def t_discard_draw_3_empty_hand():
    d, ctx, at, df, me, opp = run("- Discard a card from your hand. If you do, draw 3 cards.", base=0)
    assert d == 0 and len(me.hand) == 0, (d, len(me.hand))


# ---------------------------------------------------------------- symmetric draw

def t_each_draws_3():
    d, ctx, at, df, me, opp = run("- Each player draws 3 cards.", base=0)
    assert d == 0, d
    assert len(me.hand) == 3, len(me.hand)
    assert len(opp.hand) == 3, len(opp.hand)         # opponent draws too


# ---------------------------------------------------------------- self-Asleep + draw

def t_self_asleep_draw_2():
    d, ctx, at, df, me, opp = run("- This Pokémon is now Asleep. Draw 2 cards.", base=0)
    assert d == 0, d
    assert at.status.get('Asleep') is True, at.status   # the ATTACKER is Asleep
    assert not df.status.get('Asleep'), df.status       # NOT the defender
    assert len(me.hand) == 2, len(me.hand)


TESTS = [
    t_draw_2,
    t_draw_2_zero_base,
    t_draw_3,
    t_draw_4,
    t_draw_until_5_from_empty,
    t_draw_until_6_from_empty,
    t_draw_until_6_no_overdraw,
    t_draw_until_6_partial_fill,
    t_draw_until_7_from_empty,
    t_draw_until_stops_on_empty_deck,
    t_shuffle_draw_6,
    t_shuffle_draw_per_opp_hand,
    t_shuffle_draw_per_opp_hand_zero,
    t_discard_draw_2_with_card,
    t_discard_draw_2_empty_hand,
    t_discard_draw_3_with_card,
    t_discard_draw_3_empty_hand,
    t_each_draws_3,
    t_self_asleep_draw_2,
]

if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
