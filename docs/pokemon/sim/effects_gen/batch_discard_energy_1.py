#!/usr/bin/env python3
"""Batch: discard_energy_1 — attacks built around discarding/attaching Energy: self-energy dumps
that convert into a fixed snipe (Cramorant/Bombirdier/Armarouge), a from-hand Energy-fuel gate
(Ceruledge Infernal Slash), Special-Energy removal (Ceruledge Cursed Edge), and discard-pile Energy
recursion/acceleration (Morpeko / Grafaiai / Varoom / Poltchageist).

Return-value contract (matches attack_effects.resolve + the bench_spread batches):
  * The int returned is damage to the opponent's ACTIVE only; the engine applies Weakness after.
  * Damage dealt to a BENCHED Pokémon bypasses Weakness/Resistance and is written straight onto the
    target's `.damage` (returning 0 for the Active's share).
  * Energy moved to/from a discard pile: basic Energy lives in `player.disc_energy` (a Counter of
    types); attached Special Energy lives in a Pokémon's `.special` list and contributes pips
    (`Wild`/`Colorless`/a real type) to `.energy` per special_energy.provides().
"""
from attack_effects import effect, EffectCtx, STATUSES
from engine import Mon, L2T
import special_energy as SE


# ---------------------------------------------------------------- targeting helpers
def _snipe_one_opp(ctx, amount):
    """'does <amount> damage to 1 of your opponent's Pokémon' — the player picks the Active OR any
    one Benched Pokémon (Weakness/Resistance apply only if the target is the Active). Chooses the
    readiest KO. A Benched hit is written straight onto `.damage` and returns 0; an Active hit is
    returned so the engine can apply Weakness. Mirrors effects_gen/batch_bench_spread_*."""
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
    # 1) a Benched KO the Active hit can't achieve -> snipe it (ex first, then lowest HP left)
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


def _damage_opp_bench(ctx, amount, count):
    """Apply `amount` to up to `count` of the opponent's Benched Pokémon (no Weakness/Resistance).
    Targets the lowest-HP-remaining Benched Pokémon first (KO-oriented). Returns the Mons hit."""
    targets = sorted(ctx.opp.bench, key=lambda b: b.hp_left)[:count]
    for b in targets:
        b.damage += amount
    return targets


# ---------------------------------------------------------------- energy helpers
def _discard_all_energy_self(ctx):
    """Discard ALL Energy from the attacker: basic pips return to your discard pile (disc_energy),
    Special-Energy pseudo-pips (Wild/Colorless) and their `.special` rider names are removed."""
    at = ctx.attacker
    ctx.discard_energy_self(at.total_energy())   # routes basic->disc_energy, drops Wild/Colorless pips
    at.special.clear()                           # Special Energy cards are discarded too


def _discard_typed_energy_self(ctx, typ):
    """Discard ALL Energy of a single type `typ` (e.g. 'Fire') from the attacker. Basic pips return to
    disc_energy; any attached Special Energy that provides that exact type is removed from `.special`
    (its pip is included in the count already). Wild/Colorless-only specials (Prism, Team Rocket's)
    are NOT that specific type and stay attached."""
    at = ctx.attacker
    n = at.energy.get(typ, 0)
    if n:
        ctx.me.disc_energy[typ] += n
        del at.energy[typ]
    at.special = [s for s in at.special
                  if s not in SE.SPECIAL_ENERGY or typ not in SE.provides(s, at.card)]


def _needed_types(mon):
    """Non-colorless energy types the Mon's attack costs call for (to prefer useful attaches)."""
    types = set()
    for a in mon.card.attacks:
        for ltr in a['cost']:
            if ltr in L2T and ltr != 'C':
                types.add(L2T[ltr])
    return types


def _attach_basic_from_discard(ctx, player, n, target):
    """Move up to `n` basic Energy from `player.disc_energy` onto `target` Mon. Prefers a type the
    target's attacks actually need, else whatever basic Energy is available. Returns count moved.
    (disc_energy only holds basic Energy, so this can never move Special Energy.)"""
    if target is None:
        return 0
    need = _needed_types(target)
    moved = 0
    while moved < n:
        avail = [t for t in list(player.disc_energy) if player.disc_energy[t] > 0]
        if not avail:
            break
        pick = next((t for t in avail if t in need), avail[0])
        player.disc_energy[pick] -= 1
        if player.disc_energy[pick] <= 0:
            del player.disc_energy[pick]
        target.energy[pick] += 1
        moved += 1
    return moved


def _fund_target(ctx):
    """The one of YOUR Pokémon most worth fueling (highest-ceiling attacker), else the Active."""
    try:
        t = ctx.game.primary(ctx.me)
    except Exception:
        t = None
    return t or ctx.me.active or ctx.attacker


