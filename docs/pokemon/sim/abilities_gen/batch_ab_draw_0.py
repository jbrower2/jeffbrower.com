#!/usr/bin/env python3
"""Batch: ab_draw_0 — card-draw abilities (all `activated`, fn(actx)->bool; True == used).

Seven once-per-turn draw abilities. The "Once during your turn", "when you play/evolve this Pokémon",
and "you may use this Ability" turn-flow gating is owned by the caller (per the ab_search_0 convention);
each lambda implements the draw/discard/hand-reset itself, gated only on its own on-card condition and on
having the resources (cards in hand/deck) its cost/effect needs.

Deck-order note: the engine draws from the END of `deck` (deck.pop()), so the BOTTOM of the deck is
index 0. "Put X on the bottom of your deck" therefore inserts at the front.

Engine gap: Crobat's Shadowy Envoy keys off "played Janine's Secret Art this turn". The engine tracks
neither per-turn played Supporters nor that specific card (Janine's Secret Art isn't in the Trainer
pool at all), so it reads a (currently-absent) tracker attribute and is a conservative no-op today — it
never fires unconditionally. See `uncertain`.
"""
from ability_effects import ability, ActivatedCtx  # noqa: F401 (ActivatedCtx per batch header convention)


# ---------------------------------------------------------------- helpers
def _draw_until(player, n):
    """Draw until `player`'s hand holds n cards (or the deck empties). Return the number drawn."""
    drawn = 0
    while len(player.hand) < n and player.draw(1):
        drawn += 1
    return drawn


def _discard_from_hand(player, k):
    """Discard k cards from the end of `player`'s hand (a cost). Basic Energy tokens go to the
    disc_energy pool; every other token to the discard pile. Return the number discarded."""
    done = 0
    while done < k and player.hand:
        tok = player.hand.pop()
        if tok[0] == 'E':
            player.disc_energy[tok[1]] += 1
        else:
            player.discard.append(tok)
        done += 1
    return done


# ---------------------------------------------------------------- fixed-count draws
@ability('activated', "- Once during your turn, you may draw a card.")
def _hurried_gait(actx):
    # Rapidash (Hurried Gait): plain +1 card.
    n0 = len(actx.me.hand)
    actx.me.draw(1)
    return len(actx.me.hand) > n0


@ability('activated', "- Once during your turn, when you play this Pokémon from your hand to evolve 1 of your Pokémon, you may use this Ability. Draw 2 cards.")
def _psychic_draw(actx):
    # Kadabra (Psychic Draw): on-evolve draw 2 (the "when you evolve" trigger is the caller's; draw here).
    n0 = len(actx.me.hand)
    actx.me.draw(2)
    return len(actx.me.hand) > n0


@ability('activated', "- You must discard 2 cards from your hand in order to use this Ability. Once during your turn, you may draw a card.")
def _reconstitute(actx):
    # Team Rocket's Porygon-Z (Reconstitute): pay 2 discards, then draw 1 (net -1 card; deck-cycling /
    # discard fuel). Need 2 cards to pay the cost AND a non-empty deck (paying 2 for a 0-card draw is
    # never a real use), so it never bleeds the hand for nothing.
    me = actx.me
    if len(me.hand) < 2 or not me.deck:
        return False
    _discard_from_hand(me, 2)
    me.draw(1)
    return True


@ability('activated', "- Once during your turn, if this Pokémon is in the Active Spot, you may use this Ability. Each player draws a card.")
def _alluring_wings(actx):
    # Frosmoth (Alluring Wings): only from the Active Spot; then BOTH players draw 1. Skip when OUR own
    # deck is empty — we'd draw 0 while still forcing the opponent to draw 1, a pure gift for zero
    # self-benefit (this is a symmetric draw with no disruption value, so mirror Reconstitute's deck guard;
    # contrast Grand Wing, whose opp-draw-4 has disruption value even against a small hand).
    if actx.mon is not actx.me.active:
        return False
    if not actx.me.deck:
        return False
    actx.me.draw(1)
    actx.opp.draw(1)
    return True


# ---------------------------------------------------------------- draw-to-hand-size (+ pay a card)
@ability('activated', "- You must put a card from your hand on the bottom of your deck in order to use this Ability. Once during your turn, you may draw cards until you have 5 cards in your hand.")
def _up_tempo(actx):
    # Quaquaval (Up-Tempo): bury 1 hand card on the bottom of the deck, then refill the hand to 5.
    # Needs a card in hand to pay the cost.
    me = actx.me
    if not me.hand:
        return False
    me.deck.insert(0, me.hand.pop())        # bottom of deck = index 0 (draw pops from the end)
    _draw_until(me, 5)
    return True


@ability('activated', "- Once during your turn, if you played Janine's Secret Art from your hand this turn, you may draw cards until you have 8 cards in your hand.")
def _shadowy_envoy(actx):
    # Crobat (Shadowy Envoy): fires only if Janine's Secret Art (a Supporter) was played this turn. The
    # engine tracks neither per-turn played Supporters nor that card (it isn't in the Trainer pool), so
    # this reads a currently-absent tracker and is a conservative no-op today. It never fires
    # unconditionally; if the engine later records played Trainers on the Player, the draw-to-8 activates.
    played = getattr(actx.me, 'played_this_turn', ())
    if "Janine's Secret Art" not in played:
        return False
    _draw_until(actx.me, 8)
    return True


# ---------------------------------------------------------------- opponent hand reset
@ability('activated', "- Once during your turn, you may use this Ability. Your opponent shuffles their hand and puts it on the bottom of their deck. If they put any cards on the bottom of their deck in this way, they draw 4 cards.")
def _grand_wing(actx):
    # Vivillon (Grand Wing): opponent buries their whole hand under the deck; if any card was buried,
    # they redraw exactly 4 (hand disruption — punishes a hoarded hand). No-op if their hand is empty.
    opp = actx.opp
    if not opp.hand:
        return False
    moved = list(opp.hand)
    opp.hand = []
    opp.deck[:0] = moved                     # put the shuffled hand on the bottom (front) of the deck
    opp.draw(4)                              # then redraw 4 from the top
    return True
