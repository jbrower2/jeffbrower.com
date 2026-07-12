#!/usr/bin/env python3
"""Attack-effect batch: conditional_damage_1 — attacks whose damage is gated on / scaled by a
board condition (defender stage/type/retreat/damage, energy counts, damage counters, prizes, etc.)
plus a few conditional riders (devolve, next-turn debuff, can't-attack, cost/usage gates).

Damage-token conventions (matched to effects.py so the registry and the heuristic path agree):
  - "N×"  → damage is base * count, so it is 0 when the count is 0 (no floor).
  - "N+"  → damage is base + a conditional/scaled bonus (base is the floor).
  - "[N]" → fixed base; any clause changes side effects / usage, not the number.
  - "{X} Energy" counts BASIC typed energy only (mon.energy.get(Type,0)) — NOT rainbow 'Wild'
    or 'Colorless' special pips — matching effects.py eval_count.
  - "Energy attached" (untyped) uses total_energy() (special energy included).
  - "damage counter" = damage // 10 (10 damage per counter).
  - "Evolution Pokémon" / "evolved Pokémon" = card.stage > 0. "Basic" = card.stage == 0.
"""
from attack_effects import effect, EffectCtx, STATUSES
from engine import BY_NAME


# ---------------------------------------------------------------- module-level helpers
def _typed_energy_on(mons, typ):
    """Basic typed energy (e.g. 'Fire' for {R}) across an iterable of Mons — excludes Wild/Colorless."""
    return sum(m.energy.get(typ, 0) for m in mons)


def _damage_counters(mon):
    """Damage counters on a Mon = 10 damage each."""
    return mon.damage // 10


def _defender_cant_attack_next(ctx):
    """Disable the DEFENDER's attacks during the opponent's next turn.

    The engine skips an attack when `mon.cd_turn + 2 == game.turn` (with cd_name 'ALL'/that attack).
    The opponent's next turn is game.turn + 1, so we set the defender's cd_turn to game.turn - 1
    (so cd_turn + 2 == game.turn + 1 lands exactly on that turn). Compare `ctx.cant_attack_next`,
    which uses cd_turn = game.turn for the ATTACKER whose next turn is game.turn + 2.
    """
    ctx.defender.cd_name = 'ALL'
    ctx.defender.cd_turn = ctx.game.turn - 1


def _vulnerable_next_turn(ctx, amt):
    """Make the DEFENDER take `amt` MORE damage from attacks during the attacker's next turn.

    Reuses the engine's temp reduction hook: incoming_damage() does `red += dfn.dr_amount` when
    `dfn.dr_turn + 1 == game.turn`, then `max(0, dmg - red)`. A NEGATIVE dr_amount therefore ADDS
    damage. The attacker's next turn is game.turn + 2, so dr_turn = game.turn + 1 makes it fire only
    then (and it applies after Weakness/Resistance, since incoming_damage runs post-weakness).
    """
    ctx.defender.dr_amount = -amt
    ctx.defender.dr_turn = ctx.game.turn + 1


# No Tera subtype is stored in the card model (not in meta/rarity/energy), so a defender can't be
# identified as Tera. Read an optional flag; default False (never over-credit the +damage bonus).
# Attribute name kept as `tera` to match sibling batch_bench_spread_0._is_tera, so a future data
# addition (card.tera) lights up every Tera-gated effect uniformly rather than only some.
def _is_tera(card):
    return getattr(card, 'tera', False)


def _devolve_active(ctx):
    """Devolve the opponent's Active: move its highest-Stage Evolution card (the current card) to the
    opponent's hand and revert the Mon to the card it evolved from. Damage/energy/status stay put."""
    dfn = ctx.defender
    if dfn.card.stage <= 0:
        return False
    pre_name = dfn.card.evolves_from
    if not pre_name:
        return False
    cands = BY_NAME.get(pre_name, [])
    if not cands:
        return False
    # prefer a printing exactly one Stage below; else any printing of that pre-evolution
    lower = [c for c in cands if c.stage == dfn.card.stage - 1]
    pre = (lower or cands)[0]
    ctx.opp.hand.append(('P', dfn.card))   # highest Stage Evolution card -> opponent's hand
    dfn.card = pre                          # Mon reverts to the lower stage
    return True


# ================================================================ EFFECTS

@effect("If the Defending Pokémon is a Basic Pokémon, it can't attack during your opponent's next turn.")
def _basic_cant_attack(ctx):
    # Paldean Tauros (SV08 #101) Blocking Stomp — [90], lock a Basic defender's attacks next turn.
    if ctx.defender.card.stage == 0:
        _defender_cant_attack_next(ctx)
    return ctx.base


