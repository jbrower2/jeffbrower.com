#!/usr/bin/env python3
"""Generated ability batch: ab_immunity_0 — bench/attack damage-immunities, a sleep-lock, and two
disruption texts the engine has no mechanic for.

Kinds were chosen after reading each text against the hook contracts in ability_effects.py:

  * immunity  fn(atk, dfn, dfn_owner, game) -> bool  — True => this attack does 0 to `dfn`.
    is_immune() collects the immunity fns off every mon in dfn_owner.all_mons() and calls each with
    the CURRENT attack target as `dfn` (the holder Mon is NOT passed). So:
      - a *self*-only shield ("done to this Pokémon") must verify `dfn` is itself a holder — checked
        by matching the ability text on dfn.card — otherwise it would also shield benched teammates.
      - a *team-bench* shield ("done to your Benched Pokémon") just checks `dfn` is on the bench,
        because is_immune only ever calls it for the defender's own team.

  * between_turns for "can't be Asleep": there is no status-immunity hook, so the faithful
    approximation is to clear Asleep at every Pokémon Checkup — the mon is never left Asleep.

  * disruption texts with no engine mechanic (returning in-play Pokémon+cards to the opponent's hand;
    moving damage counters between Pokémon) are conservative no-ops registered under 'immunity'
    returning False — they never grant damage immunity and never fire spuriously.
"""
from ability_effects import ability, ActivatedCtx, normalize


def _has_ability(mon, norm_key):
    """True if `mon`'s card carries the ability whose normalized text == norm_key (i.e. mon is a holder)."""
    return any(normalize(a.get('text', '')) == norm_key for a in mon.card.abilities)


# 1) So Submerged (Misty's Magikarp) / Storehouse Hideaway (Poltchageist): self bench-shield -------
_SELF_BENCH = normalize(
    "- As long as this Pokémon is on your Bench, prevent all damage from and effects of attacks "
    "from your opponent's Pokémon done to this Pokémon.")


@ability('immunity',
         "- As long as this Pokémon is on your Bench, prevent all damage from and effects of attacks "
         "from your opponent's Pokémon done to this Pokémon.")
def _self_bench_shield(atk, dfn, dfn_owner, game):
    # Only the holder itself, and only while it is on the Bench.
    return dfn in dfn_owner.bench and _has_ability(dfn, _SELF_BENCH)


# 2) Insomnia (Hoothoot): the holder can't be Asleep ---------------------------------------------
@ability('between_turns', "- This Pokémon can't be Asleep.")
def _insomnia(mon, owner, game):
    mon.status.pop('Asleep', None)          # never left Asleep at Checkup (no status-immunity hook exists)


# 3) Mentally Calm (Milotic): opponent can't return their in-play Pokémon (+ attached cards) to hand
#    The engine models no "put a Pokémon in play (and its cards) into the hand" effect, so there is
#    nothing to prevent — conservative no-op (never grants damage immunity).
@ability('immunity',
         "- Your opponent's Pokémon in play and all attached cards can't be put into your opponent's hand.")
def _mentally_calm(atk, dfn, dfn_owner, game):
    return False


# 4) Flower Curtain (Shaymin): team bench-shield, but only for Pokémon WITHOUT a Rule Box ----------
@ability('immunity',
         "- Prevent all damage done to your Benched Pokémon that don't have a Rule Box by attacks "
         "from your opponent's Pokémon. (Pokémon ex, Pokémon V, etc. have Rule Boxes.)")
def _flower_curtain(atk, dfn, dfn_owner, game):
    # "don't have a Rule Box" ~= not an ex — the only Rule-Box marker present in this pool.
    return dfn in dfn_owner.bench and not dfn.card.is_ex


# 5) Watchful Eye (Patrat): damage counters can't be moved between Pokémon ------------------------
#    No counter-relocation mechanic exists (heals set mon.damage directly; nothing moves counters
#    from one Pokémon to another), so there is nothing to prevent — conservative no-op.
@ability('immunity',
         "- Damage counters on each Pokémon (both yours and your opponent's) can't be moved to other Pokémon.")
def _watchful_eye(atk, dfn, dfn_owner, game):
    return False


# 6) Spherical Shield (Rabsca): full team bench-shield -------------------------------------------
@ability('immunity',
         "- Prevent all damage from and effects of attacks from your opponent's Pokémon done to "
         "your Benched Pokémon.")
def _spherical_shield(atk, dfn, dfn_owner, game):
    return dfn in dfn_owner.bench
