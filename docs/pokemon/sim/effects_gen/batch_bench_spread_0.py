#!/usr/bin/env python3
"""Batch: bench_spread_0 — bench snipe / spread, "each Pokémon" AoE, own-bench self-spread,
bench-condition damage bonuses, energy- and damage-counter relocation, and a few put-onto-bench
/ shuffle-away disruption attacks. Each effect is registered by its exact normalized attack text.

Return-value contract (matches attack_effects.resolve + the sibling bench_spread batch):
  * The int returned is damage to the opponent's ACTIVE only; the engine applies Weakness after.
  * Damage dealt to BENCHED Pokémon and relocated damage COUNTERS bypass Weakness/Resistance, so
    they are written straight onto the target's `.damage` and are NOT part of the return value.
  * A "does N to 1/2/each of your opponent's Pokémon" clause with no printed base returns the
    Active's share (0 if only Bench targets were chosen).
"""
from attack_effects import effect, EffectCtx, STATUSES
from engine import Mon


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


def _snipe_two_opp(ctx, amount):
    """'does <amount> damage to 2 of your opponent's Pokémon' — 2 distinct targets among the Active
    and Bench. Weakness applies only to an Active hit (returned); Bench hits go straight to `.damage`.
    Ranks KO-able targets first, then Pokémon ex (2 prizes), then lowest HP remaining."""
    opp = ctx.opp
    ap = ctx.attacker.card.ptype

    def eff(w, m):
        if w == 'active' and m.card.weakness and m.card.weakness == ap:
            return amount * 2
        return amount

    cands = ([('active', opp.active)] if opp.active is not None else [])
    cands += [('bench', b) for b in opp.bench]
    cands.sort(key=lambda wm: (eff(*wm) < wm[1].hp_left, not wm[1].card.is_ex, wm[1].hp_left))
    ret = 0
    for w, m in cands[:2]:
        if w == 'active':
            ret += amount          # engine applies Weakness to the returned Active damage
        else:
            m.damage += amount
    return ret


def _is_tera(card):
    """Whether a card is a Tera Pokémon. The printings dataset does not capture the Tera subtype
    (it appears only inside attack/ability text, never as a card marker), so this cannot be detected
    and is treated as absent — the conditional bonus stays OFF rather than firing unconditionally.
    Reads a card attribute if the data model ever gains one."""
    return bool(getattr(card, 'tera', False))