@effect('This attack does 40 damage for each of your Pokémon that has "Tauros" in its name that has any damage counters on it.')
def _tauros_damaged_x40(ctx):
    # Paldean Tauros (ME02) — 40× per YOUR "Tauros"-named Pokémon that has damage counters.
    n = sum(1 for m in ctx.me.all_mons() if 'Tauros' in m.card.name and m.damage > 0)
    return 40 * n


@effect("If your opponent's Active Pokémon is an Evolution Pokémon, this attack does 50 more damage.")
def _evo_plus_50(ctx):
    # Tauros (SV10) — 50+, +50 vs an Evolution (stage > 0) defender.
    return ctx.base + (50 if ctx.defender.card.stage > 0 else 0)


@effect("This attack does 30 more damage for each {C} in your opponent's Active Pokémon's Retreat Cost.")
def _per_retreat_plus_30(ctx):
    # Ariados (SV06) — 10+, +30 per {C} of the defender's CURRENT Retreat Cost. eff_retreat() honors
    # the modeled Magnetic-Metal no-retreat (retreat -> 0), matching sibling batches (cond_dmg_2/3,
    # dmg_reduction_0) — "Retreat Cost" is always the current, modified cost, not the printed number.
    return ctx.base + 30 * ctx.defender.eff_retreat()


@effect("This attack does 60 damage for each {R} Energy attached to all of your opponent's Pokémon.")
def _per_opp_fire_x60(ctx):
    # Sunflora (SV06) — 60× per basic {R} (Fire) energy across ALL of the opponent's Pokémon.
    return 60 * _typed_energy_on(ctx.opp.all_mons(), 'Fire')


@effect("This attack does 10 more damage for each damage counter on your opponent's Active Pokémon.")
def _per_def_counter_plus_10(ctx):
    # Girafarig (SV05) — 20+, +10 per damage counter on the defender.
    return ctx.base + 10 * _damage_counters(ctx.defender)


@effect("This attack does 40 damage for each of your Stage 1 Pokémon in play.")
def _per_stage1_x40(ctx):
    # Farigiraf (SV06) — 40× per YOUR Stage 1 Pokémon in play.
    return 40 * sum(1 for m in ctx.me.all_mons() if m.card.stage == 1)


@effect("If your opponent's Active Pokémon already has any damage counters on it, this attack does 90 more damage.")
def _def_damaged_plus_90(ctx):
    # Granbull (ME02) — 90+, +90 if the defender already has any damage counters.
    return ctx.base + (90 if ctx.defender.damage > 0 else 0)


@effect("If a Stadium is in play, this attack does 120 more damage. Then, discard that Stadium.")
def _stadium_plus_120_discard(ctx):
    # Mamoswine (ME02) — 120+, +120 and discard the Stadium if one is in play.
    if ctx.stadium():
        ctx.discard_stadium()
        return ctx.base + 120
    return ctx.base


@effect("You can use this attack only if this Pokémon used Rollout during your last turn.")
def _rollout_gate(ctx):
    # Miltank (PRE) Moomoo Rolling — [100], usable only if this Pokémon used Rollout on your previous
    # turn (else the attack does nothing).
    return ctx.base if ctx.used_last_turn('Rollout') else 0


@effect("This attack does 70 damage for each damage counter on your opponent's Active Pokémon.")
def _per_def_counter_x70(ctx):
    # Galarian Obstagoon (ASH) — 70× per damage counter on the defender.
    return 70 * _damage_counters(ctx.defender)


@effect("Your opponent reveals their hand, and this attack does 80 damage for each Energy card you find there.")
def _per_hand_energy_x80(ctx):
    # Beautifly (ASH) — 80× per Energy card (basic 'E' or special 'S') in the opponent's hand.
    return 80 * sum(1 for t in ctx.opp.hand if t[0] in ('E', 'S'))


@effect("If a Stadium is in play, this attack does 70 more damage.")
def _stadium_plus_70(ctx):
    # Probopass (SV10) — 70+, +70 if a Stadium is in play.
    return ctx.base + (70 if ctx.stadium() else 0)


@effect("This attack does 50 damage for each of your Pokémon that has any damage counters on it.")
def _per_own_damaged_x50(ctx):
    # Aggron (SV06) — 50× per YOUR Pokémon (any) that has damage counters.
    return 50 * sum(1 for m in ctx.me.all_mons() if m.damage > 0)


@effect("If this Pokémon and your opponent's Active Pokémon have the same amount of Energy attached, this attack does 120 more damage.")
def _same_energy_plus_120(ctx):
    # Medicham (SV10) — 50+, +120 if attacker and defender have equal total Energy attached.
    return ctx.base + (120 if ctx.attacker.total_energy() == ctx.defender.total_energy() else 0)


@effect("If this Pokémon has more Energy attached than your opponent's Active Pokémon, this attack does 160 more damage.")
def _more_energy_plus_160(ctx):
    # Swalot (SV07) — 10+, +160 if attacker has strictly more total Energy than the defender.
    return ctx.base + (160 if ctx.attacker.total_energy() > ctx.defender.total_energy() else 0)


