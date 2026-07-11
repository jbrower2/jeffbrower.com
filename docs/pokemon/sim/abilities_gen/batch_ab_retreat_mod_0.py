#!/usr/bin/env python3
"""Batch ab_retreat_mod_0 — retreat-cost-modifying abilities.

All three are `retreat_mod`: fn(mon, owner, game) -> int, a delta to `mon`'s retreat cost, where
`mon` is the Pokémon whose retreat is being computed (-99 is the free-retreat sentinel).

- Agile (Charmander): self-referential — free retreat while it has no Energy attached. Fully
  engine-usable today (the holder IS the affected mon, so the holder-only retreat_delta query reaches it).
- Big Net (Ariados) / Secret Forest Path (Toedscruel): AURAS that modify a DIFFERENT Pokémon's retreat
  (the opponent's Active / your own Active). The current `retreat_delta` query is holder-only
  (`_entries(mon, ...)`, unlike hp_bonus/is_immune which scan every mon), so it only invokes these on
  the ability holder. They are written from the AFFECTED mon's perspective — they fire only under the
  exact printed condition and never return a wrong value on the holder, so they are correct-or-dormant
  today and become fully live once the engine scans in-play retreat auras the way it scans passive_hp.
"""
from ability_effects import ability, ActivatedCtx, normalize  # noqa: F401  (ActivatedCtx: prescribed header)

_BIG_NET = normalize("- Your opponent's Active Evolution Pokémon's Retreat Cost is {C} more.")
_SECRET_FOREST_PATH = normalize(
    "- As long as this Pokémon is on your Bench, your Active Pokémon's Retreat Cost is {C}{C} less.")


def _has_ability(mon, key):
    return any(normalize(ab.get('text', '')) == key for ab in mon.card.abilities)


@ability('retreat_mod', "- If this Pokémon has no Energy attached, it has no Retreat Cost.")
def _agile(mon, owner, game):
    # No Energy attached => no Retreat Cost. total_energy() also counts special energy (it increments
    # mon.energy on attach), so any attached energy of any kind cancels the free retreat.
    return -99 if mon.total_energy() == 0 else 0


@ability('retreat_mod', "- Your opponent's Active Evolution Pokémon's Retreat Cost is {C} more.")
def _big_net(mon, owner, game):
    # +{C} per Big Net Pokémon the opponent has in play, to the retreat of the Big Net holder's
    # opponent's Active Evolution Pokémon. From the affected mon's view: mon is owner's Active AND an
    # Evolution (stage>=1) AND owner's opponent has Big Net Pokémon in play (no location clause on the
    # holder -> anywhere in play). Multiple instances stack ({C} each), like any continuous TCG ability.
    if mon is not getattr(owner, 'active', None) or mon.card.stage < 1:
        return 0
    players = getattr(game, 'players', None)
    if not players:
        return 0
    opp = next((p for p in players if p is not owner), None)
    if opp is None:
        return 0
    return sum(1 for m in opp.all_mons() if _has_ability(m, _BIG_NET))


@ability('retreat_mod',
         "- As long as this Pokémon is on your Bench, your Active Pokémon's Retreat Cost is {C}{C} less.")
def _secret_forest_path(mon, owner, game):
    # -{C}{C} per Secret-Forest-Path Pokémon on the holder's own Bench, to that holder's Active Pokémon.
    # From the affected mon's view: mon is owner's Active AND owner has SFP holder(s) benched (the printed
    # "on your Bench" clause). Multiple benched SFP holders stack ({C}{C} each).
    if mon is not getattr(owner, 'active', None):
        return 0
    return -2 * sum(1 for m in getattr(owner, 'bench', []) if _has_ability(m, _SECRET_FOREST_PATH))
