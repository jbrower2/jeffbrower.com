#!/usr/bin/env python3
"""Batch: switch_retreat_0 — forced-switch / pivot / gust attacks.

Two switch DIRECTIONS, handled distinctly:
  * "Switch THIS Pokémon with 1 of your Benched Pokémon" — the ATTACKER pivots itself to the Bench
    and promotes one of ITS OWN Benched Pokémon. The opponent's Active (the damage target) is
    unchanged, so these just `return ctx.base` and perform the self-switch as a side effect.
  * "Switch in 1 of your opponent's Benched Pokémon" — a GUST: the attacker drags one of the
    OPPONENT's Benched Pokémon (attacker's choice) into the Active Spot; the displaced Active goes to
    the Bench.  Contrast with "Switch out your opponent's Active ... (opponent chooses)" (effects 10/11)
    where the OPPONENT picks the replacement — that's `ctx.switch_defender()` / promote-readiest.

Return-value convention (matches the proof batch + bench_spread siblings): the int returned is the
damage to `ctx.defender` — the opponent's ORIGINAL Active — and the engine applies Weakness to it.
Damage that lands on a DIFFERENT target (the *new* Active after a gust) is written straight onto that
Mon's `.damage` here (Weakness applied inline vs the attacker's type) and is NOT part of the return
value, so it can never be mis-applied to the original defender.
"""
from attack_effects import effect, EffectCtx, STATUSES


# ---------------------------------------------------------------- helpers
def _switch_self(ctx, pred=None):
    """'Switch this Pokémon with 1 of your Benched Pokémon' — the attacker moves to the Bench and one of
    its OWN Benched Pokémon (optionally restricted by `pred`) becomes Active. Promotes the readiest such
    bench attacker (most energy, then HP), mirroring Player.promote()'s heuristic. Returns True iff a
    switch happened (needs an eligible Bench Pokémon)."""
    me = ctx.me
    cands = [m for m in me.bench if (pred is None or pred(m))]
    if not cands or me.active is None:
        return False
    newactive = max(cands, key=lambda m: (m.total_energy(), m.card.hp))
    old = me.active
    me.bench.remove(newactive)
    me.bench.append(old)
    me.active = newactive
    newactive.came_from_bench = True
    return True


def _gust_in(ctx, amount=0):
    """Attacker drags one of the OPPONENT's Benched Pokémon (attacker's choice) into the Active Spot;
    the displaced Active goes to the Bench. Picks the benched target most valuable to the attacker: one
    this attack's `amount` can KO (2-prize ex first, then lowest HP remaining), else simply the ex/lowest
    HP target. Returns True iff a switch happened (needs an opponent Bench Pokémon)."""
    opp = ctx.opp
    if not opp.bench:
        return False
    ap = ctx.attacker.card.ptype

    def eff_dmg(b):
        d = amount
        if d and b.card.weakness and b.card.weakness == ap:
            d *= 2
        return d

    ko = [b for b in opp.bench if amount and eff_dmg(b) >= b.hp_left]
    pool = ko or opp.bench
    tgt = min(pool, key=lambda b: (not b.card.is_ex, b.hp_left))
    opp.bench.remove(tgt)
    if opp.active is not None:
        opp.bench.append(opp.active)
    opp.active = tgt
    return True


def _damage_active(ctx, mon, amount):
    """Deal `amount` of ATTACK damage to `mon` (as an Active): Weakness applies vs the attacker's type.
    Written straight onto `.damage` (so it targets the *new* Active, not the returned-value defender).
    Returns the damage actually written (0 if no target / no amount)."""
    if mon is None or amount <= 0:
        return 0
    dmg = amount
    if mon.card.weakness and mon.card.weakness == ctx.attacker.card.ptype:
        dmg *= 2
    mon.damage += dmg
    return dmg


def _gust_in_and_damage(ctx, amount):
    """'Switch in 1 of your opponent's Benched Pokémon to the Active Spot. This attack does `amount`
    damage to the new Active Pokémon.' Gust first (KO-target-aware), then apply `amount` to whatever is
    now Active — the newly-promoted mon, or (if the opponent had no Bench) the unchanged Active. Returns
    0: the printed base of these attacks is 0 and the damage is applied inline above."""
    _gust_in(ctx, amount)
    _damage_active(ctx, ctx.opp.active, amount)
    return 0


# ================================================================ effects

# ---- self-pivot: "Switch this Pokémon with 1 of your Benched Pokémon" ----
@effect("Switch this Pokémon with 1 of your Benched Pokémon.")
def _switch_self_any(ctx):
    # Deal the printed damage to the opponent's Active, then pivot the attacker to our Bench.
    _switch_self(ctx)
    return ctx.base