# ================================================================ opponent-bench snipe (base + bench)
@effect("This attack also does 30 damage to 1 of your opponent's Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _also_opp_bench_30(ctx):
    _damage_opp_bench(ctx, 30, 1)
    return ctx.base


@effect("This attack also does 20 damage to 1 of your opponent's Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _also_opp_bench_20(ctx):
    _damage_opp_bench(ctx, 20, 1)
    return ctx.base


@effect("This attack also does 10 damage to each of your opponent's Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _also_opp_bench_10_each(ctx):
    ctx.bench_damage(10, side='opp', which='all')
    return ctx.base


# ================================================================ "N to 1/2/each opponent Pokémon" (no printed base)
@effect("This attack does 50 damage to 1 of your opponent's Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _snipe_any_50(ctx):
    return _snipe_one_opp(ctx, 50)


@effect("This attack does 10 damage to 1 of your opponent's Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _snipe_any_10(ctx):
    return _snipe_one_opp(ctx, 10)


@effect("This attack does 50 damage to 2 of your opponent's Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _snipe_any_50x2(ctx):
    return _snipe_two_opp(ctx, 50)


@effect("This attack does 30 damage to each of your opponent's Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _all_opp_30(ctx):
    # 30 to every opponent Pokémon: Bench directly (no W&R), Active via the return (Weakness applies).
    ctx.bench_damage(30, side='opp', which='all')
    return 30


@effect("This attack does 50 damage to each Pokémon that has any damage counters on it (both yours and your opponent's), except for this Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _50_each_damaged_except_self(ctx):
    # 50 to every ALREADY-damaged Pokémon on both sides, except the attacker itself.
    for m in ctx.me.all_mons():
        if m is not ctx.attacker and m.damage > 0:
            m.damage += 50
    for m in ctx.opp.bench:
        if m.damage > 0:
            m.damage += 50
    if ctx.opp.active is not None and ctx.opp.active.damage > 0:
        return 50                              # opponent's Active is damaged -> hit it (Weakness applies)
    return 0


# ================================================================ own-bench / both-bench self-spread (base + bench)
@effect("This attack also does 30 damage to each of your Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _also_own_bench_30_each(ctx):
    ctx.bench_damage(30, side='me', which='all')
    return ctx.base


@effect("This attack also does 10 damage to each of your Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _also_own_bench_10_each(ctx):
    ctx.bench_damage(10, side='me', which='all')
    return ctx.base


@effect("This attack also does 10 damage to 1 of your Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _also_own_bench_10_one(ctx):
    # Self-inflicted on one of OUR Benched Pokémon; pick the sturdiest (most HP left) to minimize risk.
    if ctx.me.bench:
        max(ctx.me.bench, key=lambda m: m.hp_left).damage += 10
    return ctx.base


@effect("This attack also does 20 damage to each Benched Pokémon (both yours and your opponent's). (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _also_all_bench_20(ctx):
    ctx.bench_damage(20, side='opp', which='all')
    ctx.bench_damage(20, side='me', which='all')
    return ctx.base


# ================================================================ ×-scaling off bench count / bench damage counters
@effect("This attack does 20 damage for each of your Benched Pokémon.")
def _20x_own_bench_count(ctx):
    return ctx.base * len(ctx.me.bench)


@effect("This attack does 10 damage for each damage counter on all of your Benched Cynthia's Pokémon. This attack's damage isn't affected by Weakness.")
def _10x_cynthia_bench_counters(ctx):
    # 10× the total damage counters on your benched Cynthia's Pokémon, dealt to the opponent's Active.
    # "Isn't affected by Weakness" can't be signalled through the int return (the engine would double
    # it on Weakness), so — matching batch_misc_1's _snipe_70_no_wr convention — write the damage
    # straight onto the Active's .damage and return 0.
    counters = sum(m.damage // 10 for m in ctx.me.bench if m.card.name.startswith("Cynthia's"))
    ctx.defender.damage += ctx.base * counters
    return 0


@effect("This attack does 40 damage for each damage counter on all of your Benched Rattata.")
def _40x_rattata_bench_counters(ctx):
    counters = sum(m.damage // 10 for m in ctx.me.bench if m.card.name == 'Rattata')
    return ctx.base * counters


# ================================================================ +bonus conditioned on bench contents
@effect("If you have any {M} Pokémon on your Bench, this attack does 80 more damage.")
def _plus_80_if_metal_bench(ctx):
    bonus = 80 if any(m.card.ptype == 'Metal' for m in ctx.me.bench) else 0
    return ctx.base + bonus


@effect("If a Pokémon that has \"Nidoking\" in its name is on your Bench, this attack does 120 more damage.")
def _plus_120_if_nidoking_bench(ctx):
    bonus = 120 if any('Nidoking' in m.card.name for m in ctx.me.bench) else 0
    return ctx.base + bonus


@effect("If any of your Benched Cubone have any damage counters on them, this attack does 120 more damage.")
def _plus_120_if_cubone_damaged(ctx):
    bonus = 120 if any(m.card.name == 'Cubone' and m.damage > 0 for m in ctx.me.bench) else 0
    return ctx.base + bonus


@effect("If you have any Tera Pokémon on your Bench, this attack does 100 more damage.")
def _plus_100_if_tera_bench(ctx):
    bonus = 100 if any(_is_tera(m.card) for m in ctx.me.bench) else 0
    return ctx.base + bonus


@effect("If Mightyena is on your Bench, this attack does 90 more damage.")
def _plus_90_if_mightyena_bench(ctx):
    bonus = 90 if any(m.card.name == 'Mightyena' for m in ctx.me.bench) else 0
    return ctx.base + bonus


@effect("If you have any Stage 2 {D} Pokémon on your Bench, this attack does 70 more damage.")
def _plus_70_if_stage2_dark_bench(ctx):
    bonus = 70 if any(m.card.stage == 2 and m.card.ptype == 'Darkness' for m in ctx.me.bench) else 0
    return ctx.base + bonus


@effect("If you don't have Lunatone on your Bench, this attack does nothing. This attack's damage isn't affected by Weakness or Resistance.")
def _solrock_needs_lunatone(ctx):
    # Does nothing without a benched Lunatone. The printed damage hits the Active but "isn't affected
    # by Weakness or Resistance", so — matching batch_misc_1's _snipe_70_no_wr convention — write it
    # straight onto the Active's .damage and return 0 (returning it would let the engine double it on
    # Weakness).
    if any(m.card.name == 'Lunatone' for m in ctx.me.bench):
        ctx.defender.damage += ctx.base
    return 0


# ================================================================ energy / damage-counter relocation
@effect("Move an Energy from this Pokémon to 1 of your Benched Pokémon.")
def _move_energy_to_bench(ctx):
    at = ctx.attacker
    if ctx.me.bench and at.total_energy() > 0:
        tgt = max(ctx.me.bench, key=lambda m: m.total_energy())   # feed the readiest bench attacker
        t = max(at.energy, key=lambda k: at.energy[k])            # move the attacker's most-abundant pip
        at.energy[t] -= 1
        if at.energy[t] <= 0:
            del at.energy[t]
        tgt.energy[t] += 1
    return ctx.base


@effect("Move all damage counters from 1 of your Benched Pokémon to your opponent's Active Pokémon.")
def _move_counters_bench_to_opp_active(ctx):
    # Relocate ALL counters from our most-damaged Benched Pokémon onto the opponent's Active.
    # Counter placement (no Weakness/Resistance, not attack damage) -> written straight to .damage.
    if ctx.opp.active is None:
        return 0
    srcs = [m for m in ctx.me.bench if m.damage > 0]
    if srcs:
        src = max(srcs, key=lambda m: m.damage)
        ctx.opp.active.damage += src.damage
        src.damage = 0
    return 0


@effect("You may move any number of damage counters from your opponent's Benched Pokémon to their Active Pokémon.")
def _gather_opp_bench_counters(ctx):
    # Pile ALL of the opponent's Bench counters onto their Active (the target we keep attacking).
    opp = ctx.opp
    if opp.active is not None:
        moved = 0
        for m in opp.bench:
            moved += m.damage
            m.damage = 0
        opp.active.damage += moved
    return 0


# ================================================================ put-onto-bench / shuffle-away disruption
@effect("Put up to 3 Duskull from your discard pile onto your Bench.")
def _put_duskull_from_discard(ctx):
    me = ctx.me
    moved = 0
    for tok in list(me.discard):
        if moved >= 3 or len(me.bench) >= 5:
            break
        if tok[0] == 'P' and tok[1].name == 'Duskull':
            me.bench.append(Mon(tok[1]))
            me.discard.remove(tok)
            moved += 1
    return 0


@effect("Your opponent reveals their hand. Put up to 2 Basic Pokémon you find there onto your opponent's Bench.")
def _bench_opp_basics_from_hand(ctx):
    opp = ctx.opp
    moved = 0
    for tok in list(opp.hand):
        if moved >= 2 or len(opp.bench) >= 5:
            break
        if tok[0] == 'P' and tok[1].stage == 0:
            opp.bench.append(Mon(tok[1]))
            opp.hand.remove(tok)
            moved += 1
    return 0


@effect("Choose 3 of your opponent's Benched Pokémon. If you do, shuffle all of your opponent's Benched Pokémon that you didn't choose, and all cards attached to those Pokémon, into their deck.")
def _shiftry_shuffle_bench(ctx):
    # Keep (choose) the 3 LEAST-developed Benched Pokémon; shuffle the biggest threats — and their
    # attached basic Energy — back into the opponent's deck. Nothing to do with <=3 on the Bench.
    opp = ctx.opp
    if len(opp.bench) <= 3:
        return 0
    ranked = sorted(opp.bench, key=lambda m: (m.total_energy(), m.card.stage, m.card.hp))
    for m in ranked[3:]:
        opp.deck.append(('P', m.card))
        for t, n in list(m.energy.items()):
            if t not in ('Wild', 'Colorless'):        # basic Energy returns as ('E', type); pseudo-types skipped
                for _ in range(n):
                    opp.deck.append(('E', t))
        opp.bench.remove(m)
    ctx.rng.shuffle(opp.deck)
    return 0
