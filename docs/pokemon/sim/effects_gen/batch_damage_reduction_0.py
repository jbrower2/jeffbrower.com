#!/usr/bin/env python3
"""Attack-effect batch: damage_reduction_0 — attacks that reduce damage, either as an
immediate scaling ("this attack does N less for each X") or a defensive rider set up for the
opponent's next turn ("this Pokémon takes N less", "prevent all damage ...").

Each effect is keyed by its exact (damage-stripped) card text and returns the raw damage dealt to
the defender's Active (the engine applies Weakness afterward).

Conventions (matched to sibling batches + effects.py)
-----------------------------------------------------
* FLAT self-reduction "this Pokémon takes N less damage from attacks (after W&R)" reuses the engine
  hook Mon.dr_amount / Mon.dr_turn. incoming_damage() adds dr_amount when `dr_turn + 1 == game.turn`
  (exactly the opponent's next turn), then it lapses on its own. This IS wired into the live engine.
* UNCONDITIONAL "prevent all damage done to this Pokémon" reuses the same hook with a huge amount
  (_WALL) — max(0, dmg - _WALL) == 0 for any realistic hit. Same as batch_coinflip_gate_0._WALL.
* IMMEDIATE "this attack does N less for each X" is computed and returned now (floored at 0).
* CONDITIONAL preventions ("... by attacks from Basic / Ancient / Ability Pokémon", "... if that
  damage is N or less", team "Future" auras) and the DEFENDER-outgoing debuffs ("attacks used by the
  Defending Pokémon do N less") have NO engine hook: incoming_damage()'s only dynamic per-hit hook is
  the *flat, unconditional* dr_amount. Modelling them with dr_amount=_WALL would wrongly prevent ALL
  damage (the exact "conditional applied unconditionally" bug we must avoid), so instead the precise
  intent is recorded as a marker (turn-stamped, mirroring the CantRetreat / CoinToAttack convention)
  and the printed base damage is dealt. The marker is testable and future-wireable; it never over- or
  mis-applies prevention in the current sim.
"""
from attack_effects import effect, EffectCtx, STATUSES

# Large enough that max(0, dmg - _WALL) == 0 for any hit (post-Weakness doubling <<< this).
_WALL = 100000


# ---------------------------------------------------------------- module-level helpers
def _reduce_next_turn(ctx: EffectCtx, n):
    """Schedule a flat -n damage reduction to THIS Pokémon during the opponent's next turn.
    incoming_damage() applies dr_amount when `dr_turn + 1 == game.turn`, then it lapses."""
    ctx.attacker.dr_amount = n
    ctx.attacker.dr_turn = ctx.game.turn


def _wall_next_turn(ctx: EffectCtx):
    """Prevent ALL attack damage to THIS Pokémon during the opponent's next turn (unconditional)."""
    ctx.attacker.dr_amount = _WALL
    ctx.attacker.dr_turn = ctx.game.turn


def _record_prevent(ctx: EffectCtx, key):
    """Record a CONDITIONAL 'prevent damage to this Pokémon next turn' intent (no engine hook yet).
    Turn-stamped so a future incoming_damage() pass could read `mon.status[key] == turn - 1` on the
    opponent's next turn and enforce the specific condition against the actual attacker."""
    ctx.attacker.status[key] = ctx.game.turn


def _defender_attack_penalty(ctx: EffectCtx, n):
    """Record 'attacks used by the Defending Pokémon do n less damage during the opponent's next
    turn' as intent on the defender (no engine hook: best_attack() has no outgoing-debuff term).
    Turn-stamped for a future best_attack() pass; the printed base damage is still dealt now."""
    ctx.defender.next_atk_penalty = n
    ctx.defender.next_atk_penalty_turn = ctx.game.turn


def _ko_predicted(ctx: EffectCtx):
    """Would this attack's damage Knock Out the Defending Pokémon? Uses printed base with the engine's
    Weakness ×2 (best_attack applies only Weakness, no Resistance), compared to the defender's HP left."""
    dmg = ctx.base
    d = ctx.defender
    if d.card.weakness and d.card.weakness == ctx.attacker.card.ptype:
        dmg *= 2
    return dmg > 0 and dmg >= d.hp_left


