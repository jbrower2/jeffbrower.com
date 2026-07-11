# -*- coding: utf-8 -*-
"""Generated trainer-effect batch: tr_stadium_1 (12 Stadiums).

Faithful exact-text implementations, registered by exact text via @trainer('stadium', text).
A Stadium action fn takes a TrainerCtx and returns True if the "Once during each player's turn,
that player may ..." OPTIONAL action did something (its presence on the board is game.stadium).

SIX of these Stadiums are PURELY PASSIVE — continuous board modifiers with NO once-per-turn
optional action (no "Once during each player's turn, may ..." clause). The stadium-action hook
cannot express a continuous modifier, so those are registered as conservative NO-OPS (return
False). Their passive effect is applied elsewhere by Stadium name (game.stadium — see
attack_effects.stadium() / effects.py) when the registry is integrated, not through this hook.
Each is noted individually below.

Model reminders (see engine.py):
  - Hand/deck tokens: ('P', Card) | ('E', basic_type_str) | ('T', trainer_dict) | ('S', special_dict).
  - Top of deck == END of the deck list; player.draw() does deck.pop().
  - Discarded basic energy -> player.disc_energy (a Counter); every other card -> player.discard.
  - card.ptype is the on-card type string: 'Water' == {W}, 'Psychic' == {P}, 'Darkness' == {D}, etc.
"""
from trainer_effects import trainer, TrainerCtx


# ---------------- shared helpers ----------------
def _tok_priority(tok):
    """Generic 'how useful to keep' ranking; when we must discard, we drop the lowest first."""
    k = tok[0]
    if k == 'P':
        return 4 if tok[1].stage == 0 else 3      # a Basic can hit the board immediately
    if k in ('E', 'S'):
        return 2
    return 1                                       # Trainers are situational


def _discard_token(me, tok):
    """Send a hand card to the correct discard store (basic energy -> disc_energy Counter)."""
    if tok[0] == 'E':
        me.disc_energy[tok[1]] += 1
    else:
        me.discard.append(tok)


# The "Team Rocket's" *Supporters* in the pool (deckgen/trainers.json). Team Rocket's Factory draws
# only when a played card is a SUPPORTER with "Team Rocket" in its name — NOT a Team Rocket's Item
# (Bother-Bot, Great Ball, Transceiver, Venture Bomb), Tool (Hypnotizer), or Stadium (Factory itself,
# Watchtower), all of whose names ALSO contain "Team Rocket" and get logged into me.played when played
# (engine play_trainers). me.played records names only (no trainerType), so we match this explicit set
# rather than a bare "Team Rocket" substring, which would over-trigger (incl. the Factory on itself).
_TR_SUPPORTERS = frozenset({
    "Team Rocket's Archer", "Team Rocket's Ariana", "Team Rocket's Giovanni",
    "Team Rocket's Petrel", "Team Rocket's Proton",
})


# ================================================================ ACTION STADIUMS
# (each grants a real "Once during each player's turn, that player may ..." optional action)

@trainer('stadium', "Once during each player's turn, that player may search their deck for a Basic Pokémon and put it onto their Bench. Then, that player shuffles their deck. If a player searches their deck in this way, their turn ends.")
def _lumiose_city(t):
    # NOTE: the "their turn ends" drawback is NOT modeled (the stadium-action contract has no
    # turn-end signal); only the beneficial Basic-to-Bench search is applied. This makes the
    # action look like pure card advantage, so the integrator must gate its use accordingly.
    got = t.search_pokemon(lambda c: True, 1, to_bench=True)   # to_bench enforces stage==0 & bench<5
    if got:
        t.rng.shuffle(t.me.deck)
    return got > 0


@trainer('stadium', "Once during each player's turn, that player may discard an Energy card from their hand in order to draw cards until they have as many cards in their hand as they have {P} Pokémon in play.")
def _mystery_garden(t):
    me = t.me
    energy = next((x for x in me.hand if x[0] in ('E', 'S')), None)   # cost: discard 1 Energy card
    if energy is None:
        return False
    target = sum(1 for m in me.all_mons() if m.card.ptype == 'Psychic')   # your {P} Pokémon in play
    # After paying the cost the hand is len-1; we draw up to `target`. Only fire if that draws >=1
    # (target >= current hand size) so the action never just discards an Energy for nothing.
    if target - (len(me.hand) - 1) < 1 or not me.deck:
        return False
    me.hand.remove(energy)
    _discard_token(me, energy)
    while len(me.hand) < target and me.deck:
        me.draw(1)
    return True


