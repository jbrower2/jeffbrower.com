#!/usr/bin/env python3
"""Batch: ab_on_damaged_0 — "when I'm damaged, hit back" reactions (all `on_damaged`).

Hook: fn(atk_mon, dfn_mon, dfn_owner, game). The engine fires these on the DAMAGED Pokémon
(`dfn_mon`) right after an opponent's attack deals damage and BEFORE KO resolution — so the
printed "(even if this Pokémon is Knocked Out)" clause is covered for free: `dfn_mon` is still
in the Active Spot at this moment, so `dfn_mon is dfn_owner.active` holds even on a lethal hit.

Convention (matches the proof batch + attack_effects.py):
  * Special Conditions inflicted on the Attacking Pokémon respect `atk_mon.effect_immune()`
    (Mist / Rocky Fighting / Bubbly Water shields) — like Poison Point.
  * Damage counters and energy discard do NOT check effect_immune (the engine applies raw
    damage counters and energy removal without that gate).

Engine gap: Spiritomb's Spiteful Swirl keys off "your Active {D} Pokémon" being damaged even
while Spiritomb is BENCHED, but the on_damaged query only fires the *damaged* mon's own
abilities. So it is modeled only when Spiritomb itself is the Active (Darkness) mon that is
damaged; the benched-Spiritomb-guards-another-{D}-attacker case can't fire under this hook.
"""
from ability_effects import ability, ActivatedCtx


def _attacker_owner(game, dfn_owner):
    """The Player who owns the Attacking Pokémon (opponent of dfn_owner). None if unavailable
    (e.g. the lightweight test kit builds a Game without a `players` list)."""
    players = getattr(game, 'players', None)
    if players and len(players) == 2 and dfn_owner in players:
        return players[0] if players[1] is dfn_owner else players[1]
    return None


# ---------------------------------------------------------------- damage-counter counterattacks
@ability('on_damaged', "- If this Pokémon is in the Active Spot and is damaged by an attack from your opponent's Pokémon (even if this Pokémon is Knocked Out), put 3 damage counters on the Attacking Pokémon.")
def _counterattack_3(atk_mon, dfn_mon, dfn_owner, game):
    # Bruxish (Counterattack) / Iron Jugulis (Automated Combat): 3 counters = 30 damage.
    if dfn_mon is dfn_owner.active:
        atk_mon.damage += 30


@ability('on_damaged', "- If your Active {D} Pokémon is damaged by an attack from your opponent's Pokémon (even if your Active {D} Pokémon is Knocked Out), place 1 damage counter on the Attacking Pokémon.")
def _spiteful_swirl(atk_mon, dfn_mon, dfn_owner, game):
    # Spiritomb: fires when the Active Darkness Pokémon is damaged. Under this hook that means
    # Spiritomb itself is Active (see module note). 1 counter = 10 damage.
    if dfn_mon is dfn_owner.active and getattr(dfn_mon.card, 'ptype', None) == 'Darkness':
        atk_mon.damage += 10


# ---------------------------------------------------------------- condition on the attacker
@ability('on_damaged', "- If this Pokémon is in the Active Spot and is damaged by an attack from your opponent's Pokémon (even if this Pokémon is Knocked Out), the Attacking Pokémon is now Burned.")
def _incandescent_body(atk_mon, dfn_mon, dfn_owner, game):
    # Numel (Incandescent Body). Burned is a Special Condition -> respect the attacker's shields.
    if dfn_mon is dfn_owner.active and not atk_mon.effect_immune():
        atk_mon.status['Burned'] = True


# ---------------------------------------------------------------- energy discard off the attacker
@ability('on_damaged', "- If this Pokémon is in the Active Spot and is damaged by an attack from your opponent's Pokémon (even if this Pokémon is Knocked Out), discard an Energy from the Attacking Pokémon.")
def _shell_spikes(atk_mon, dfn_mon, dfn_owner, game):
    # Turtonator (Shell Spikes): remove one energy pip from the attacker. Route a basic-type pip
    # to the attacker's discard (special-energy pseudo-types 'Wild'/'Colorless' aren't tracked in
    # disc_energy, matching attack_effects._pull_energy).
    if dfn_mon is not dfn_owner.active:
        return
    atk_owner = _attacker_owner(game, dfn_owner)
    for t in list(atk_mon.energy):
        if atk_mon.energy[t] > 0:
            atk_mon.energy[t] -= 1
            if atk_mon.energy[t] <= 0:
                del atk_mon.energy[t]
            if atk_owner is not None and t not in ('Wild', 'Colorless'):
                atk_owner.disc_energy[t] += 1
            return


# ---------------------------------------------------------------- search own deck -> bench
@ability('on_damaged', '- If this Pokémon is in the Active Spot and is damaged by an attack from your opponent\'s Pokémon (even if this Pokémon is Knocked Out), search your deck for up to 2 Pokémon that have "Koffing" in their name and put them onto your Bench. Then, shuffle your deck.')
def _smog_signals(atk_mon, dfn_mon, dfn_owner, game):
    # Team Rocket's Koffing (Smog Signals): bench up to 2 "Koffing"-named basics from your deck.
    # (All Koffing printings are Basic, so the Basic-only bench helper covers them.)
    if dfn_mon is not dfn_owner.active:
        return
    game._search_basics_to_bench(dfn_owner, lambda c: 'Koffing' in c.name, 2)
    game.rng.shuffle(dfn_owner.deck)