# ================================================================ A. FLAT self-reduction next turn
# "During your opponent's next turn, this Pokémon takes N less damage from attacks (after applying
# Weakness and Resistance)." — wired via Mon.dr_amount / dr_turn. Deals the printed base damage.

@effect("During your opponent's next turn, this Pokémon takes 10 less damage from attacks (after applying Weakness and Resistance).")
def _dr_self_10(ctx):
    _reduce_next_turn(ctx, 10)
    return ctx.base


@effect("During your opponent's next turn, this Pokémon takes 20 less damage from attacks (after applying Weakness and Resistance).")
def _dr_self_20(ctx):
    _reduce_next_turn(ctx, 20)
    return ctx.base


@effect("During your opponent's next turn, this Pokémon takes 30 less damage from attacks (after applying Weakness and Resistance).")
def _dr_self_30(ctx):
    _reduce_next_turn(ctx, 30)
    return ctx.base


@effect("During your opponent's next turn, this Pokémon takes 40 less damage from attacks (after applying Weakness and Resistance).")
def _dr_self_40(ctx):
    _reduce_next_turn(ctx, 40)
    return ctx.base


@effect("During your opponent's next turn, this Pokémon takes 50 less damage from attacks (after applying Weakness and Resistance).")
def _dr_self_50(ctx):
    _reduce_next_turn(ctx, 50)
    return ctx.base


@effect("During your opponent's next turn, this Pokémon takes 60 less damage from attacks (after applying Weakness and Resistance).")
def _dr_self_60(ctx):
    _reduce_next_turn(ctx, 60)
    return ctx.base


# ================================================================ E. IMMEDIATE variable reduction
# "This attack does N less damage for each X." Computed and returned now, floored at 0. The engine
# applies Weakness to the returned value afterward (these clauses modify the attack's base damage).

@effect("This attack does 10 less damage for each damage counter on this Pokémon.")
def _minus_10_per_own_counter(ctx):
    # Tangrowth (150) / Carnivine (130): -10 per damage counter (= self damage // 10) on the attacker.
    counters = ctx.attacker.damage // 10
    return max(0, ctx.base - 10 * counters)


@effect("This attack does 30 less damage for each {C} in your opponent's Active Pokémon's Retreat Cost.")
def _minus_30_per_retreat(ctx):
    # Throh (120): -30 per {C} of the defender's CURRENT Retreat Cost (eff_retreat honours in-play
    # modifiers the engine models, e.g. Magnetic Metal Energy -> 0). Retreat cost is all Colorless.
    return max(0, ctx.base - 30 * ctx.defender.eff_retreat())


@effect("This attack does 50 less damage for each {C} in your opponent's Active Pokémon's Retreat Cost.")
def _minus_50_per_retreat(ctx):
    # Iron Bundle (200): -50 per {C} of the defender's CURRENT Retreat Cost (see _minus_30_per_retreat).
    return max(0, ctx.base - 50 * ctx.defender.eff_retreat())


@effect("This attack does 60 less damage for each Energy attached to your opponent's Active Pokémon.")
def _minus_60_per_opp_energy(ctx):
    # Tinkaton (240): -60 per Energy attached to the defender (matches effects.eval_count's total_energy).
    return max(0, ctx.base - 60 * ctx.defender.total_energy())


# ================================================================ F. KO -> unconditional wall
@effect("If your opponent's Pokémon is Knocked Out by damage from this attack, during your opponent's next turn, prevent all damage from and effects of attacks done to this Pokémon.")
def _ko_then_wall(ctx):
    # Golisopod (30) / Marshadow (60): only if this attack KOs the defender, wall off ALL incoming
    # damage next turn. (The "and effects of attacks" clause has no separate engine hook; the damage
    # wall is the modelled part.) Deal the printed base damage regardless.
    if _ko_predicted(ctx):
        _wall_next_turn(ctx)
    return ctx.base


# ================================================================ B. CONDITIONAL prevent-by-class
# "During your opponent's next turn, prevent all damage done to this Pokémon by attacks from
# <class> Pokémon." No engine hook enforces the attacker class per hit — recorded as precise intent
# (NOT dr_amount=_WALL, which would wrongly wall every attacker). Deals the printed base damage.

