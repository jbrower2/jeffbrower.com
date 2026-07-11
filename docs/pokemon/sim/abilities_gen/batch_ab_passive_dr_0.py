#!/usr/bin/env python3
"""Generated ability batch: ab_passive_dr_0 — passive damage-reduction (DR) auras.

Each fn has the passive_dr hook signature  fn(dmg, atk, dfn, dfn_owner, game) -> int  and returns the
reduced incoming damage (raw `dmg - N`; the registry's reduce_damage() clamps the final result at 0).
The registry only ever invokes a DR fn for an ability that is on a Pokémon actually in play, so mere
"is this source in play" never needs re-checking here — only the ability's own extra conditions
(attacker type, holder position, protected family) do.
"""
from ability_effects import ability, ActivatedCtx  # noqa: F401 (ActivatedCtx per batch header convention)


def _has_ability(mon, name):
    """True if `mon` carries the named ability (used to locate an aura's holder on the board)."""
    return mon is not None and any(ab.get('name') == name for ab in mon.card.abilities)


# ---- Thick Fat (Dewgong ME02:#022/094) ----------------------------------------------------------
# "This Pokémon takes 30 less damage from attacks from your opponent's {R} or {W} Pokémon (after
#  applying Weakness and Resistance)."
#
# Self-DR gated on the ATTACKER's on-card type: -30 only when the attacking Pokémon is Fire ({R}) or
# Water ({W}). Any other type -> no reduction. atk.card.ptype is the single on-card type string.
@ability('passive_dr', "- This Pokémon takes 30 less damage from attacks from your opponent's {R} or {W} Pokémon (after applying Weakness and Resistance).")
def _thick_fat(dmg, atk, dfn, dfn_owner, game):
    if atk is not None and atk.card.ptype in ('Fire', 'Water'):
        return dmg - 30
    return dmg


# ---- Protective Bell (Bronzong PRE:#067/131) ----------------------------------------------------
# "All of your Pokémon take 10 less damage from attacks from your opponent's Pokémon (after applying
#  Weakness and Resistance)."
#
# Team-wide flat DR with no positional condition on Bronzong (works from Active or Bench). In the DR
# hook the defender is always one of dfn_owner's Pokémon and the attacker is always the opponent's, so
# the aura's condition is inherently satisfied every time it is queried -> flat -10. Has no
# "doesn't stack" clause, so multiple Bronzong correctly stack when the query iterates per-holder.
@ability('passive_dr', "- All of your Pokémon take 10 less damage from attacks from your opponent's Pokémon (after applying Weakness and Resistance).")
def _protective_bell(dmg, atk, dfn, dfn_owner, game):
    return dmg - 10


# ---- Gloomy Garbage (Garbodor ME04:#057/086) ----------------------------------------------------
# "Attacks used by your opponent's Active Pokémon that has a Pokémon Tool attached do 20 less damage
#  (before applying Weakness and Resistance)."
#
# The reduction is gated on the ATTACKER (the opponent's Active Pokémon) having a Pokémon Tool
# attached. Pokémon Tools are now persisted on the Mon (`mon.tools`), so shave 20 exactly when the
# attacker carries at least one Tool — nothing otherwise.
@ability('passive_dr', "- Attacks used by your opponent's Active Pokémon that has a Pokémon Tool attached do 20 less damage (before applying Weakness and Resistance).")
def _gloomy_garbage(dmg, atk, dfn, dfn_owner, game):
    if atk is not None and atk.tools:
        return dmg - 20
    return dmg


# ---- Intimidating Fang (Pyroar ME01:#024/132) ---------------------------------------------------
# "As long as this Pokémon is in the Active Spot, attacks used by your opponent's Active Pokémon do
#  30 less damage (before applying Weakness and Resistance)."
#
# DR that is live only while the holder (Pyroar) is the defender-owner's Active Pokémon. The attacker
# is always the opponent's Active in this engine, so no extra attacker check is needed — just confirm
# a holder is in the Active Spot on the defending side. -30 while active; nothing while it is benched.
@ability('passive_dr', "- As long as this Pokémon is in the Active Spot, attacks used by your opponent's Active Pokémon do 30 less damage (before applying Weakness and Resistance).")
def _intimidating_fang(dmg, atk, dfn, dfn_owner, game):
    if _has_ability(dfn_owner.active, 'Intimidating Fang'):
        return dmg - 30
    return dmg


# ---- Stone Palace (Steven's Carbink SV10:#086/182) ----------------------------------------------
# "As long as this Pokémon is on your Bench, all of your Steven's Pokémon take 30 less damage from
#  attacks from your opponent's Pokémon (after applying Weakness and Resistance). The effect of Stone
#  Palace doesn't stack."
#
# Team aura restricted to the "Steven's" family, live only while a Stone Palace holder (Carbink) is on
# the defending side's Bench. Only your Steven's Pokémon benefit. "Doesn't stack" is honored by
# applying a single flat -30 for the presence of any benched holder (not once per Carbink).
@ability('passive_dr', "- As long as this Pokémon is on your Bench, all of your Steven's Pokémon take 30 less damage from attacks from your opponent's Pokémon (after applying Weakness and Resistance). The effect of Stone Palace doesn't stack.")
def _stone_palace(dmg, atk, dfn, dfn_owner, game):
    if not dfn.card.name.startswith("Steven's"):
        return dmg
    if any(_has_ability(m, 'Stone Palace') for m in dfn_owner.bench):
        return dmg - 30
    return dmg
