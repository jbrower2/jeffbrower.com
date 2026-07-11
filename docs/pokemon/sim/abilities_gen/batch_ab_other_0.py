#!/usr/bin/env python3
"""Generated ability batch: ab_other_0 — the "other" bucket: abilities the kind_hint classifier
could not route (evolution-timing permissions, play/effect-prevention disruptions, prize denial,
KO reactions, and two genuine damage-modifiers).

Kinds were chosen by reading each text against the hook contracts in ability_effects.py:

  * passive_dr  fn(dmg, atk, dfn, dfn_owner, game) -> int — Kecleon's coin-prevent and Crustle's
    Sturdy are true incoming-damage modifiers, so they get the real DR hook.
  * on_damaged  fn(atk_mon, dfn_mon, dfn_owner, game) — Maractus (Exploding Needles) hits the
    attacker back on a KO; Shedinja (Fragile Husk) triggers on the same KO event but its effect
    (prize denial) has no engine hook, so it is a documented no-op under the trigger-matched kind.
  * immunity   fn(atk, dfn, dfn_owner, game) -> bool — the house convention (see batch_ab_immunity_0)
    for texts with NO engine mechanic: register as `immunity` returning False so they never grant
    damage immunity and never fire spuriously. Used here for evolution-timing permissions, hand-play
    and trainer-effect prevention, and opponent-event triggers (retreat / evolve) the engine can't
    observe. Each carries a comment naming the real effect and why it is unmodeled.
"""
from ability_effects import ability, ActivatedCtx  # noqa: F401 (ActivatedCtx per batch header convention)


# ============================================================ implemented: incoming-damage modifiers
# ---- Expert Hider (Kecleon SV08:#150/191) -------------------------------------------------------
# "If any damage is done to this Pokémon by attacks, flip a coin. If heads, prevent that damage."
# Coin-flip total prevention. Heads -> 0; tails -> unchanged. Mirrors effects.incoming_damage's own
# "flip a coin ... prevent that damage" branch (heads = rng.random() < 0.5).
@ability('passive_dr', "- If any damage is done to this Pokémon by attacks, flip a coin. If heads, prevent that damage.")
def _expert_hider(dmg, atk, dfn, dfn_owner, game):
    return 0 if game.rng.random() < 0.5 else dmg


# ---- Sturdy (Crustle BLK:#052/086) --------------------------------------------------------------
# "If this Pokémon has full HP and would be Knocked Out by damage from an attack, it is not Knocked
#  Out, and its remaining HP becomes 10."
# Only when currently undamaged (full HP) AND the post-Weakness hit would KO (dmg >= max_hp): cap the
# damage so remaining HP == 10 (i.e. deal max_hp - 10). Otherwise the hit is unchanged.
@ability('passive_dr', "- If this Pokémon has full HP and would be Knocked Out by damage from an attack, it is not Knocked Out, and its remaining HP becomes 10.")
def _sturdy(dmg, atk, dfn, dfn_owner, game):
    if dfn.damage == 0 and dmg >= dfn.max_hp:
        return dfn.max_hp - 10
    return dmg


# ============================================================ implemented: KO reaction
# ---- Exploding Needles (Maractus SV09:#008/159) -------------------------------------------------
# "If this Pokémon is in the Active Spot and is Knocked Out by damage from an attack from your
#  opponent's Pokémon, put 6 damage counters on the Attacking Pokémon."
# Fires only when the holder is the Active Pokémon AND the hit KO'd it (on_damaged runs after the
# damage is applied, before KO resolution, so is_ko already reflects the lethal hit). 6 counters = 60.
# Damage counters are applied raw (no effect_immune gate) per the on_damaged batch convention.
@ability('on_damaged', "- If this Pokémon is in the Active Spot and is Knocked Out by damage from an attack from your opponent's Pokémon, put 6 damage counters on the Attacking Pokémon.")
def _exploding_needles(atk_mon, dfn_mon, dfn_owner, game):
    if dfn_mon is dfn_owner.active and game.is_ko(dfn_mon, dfn_owner):
        atk_mon.damage += 60


# ============================================================ no-op: KO reaction with no effect hook
# ---- Fragile Husk (Shedinja ME01:#061/132) ------------------------------------------------------
# "If this Pokémon is Knocked Out by damage from an attack from your opponent's Pokémon ex, your
#  opponent can't take any Prize cards for it."
# Trigger is a KO (an on_damaged-natured event, parallel to Exploding Needles), but the effect is
# prize denial. The engine's _resolve_kos / _checkup award Prizes unconditionally with no
# per-Pokémon prize-denial hook, so there is nothing to write -> conservative documented no-op.
@ability('on_damaged', "- If this Pokémon is Knocked Out by damage from an attack from your opponent's Pokémon ex, your opponent can't take any Prize cards for it.")
def _fragile_husk(atk_mon, dfn_mon, dfn_owner, game):
    return None  # unmodeled: no prize-denial mechanism in the engine


# ============================================================ no-op: no engine mechanic (immunity/False)
# ---- Boosted Evolution (Eevee) ------------------------------------------------------------------
# "As long as this Pokémon is in the Active Spot, it can evolve during your first turn or the turn
#  you play it." Evolution-timing permission. evolve_all's "mon.turns < 1" gate is not ability-aware
#  and no evolution-timing hook exists -> no-op (never grants damage immunity).
@ability('immunity', "- As long as this Pokémon is in the Active Spot, it can evolve during your first turn or the turn you play it.")
def _boosted_evolution(atk, dfn, dfn_owner, game):
    return False