# ================================================================ self-discard -> fixed snipe
@effect("Discard all Energy from this Pokémon. This attack does 120 damage to 1 of your opponent's Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _spit_shot(ctx):
    # Cramorant SV06 Spit Shot: dump all of the attacker's Energy, then 120 to any 1 opponent Pokémon
    # (Active or Bench, player's choice). The 120 is fixed — independent of how much was discarded.
    _discard_all_energy_self(ctx)
    return _snipe_one_opp(ctx, 120)


@effect("Discard all Energy from this Pokémon, and this attack does 120 damage to 1 of your opponent's Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _drop_shot(ctx):
    # Bombirdier SV09 Drop Shot: same as Spit Shot (the ", and" phrasing is a distinct registry key).
    _discard_all_energy_self(ctx)
    return _snipe_one_opp(ctx, 120)


@effect("Discard all {R} Energy from this Pokémon, and this attack does 180 damage to 1 of your opponent's Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _crimson_blaster(ctx):
    # Armarouge SV08 Crimson Blaster: discard all {R} (Fire) Energy from the attacker (unconditional),
    # then 180 to ONE of the opponent's BENCHED Pokémon (no W&R). No Active hit -> return 0. If the
    # opponent has no Bench, only the discard happens.
    _discard_typed_energy_self(ctx, 'Fire')
    _damage_opp_bench(ctx, 180, 1)
    return 0


# ================================================================ from-hand fuel gate
@effect("Discard 4 Basic {R} Energy cards from your hand. If you can't discard 4 cards in this way, this attack does nothing.")
def _infernal_slash(ctx):
    # Ceruledge ME02 Infernal Slash [220]: you MUST discard 4 basic {R} (Fire) Energy from hand; if you
    # can't discard 4, the attack does nothing (and nothing is discarded).
    fire = [t for t in ctx.me.hand if t[0] == 'E' and t[1] == 'Fire']
    if len(fire) < 4:
        return 0
    for t in fire[:4]:
        ctx.me.hand.remove(t)
        ctx.me.disc_energy['Fire'] += 1
    return ctx.base


# ================================================================ special-energy removal
@effect("Discard all Special Energy from all of your opponent's Pokémon.")
def _cursed_edge(ctx):
    # Ceruledge SV08 Cursed Edge: strip every attached Special Energy from ALL of the opponent's
    # Pokémon (Active + Bench). Remove the rider name from `.special` and subtract the pips it provided
    # from `.energy` (basic Energy on those Pokémon is untouched). No damage -> return 0.
    for m in ctx.opp.all_mons():
        for name in list(m.special):
            if name in SE.SPECIAL_ENERGY:
                for typ, c in SE.provides(name, m.card).items():
                    m.energy[typ] -= c
                    if m.energy[typ] <= 0:
                        del m.energy[typ]
        m.special.clear()
    return 0


# ================================================================ discard-pile energy recursion / accel
@effect("Attach up to 2 Basic Energy cards from your discard pile to your Pokémon in any way you like.")
def _pick_and_stick(ctx):
    # Morpeko SV06 Pick and Stick: accelerate up to 2 basic Energy out of YOUR discard onto YOUR
    # Pokémon. Load the highest-ceiling attacker being developed. No damage -> return 0.
    _attach_basic_from_discard(ctx, ctx.me, 2, _fund_target(ctx))
    return ctx.base


@effect("Attach up to 3 Energy cards from your opponent's discard pile to their Pokémon in any way you like.")
def _mischievous_painting(ctx):
    # Grafaiai SV08 Mischievous Painting: attach up to 3 basic Energy from the OPPONENT's discard onto
    # THEIR Pokémon. This is the setup half of Grafaiai's combo — its other attack, Energized Graffiti,
    # does 40x per Energy on the opponent's Pokémon — so pile the Energy onto the opponent's Active
    # (the Pokémon you intend to hit). No damage of its own -> return 0.
    target = ctx.opp.active or (ctx.opp.bench[0] if ctx.opp.bench else None)
    _attach_basic_from_discard(ctx, ctx.opp, 3, target)
    return ctx.base


@effect("Attach a Basic {M} Energy card from your discard pile to this Pokémon.")
def _metal_coating(ctx):
    # Varoom SV06 Metal Coating: recover 1 basic {M} (Metal) Energy from YOUR discard onto the attacker.
    if ctx.me.disc_energy.get('Metal', 0) > 0:
        ctx.me.disc_energy['Metal'] -= 1
        if ctx.me.disc_energy['Metal'] <= 0:
            del ctx.me.disc_energy['Metal']
        ctx.attacker.energy['Metal'] += 1
    return ctx.base


@effect("Put a Basic {G} Energy card from your discard pile into your hand.")
def _tea_server(ctx):
    # Poltchageist SV06 Tea Server: return 1 basic {G} (Grass) Energy from YOUR discard to your HAND
    # (not attached).
    if ctx.me.disc_energy.get('Grass', 0) > 0:
        ctx.me.disc_energy['Grass'] -= 1
        if ctx.me.disc_energy['Grass'] <= 0:
            del ctx.me.disc_energy['Grass']
        ctx.me.hand.append(('E', 'Grass'))
    return ctx.base
