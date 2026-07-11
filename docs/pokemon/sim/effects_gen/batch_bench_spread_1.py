#!/usr/bin/env python3
"""Batch: bench_spread_1 — bench snipe / spread, self-bench splash, energy relocation, damage-counter
placement, shuffle/pick-up to deck-or-hand, and Benched-Pokémon conditional/counting bonuses.

Every effect returns the int damage to the opponent's ACTIVE (the engine applies Weakness after).
Damage dealt to BENCHED Pokémon, and damage COUNTERS placed/doubled by an attack, bypass
Weakness/Resistance — those are written straight onto the target's `.damage` and are NOT part of the
return value. Helper names/behaviour mirror effects_gen/batch_bench_spread_2 for a consistent family.
"""
from collections import Counter
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


def _is_v(card):
    """Pokémon V family (V / VMAX / VSTAR). None are in the current H/I/J pool, but keep the check
    faithful to the card text alongside the `is_ex` test."""
    n = card.name
    return n.endswith(' V') or n.endswith(' VMAX') or n.endswith(' VSTAR')


def _shuffle_mon_into_deck(player, mon, rng):
    """Move a Pokémon and its attached basic Energy from play into its owner's deck, then shuffle.
    (Special-energy pseudo-types Wild/Colorless aren't basic-energy tokens, so they leave with the
    Pokémon rather than being re-created as deck cards.)"""
    for t, n in list(mon.energy.items()):
        if t not in ('Wild', 'Colorless'):
            player.deck.extend([('E', t)] * n)
    player.deck.append(('P', mon.card))
    rng.shuffle(player.deck)


def _pickup_mon_to_hand(player, mon):
    """Move a Pokémon and its attached basic Energy from play into its owner's hand."""
    for t, n in list(mon.energy.items()):
        if t not in ('Wild', 'Colorless'):
            player.hand.extend([('E', t)] * n)
    player.hand.append(('P', mon.card))


def _move_one_energy(src, dest):
    """Move a single Energy pip from `src` to `dest` (prefer a basic-typed pip). Returns True if moved."""
    order = ([t for t in src.energy if t not in ('Wild', 'Colorless') and src.energy[t] > 0]
             + [t for t in src.energy if t in ('Wild', 'Colorless') and src.energy[t] > 0])
    if not order:
        return False
    t = order[0]
    src.energy[t] -= 1
    if src.energy[t] <= 0:
        del src.energy[t]
    dest.energy[t] += 1
    return True


# ---------------------------------------------------------------- effects

