#!/usr/bin/env python3
"""Generated ability batch: ab_lock_0.

Contains the "Damp" ability (Psyduck ASH:#039/217, Golduck ASH:#040/217) — a passive ability lock.
"""
from ability_effects import ability, ActivatedCtx  # noqa: F401 (ActivatedCtx per batch header convention)


# ---- Damp (Psyduck, Golduck) --------------------------------------------------------------------
# "Pokémon in play (both yours and your opponent's) lose any Ability that requires the Pokémon
#  using it to Knock Out itself."
#
# A lock: while this Pokémon is in play, every Pokémon on BOTH sides loses any Ability whose cost is
# to Knock its own user Out (e.g. the proof-batch Cursed Blast, and self-KO snipes/energy dumps like
# Dusclops/Magneton). It is unconditional and always-on — there is no Stadium/named-card/Tera
# dependency the engine lacks — and a lock query will only invoke a lock fn for a holder already in
# play (like every other `_entries`-based query, it iterates a player's mons; the lock query itself
# is not wired into the engine yet — see the batch's structured-output caveat). So the faithful
# signal is simply "this self-KO lock is active" -> return True whenever queried; firing here is
# correct, not an over-fire. The lock-query layer decides *which* victim abilities count as self-KO
# abilities (the "matching" in the hook contract) and that Damp hits BOTH sides, not just the
# opponent ("both yours and your opponent's"); this fn only reports that the Damp lock is in effect.
@ability('lock', "- Pokémon in play (both yours and your opponent's) lose any Ability that requires the Pokémon using it to Knock Out itself.")
def _damp(mon, owner, opp, game):
    return True
