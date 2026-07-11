#!/usr/bin/env python3
"""Batch: heal_0 — healing attacks (self / one-of-mine / each-of-mine / typed & Ancient bench),
attach-then-heal, heal + self-can't-retreat, and a "healed this turn" damage rider.

Every effect returns the int damage to the opponent's ACTIVE (the engine applies Weakness after).
Healing removes damage counters from OUR OWN Pokémon and is NOT part of the return value; it is done
through `ctx.heal(n, mon=...)`, which clamps at 0 (never negative damage).
"""
from attack_effects import effect, EffectCtx, STATUSES


# ---------------------------------------------------------------- helpers
# Ancient-trait Pokémon in the pool. The card model carries no Ancient subtype, so this mirrors the
# grounded name allow-list used by batch_bench_spread_2 (conservative: only clearly-Ancient paradox
# Pokémon). A false positive would heal a Pokémon it shouldn't.
ANCIENT = {
    'Great Tusk', 'Great Tusk ex', 'Scream Tail', 'Scream Tail ex', 'Brute Bonnet', 'Flutter Mane',
    'Slither Wing', 'Sandy Shocks', 'Sandy Shocks ex', 'Roaring Moon', 'Roaring Moon ex',
    'Walking Wake', 'Walking Wake ex', 'Gouging Fire', 'Gouging Fire ex',
    'Raging Bolt', 'Raging Bolt ex',
}


def _heal_one_of_mine(ctx, n, pool=None, pred=None):
    """Heal `n` from a single one of OUR Pokémon (player's choice -> the most-damaged eligible one,
    which maximizes the heal). `pool` defaults to all of our Pokémon; `pred` optionally filters
    (e.g. a benched {P} or Ancient Pokémon). No-op if nothing damaged/eligible. Returns the target."""
    mons = pool if pool is not None else ctx.me.all_mons()
    cands = [m for m in mons if m.damage > 0 and (pred is None or pred(m))]
    if not cands:
        return None
    tgt = max(cands, key=lambda m: m.damage)
    ctx.heal(n, mon=tgt)
    return tgt


def _self_cant_retreat(ctx):
    """Mark the attacker as unable to retreat next turn (turn-stamped marker, mirroring the
    CantRetreat convention set by EffectCtx.defender_cant_retreat but on our OWN Active)."""
    ctx.attacker.status['CantRetreat'] = ctx.game.turn


# ---------------------------------------------------------------- self-heal (fixed amount)

@effect("Heal 10 damage from this Pokémon.")
def _heal_self_10(ctx):
    ctx.heal(10)
    return ctx.base


@effect("Heal 40 damage from this Pokémon.")
def _heal_self_40(ctx):
    ctx.heal(40)
    return ctx.base


@effect("Heal from this Pokémon the same amount of damage you did to your opponent's Active Pokémon.")
def _heal_same_as_dealt(ctx):
    # These attacks deal a fixed printed amount (10/30/50). "The same amount of damage you did" = the
    # damage this attack does, i.e. ctx.base (the engine applies Weakness/Resistance to the returned
    # value afterward, outside this layer). Heal that off ourselves; return the damage to the Active.
    ctx.heal(ctx.base)
    return ctx.base


# ---------------------------------------------------------------- heal 1 of your Pokémon

@effect("Heal 30 damage from 1 of your Pokémon.")
def _heal_one_30(ctx):
    _heal_one_of_mine(ctx, 30)
    return ctx.base


@effect("Heal 40 damage from 1 of your Pokémon.")
def _heal_one_40(ctx):
    _heal_one_of_mine(ctx, 40)
    return ctx.base


@effect("Heal 120 damage from 1 of your Benched {P} Pokémon.")
def _heal_bench_psychic_120(ctx):
    _heal_one_of_mine(ctx, 120, pool=ctx.me.bench, pred=lambda m: m.card.ptype == 'Psychic')
    return ctx.base


@effect("Heal 100 damage from 1 of your Benched Ancient Pokémon.")
def _heal_bench_ancient_100(ctx):
    _heal_one_of_mine(ctx, 100, pool=ctx.me.bench, pred=lambda m: m.card.name in ANCIENT)
    return ctx.base


# ---------------------------------------------------------------- heal each of your Pokémon

@effect("Heal 10 damage from each of your Pokémon.")
def _heal_each_10(ctx):
    for m in ctx.me.all_mons():
        ctx.heal(10, mon=m)
    return ctx.base


@effect("Heal 100 damage from each of your Basic Pokémon.")
def _heal_each_basic_100(ctx):
    for m in ctx.me.all_mons():
        if m.card.stage == 0:
            ctx.heal(100, mon=m)
    return ctx.base


# ---------------------------------------------------------------- attach energy, then heal

@effect("Attach a Basic {G} Energy card from your hand to 1 of your Benched Pokémon. If you do, heal all damage from that Pokémon.")
def _leafeon_attach_g_heal_all(ctx):
    # Requires a basic Grass Energy in hand AND a Benched Pokémon. "If you do" -> the heal is gated on
    # the attach happening. We attach to (and full-heal) the most-damaged Benched Pokémon for max value.
    tok = next((t for t in ctx.me.hand if t[0] == 'E' and t[1] == 'Grass'), None)
    if tok is not None and ctx.me.bench:
        tgt = max(ctx.me.bench, key=lambda m: m.damage)
        tgt.energy['Grass'] += 1
        ctx.me.hand.remove(tok)
        tgt.damage = 0                       # heal ALL damage from that Pokémon
    return ctx.base


@effect("Attach an Energy card from your hand to this Pokémon. If you do, heal 60 damage from this Pokémon.")
def _snorlax_attach_heal_60(ctx):
    # Requires an Energy card in hand (basic-energy token). "If you do" -> heal is gated on the attach.
    tok = next((t for t in ctx.me.hand if t[0] == 'E'), None)
    if tok is not None:
        ctx.attacker.energy[tok[1]] += 1
        ctx.me.hand.remove(tok)
        ctx.heal(60)
    return ctx.base


# ---------------------------------------------------------------- heal + self can't-retreat

@effect("Heal 50 damage from this Pokémon. During your next turn, this Pokémon can't retreat.")
def _heal_self_50_no_retreat(ctx):
    ctx.heal(50)
    _self_cant_retreat(ctx)
    return ctx.base


@effect("Heal 60 damage from this Pokémon. During your next turn, this Pokémon can't retreat.")
def _heal_self_60_no_retreat(ctx):
    ctx.heal(60)
    _self_cant_retreat(ctx)
    return ctx.base


# ---------------------------------------------------------------- healed-this-turn rider

@effect("If this Pokémon was healed during this turn, this attack does 100 more damage.")
def _plus_100_if_healed(ctx):
    # +100 only if the attacker was healed earlier this turn. The engine does not (yet) track a
    # per-turn heal flag, so this reads a conventional `healed_this_turn` marker and stays at base
    # otherwise — a conservative under-count, never an unconditional bonus.
    bonus = 100 if getattr(ctx.attacker, 'healed_this_turn', False) else 0
    return ctx.base + bonus
