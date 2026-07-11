#!/usr/bin/env python3
"""Effect batch: tool_0 — Pokémon-Tool interactions.

All seven attacks in this batch reference **Pokémon Tools**. The engine now models Tool
attachment: each `Mon` carries a `tools` list, exposed to effects through the EffectCtx
trackers `ctx.has_tool(mon)`, `ctx.count_tools(side)` and `ctx.discard_tools(mon)`. These
effects read/write that state directly, so they scale and discard for real:
    * "N damage for each Tool …"    -> N × ctx.count_tools(side)
    * "… if a Tool is attached, +N" -> +N only when ctx.has_tool(...) is true
    * "discard all/up-to Tools …"   -> actually clears the Tools (respecting an 'up to 2' cap)
None of these over-apply the printed damage (the class of bug we guard against): with no Tool
in play the count is 0 and the conditional bonus never triggers.

The one HAND-disruption attack (reveal + discard the opponent's Item/Tool cards) works on hand
tokens — real `('T', dict)` tokens with a `trainerType` — so it strips Items and Tools from the
opponent's hand.

Every effect returns pre-Weakness damage to the defender's Active; the engine applies
Weakness afterward.
"""
from attack_effects import effect, EffectCtx, STATUSES


# ---------------------------------------------------------------- module-level helpers
def _is_item_or_tool(tok):
    """True for a hand token that is an Item or Pokémon Tool Trainer card."""
    return tok[0] == 'T' and tok[1].get('trainerType') in ('Item', 'Tool')


# ---------------------------------------------------------------- discard tools from opponent
@effect("Before doing damage, discard all Pokémon Tools from your opponent's Active Pokémon.")
def _discard_all_tools_opp_active(ctx):
    # Strip every Tool from the Defending Active, THEN deal the printed damage.
    ctx.discard_tools(ctx.defender)
    return ctx.base


@effect("Discard up to 2 Pokémon Tools from your opponent's Pokémon.")
def _discard_2_tools_opp(ctx):
    # Any of the opponent's Pokémon (Active + Bench); at most 2 Tools total. Pure utility (base 0).
    removed = 0
    for m in ctx.opp.all_mons():
        while m.tools and removed < 2:
            m.tools.pop()
            removed += 1
        if removed >= 2:
            break
    return ctx.base


@effect("Your opponent reveals their hand. Discard all Item cards and Pokémon Tool cards you find there.")
def _discard_opp_items_tools_hand(ctx):
    # Fully modeled: hand cards are real ('T', dict) tokens with a trainerType. Drop every
    # Item and Tool from the opponent's hand (Trainers aren't tracked in a discard pile, per the
    # engine's hand-dump routing, so they simply leave hand). Pure utility (base 0).
    ctx.opp.hand = [t for t in ctx.opp.hand if not _is_item_or_tool(t)]
    return ctx.base


# ---------------------------------------------------------------- damage scaling by tool count
@effect("This attack does 30 damage for each Pokémon Tool attached to all of your Pokémon.")
def _dmg_per_tool_mine_30(ctx):
    # "all of YOUR Pokémon" -> attacker's side only (Active + Bench).
    return 30 * ctx.count_tools('me')


@effect("This attack does 40 damage for each Pokémon Tool attached to all Pokémon.")
def _dmg_per_tool_all_40(ctx):
    # "all Pokémon" (no "your") -> every Pokémon in play, BOTH sides.
    return 40 * ctx.count_tools('all')


# ---------------------------------------------------------------- conditional bonus if a tool present
@effect("If your opponent's Active Pokémon has a Pokémon Tool attached, this attack does 80 more damage.")
def _plus_80_if_opp_tool(ctx):
    return ctx.base + (80 if ctx.has_tool(ctx.defender) else 0)


@effect("If this Pokémon has a Pokémon Tool attached, this attack does 70 more damage.")
def _plus_70_if_self_tool(ctx):
    return ctx.base + (70 if ctx.has_tool(ctx.attacker) else 0)
