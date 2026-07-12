#!/usr/bin/env python3
"""Effect batch: status_0 — Special Conditions (Burned / Poisoned / Asleep / Paralyzed / Confused),
their combinations, condition-gated damage bonuses, and a few status attacks with structural riders
(self-energy discard, self-switch, next-turn buff, heavy-poison / heavy-confusion counter overrides).

Each effect is registered by its exact (damage-stripped) card text and returns the PRE-Weakness damage
dealt to the defender's Active (the engine applies Weakness afterward). Status infliction runs through
`ctx.status(kind, mon=...)`, which routes Asleep/Burned/Confused/Paralyzed/Poisoned and RESPECTS the
Mist/Rocky/Bubbly effect-shields (Mon.effect_immune) — the same gate the live engine uses. It returns
True when the condition actually lands, so riders keyed to a landed condition (Crobat's heavy poison)
guard on it.

Conventions (matched to sibling batches + effects.py / engine.py)
----------------------------------------------------------------
* SELF conditions ("This Pokémon is now Confused/Asleep") apply to the ATTACKER via
  `ctx.status(kind, mon=ctx.attacker)`. Passing the attacker still honors its own Bubbly-Water shield
  (Bubbly blocks conditions on the Pokémon it is attached to), which is the faithful ruling.
* CAN'T-RETREAT riders use `ctx.defender_cant_retreat()` (sets defender.status['CantRetreat']), exactly
  as the proof-batch `_defender_no_retreat` does — "that Pokémon" and "the Defending Pokémon" both mean
  the opponent's Active.
* CONDITION-GATED DAMAGE ("if the opponent is Poisoned/Burned, this attack does N more/does nothing")
  reads the defender's live status dict — never applies the bonus unconditionally (the anti-bug rule).
* HEAVY POISON ("put 2 damage counters instead of 1"): scale Mon.poison_amt to N*10, mirroring
  effects.set_status; the between-turns checkup reads poison_amt.
* HEAVY CONFUSION ("put 8 damage counters instead of 3"): the engine models confusion self-damage as a
  hardcoded 30 in effects.can_attack (no per-Mon field). Best-effort: record the override on the mon
  (confuse_amt) for future wiring and still apply Confused. Deals the printed base (never over-applies).
* NEXT-TURN OFFENSE BUFF (Komala) uses the engine's mon.ramp "next turn does N more" hook (added to a
  named attack's damage in best_attack, before Weakness — matching the parenthetical). See the note on
  that effect for why it differs from the _buff_next_turn_120 sibling.
* UNMODELED RIDERS (energy-attach lock) have no engine hook; record the intent turn-stamped for future
  wiring and deal the printed base — nothing over-applies.
* POKÉMON TOOLS ARE now modeled (Mon.tools, exposed via ctx.has_tool / ctx.discard_tools): N's Joltik
  strips the defender's Tools and Paralyzes it only if one was actually discarded (no Tool -> no Paralysis).
"""
from attack_effects import effect, EffectCtx, STATUSES


# ---------------------------------------------------------------- module-level helpers
def _discard_all_self_energy(ctx):
    """Discard EVERY Energy attached to the attacker (basic pips route to my disc_energy via the
    engine helper; Wild/Colorless special-energy pseudo-pips are removed untracked, as elsewhere)."""
    ctx.discard_energy_self(ctx.attacker.total_energy())


def _self_switch(me):
    """'Switch this Pokémon with 1 of your Benched Pokémon': the Active goes to the Bench and the
    readiest benched Pokémon (most energy, then HP — engine.Player.promote's ordering) comes up.
    No-op with an empty Bench (nothing to switch to)."""
    if not me.bench:
        return
    old = me.active
    me.promote()               # promote the readiest currently-benched Pokémon into Active
    me.bench.append(old)       # the switched-out Active joins the Bench


def _cond_active(ctx, kind):
    """True iff the opponent's Active currently has Special Condition `kind`."""
    return bool(ctx.defender and ctx.defender.status.get(kind))


# ================================================================ single condition — opponent Active
@effect("Your opponent's Active Pokémon is now Burned.")
def _burn(ctx):
    ctx.status('Burned')
    return ctx.base


# ================================================================ single condition — self
@effect("This Pokémon is now Confused.")
def _self_confuse(ctx):
    ctx.status('Confused', mon=ctx.attacker)
    return ctx.base


