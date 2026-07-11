# -*- coding: utf-8 -*-
"""Generated trainer-effect batch: tr_tool_2 (Pokémon Tools).

Faithful exact-text implementation for 1 Pokémon Tool card.

Notation note: the on-card energy symbols use {G}=Grass, {R}=Fire, {W}=Water, {L}=Lightning,
and {N}=Dragon (D already denotes Darkness, so Dragon is written {N}). "Thick Scale" is therefore
a Dragon-only defensive Tool that walls the four "physical" attacking types.
"""
from trainer_effects import trainer, TrainerCtx  # noqa: F401 (TrainerCtx kept for uniform import)


# Attacker types the Tool defends against ({G}/{R}/{W}/{L}).
_TRIGGER_TYPES = ('Grass', 'Fire', 'Water', 'Lightning')


@trainer(
    'tool_dr',
    "The {N} Pokémon this card is attached to takes 50 less damage from attacks from your "
    "opponent's {G}, {R}, {W}, or {L} Pokémon (after applying Weakness and Resistance).",
)
def _thick_scale(dmg, atk, dfn, dfn_owner, game):
    """Thick Scale — the holder takes 50 less damage from an opponent's Grass/Fire/Water/Lightning
    attacker. Reduction is applied after Weakness/Resistance (the caller passes post-W/R `dmg`)."""
    # "{N} Pokémon this card is attached to": only functions while attached to a Dragon Pokémon.
    if dfn is None or getattr(dfn.card, 'ptype', None) != 'Dragon':
        return dmg
    # Only reduces damage from the opponent's {G}/{R}/{W}/{L} Pokémon; any other attacker type is
    # unaffected. If there is no identifiable attacker, do nothing (conservative — never fire blind).
    if atk is None or getattr(atk.card, 'ptype', None) not in _TRIGGER_TYPES:
        return dmg
    return max(0, dmg - 50)
