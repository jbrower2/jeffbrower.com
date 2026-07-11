#!/usr/bin/env python3
"""Attack-effect batch: conditional_damage_2 — attacks whose damage is scaled by a count
("N× / N+ ... for each X") or gated on a board condition (defender ex/V, hand size, special
condition, own energy/special-energy, retreat cost, Round-attack count, Item-in-discard, etc.).

Token / counting conventions (matched to effects.py and the sibling conditional_damage batches so
the registry and the heuristic path agree):
  - "N×"  → damage is `ctx.base * count` (base IS the per-unit multiplier; 0 when count is 0).
  - "N+"  → damage is `ctx.base + <bonus>` (base is the floor); the per-each / flat bonus M is
            written in the text and is NOT the base, so those hard-code M.
  - "[N]" → fixed base; any clause changes side effects / cost / usage, not the number.
  - "{X} Energy attached" counts BASIC typed energy only (mon.energy.get(Type,0)) — NOT rainbow
    'Wild' / 'Colorless' special pips — matching effects.py eval_count. ({R}=Fire, {F}=Fighting,
    {L}=Lightning, {C}=Colorless.)
  - "Energy attached" (untyped) uses total_energy() (special-energy pips included).
  - "Special Energy card attached" counts CARDS via mon.special (each attached special energy = 1).
  - "Evolution Pokémon" = card.stage > 0.  "Special Condition" = one of STATUSES (not 'CantRetreat').

The engine now tracks Stadium presence (`ctx.stadium()`), whether one of your Pokémon was KO'd on the
opponent's last turn (`ctx.ko_last_turn()`), and the Trainer names you played this turn
(`ctx.played_this_turn(name)`), so those conditions are now applied exactly. Conditions the engine
still keeps NO state for (a defender's Resistance type, the reactive damage-counter hook) return
`ctx.base` — the faithful conservative choice that never commits the "conditional bonus applied
unconditionally" over-application bug.
"""
from attack_effects import effect, EffectCtx, STATUSES


# ---------------------------------------------------------------- module-level helpers
def _round_mons(me):
    """Count YOUR in-play Pokémon that have an attack named 'Round'."""
    return sum(1 for m in me.all_mons()
               if any(a.get('name') == 'Round' for a in m.card.attacks))


def _evolution_mons(me):
    """Count YOUR in-play Evolution Pokémon (card.stage > 0)."""
    return sum(1 for m in me.all_mons() if m.card.stage > 0)


def _items_in_opp_discard(opp):
    """Count Item cards in the opponent's discard pile (token ('T', trainer dict))."""
    return sum(1 for t in opp.discard
               if t[0] == 'T' and t[1].get('trainerType') == 'Item')


def _is_ex_or_v(mon):
    """A Pokémon ex (or Pokémon V — none exist in this reg-H/I/J pool, so this reduces to is_ex)."""
    c = mon.card
    return bool(c.is_ex) or c.name.endswith((' V', ' VMAX', ' VSTAR'))


def _has_special_condition(mon):
    """Is this Pokémon affected by any Special Condition (Asleep/Burned/Confused/Paralyzed/Poisoned)?
    Ignores non-condition status keys such as 'CantRetreat'."""
    return any(s in mon.status for s in STATUSES)


def _defender_resistance(mon):
    """The defender's Resistance type, or None. Resistance is NOT in the card data model (no printing
    in the pool carries it), so this reads an optional Mon attribute defaulting to None — the bonus
    never over-credits, and the branch stays testable."""
    return getattr(mon, 'resistance', None)


# ================================================================ per-each scaling (× / +)

@effect("This attack does 30 damage for each Energy attached to this Pokémon.")
def _dewott_x30_per_energy(ctx):
    # Dewott (WHT) — 30× per Energy attached to the attacker (total; special-energy pips included).
    return ctx.base * ctx.attacker.total_energy()


@effect("This attack does 20 damage for each of your Pokémon in play that has the Round attack.")
def _tympole_x20_per_round(ctx):
    # Tympole (BLK) Round — 20× per YOUR in-play Pokémon that has a 'Round' attack (counts itself).
    return ctx.base * _round_mons(ctx.me)


@effect("This attack does 70 damage for each of your Pokémon in play that has the Round attack.")
def _seismitoad_x70_per_round(ctx):
    # Seismitoad (BLK) Round — 70× per YOUR in-play Pokémon that has a 'Round' attack.
    return ctx.base * _round_mons(ctx.me)