@effect("This Pokémon is now Asleep.")
def _self_sleep(ctx):
    ctx.status('Asleep', mon=ctx.attacker)
    return ctx.base


@effect("This Pokémon is now Asleep. Heal 30 damage from it.")
def _self_sleep_heal30(ctx):
    ctx.status('Asleep', mon=ctx.attacker)
    ctx.heal(30)               # "it" = this Pokémon (the attacker), the default heal target
    return ctx.base


# ================================================================ combined conditions — opponent Active
@effect("Your opponent's Active Pokémon is now Burned and Confused.")
def _burn_confuse(ctx):
    ctx.status('Burned')
    ctx.status('Confused')
    return ctx.base


@effect("Your opponent's Active Pokémon is now Asleep and Poisoned.")
def _sleep_poison(ctx):
    ctx.status('Asleep')
    ctx.status('Poisoned')
    return ctx.base


@effect("Your opponent's Active Pokémon is now Burned, Confused, and Poisoned.")
def _burn_confuse_poison(ctx):
    ctx.status('Burned')
    ctx.status('Confused')
    ctx.status('Poisoned')
    return ctx.base


# ================================================================ condition + can't-retreat rider
@effect("Your opponent's Active Pokémon is now Confused. During your opponent's next turn, that Pokémon can't retreat.")
def _confuse_noretreat(ctx):
    ctx.status('Confused')
    ctx.defender_cant_retreat()
    return ctx.base


@effect("Your opponent's Active Pokémon is now Poisoned. During your opponent's next turn, that Pokémon can't retreat.")
def _poison_noretreat_that(ctx):
    ctx.status('Poisoned')
    ctx.defender_cant_retreat()
    return ctx.base


@effect("Your opponent's Active Pokémon is now Poisoned. During your opponent's next turn, the Defending Pokémon can't retreat.")
def _poison_noretreat_defending(ctx):
    ctx.status('Poisoned')
    ctx.defender_cant_retreat()
    return ctx.base


@effect("Your opponent's Active Pokémon is now Burned. During your opponent's next turn, that Pokémon can't retreat.")
def _burn_noretreat(ctx):
    ctx.status('Burned')
    ctx.defender_cant_retreat()
    return ctx.base


# ================================================================ discard-energy / recoil + condition
@effect("Discard all Energy from this Pokémon. Your opponent's Active Pokémon is now Paralyzed.")
def _discardall_paralyze(ctx):
    _discard_all_self_energy(ctx)
    ctx.status('Paralyzed')
    return ctx.base


@effect("This Pokémon also does 70 damage to itself. Your opponent's Active Pokémon is now Paralyzed and Poisoned.")
def _self70_paralyze_poison(ctx):
    ctx.self_damage(70)
    ctx.status('Paralyzed')
    ctx.status('Poisoned')
    return ctx.base


# ================================================================ self-switch + condition
@effect("Your opponent's Active Pokémon is now Confused and Poisoned. Switch this Pokémon with 1 of your Benched Pokémon.")
def _confuse_poison_selfswitch(ctx):
    ctx.status('Confused')
    ctx.status('Poisoned')
    _self_switch(ctx.me)       # my Active pivots to the Bench (opponent's Active already conditioned)
    return ctx.base


# ================================================================ heavy-poison / heavy-confusion overrides
@effect("Your opponent's Active Pokémon is now Poisoned. During Pokémon Checkup, put 2 damage counters on that Pokémon instead of 1.")
def _heavy_poison_2(ctx):
    if ctx.status('Poisoned'):             # only scale the checkup damage if the poison actually landed
        ctx.defender.poison_amt = 20       # 2 damage counters (20) per checkup instead of 1 (10)
    return ctx.base


@effect("Your opponent's Active Pokémon is now Confused. Put 8 damage counters instead of 3 on that Pokémon for this Special Condition.")
def _heavy_confuse_8(ctx):
    # Confusion self-damage (failed-attack coin) is a hardcoded 30 in effects.can_attack — no per-Mon
    # field exists. Record the 80-damage (8-counter) override for future wiring and apply Confused.
    if ctx.status('Confused'):
        ctx.defender.confuse_amt = 80
    return ctx.base