@effect("This attack also does 40 damage to 1 of your Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _also_self_bench_40(ctx):
    # Manectric: base to the Active, PLUS 40 to ONE of YOUR OWN Benched Pokémon (self-inflicted, no W&R).
    # Pick the sturdiest own bench mon (highest HP remaining) so the splash is least likely to self-KO.
    if ctx.me.bench:
        tgt = max(ctx.me.bench, key=lambda m: m.hp_left)
        tgt.damage += 40
    return ctx.base


@effect("If Illumise is on your Bench, this attack does 60 more damage.")
def _plus_60_if_illumise(ctx):
    bonus = 60 if any(m.card.name == 'Illumise' for m in ctx.me.bench) else 0
    return ctx.base + bonus


@effect("You can use this attack only if you go second, and only during your first turn. Shuffle 1 of your opponent's Benched Pokémon and all attached cards into their deck.")
def _go_second_shuffle_opp_bench(ctx):
    # Usage restriction: only the player going SECOND, on their FIRST turn — which is uniquely global
    # turn 1 (turn 0 = first player's first turn; only player-index-1 acts on turn 1). Otherwise the
    # attack can't be used -> do nothing. Base is 0 either way.
    if ctx.game.turn == 1 and ctx.opp.bench:
        # Disrupt the opponent's best-developed benched Pokémon (most Energy, then bulkiest).
        tgt = max(ctx.opp.bench, key=lambda m: (m.total_energy(), m.card.hp))
        ctx.opp.bench.remove(tgt)
        _shuffle_mon_into_deck(ctx.opp, tgt, ctx.rng)
    return 0


@effect("This attack also does 30 damage to 2 of your opponent's Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _also_opp_bench_30x2(ctx):
    # Cynthia's Milotic: base to the Active, PLUS 30 to two of the opponent's Benched Pokémon (no W&R).
    _damage_opp_bench(ctx, 30, 2)
    return ctx.base


@effect("Move all Energy from this Pokémon to 1 of your Benched Pokémon.")
def _move_all_energy_to_bench(ctx):
    # Castform Sunny Form: base damage, then dump ALL of the attacker's Energy onto ONE Benched
    # Pokémon (consolidate onto the readiest one). Special-energy pips + rider names move together.
    if ctx.me.bench and ctx.attacker.total_energy() > 0:
        tgt = max(ctx.me.bench, key=lambda m: m.total_energy())
        for t, n in list(ctx.attacker.energy.items()):
            tgt.energy[t] += n
        ctx.attacker.energy.clear()
        if ctx.attacker.special:
            tgt.special.extend(ctx.attacker.special)
            ctx.attacker.special.clear()
    return ctx.base


@effect("This attack does 30 damage to 1 of your opponent's Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _snipe_any_30(ctx):
    # Kecleon: no printed base; 30 to any 1 opponent Pokémon (Active or Bench, player's choice).
    return _snipe_one_opp(ctx, 30)


@effect("Shuffle 1 of your Benched Pokémon and all attached cards into your deck.")
def _shuffle_own_bench_into_deck(ctx):
    # Chimecho: no damage; recycle one of YOUR OWN Benched Pokémon (with its Energy) back into the
    # deck. Choose the most-damaged bench mon (shuffling it away "resets" it to a fresh copy in deck).
    if ctx.me.bench:
        tgt = max(ctx.me.bench, key=lambda m: m.damage)
        ctx.me.bench.remove(tgt)
        _shuffle_mon_into_deck(ctx.me, tgt, ctx.rng)
    return 0


@effect("If this Pokémon has at least 2 extra Energy attached (in addition to this attack's cost), this attack also does 120 damage to 1 of your opponent's Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _extra_energy_bench_120(ctx):
    # Deoxys: base to the Active; if the attacker has >= 2 Energy beyond this attack's own cost,
    # ALSO 120 to one Benched opponent (no W&R). Cost length comes from the attack def.
    cost = ctx.attack.get('cost') or ''
    if ctx.attacker.total_energy() - len(cost) >= 2:
        _damage_opp_bench(ctx, 120, 1)
    return ctx.base


@effect("This attack does 70 damage to 1 of your opponent's Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _bench_snipe_70(ctx):
    # Prinplup: no damage to the Active (printed base 0); 70 to one Benched opponent (no W&R).
    _damage_opp_bench(ctx, 70, 1)
    return 0


@effect("This attack does 50 damage for each of your Drifloon and Drifblim in play. This attack also does 30 damage to each of your Drifloon and Drifblim. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _drifblim_swarm(ctx):
    # Drifblim: damage to the Active = 50 x (your Drifloon + Drifblim in play, INCLUDING this attacker).
    # Then 30 to EACH of those same Pokémon (self-inflicted; the attacker takes 30 too).
    mine = [m for m in ctx.me.all_mons() if m.card.name in ('Drifloon', 'Drifblim')]
    for m in mine:
        m.damage += 30
    return 50 * len(mine)


@effect("This attack does 50 damage to 1 of your opponent's Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _bench_snipe_50(ctx):
    # Lopunny: no damage to the Active (printed base 0); 50 to one Benched opponent (no W&R).
    _damage_opp_bench(ctx, 50, 1)
    return 0


@effect("This attack also does 40 damage to each Benched Pokémon that has any damage counters on it (both yours and your opponent's). (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _also_40_each_damaged_bench(ctx):
    # Hippowdon: base to the Active, PLUS 40 to EVERY already-damaged Benched Pokémon on BOTH sides.
    for m in ctx.me.bench + ctx.opp.bench:
        if m.damage > 0:
            m.damage += 40
    return ctx.base


@effect("Put 2 damage counters on each of your opponent's Pokémon.")
def _counters_2_each_opp(ctx):
    # Uxie: place 2 damage counters (= 20) on EACH opponent Pokémon (Active + Bench). Counter
    # placement bypasses Weakness/Resistance -> written straight onto .damage; the attack deals no
    # HP damage of its own, so return 0.
    for m in ctx.opp.all_mons():
        m.damage += 20
    return 0


@effect("If you don't have Uxie and Azelf on your Bench, this attack does nothing.")
def _needs_uxie_azelf(ctx):
    # Mesprit: full base only if BOTH Uxie AND Azelf are on your Bench; otherwise nothing.
    have_uxie = any(m.card.name == 'Uxie' for m in ctx.me.bench)
    have_azelf = any(m.card.name == 'Azelf' for m in ctx.me.bench)
    return ctx.base if (have_uxie and have_azelf) else 0


@effect("This attack does 60 damage to 1 of your opponent's Benched Pokémon ex or Benched Pokémon V. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _bench_snipe_60_exv(ctx):
    # Shaymin: no damage to the Active; 60 to one Benched opponent that is a Pokémon ex or Pokémon V
    # (no W&R). If no legal (ex/V) Benched target exists, the attack does nothing.
    cand = [b for b in ctx.opp.bench if b.card.is_ex or _is_v(b.card)]
    if cand:
        tgt = min(cand, key=lambda b: b.hp_left)   # secure the readiest KO among ex/V
        tgt.damage += 60
    return 0


@effect("This attack does 20 damage for each damage counter on all of your Benched {F} Pokémon.")
def _20x_bench_fighting_counters(ctx):
    # Gigalith: 20 x (total damage COUNTERS across all your Benched Fighting-type Pokémon).
    # A damage counter is 10 HP, so counters on a mon = damage // 10.
    counters = sum(m.damage // 10 for m in ctx.me.bench if m.card.ptype == 'Fighting')
    return 20 * counters


@effect("Put 1 of your Benched Pokémon and all attached cards into your hand.")
def _pickup_own_bench_to_hand(ctx):
    # Swoobat: no damage; pick up one of YOUR OWN Benched Pokémon (with its Energy) into your hand.
    # Choose the most-damaged (rescuing it resets its damage when replayed).
    if ctx.me.bench:
        tgt = max(ctx.me.bench, key=lambda m: m.damage)
        ctx.me.bench.remove(tgt)
        _pickup_mon_to_hand(ctx.me, tgt)
    return 0


@effect("This attack does 20 more damage for each of your Benched Pokémon.")
def _plus_20_per_bench(ctx):
    # Cinccino: base + 20 for each of YOUR Benched Pokémon.
    return ctx.base + 20 * len(ctx.me.bench)


@effect("Look at the top 8 cards of your deck. You may put any number of Pokémon you find there onto your Bench. Shuffle the other cards back into your deck.")
def _dig8_bench_pokemon(ctx):
    # Reuniclus (SV05): reveal the top 8, bench any Pokémon found (up to the 5-Bench cap), shuffle the
    # rest back. The deck's END is its top (engine draws via deck.pop()), so scan the last 8 tokens.
    me = ctx.me
    top = me.deck[-8:]
    for tok in reversed(top):                      # topmost first
        if len(me.bench) >= 5:
            break
        if tok[0] == 'P':
            me.deck.remove(tok)
            me.bench.append(Mon(tok[1]))
    ctx.rng.shuffle(me.deck)
    return 0


@effect("Double the number of damage counters on each of your opponent's Pokémon.")
def _double_opp_counters(ctx):
    # N's Vanilluxe: double the damage counters on EACH opponent Pokémon (Active + Bench). Damage is
    # tracked in 10-HP counters, so doubling counters == doubling .damage. Counter manipulation, no
    # W&R; the attack deals no HP damage of its own -> return 0.
    for m in ctx.opp.all_mons():
        m.damage *= 2
    return 0


@effect("This attack also does 10 damage to each Benched Pokémon (both yours and your opponent's). (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _also_10_each_bench_both(ctx):
    # Emolga: base to the Active, PLUS 10 to EVERY Benched Pokémon on BOTH sides (no W&R).
    for m in ctx.me.bench + ctx.opp.bench:
        m.damage += 10
    return ctx.base


@effect("This attack does 20 damage to 1 of your opponent's Pokémon for each Energy attached to this Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _snipe_any_20_per_energy(ctx):
    # Ferrothorn: 20 x (Energy attached to the attacker), directed at any 1 opponent Pokémon
    # (Active or Bench, player's choice; W&R only if it hits the Active).
    return _snipe_one_opp(ctx, 20 * ctx.attacker.total_energy())


@effect("If Durant is on your Bench, this attack does 20 more damage.")
def _plus_20_if_durant(ctx):
    bonus = 20 if any(m.card.name == 'Durant' for m in ctx.me.bench) else 0
    return ctx.base + bonus


@effect("If any of your Benched Pancham have any damage counters on them, this attack does 120 more damage.")
def _plus_120_if_pancham_damaged(ctx):
    bonus = 120 if any(m.card.name == 'Pancham' and m.damage > 0 for m in ctx.me.bench) else 0
    return ctx.base + bonus


@effect("You may move an Energy from your opponent's Active Pokémon to 1 of their Benched Pokémon.")
def _move_opp_active_energy_to_bench(ctx):
    # Meowstic: base to the Active; optionally relocate one Energy off the opponent's Active onto one
    # of their Benched Pokémon (disruption — take it off the attacker). Park it on their least-developed
    # bench mon.
    if ctx.opp.bench and ctx.opp.active is not None and ctx.opp.active.total_energy() > 0:
        dest = min(ctx.opp.bench, key=lambda m: m.total_energy())
        _move_one_energy(ctx.opp.active, dest)
    return ctx.base


@effect("If your Benched Pokémon have any damage counters on them, this attack does 60 more damage.")
def _plus_60_if_bench_damaged(ctx):
    bonus = 60 if any(m.damage > 0 for m in ctx.me.bench) else 0
    return ctx.base + bonus


@effect("Put 2 damage counters on each of your opponent's Pokémon that has any damage counters on it.")
def _counters_2_each_already_damaged_opp(ctx):
    # Yveltal: place 2 damage counters (= 20) on each opponent Pokémon that ALREADY has damage.
    # Counter placement (no W&R); no HP damage of its own -> return 0.
    for m in ctx.opp.all_mons():
        if m.damage > 0:
            m.damage += 20
    return 0


@effect("This attack does 80 more damage for each of your Benched Charjabug.")
def _plus_80_per_bench_charjabug(ctx):
    # Vikavolt: base + 80 for EACH Charjabug on your Bench.
    n = sum(1 for m in ctx.me.bench if m.card.name == 'Charjabug')
    return ctx.base + 80 * n