@effect("Switch this Pokémon with 1 of your Benched {L} Pokémon.")
def _switch_self_lightning(ctx):
    # Same pivot, but only a benched Lightning Pokémon is an eligible new Active.
    _switch_self(ctx, pred=lambda m: m.card.ptype == 'Lightning')
    return ctx.base


# ---- gust: "Switch in 1 of your opponent's Benched Pokémon to the Active Spot" ----
@effect("Switch in 1 of your opponent's Benched Pokémon to the Active Spot.")
def _gust_only(ctx):
    # Pure disruption: drag up an opponent's benched Pokémon (attacker's pick). No damage (base 0).
    _gust_in(ctx)
    return ctx.base


@effect("Switch in 1 of your opponent's Benched Pokémon to the Active Spot. This attack does 20 damage to the new Active Pokémon.")
def _gust_dmg_20(ctx):
    return _gust_in_and_damage(ctx, 20)


@effect("Switch in 1 of your opponent's Benched Pokémon to the Active Spot. This attack does 30 damage to the new Active Pokémon.")
def _gust_dmg_30(ctx):
    return _gust_in_and_damage(ctx, 30)


@effect("Switch in 1 of your opponent's Benched Pokémon to the Active Spot. This attack does 40 damage to the new Active Pokémon.")
def _gust_dmg_40(ctx):
    return _gust_in_and_damage(ctx, 40)


@effect("Switch in 1 of your opponent's Benched Pokémon to the Active Spot. This attack does 70 damage to the new Active Pokémon.")
def _gust_dmg_70(ctx):
    return _gust_in_and_damage(ctx, 70)


@effect("Switch in 1 of your opponent's Benched Pokémon to the Active Spot. If you do, this attack does 120 damage to the new Active Pokémon. If you didn't play Xerosic's Machinations from your hand during this turn, this attack does nothing.")
def _malamar_xerosic(ctx):
    # Gated on having played the Supporter "Xerosic's Machinations" from hand THIS turn — the engine now
    # tracks per-turn plays (ctx.played_this_turn reads me.played). Not played -> "this attack does
    # nothing": no switch, no damage. Played -> gust up a benched Pokémon (KO-target-aware) and deal 120
    # to the new Active. (The AI rarely plays that 'OTHER'-category Supporter, so live this usually still
    # does nothing — but the gate is now a real, testable condition rather than a hard 0-floor.)
    if not ctx.played_this_turn("Xerosic's Machinations"):
        return 0
    return _gust_in_and_damage(ctx, 120)


# ---- opponent-chosen switch-out: "(Your opponent chooses the new Active Pokémon.)" ----
@effect("You may switch out your opponent's Active Pokémon to the Bench. (Your opponent chooses the new Active Pokémon.)")
def _may_switch_out(ctx):
    # Optional. Take it only when it downgrades the opponent's Active slot — i.e. their Active is their
    # most energy-invested Pokémon, so the readiest bench mon they promote is at most as charged. The
    # printed base damage still lands on the (original) Active regardless.
    opp = ctx.opp
    if opp.bench and opp.active is not None:
        bench_peak = max((b.total_energy() for b in opp.bench), default=0)
        if opp.active.total_energy() > bench_peak:
            ctx.switch_defender()
    return ctx.base


@effect("Switch this Pokémon with 1 of your Benched Pokémon. If you do, switch out your opponent's Active Pokémon to the Bench. (Your opponent chooses the new Active Pokémon.)")
def _self_pivot_then_switch_out(ctx):
    # Iron Bundle: pivot the attacker to our Bench; only "if you do" (a self-switch actually happened)
    # do we also bump the opponent's Active back (they choose its replacement).
    if _switch_self(ctx):
        ctx.switch_defender()
    return ctx.base


# ---- stall + vulnerability: Stunfisk ----
@effect("During your opponent's next turn, the Defending Pokémon can't retreat. During your next turn, the Defending Pokémon takes 100 more damage from attacks (after applying Weakness and Resistance).")
def _stunfisk_trap(ctx):
    # (1) Lock the Defending Pokémon in place next (opponent's) turn.
    ctx.defender_cant_retreat()
    # (2) "During YOUR next turn it takes 100 MORE damage": reuse the engine's temp damage hook
    #     (Mon.dr_amount/dr_turn -> incoming_damage() adds dr_amount when dr_turn+1 == game.turn).
    #     A NEGATIVE reduction = extra damage; dr_turn = turn+1 so it fires on the ATTACKER's NEXT
    #     turn (game.turn+2), not the opponent's turn in between. incoming_damage runs after Weakness.
    ctx.defender.dr_amount = -100
    ctx.defender.dr_turn = ctx.game.turn + 1
    return ctx.base
