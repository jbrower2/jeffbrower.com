#!/usr/bin/env python3
"""Batch: bench_spread_2 — bench snipe / spread + energy-move-to-bench + damage-counter relocation.

Every effect returns the int damage to the opponent's ACTIVE (the engine applies Weakness after).
Damage dealt to BENCHED Pokémon and relocated damage COUNTERS bypass Weakness/Resistance, so those
are written straight onto the target's `.damage` and are NOT part of the return value.
"""
from attack_effects import effect, EffectCtx, STATUSES


# ---------------------------------------------------------------- helpers
def _damage_opp_bench(ctx, amount, count):
    """Apply `amount` to up to `count` of the opponent's Benched Pokémon (no Weakness/Resistance).
    Targets the lowest-HP-remaining Benched Pokémon first (KO-oriented), mirroring
    effects.apply_spread's target selection. Returns the list of Benched Mons hit."""
    targets = sorted(ctx.opp.bench, key=lambda b: b.hp_left)[:count]
    for b in targets:
        b.damage += amount
    return targets


def _snipe_one_opp(ctx, amount):
    """'does <amount> damage to 1 of your opponent's Pokémon' — the player picks the Active OR any
    one Benched Pokémon (Weakness/Resistance apply only if the target is the Active). Chooses the
    readiest KO. A Benched hit is written straight onto `.damage` and returns 0; an Active hit is
    returned so the engine can apply Weakness."""
    opp = ctx.opp
    ap = ctx.attacker.card.ptype

    def active_dmg(a):
        d = amount
        if a.card.weakness and a.card.weakness == ap:
            d *= 2
        return d

    active = opp.active
    active_kos = active is not None and active_dmg(active) >= active.hp_left
    ko_bench = [b for b in opp.bench if amount >= b.hp_left]
    # 1) a Benched KO the Active hit can't achieve -> snipe it (ex first, then lowest HP)
    if ko_bench and not active_kos:
        tgt = min(ko_bench, key=lambda b: (not b.card.is_ex, b.hp_left))
        tgt.damage += amount
        return 0
    # 2) KO the Active if we can
    if active_kos:
        return amount
    # 3) no KO available: snipe the most valuable Benched threat, else chip the Active
    if opp.bench:
        tgt = min(opp.bench, key=lambda b: (not b.card.is_ex, b.hp_left))
        tgt.damage += amount
        return 0
    return amount if active is not None else 0


# Ancient-trait Pokémon in the pool. The card model doesn't carry the Ancient subtype (it isn't in the
# printing meta — only some attack/ability *text* mentions "Ancient"), so this is a grounded name
# allow-list of the paradox-past ("Ancient") species. Every printing of a paradox-past species carries
# the Ancient trait, so listing both the base and the `ex` form by name is safe. Koraidon/Miraidon are
# deliberately EXCLUDED: they are box legendaries with BOTH Ancient prints (e.g. SV08 Koraidon, whose
# own attack references "your other Ancient Pokémon") and non-Ancient prints (e.g. the SV05 Dragon
# Koraidon), and a name-keyed list can't tell those printings apart — including them would falsely tag
# the non-Ancient print. (`Great Tusk ex` / `Roaring Moon ex` / `Sandy Shocks ex` are listed for
# completeness but have no printing in the current pool, so they simply never match.)
ANCIENT = {
    'Great Tusk', 'Great Tusk ex', 'Scream Tail', 'Scream Tail ex', 'Brute Bonnet', 'Flutter Mane',
    'Slither Wing', 'Sandy Shocks', 'Sandy Shocks ex', 'Roaring Moon', 'Roaring Moon ex',
    'Walking Wake', 'Walking Wake ex', 'Gouging Fire', 'Gouging Fire ex',
    'Raging Bolt', 'Raging Bolt ex',
}


# ---------------------------------------------------------------- effects