# ---- Food Prep (Crabominable, Veluza) -----------------------------------------------------------
# "Attacks used by this Pokémon cost {C} less for each Kofu card in your discard pile." Kofu is a
#  Supporter, absent from the Pokémon-only pool, so the count is always 0 (and attack-cost reduction
#  has no hook regardless: cost_met reads printed cost vs attached energy) -> no-op.
@ability('immunity', "- Attacks used by this Pokémon cost {C} less for each Kofu card in your discard pile.")
def _food_prep(atk, dfn, dfn_owner, game):
    return False


# ---- Potent Glare (Team Rocket's Arbok) ---------------------------------------------------------
# "As long as this Pokémon is in the Active Spot, your opponent can't play any Pokémon that has an
#  Ability from their hand, except for Team Rocket's Pokémon." A hand-play restriction (NOT an
#  ability lock — it never turns off abilities already in play). The AI benches/evolves without
#  consulting any such restriction and no hook exists -> no-op.
@ability('immunity', "- As long as this Pokémon is in the Active Spot, your opponent can't play any Pokémon that has an Ability from their hand, except for Team Rocket's Pokémon.")
def _potent_glare(atk, dfn, dfn_owner, game):
    return False


# ---- Holes (Team Rocket's Dugtrio) --------------------------------------------------------------
# "Whenever your opponent's Active Pokémon moves to the Bench during their turn, place 2 damage
#  counters on that Pokémon." Triggered off an opponent retreat/switch; the engine fires no hook when
#  an Active moves to the Bench -> no-op (unobservable trigger).
@ability('immunity', "- Whenever your opponent's Active Pokémon moves to the Bench during their turn, place 2 damage counters on that Pokémon.")
def _holes(atk, dfn, dfn_owner, game):
    return False


# ---- Darkest Impulse (Team Rocket's Ampharos) ---------------------------------------------------
# "Whenever your opponent plays a Pokémon from their hand to evolve 1 of their Pokémon, put 4 damage
#  counters on that Pokémon. The effect of Darkest Impulse doesn't stack." Triggered off an opponent
#  evolution; evolve_all fires no hook -> no-op (unobservable trigger).
@ability('immunity', "- Whenever your opponent plays a Pokémon from their hand to evolve 1 of their Pokémon, put 4 damage counters on that Pokémon. The effect of Darkest Impulse doesn't stack.")
def _darkest_impulse(atk, dfn, dfn_owner, game):
    return False


# ---- Glistening Bubbles (Azumarill) -------------------------------------------------------------
# "If you have any Tera Pokémon in play, this Pokémon can use the Double-Edge attack for {P}." The
#  Card model carries no Tera subtype and attack-cost substitution has no hook, so the condition is
#  unobservable -> no-op.
@ability('immunity', "- If you have any Tera Pokémon in play, this Pokémon can use the Double-Edge attack for {P}.")
def _glistening_bubbles(atk, dfn, dfn_owner, game):
    return False


# ---- Fighting Roar (Luxio) ----------------------------------------------------------------------
# "If your opponent's Active Pokémon is a Pokémon ex, this Pokémon can evolve during your first turn
#  or the turn you play it." Evolution-timing permission (conditioned on the opposing Active being an
#  ex); no evolution-timing hook -> no-op.
@ability('immunity', "- If your opponent's Active Pokémon is a Pokémon ex, this Pokémon can evolve during your first turn or the turn you play it.")
def _fighting_roar(atk, dfn, dfn_owner, game):
    return False


# ---- Stimulated Evolution (Karrablast) ----------------------------------------------------------
# "If you have Shelmet in play, this Pokémon can evolve during your first turn or the turn you play
#  it." Evolution-timing permission (conditioned on Shelmet in play); no evolution-timing hook -> no-op.
@ability('immunity', "- If you have Shelmet in play, this Pokémon can evolve during your first turn or the turn you play it.")
def _stimulated_evolution(atk, dfn, dfn_owner, game):
    return False


# ---- Startling Drop (Ferrothorn) ----------------------------------------------------------------
# "During your opponent's turn, if this Pokémon is discarded from your deck by an effect of an attack
#  or Ability from your opponent's Pokémon, or by an effect of your opponent's Item or Supporter
#  cards, discard the top 8 cards of your opponent's deck." The engine models no "discarded from deck
#  by an opponent effect" event -> no-op (unobservable trigger).
@ability('immunity', "- During your opponent's turn, if this Pokémon is discarded from your deck by an effect of an attack or Ability from your opponent's Pokémon, or by an effect of your opponent's Item or Supporter cards, discard the top 8 cards of your opponent's deck.")
def _startling_drop(atk, dfn, dfn_owner, game):
    return False


# ---- Unnerve (Fraxure) --------------------------------------------------------------------------
# "Whenever your opponent plays an Item or Supporter card from their hand, prevent all effects of
#  that card done to this Pokémon." The engine's Trainers apply global draw/search/gust/heal effects
#  and never a preventable harmful effect targeted at a specific opposing Pokémon, so there is nothing
#  to prevent -> no-op.
@ability('immunity', "- Whenever your opponent plays an Item or Supporter card from their hand, prevent all effects of that card done to this Pokémon.")
def _unnerve(atk, dfn, dfn_owner, game):
    return False