@effect("This attack does 30 damage for each Item card in your opponent's discard pile.")
def _tirtouga_x30_per_item(ctx):
    # Tirtouga (BLK) — 30× per Item card in the OPPONENT's discard pile.
    return ctx.base * _items_in_opp_discard(ctx.opp)


@effect("This attack does 70 damage for each Special Energy card attached to this Pokémon.")
def _cinccino_x70_per_special(ctx):
    # Cinccino (SV05) — 70× per Special Energy CARD attached to the attacker (mon.special = 1/card).
    return ctx.base * len(ctx.attacker.special)


@effect("This attack does 20 more damage for each {R} Energy attached to this Pokémon.")
def _darumaka_plus20_per_fire(ctx):
    # Darumaka (ME02) — 10+, +20 per basic {R} (Fire) energy attached to the attacker.
    return ctx.base + 20 * ctx.attacker.energy.get('Fire', 0)


@effect("This attack does 40 more damage for each {R} Energy attached to this Pokémon.")
def _darmanitan_plus40_per_fire(ctx):
    # Darmanitan (ME02) — 40+, +40 per basic {R} (Fire) energy attached to the attacker.
    return ctx.base + 40 * ctx.attacker.energy.get('Fire', 0)


@effect("This attack does 40 more damage for each of your Evolution Pokémon in play.")
def _reuniclus_plus40_per_evolution(ctx):
    # Reuniclus (BLK) — 40+, +40 per YOUR Evolution (stage > 0) Pokémon in play.
    return ctx.base + 40 * _evolution_mons(ctx.me)


# ================================================================ if-condition flat bonus (+)

@effect("If this Pokémon has any Special Energy attached, this attack does 100 more damage.")
def _stoutland_plus100_if_special(ctx):
    # Stoutland (WHT) — 100+, +100 if the attacker has any Special Energy attached.
    return ctx.base + (100 if ctx.attacker.special else 0)


@effect("If this Pokémon has any Special Energy attached, this attack does 70 more damage.")
def _ferrothorn_plus70_if_special(ctx):
    # Ferrothorn (ME04) — 70+, +70 if the attacker has any Special Energy attached.
    return ctx.base + (70 if ctx.attacker.special else 0)


@effect("If this Pokémon has any {L} Energy attached, this attack does 80 more damage.")
def _galvantula_plus80_if_lightning(ctx):
    # Galvantula (SFA) — 50+, +80 if the attacker has any basic {L} (Lightning) energy attached.
    return ctx.base + (80 if ctx.attacker.energy.get('Lightning', 0) > 0 else 0)


@effect("If this Pokémon has any {F} Energy attached, this attack does 20 more damage.")
def _stunfisk_plus20_if_fighting(ctx):
    # Stunfisk (WHT) — 20+, +20 if the attacker has any basic {F} (Fighting) energy attached.
    return ctx.base + (20 if ctx.attacker.energy.get('Fighting', 0) > 0 else 0)


@effect("If your opponent's Active Pokémon is a Pokémon ex, this attack does 40 more damage.")
def _marnies_purrloin_plus40_if_ex(ctx):
    # Marnie's Purrloin (SV10) — 20+, +40 vs a Pokémon ex defender.
    return ctx.base + (40 if ctx.defender.card.is_ex else 0)


@effect("If your opponent's Active Pokémon is a Pokémon ex or Pokémon V, this attack does 90 more damage.")
def _swanna_plus90_if_ex_or_v(ctx):
    # Swanna (SV06) — 20+, +90 vs a Pokémon ex / Pokémon V defender.
    return ctx.base + (90 if _is_ex_or_v(ctx.defender) else 0)


@effect("If your opponent's Active Pokémon is a Pokémon ex or Pokémon V, this attack does 120 more damage.")
def _golurk_plus120_if_ex_or_v(ctx):
    # Golurk (SV05) — 120+, +120 vs a Pokémon ex / Pokémon V defender.
    return ctx.base + (120 if _is_ex_or_v(ctx.defender) else 0)


@effect("If your opponent's Active Pokémon is affected by a Special Condition, this attack does 120 more damage.")
def _amoonguss_plus120_if_condition(ctx):
    # Amoonguss (BLK) — 30+, +120 if the defender is affected by a Special Condition.
    return ctx.base + (120 if _has_special_condition(ctx.defender) else 0)


@effect("If your opponent's Active Pokémon already has any damage counters on it, this attack does 80 more damage.")
def _larrys_rufflet_plus80_if_damaged(ctx):
    # Larry's Rufflet (ASH) — 20+, +80 if the defender already has any damage counters.
    return ctx.base + (80 if ctx.defender.damage > 0 else 0)