@effect("This attack does 40 damage to 1 of your opponent's Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _bench_snipe_40(ctx):
    # No damage to the Active (printed base is 0); 40 to one Benched opponent (no W&R).
    _damage_opp_bench(ctx, 40, 1)
    return 0


@effect("This attack does 40 damage to 1 of your opponent's Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _snipe_any_40(ctx):
    # No printed base; 40 to any 1 opponent Pokémon (Active or Bench, player's choice).
    return _snipe_one_opp(ctx, 40)


@effect("This attack also does 50 damage to 1 of your opponent's Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _also_bench_snipe_50(ctx):
    # Base damage to the Active, PLUS 50 to one Benched opponent (no W&R).
    _damage_opp_bench(ctx, 50, 1)
    return ctx.base


@effect("This attack also does 20 damage to each of your Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _also_own_bench_20_each(ctx):
    # Base damage to the Active, PLUS 20 to EACH of YOUR OWN Benched Pokémon (self-inflicted, no W&R).
    ctx.bench_damage(20, side='me', which='all')
    return ctx.base


@effect("Move a {W} Energy from this Pokémon to 1 of your Benched Pokémon.")
def _move_w_to_bench(ctx):
    # Base damage; then move one basic Water Energy off the attacker onto a Benched Pokémon of ours.
    if ctx.me.bench and ctx.attacker.energy.get('Water', 0) > 0:
        ctx.attacker.energy['Water'] -= 1
        if ctx.attacker.energy['Water'] <= 0:
            del ctx.attacker.energy['Water']
        tgt = max(ctx.me.bench, key=lambda m: m.total_energy())   # feed the readiest bench attacker
        tgt.energy['Water'] += 1
    return ctx.base


@effect("This attack does 20 damage to 1 of your opponent's Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _snipe_any_20(ctx):
    # No printed base; 20 to any 1 opponent Pokémon (Active or Bench, player's choice).
    return _snipe_one_opp(ctx, 20)


@effect("Move all Energy from this Pokémon to your Benched Pokémon in any way you like.")
def _move_all_to_bench(ctx):
    # Base damage; then dump ALL of the attacker's Energy onto a Benched Pokémon (any distribution;
    # we consolidate onto the readiest one). Special-energy pips + their rider names move together.
    if ctx.me.bench and ctx.attacker.total_energy() > 0:
        tgt = max(ctx.me.bench, key=lambda m: m.total_energy())
        for t, n in list(ctx.attacker.energy.items()):
            tgt.energy[t] += n
        ctx.attacker.energy.clear()
        if ctx.attacker.special:
            tgt.special.extend(ctx.attacker.special)
            ctx.attacker.special.clear()
    return ctx.base


@effect("If your Benched Pokémon have any damage counters on them, this attack does 80 more damage.")
def _plus_80_if_bench_damaged(ctx):
    bonus = 80 if any(m.damage > 0 for m in ctx.me.bench) else 0
    return ctx.base + bonus


@effect("Move all damage counters from 1 of your Benched Ancient Pokémon to your opponent's Active Pokémon.")
def _move_counters_ancient(ctx):
    # Relocate ALL damage counters from one of our Benched Ancient Pokémon onto the opponent's Active.
    # This is damage-counter placement (no Weakness/Resistance, not attack damage) -> applied directly
    # to the Active's .damage; the attack itself deals no HP damage, so return 0.
    if ctx.opp.active is None:
        return 0
    srcs = [m for m in ctx.me.bench if m.card.name in ANCIENT and m.damage > 0]
    if srcs:
        src = max(srcs, key=lambda m: m.damage)   # move the most counters we can
        moved = src.damage
        src.damage = 0
        ctx.opp.active.damage += moved
    return 0


@effect("If there are 3 or fewer cards in your deck, this attack also does 120 damage to 2 of your opponent's Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _mill_finisher_bench_120x2(ctx):
    # Base damage to the Active always; only when our deck is down to <=3 cards does the bench spread fire.
    if len(ctx.me.deck) <= 3:
        _damage_opp_bench(ctx, 120, 2)
    return ctx.base