@effect("During your opponent's next turn, prevent all damage done to this Pokémon by attacks from Basic Pokémon.")
def _prevent_from_basic(ctx):
    # Golbat (30) / Dipplin (20) / Archaludon (120): immune only to Basic-Pokémon attackers next turn.
    _record_prevent(ctx, 'PreventDmgFromBasic')
    return ctx.base


@effect("During your opponent's next turn, prevent all damage done to this Pokémon by attacks from Pokémon that have an Ability.")
def _prevent_from_ability(ctx):
    # Deoxys (80): immune only to attackers that have an Ability next turn.
    _record_prevent(ctx, 'PreventDmgFromAbility')
    return ctx.base


@effect("During your opponent's next turn, prevent all damage done to this Pokémon by attacks from Ancient Pokémon.")
def _prevent_from_ancient(ctx):
    # Iron Moth (120): immune only to Ancient-Pokémon attackers next turn. (The Card model carries no
    # Ancient/Future subtype, so the class can't even be evaluated here — intent recorded.)
    _record_prevent(ctx, 'PreventDmgFromAncient')
    return ctx.base


# ================================================================ C. CONDITIONAL prevent-by-threshold
# "During your opponent's next turn, prevent all damage done to this Pokémon by attacks if that
# damage is N or less." All-or-nothing per hit (a hit ABOVE the threshold is dealt in FULL, so a flat
# dr_amount=N is wrong). No threshold hook in incoming_damage — recorded as intent. base is 0 here.

@effect("During your opponent's next turn, prevent all damage done to this Pokémon by attacks if that damage is 40 or less.")
def _prevent_if_le_40(ctx):
    # Roggenrola (base 0): next turn, prevent a hit only if its damage is <= 40 (else full damage).
    _record_prevent(ctx, 'PreventDmgIfLE40')
    return ctx.base


@effect("During your opponent's next turn, prevent all damage done to this Pokémon by attacks if that damage is 60 or less.")
def _prevent_if_le_60(ctx):
    # Metapod (base 0): next turn, prevent a hit only if its damage is <= 60 (else full damage).
    _record_prevent(ctx, 'PreventDmgIfLE60')
    return ctx.base


# ================================================================ G. TEAM Future-vs-ex prevention
@effect("During your opponent's next turn, prevent all damage done to each of your Future Pokémon by attacks from Pokémon ex. If this Pokémon is no longer your Active Pokémon, this effect ends.")
def _prevent_future_from_ex(ctx):
    # Miraidon (40): next turn, all YOUR Future Pokémon take no damage from Pokémon-ex attacks, but
    # only while this Pokémon stays Active. Team-wide + attacker-class + active-persistence conditions
    # have no engine hook — recorded as intent on this Pokémon. Deal the printed base damage.
    _record_prevent(ctx, 'PreventFutureFromEx')
    return ctx.base


# ================================================================ D. DEFENDER outgoing-attack debuff
# "During your opponent's next turn, attacks used by the Defending Pokémon do N less damage (before
# applying Weakness and Resistance)." Reduces the DEFENDER's OUTGOING damage next turn — best_attack()
# has no outgoing-debuff term, so the intent is recorded on the defender. Deals the printed base damage.

@effect("During your opponent's next turn, attacks used by the Defending Pokémon do 20 less damage (before applying Weakness and Resistance).")
def _def_attacks_minus_20(ctx):
    # Chikorita / Buneary / Hop's Rookidee (base 0).
    _defender_attack_penalty(ctx, 20)
    return ctx.base


@effect("During your opponent's next turn, attacks used by the Defending Pokémon do 30 less damage (before applying Weakness and Resistance).")
def _def_attacks_minus_30(ctx):
    # Pawmi (base 0) / Flutter Mane (base 70).
    _defender_attack_penalty(ctx, 30)
    return ctx.base


@effect("During your opponent's next turn, attacks used by the Defending Pokémon do 40 less damage (before applying Weakness and Resistance).")
def _def_attacks_minus_40(ctx):
    # Marowak (base 0).
    _defender_attack_penalty(ctx, 40)
    return ctx.base


@effect("During your opponent's next turn, attacks used by the Defending Pokémon do 100 less damage (before applying Weakness and Resistance).")
def _def_attacks_minus_100(ctx):
    # Houndoom (base 100).
    _defender_attack_penalty(ctx, 100)
    return ctx.base