@effect("If your opponent's Active Pokémon has {F} Resistance, this attack does 50 more damage.")
def _boldore_plus50_if_fighting_resistance(ctx):
    # Boldore (WHT) — 30+, +50 vs a defender with {F} (Fighting) Resistance. Resistance isn't in the
    # card data model (see _defender_resistance), so this defaults off — never over-credits.
    return ctx.base + (50 if _defender_resistance(ctx.defender) == 'Fighting' else 0)


@effect("If the Retreat Cost of your opponent's Active Pokémon is {C}{C} or more, this attack does 110 more damage.")
def _talonflame_plus110_if_heavy_retreat(ctx):
    # Talonflame (SV07) — 110+, +110 if the defender's (effective) Retreat Cost is 2 or more.
    return ctx.base + (110 if ctx.defender.eff_retreat() >= 2 else 0)


@effect("If your opponent has 3 or fewer cards in their hand, this attack does 120 more damage.")
def _krookodile_plus120_if_small_hand(ctx):
    # Krookodile (BLK) — 120+, +120 if the opponent has 3 or fewer cards in hand.
    return ctx.base + (120 if len(ctx.opp.hand) <= 3 else 0)


@effect("If your opponent has 5 or fewer cards in their hand, this attack does 60 more damage.")
def _mienshao_plus60_if_small_hand(ctx):
    # Mienshao (SV07) — 30+, +60 if the opponent has 5 or fewer cards in hand.
    return ctx.base + (60 if len(ctx.opp.hand) <= 5 else 0)


@effect("If a Stadium is in play, this attack does 60 more damage.")
def _vivillon_plus60_if_stadium(ctx):
    # Vivillon (ME03) — 60+, +60 if a Stadium is in play (engine now tracks the Stadium via ctx.stadium()).
    return ctx.base + (60 if ctx.stadium() else 0)


# ================================================================ conditional "does nothing" gates

@effect("If your opponent's Active Pokémon isn't a Pokémon ex, this attack does nothing. This attack's damage isn't affected by Weakness or Resistance.")
def _sawk_ex_only(ctx):
    # Sawk (WHT) — [90] only vs a Pokémon ex defender, else nothing. (The "not affected by Weakness/
    # Resistance" rider is an engine-side concern; this layer just returns the base damage.)
    return ctx.base if ctx.defender.card.is_ex else 0


@effect("If your opponent's Active Pokémon has no damage counters on it before this attack does damage, this attack does nothing.")
def _basculin_needs_damaged(ctx):
    # Basculin (WHT) — [50] only if the defender already has damage counters (before this hit), else 0.
    return ctx.base if ctx.defender.damage > 0 else 0


# ================================================================ fixed base / cost / cross-turn gates

@effect("If this Pokémon is affected by a Special Condition, ignore all Energy in this attack's cost.")
def _conkeldurr_cost_ignore(ctx):
    # Conkeldurr (SV06) — [250] always; the "ignore all Energy in this attack's cost" clause is a COST
    # discount (resolved by the engine's cost check), so the damage number is unconditionally base.
    return ctx.base


@effect("During your opponent's next turn, if this Pokémon is damaged by an attack (even if this Pokémon is Knocked Out), put 6 damage counters on the Attacking Pokémon.")
def _bouffalant_retaliate(ctx):
    # Bouffalant (SV08) — [40] now; a reactive counter (60 to whoever damages this Pokémon next turn).
    # The engine has no damage-reaction hook (only Spiky Energy's fixed +20), so the retaliation is
    # unmodeled; the intent is recorded on the Mon for a future engine layer. Damage this turn = base.
    ctx.attacker.retaliate_counters = 6
    ctx.attacker.retaliate_turn = ctx.game.turn
    return ctx.base


@effect("If any of your Pokémon were Knocked Out by damage from an attack during your opponent's last turn, this attack does 160 more damage.")
def _krookodile_comeback(ctx):
    # Krookodile (ME02) — 60+, +160 comeback bonus when one of your Pokémon was KO'd on the opponent's
    # last turn (engine now records player.last_ko_turn, surfaced by ctx.ko_last_turn()).
    return ctx.base + (160 if ctx.ko_last_turn() else 0)


@effect("If you played Emma from your hand during this turn, this attack does 60 more damage.")
def _espurr_emma_bonus(ctx):
    # Espurr (ME04) — 10+, +60 if you played the Supporter "Emma" this turn (engine now records the
    # Trainer names played this turn in player.played, surfaced by ctx.played_this_turn(name)).
    return ctx.base + (60 if ctx.played_this_turn('Emma') else 0)