# ================================================================ next-turn offense buff (Komala)
@effect("Both Active Pokémon are now Asleep. During your next turn, attacks used by this Pokémon do 100 more damage to your opponent's Active Pokémon (before applying Weakness and Resistance).")
def _slumbering_smack(ctx):
    ctx.status('Asleep', mon=ctx.attacker)     # this Pokémon
    ctx.status('Asleep')                        # opponent's Active
    # "+100 to attacks used by this Pokémon during your NEXT turn." Komala's only attack is Slumbering
    # Smack, so buff it (plus every card attack, and the test's synthetic name). buff_next_turn overwrites
    # (flat +100, never cumulative) and stamps the turn so it EXPIRES if Komala sleeps through its next
    # turn — no more banking +100 indefinitely.
    names = {ctx.attack.get('name')} | {a['name'] for a in ctx.attacker.card.attacks}
    ctx.buff_next_turn(100, names)
    return ctx.base


# ================================================================ spread + condition
@effect("This attack does 20 damage to each of your opponent's Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.) Your opponent's Active Pokémon is now Asleep.")
def _frosmoth_powder_snow(ctx):
    # 20 to EACH of the opponent's Pokémon. The Bench takes a flat 20 (no Weakness/Resistance); the
    # Active's 20 is returned so the engine applies Weakness to it. Then the Active falls Asleep.
    ctx.bench_damage(20, side='opp')            # which='all' by default -> every benched Pokémon
    ctx.status('Asleep')
    return 20


# ================================================================ condition-gated: does-nothing
@effect("If your opponent's Active Pokémon isn't Burned, this attack does nothing.")
def _only_if_burned(ctx):
    return ctx.base if _cond_active(ctx, 'Burned') else 0


# ================================================================ condition-gated: bonus damage (Poison / Burn)
@effect("If your opponent's Active Pokémon is Poisoned, this attack does 50 more damage.")
def _plus50_if_poisoned(ctx):
    return ctx.base + (50 if _cond_active(ctx, 'Poisoned') else 0)


@effect("If your opponent's Active Pokémon is Poisoned, this attack does 60 more damage.")
def _plus60_if_poisoned(ctx):
    return ctx.base + (60 if _cond_active(ctx, 'Poisoned') else 0)


@effect("If your opponent's Active Pokémon is Poisoned, this attack does 90 more damage.")
def _plus90_if_poisoned(ctx):
    return ctx.base + (90 if _cond_active(ctx, 'Poisoned') else 0)


@effect("If your opponent's Active Pokémon is Poisoned, this attack does 100 more damage.")
def _plus100_if_poisoned(ctx):
    return ctx.base + (100 if _cond_active(ctx, 'Poisoned') else 0)


@effect("If your opponent's Active Pokémon is Burned, this attack does 40 more damage.")
def _plus40_if_burned(ctx):
    return ctx.base + (40 if _cond_active(ctx, 'Burned') else 0)


# ================================================================ prize-gated condition
@effect("If you have exactly 1 Prize card remaining, your opponent's Active Pokémon is now Paralyzed.")
def _paralyze_if_1_prize(ctx):
    if ctx.my_prizes() == 1:
        ctx.status('Paralyzed')
    return ctx.base


# ================================================================ tool discard -> conditional Paralysis
@effect("Before doing damage, discard all Pokémon Tools from your opponent's Active Pokémon. If you discarded a Pokémon Tool in this way, your opponent's Active Pokémon is now Paralyzed.")
def _tool_strip_paralyze(ctx):
    # N's Joltik: strip every Pokémon Tool from the opponent's Active. Only "if you discarded a Tool in
    # this way" does that Pokémon become Paralyzed — so read has_tool BEFORE the discard and gate on it.
    had_tool = ctx.has_tool(ctx.defender)
    ctx.discard_tools(ctx.defender)
    if had_tool:
        ctx.status('Paralyzed')
    return ctx.base


# ================================================================ energy-attach lock (unmodeled rider)
@effect("Your opponent's Active Pokémon is now Poisoned. During your opponent's next turn, Energy cards can't be attached from your opponent's hand to that Pokémon.")
def _poison_no_energy_attach(ctx):
    ctx.status('Poisoned')
    # The "can't attach Energy from hand next turn" lock has no engine hook (attach_energy ignores it).
    # Record the intent turn-stamped for the opponent's next turn (T+1) for future wiring; poison lands
    # now and the printed base is dealt.
    ctx.defender.no_energy_attach_until = ctx.game.turn + 1
    return ctx.base
