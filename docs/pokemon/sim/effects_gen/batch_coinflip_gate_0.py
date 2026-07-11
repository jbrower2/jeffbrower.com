#!/usr/bin/env python3
"""Effect batch: coinflip_gate_0.

Coin-flip-gated attacks whose heads branch also sets up a defensive "wall" for the
opponent's next turn. Each effect is registered by its exact (damage-stripped) text.
"""
from attack_effects import effect, EffectCtx, STATUSES

# A reduction large enough to zero out ANY realistic incoming attack damage (post-weakness
# doubling is still <<< this). incoming_damage() does `max(0, dmg - dr_amount)`, so this models
# "prevent all damage ... done to this Pokémon" during the opponent's next turn.
_WALL = 100000


def _wall_next_turn(ctx: EffectCtx):
    """Schedule 'prevent all attack damage to this Pokémon during your opponent's next turn'.

    Reuses the engine's temp damage-reduction hook (Mon.dr_amount / Mon.dr_turn): incoming_damage()
    applies dr_amount when `dr_turn + 1 == game.turn`, i.e. exactly the opponent's following turn,
    then it lapses on its own (no cleanup needed). A huge amount prevents ALL of the damage.
    """
    ctx.attacker.dr_amount = _WALL
    ctx.attacker.dr_turn = ctx.game.turn


@effect("Flip a coin. If tails, this attack does nothing. If heads, during your opponent's next turn, "
        "prevent all damage from and effects of attacks done to this Pokémon.")
def _tails_nothing_heads_wall(ctx):
    # Tails: the attack does nothing at all (no damage, no wall).
    if not ctx.flip():
        return 0
    # Heads: deal the printed base damage AND wall off the attacker next turn.
    _wall_next_turn(ctx)
    return ctx.base