@trainer('stadium', "Once during each player's turn, that player may discard 2 cards from their hand in order to draw a card.")
def _prism_tower(t):
    me = t.me
    if len(me.hand) < 2 or not me.deck:          # need 2 to pay, and a card to draw
        return False
    order = sorted(range(len(me.hand)), key=lambda i: _tok_priority(me.hand[i]))   # least useful first
    for i in sorted(order[:2], reverse=True):    # pop the 2 lowest-priority cards (high->low index)
        _discard_token(me, me.hand.pop(i))
    me.draw(1)
    return True


@trainer('stadium', "Once during each player's turn, that player may search their deck for a Marnie's Pokémon, reveal it, and put it into their hand. Then, that player shuffles their deck.")
def _spikemuth_gym(t):
    got = t.search_pokemon(lambda c: c.name.startswith("Marnie's"), 1)
    if got:
        t.rng.shuffle(t.me.deck)
    return got > 0


@trainer('stadium', "Once during each player's turn, that player may switch their Active {W} Pokémon with 1 of their Benched {W} Pokémon.")
def _surfing_beach(t):
    me = t.me
    if not me.active or me.active.card.ptype != 'Water':
        return False
    wbench = [(i, m) for i, m in enumerate(me.bench) if m.card.ptype == 'Water']
    if not wbench:
        return False
    idx, chosen = max(wbench, key=lambda im: (im[1].total_energy(), im[1].card.hp))   # readiest {W}
    old = me.active
    me.active = me.bench.pop(idx)
    me.bench.append(old)
    me.active.came_from_bench = True
    return True


@trainer('stadium', "Once during each player's turn, if they played a Supporter card that has \"Team Rocket\" in its name from their hand this turn, they may draw 2 cards.")
def _team_rockets_factory(t):
    # me.played is a list of Trainer NAMES played this turn (no type recorded) and includes Items,
    # Tools and Stadiums — including "Team Rocket's Factory"/"...Watchtower" themselves, whose names
    # contain "Team Rocket". A bare substring test would self-trigger off the Factory Stadium and off
    # any Team Rocket's Item, so match the explicit "Team Rocket's" *Supporter* set to honor the
    # text's "Supporter card" qualifier.
    if any(nm in _TR_SUPPORTERS for nm in t.me.played):
        t.draw(2)
        return True
    return False


# ================================================================ PASSIVE STADIUMS (no-op actions)
# Continuous modifiers with NO once-per-turn action -> registered as no-ops (return False). The
# passive effect is applied by Stadium name when integrated, not through this action hook.

@trainer('stadium', "N's Pokémon in play (both yours and your opponent's) have no Retreat Cost.")
def _ns_castle(t):
    # PASSIVE: zeroes Retreat Cost for the "N's" named family on both sides. No per-turn action;
    # would be a name-based override of Mon.eff_retreat() for N's Pokémon while this Stadium is out.
    return False


@trainer('stadium', "Attacks used by each Tera Pokémon in play (both yours and your opponent's) cost {C} more.")
def _nighttime_mine(t):
    # PASSIVE + out-of-scope mechanic: the engine/pool has no Tera Pokémon, so this modifies
    # nothing even if hooked. Doubly a no-op.
    return False


@trainer('stadium', "During Pokémon Checkup, put 2 more damage counters on each Poisoned non-{D} Pokémon (both yours and your opponent's).")
def _perilous_jungle(t):
    # PASSIVE: a Pokémon-Checkup hook (extra +20 poison damage to Poisoned non-Darkness Pokémon on
    # both sides). Not a once-per-turn action; would live in Game._checkup(), not here.
    return False


@trainer('stadium', "Attacks used by Hop's Pokémon (both yours and your opponent's) do 30 more damage to the opponent's Active Pokémon (before applying Weakness and Resistance).")
def _postwick(t):
    # PASSIVE: a name-based team attack buff (+30) for the "Hop's" family on both sides. Not an
    # action; would be an effects.team_attack_bonus contribution gated on this Stadium being out.
    return False


@trainer('stadium', "Whenever any player puts a Basic non-{D} Pokémon onto their Bench during their turn, place 2 damage counters on that Pokémon.")
def _risky_ruins(t):
    # PASSIVE: a bench-placement trigger (+20 damage to each Basic non-Darkness Pokémon newly
    # benched, both sides). Not a once-per-turn action; would hook wherever Mons are benched.
    return False


@trainer('stadium', "{C} Pokémon in play (both yours and your opponent's) have no Abilities.")
def _team_rockets_watchtower(t):
    # PASSIVE: an ability-lock for {C} (Colorless) Pokémon on both sides. Not an action; would be a
    # name-based extension of ability_effects.abilities_disabled while this Stadium is out.
    return False
