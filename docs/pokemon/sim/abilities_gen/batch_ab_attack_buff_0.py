#!/usr/bin/env python3
"""Batch ab_attack_buff_0 — offensive "attacks do N more damage" abilities.

All five register as kind 'attack_buff':  fn(atk_mon, dfn_mon, attack, game) -> int
extra pre-Weakness damage the attack deals. Two shapes:

  * SELF buffs ("attacks used by this Pokemon ...") — Seviper's Excited Power and
    Galvantula's Compound Eyes. The registry query (`attack_bonus`) only invokes an
    attack_buff fn for the ATTACKER's own abilities, so the self scope is exact; the
    fn only has to evaluate the printed condition (a board state / the defender).

  * TEAM buffs ("attacks used by your {X} Pokemon ...") — Victini, Lilligant, Garganacl.
    Keyed on the ATTACKER's on-card type/stage, never firing for a Pokemon that does not
    match the printed type. This is correct whether the engine keeps the attacker-own-
    abilities query (buffs the holder when it matches its own criterion — e.g. Grass
    Lilligant / Fighting Garganacl buff themselves; Basic Victini, not an Evolution, is a
    no-op on its own attack) or is later extended to iterate team sources and call each
    source's fn with the real attacker (full propagation to matching teammates). The
    "for each source in play" stacking and the "your side" scope are the engine's job.
"""
from ability_effects import ability, ActivatedCtx


def _owner_of(mon, game):
    """The Player whose in-play Pokemon include `mon` (or None if not found / no players)."""
    for p in getattr(game, 'players', None) or ():
        if mon in p.all_mons():
            return p
    return None


# Seviper — Excited Power: self +120, gated on a Darkness Mega-Evolution ex on your board.
@ability('attack_buff', "- If you have any {D} Mega Evolution Pokémon ex in play, attacks used by this Pokémon do 120 more damage to your opponent's Active Pokémon (before applying Weakness and Resistance).")
def _excited_power(atk_mon, dfn_mon, attack, game):
    owner = _owner_of(atk_mon, game)
    if owner and any(m.card.name.startswith('Mega ') and m.card.is_ex and m.card.ptype == 'Darkness'
                     for m in owner.all_mons()):
        return 120
    return 0


# Victini — Victory Cheer: your Evolution {R} (Fire, Stage 1+) Pokemon +10.
@ability('attack_buff', "- Attacks used by your Evolution {R} Pokémon do 10 more damage to your opponent's Active Pokémon (before applying Weakness and Resistance).")
def _victory_cheer(atk_mon, dfn_mon, attack, game):
    c = atk_mon.card
    return 10 if (c.stage > 0 and c.ptype == 'Fire') else 0


# Lilligant — Sunny Day: your {G} and {R} (Grass or Fire) Pokemon +20.
@ability('attack_buff', "- Attacks used by your {G} Pokémon and {R} Pokémon do 20 more damage to your opponent's Active Pokémon (before applying Weakness and Resistance).")
def _sunny_day(atk_mon, dfn_mon, attack, game):
    return 20 if atk_mon.card.ptype in ('Grass', 'Fire') else 0


# Galvantula — Compound Eyes: self +50, only when the defender has an Ability.
@ability('attack_buff', "- Attacks used by this Pokémon do 50 more damage to your opponent's Active Pokémon that has an Ability (before applying Weakness and Resistance).")
def _compound_eyes(atk_mon, dfn_mon, attack, game):
    return 50 if (dfn_mon is not None and dfn_mon.card.abilities) else 0


# Garganacl — Powerful a-Salt: your {F} (Fighting) Pokemon +30.
@ability('attack_buff', "- Attacks used by your {F} Pokémon do 30 more damage to your opponent's Active Pokémon (before applying Weakness and Resistance).")
def _powerful_a_salt(atk_mon, dfn_mon, attack, game):
    return 30 if atk_mon.card.ptype == 'Fighting' else 0
