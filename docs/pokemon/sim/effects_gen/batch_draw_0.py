#!/usr/bin/env python3
"""Effect batch: draw_0.

Card-draw attacks: fixed-count draws, "draw up to N in hand" refills, hand-shuffle
redraws, discard-to-draw, symmetric draws, and a self-Asleep draw. Each effect is
registered by its exact (damage-stripped) text and returns the printed base damage
(often 0 for these utility attacks) after performing the draw side effect.

All draws go to the ATTACKING player's hand (ctx.me) unless the text says otherwise
("Each player draws"). Draw helpers stop cleanly on an empty deck (Player.draw returns
False), so no deck-out crash — the engine's deck-out loss is handled separately.
"""
from attack_effects import effect, EffectCtx, STATUSES


def _draw_up_to(ctx: EffectCtx, target):
    """Draw one card at a time until the attacker's hand holds `target` cards.
    No-op if the hand already has >= target; stops early if the deck empties.
    Models both the mandatory and "you may" refills (drawing is always taken)."""
    while len(ctx.me.hand) < target and ctx.me.draw(1):
        pass


def _discard_one_from_hand(player):
    """Discard exactly one card from `player`'s hand, routing basic energy to the
    energy-discard counter and everything else to the discard pile. Returns True iff a
    card was actually discarded (False on an empty hand -> the "If you do" gate fails)."""
    if not player.hand:
        return False
    tok = player.hand.pop()
    if tok[0] == 'E':
        player.disc_energy[tok[1]] += 1
    else:
        player.discard.append(tok)
    return True


# ---------------------------------------------------------------- fixed-count draws

@effect("Draw 2 cards.")
def _draw_2(ctx):
    ctx.draw(2)
    return ctx.base


@effect("Draw 3 cards.")
def _draw_3(ctx):
    ctx.draw(3)
    return ctx.base


@effect("Draw 4 cards.")
def _draw_4(ctx):
    ctx.draw(4)
    return ctx.base


# ---------------------------------------------------------------- refill to N in hand

@effect("You may draw cards until you have 5 cards in your hand.")
def _draw_until_5(ctx):
    _draw_up_to(ctx, 5)
    return ctx.base


@effect("You may draw cards until you have 6 cards in your hand.")
def _draw_until_6(ctx):
    _draw_up_to(ctx, 6)
    return ctx.base


@effect("Draw cards until you have 7 cards in your hand.")
def _draw_until_7(ctx):
    _draw_up_to(ctx, 7)
    return ctx.base


# ---------------------------------------------------------------- shuffle-hand redraws

@effect("Shuffle your hand into your deck. Then, draw 6 cards.")
def _shuffle_draw_6(ctx):
    ctx.me.deck += ctx.me.hand
    ctx.me.hand = []
    ctx.rng.shuffle(ctx.me.deck)
    ctx.me.draw(6)
    return ctx.base


@effect("Shuffle your hand into your deck. Then, draw a card for each card in your opponent's hand.")
def _shuffle_draw_per_opp_hand(ctx):
    n = len(ctx.opp.hand)                 # count BEFORE shuffling our own hand away
    ctx.me.deck += ctx.me.hand
    ctx.me.hand = []
    ctx.rng.shuffle(ctx.me.deck)
    ctx.me.draw(n)
    return ctx.base


# ---------------------------------------------------------------- discard-to-draw (gated)

@effect("Discard a card from your hand. If you do, draw 2 cards.")
def _discard_draw_2(ctx):
    if _discard_one_from_hand(ctx.me):    # only draw if a card was actually discarded
        ctx.draw(2)
    return ctx.base


@effect("Discard a card from your hand. If you do, draw 3 cards.")
def _discard_draw_3(ctx):
    if _discard_one_from_hand(ctx.me):
        ctx.draw(3)
    return ctx.base


# ---------------------------------------------------------------- symmetric draw

@effect("Each player draws 3 cards.")
def _each_draws_3(ctx):
    ctx.me.draw(3)
    ctx.opp.draw(3)
    return ctx.base


# ---------------------------------------------------------------- self-Asleep + draw

@effect("This Pokémon is now Asleep. Draw 2 cards.")
def _self_asleep_draw_2(ctx):
    # "This Pokémon" is the ATTACKER, which puts itself to Sleep (self-inflicted, so
    # opponent-facing effect shields don't apply). Then the attacker's player draws 2.
    ctx.attacker.status['Asleep'] = True
    ctx.draw(2)
    return ctx.base
