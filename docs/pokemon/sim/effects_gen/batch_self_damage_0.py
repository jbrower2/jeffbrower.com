#!/usr/bin/env python3
"""Attack-effect batch: self_damage_0 — attacks that deal recoil damage to the ATTACKER
("This Pokémon also does N damage to itself"), plus one optional-recoil ("you may do 30 more,
then take 30") and one damage-counter-scaled recoil (Palafin).

Each effect returns the raw (pre-Weakness) damage to the defender's Active and applies the recoil
to the attacker via ctx.self_damage(). The engine reaps a resulting attacker self-KO afterward, so
these effects never need to handle the KO themselves — they only add the damage counters.

Conventions (matched to attack_effects.py proof batch + sibling batches / effects.py):
  - "also does N damage to itself" is UNCONDITIONAL recoil: self_damage(N), return base.
  - "for each damage counter on it" counts the attacker's OWN counters = mon.damage // 10 (identical
    to effects.eval_count's 'damage counter on this pok' rule). Counted at attack time, before the
    recoil is applied, so it never compounds on itself.
  - The "You may do 30 more damage" clause is OPTIONAL: the +30 output AND the 30 self-damage are a
    matched pair (take both or neither). The AI opts in greedily but not suicidally (see below).
"""
from attack_effects import effect, EffectCtx, STATUSES


# ---------------------------------------------------------------- module-level helpers
def _weak_mult(ctx):
    """2 if the defender is Weak to the attacker's type, else 1 (for KO-decision math only —
    the returned damage stays pre-Weakness; the engine re-applies Weakness to it)."""
    dfn = ctx.defender
    if dfn is not None and dfn.card.weakness and dfn.card.weakness == ctx.attacker.card.ptype:
        return 2
    return 1


# ================================================================ flat recoil
@effect("This Pokémon also does 40 damage to itself.")
def _self_40(ctx):
    ctx.self_damage(40)
    return ctx.base


@effect("This Pokémon also does 50 damage to itself.")
def _self_50(ctx):
    ctx.self_damage(50)
    return ctx.base


@effect("This Pokémon also does 60 damage to itself.")
def _self_60(ctx):
    ctx.self_damage(60)
    return ctx.base


@effect("This Pokémon also does 70 damage to itself.")
def _self_70(ctx):
    ctx.self_damage(70)
    return ctx.base


# ================================================================ counter-scaled recoil
@effect("This Pokémon also does 10 damage to itself for each damage counter on it.")
def _self_10_per_counter(ctx):
    # Palafin (SV05, base 130). Recoil = 10 × (damage counters already on the attacker).
    # A damage counter is 10 HP, so #counters = attacker.damage // 10. Counted BEFORE the recoil
    # lands, so the attack does NOT feed its own recoil.
    counters = ctx.attacker.damage // 10
    ctx.self_damage(10 * counters)
    return ctx.base


# ================================================================ optional recoil ("you may")
@effect("You may do 30 more damage. If you do, this Pokémon also does 30 damage to itself.")
def _gurdurr_may_30(ctx):
    # Gurdurr (SV06, base 50). The +30 output and the 30 self-damage are one package: take both or
    # neither. Opt in greedily but not pointlessly-suicidally:
    #   - skip if the base already KOs the defender (the extra 30 is wasted overkill + free recoil);
    #   - otherwise take it when the +30 secures the KO OR the attacker survives the recoil.
    dfn = ctx.defender
    base = ctx.base
    mult = _weak_mult(ctx)
    if dfn is not None and base * mult >= dfn.hp_left:
        return base                                    # already lethal — no reason to self-damage
    full_kos = dfn is not None and (base + 30) * mult >= dfn.hp_left
    survives = ctx.attacker.hp_left > 30               # 30 recoil leaves the attacker in play
    if full_kos or survives:
        ctx.self_damage(30)                            # commit: +30 output, +30 recoil
        return base + 30
    return base                                        # would self-KO without landing a KO — decline