@effect("During your next turn, the Defending Pokémon takes 50 more damage from attacks (after applying Weakness and Resistance).")
def _defender_vuln_50(ctx):
    # Vibrava (SV08) Screech — 0 damage; defender takes +50 from attacks during your next turn.
    _vulnerable_next_turn(ctx, 50)
    return ctx.base


@effect("If this Pokémon has any damage counters on it, this attack can be used for {D}.")
def _damaged_cost_discount(ctx):
    # Crawdaunt (ME01) Cutting Riposte — [130] always; the "can be used for {D}" clause is a COST
    # discount (resolved by the engine's cost check), so the damage number is unconditionally base.
    return ctx.base


@effect("If your opponent's Active Pokémon is an evolved Pokémon, devolve it by putting the highest Stage Evolution card on it into your opponent's hand.")
def _devolve_if_evolved(ctx):
    # Claydol (ME04) Devolution Ray — [50]; devolve an evolved defender by one stage.
    _devolve_active(ctx)
    return ctx.base


@effect("If you have at least 3 {D} Energy in play, this attack does 50 more damage.")
def _three_dark_plus_50(ctx):
    # Absol (SFA) — 20+, +50 if you have >= 3 basic {D} (Darkness) energy across your Pokémon.
    return ctx.base + (50 if _typed_energy_on(ctx.me.all_mons(), 'Darkness') >= 3 else 0)


@effect("During your next turn, this Pokémon's Meteor Mash attack does 60 more damage (before applying Weakness and Resistance).")
def _meteor_mash_ramp(ctx):
    # Metagross (SV05) Meteor Mash — [60]; "during your next turn, this attack does 60 more." This is a
    # ONE-SHOT +60 for the immediately-following turn, NOT a stacking pile: using it every turn steadies
    # at 60 -> 120 -> 120, not 60 -> 120 -> 180. buff_next_turn overwrites and expires it.
    ctx.buff_next_turn(60)
    return ctx.base


@effect("This attack does 20 more damage for each Energy attached to your opponent's Active Pokémon.")
def _per_def_energy_plus_20(ctx):
    # Deoxys (ME04) — 80+, +20 per Energy attached to the defender (total, special included).
    return ctx.base + 20 * ctx.defender.total_energy()


@effect("If your opponent's Active Pokémon is a {P} Pokémon, this attack does 30 more damage.")
def _psychic_def_plus_30(ctx):
    # Bronzor (SV05) — 10+, +30 if the defender is a {P} (Psychic) Pokémon.
    return ctx.base + (30 if ctx.defender.card.ptype == 'Psychic' else 0)


@effect("If your opponent's Active Pokémon is an Evolution Pokémon, this attack does 90 more damage.")
def _evo_plus_90(ctx):
    # Toxicroak (SFA) — 90+, +90 vs an Evolution (stage > 0) defender.
    return ctx.base + (90 if ctx.defender.card.stage > 0 else 0)


@effect("If your opponent's Active Pokémon has no Retreat Cost, this attack does 80 more damage.")
def _no_retreat_plus_80(ctx):
    # Carnivine (ME04) — 80+, +80 if the defender's CURRENT Retreat Cost is 0. eff_retreat() honors the
    # modeled Magnetic-Metal no-retreat (so a printed-retreat mon carrying it still counts as "no Retreat
    # Cost"), matching sibling batches (cond_dmg_2/3, dmg_reduction_0).
    return ctx.base + (80 if ctx.defender.eff_retreat() == 0 else 0)


@effect("If this Pokémon has 2 or more {G} Energy attached, this attack does 120 more damage.")
def _two_grass_plus_120(ctx):
    # Abomasnow (SV10) — 120+, +120 if the attacker has >= 2 basic {G} (Grass) energy attached.
    return ctx.base + (120 if ctx.attacker.energy.get('Grass', 0) >= 2 else 0)


@effect("This attack does 10 more damage for each damage counter on all of your opponent's Pokémon.")
def _per_all_opp_counters_plus_10(ctx):
    # Azelf (SV08) — 10+, +10 per damage counter across ALL of the opponent's Pokémon.
    return ctx.base + 10 * sum(_damage_counters(m) for m in ctx.opp.all_mons())


@effect("If your opponent's Active Pokémon is a Tera Pokémon, this attack does 230 more damage.")
def _tera_plus_230(ctx):
    # Regigigas (PRE) Jewel Breaker — 100+, +230 vs a Tera defender. Tera isn't marked in the card
    # model, so this never over-credits (defaults to no bonus) — see _is_tera.
    return ctx.base + (230 if _is_tera(ctx.defender.card) else 0)
