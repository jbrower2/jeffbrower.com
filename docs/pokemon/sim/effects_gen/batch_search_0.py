#!/usr/bin/env python3
"""Effect batch: search_0.

Deck-search attacks. Four mechanical families, all ending in "Then, shuffle your deck.":
  1. put Basic Pokémon (optionally a named subset) onto the Bench,
  2. search cards (Pokémon / Energy / Supporter / Item / Tool / Stadium / any) into hand,
  3. search Basic Energy of a given type out of the deck and ATTACH it (to this Pokémon,
     to one Benched Pokémon, or spread across your Pokémon),
  4. search a card that evolves from a Pokémon and evolve it in place (this Pokémon,
     every Benched Pokémon, or up to 2 of your {D} Pokémon).

Each effect returns the printed base damage (ctx.base — 0 for the pure-utility attacks,
but non-zero for Team Rocket's Pupitar [30], Quilladin [20], Noctowl [70]) after doing
the search side effect. Searches reuse the engine's deck helpers (search-from-the-end of
the already-shuffled deck), then re-shuffle to honour the card text. "If you go first,
you can use this attack during your first turn" is a turn-legality clause the engine's
turn loop enforces, not a damage condition, so those effects mirror their unprefixed twin.
"""
from attack_effects import effect, EffectCtx, STATUSES
from engine import Mon, L2T

ALL_BASIC_TYPES = ['Grass', 'Fire', 'Water', 'Lightning', 'Psychic', 'Fighting', 'Darkness', 'Metal']


# ---------------------------------------------------------------- helpers

def _shuffle(ctx):
    """Re-shuffle the searching player's deck (no-op under the scripted test RNG)."""
    ctx.rng.shuffle(ctx.me.deck)


def _to_hand(ctx, pred, n):
    """Search up to n deck tokens matching `pred` (token -> bool) into the attacker's hand."""
    return ctx.game._search_deck_to_hand(ctx.me, pred, n)


def _to_bench(ctx, cardpred, n):
    """Search up to n Basic Pokémon (card -> bool) onto the attacker's Bench (engine caps at 5)."""
    return ctx.game._search_basics_to_bench(ctx.me, cardpred, n)


def _pull_energy_to(ctx, target, etype, n):
    """Remove up to n ('E', etype) basic-energy tokens from deck and attach each to `target`.
    Returns the number actually attached (fewer if the deck runs out)."""
    me = ctx.me
    got = 0
    i = len(me.deck) - 1
    while i >= 0 and got < n:
        tok = me.deck[i]
        if tok[0] == 'E' and tok[1] == etype:
            me.deck.pop(i)
            target.energy[etype] += 1
            got += 1
        i -= 1
    return got


def _find_evo_idx(player, mon):
    """Deck index of a Pokémon card that evolves from `mon` (name + exactly one stage up), or None."""
    for i in range(len(player.deck) - 1, -1, -1):
        tok = player.deck[i]
        if tok[0] == 'P' and tok[1].evolves_from == mon.card.name and tok[1].stage == mon.card.stage + 1:
            return i
    return None


def _evolve_in_place(player, mon, evo_card):
    """Replace `mon` (Active or Bench) with its evolution, carrying over all in-play state."""
    ev = Mon(evo_card)
    ev.damage = mon.damage
    ev.energy = mon.energy
    ev.turns = mon.turns
    ev.came_from_bench = mon.came_from_bench
    ev.cd_name = mon.cd_name
    ev.cd_turn = mon.cd_turn
    ev.status = mon.status
    ev.poison_amt = mon.poison_amt
    ev.dr_amount = mon.dr_amount
    ev.dr_turn = mon.dr_turn
    ev.special = mon.special
    ev.ramp = mon.ramp
    if mon is player.active:
        player.active = ev
    else:
        player.bench[player.bench.index(mon)] = ev
    return ev


def _evolve_search(player, mon):
    """Search the deck for a card that evolves from `mon` and evolve it in place. Returns the new
    Mon, or None if nothing in the deck evolves from it (attack-driven, so the turn-timing rule
    that normally blocks same-turn evolution does not apply)."""
    idx = _find_evo_idx(player, mon)
    if idx is None:
        return None
    evo_card = player.deck.pop(idx)[1]
    return _evolve_in_place(player, mon, evo_card)


def _move_one_energy(src, dst):
    """Move a single energy pip from `src` to `dst`, preferring a real basic-type pip over the
    Wild/Colorless pseudo-types. Returns True iff an energy was moved."""
    order = ([t for t in src.energy if t not in ('Wild', 'Colorless')]
             + [t for t in src.energy if t in ('Wild', 'Colorless')])
    for t in order:
        if src.energy[t] > 0:
            src.energy[t] -= 1
            if src.energy[t] <= 0:
                del src.energy[t]
            dst.energy[t] += 1
            return True
    return False


def _bench_target(ctx):
    """Choose '1 of your Benched Pokémon' to receive energy: the ace if it is benched, else the
    benched Pokémon closest to attacking (most energy). None if the Bench is empty."""
    bench = ctx.me.bench
    if not bench:
        return None
    ace = ctx.game.primary(ctx.me)
    return ace if ace in bench else max(bench, key=lambda m: m.total_energy())


# ================================================================ put Basic Pokémon on Bench

@effect("Search your deck for up to 2 Basic Pokémon and put them onto your Bench. Then, shuffle your deck.")
def _bench_2_basic(ctx):
    _to_bench(ctx, lambda c: True, 2)
    _shuffle(ctx)
    return ctx.base


@effect("Search your deck for a Basic Pokémon and put it onto your Bench. Then, shuffle your deck.")
def _bench_1_basic(ctx):
    _to_bench(ctx, lambda c: True, 1)
    _shuffle(ctx)
    return ctx.base


@effect("Search your deck for up to 3 Basic Pokémon and put them onto your Bench. Then, shuffle your deck.")
def _bench_3_basic(ctx):
    _to_bench(ctx, lambda c: True, 3)
    _shuffle(ctx)
    return ctx.base


@effect("Search your deck for up to 2 Basic Steven's Pokémon and put them onto your Bench. Then, shuffle your deck.")
def _bench_2_steven(ctx):
    _to_bench(ctx, lambda c: c.name.startswith("Steven's"), 2)
    _shuffle(ctx)
    return ctx.base


@effect("If you go first, you can use this attack during your first turn. Search your deck for up to 2 Basic Pokémon and put them onto your Bench. Then, shuffle your deck.")
def _bench_2_basic_first_turn(ctx):
    _to_bench(ctx, lambda c: True, 2)
    _shuffle(ctx)
    return ctx.base


@effect("Search your deck for a Basic Pokémon and put it onto your Bench. Then, shuffle your deck. If you put any Pokémon onto your Bench in this way, move an Energy from this Pokémon to the new Benched Pokémon.")
def _bench_1_move_energy(ctx):
    before = len(ctx.me.bench)
    _to_bench(ctx, lambda c: True, 1)
    if len(ctx.me.bench) > before:                     # a Pokémon was actually benched
        _move_one_energy(ctx.attacker, ctx.me.bench[-1])
    _shuffle(ctx)
    return ctx.base


# ================================================================ search cards into hand

@effect("Search your deck for up to 3 Pokémon, reveal them, and put them into your hand. Then, shuffle your deck.")
def _hand_3_poke(ctx):
    _to_hand(ctx, lambda t: t[0] == 'P', 3)
    _shuffle(ctx)
    return ctx.base


@effect("Search your deck for a Pokémon, reveal it, and put it into your hand. Then, shuffle your deck.")
def _hand_1_poke(ctx):
    _to_hand(ctx, lambda t: t[0] == 'P', 1)
    _shuffle(ctx)
    return ctx.base


@effect("Search your deck for up to 3 Misty's Pokémon, reveal them, and put them into your hand. Then, shuffle your deck.")
def _hand_3_misty(ctx):
    _to_hand(ctx, lambda t: t[0] == 'P' and t[1].name.startswith("Misty's"), 3)
    _shuffle(ctx)
    return ctx.base


@effect("Search your deck for a Supporter card, reveal it, and put it into your hand. Then, shuffle your deck.")
def _hand_supporter(ctx):
    _to_hand(ctx, lambda t: t[0] == 'T' and t[1].get('trainerType') == 'Supporter', 1)
    _shuffle(ctx)
    return ctx.base


@effect("Search your deck for an Item card, reveal it, and put it into your hand. Then, shuffle your deck.")
def _hand_item(ctx):
    _to_hand(ctx, lambda t: t[0] == 'T' and t[1].get('trainerType') == 'Item', 1)
    _shuffle(ctx)
    return ctx.base


@effect("Search your deck for a Pokémon Tool card, reveal it, and put it into your hand. Then, shuffle your deck.")
def _hand_tool(ctx):
    _to_hand(ctx, lambda t: t[0] == 'T' and t[1].get('trainerType') == 'Tool', 1)
    _shuffle(ctx)
    return ctx.base


@effect("Search your deck for up to 2 Transformation Tome cards, reveal them, and put them into your hand. Then, shuffle your deck.")
def _hand_2_tome(ctx):
    _to_hand(ctx, lambda t: t[0] == 'T' and t[1].get('name') == 'Transformation Tome', 2)
    _shuffle(ctx)
    return ctx.base


@effect("Search your deck for up to 3 in any combination of {G} Pokémon and Stadium cards, reveal them, and put them into your hand. Then, shuffle your deck.")
def _hand_3_grass_or_stadium(ctx):
    def pred(t):
        if t[0] == 'P':
            return t[1].ptype == 'Grass'
        if t[0] == 'T':
            return t[1].get('trainerType') == 'Stadium'
        return False
    _to_hand(ctx, pred, 3)
    _shuffle(ctx)
    return ctx.base


@effect("You may search your deck for up to 2 cards and put them into your hand. Then, shuffle your deck.")
def _hand_2_any(ctx):
    _to_hand(ctx, lambda t: True, 2)                   # "You may" — always beneficial, always taken
    _shuffle(ctx)
    return ctx.base


@effect("If you go first, you can use this attack during your first turn. Search your deck for a card and put it into your hand. Then, shuffle your deck.")
def _hand_1_any_first_turn(ctx):
    _to_hand(ctx, lambda t: True, 1)
    _shuffle(ctx)
    return ctx.base


# ================================================================ search Basic Energy into hand

@effect("Search your deck for up to 2 Basic Energy cards, reveal them, and put them into your hand. Then, shuffle your deck.")
def _hand_2_basic_energy(ctx):
    _to_hand(ctx, lambda t: t[0] == 'E', 2)
    _shuffle(ctx)
    return ctx.base


@effect("Search your deck for a Basic Energy card, reveal it, and put it into your hand. Then, shuffle your deck.")
def _hand_1_basic_energy(ctx):
    _to_hand(ctx, lambda t: t[0] == 'E', 1)
    _shuffle(ctx)
    return ctx.base


@effect("Search your deck for up to 3 Basic Energy cards of different types, reveal them, and put them into your hand. Then, shuffle your deck.")
def _hand_3_diff_energy(ctx):
    me = ctx.me
    seen = set()
    got = 0
    for i in range(len(me.deck) - 1, -1, -1):          # search-from-end, one per distinct type
        if got >= 3:
            break
        tok = me.deck[i]
        if tok[0] == 'E' and tok[1] not in seen:
            seen.add(tok[1])
            me.hand.append(me.deck.pop(i))
            got += 1
    _shuffle(ctx)
    return ctx.base


# ================================================================ search Basic Energy and ATTACH

@effect("Search your deck for a Basic {G} Energy card and attach it to this Pokémon. Then, shuffle your deck.")
def _attach_1_grass_self(ctx):
    _pull_energy_to(ctx, ctx.attacker, 'Grass', 1)
    _shuffle(ctx)
    return ctx.base


@effect("Search your deck for up to 2 Basic {P} Energy cards and attach them to this Pokémon. Then, shuffle your deck.")
def _attach_2_psychic_self(ctx):
    _pull_energy_to(ctx, ctx.attacker, 'Psychic', 2)
    _shuffle(ctx)
    return ctx.base


@effect("Search your deck for up to 2 Basic {W} Energy cards and attach them to this Pokémon. Then, shuffle your deck.")
def _attach_2_water_self(ctx):
    _pull_energy_to(ctx, ctx.attacker, 'Water', 2)
    _shuffle(ctx)
    return ctx.base


@effect("Search your deck for up to 2 Basic {P} Energy cards and attach them to 1 of your Benched Pokémon. Then, shuffle your deck.")
def _attach_2_psychic_bench(ctx):
    target = _bench_target(ctx)
    if target is not None:
        _pull_energy_to(ctx, target, 'Psychic', 2)
    _shuffle(ctx)
    return ctx.base


@effect("Search your deck for up to 2 Basic Energy cards and attach them to your Pokémon in any way you like. Then, shuffle your deck.")
def _attach_2_any_energy(ctx):
    target = ctx.game.primary(ctx.me) or ctx.attacker or ctx.me.active
    if target is not None:
        need = ctx.game._cheapest_cost(target) or ''
        pref = [L2T[c] for c in dict.fromkeys(need) if c in 'GRWLPFDM']   # types this ace wants, deduped
        order = pref + [t for t in ALL_BASIC_TYPES if t not in pref]
        got = 0
        for etype in order:
            got += _pull_energy_to(ctx, target, etype, 2 - got)
            if got >= 2:
                break
    _shuffle(ctx)
    return ctx.base


# ================================================================ evolve-search

@effect("Search your deck for a card that evolves from this Pokémon and put it onto this Pokémon to evolve it. Then, shuffle your deck.")
def _evolve_self(ctx):
    ev = _evolve_search(ctx.me, ctx.attacker)
    if ev is not None:
        ctx.attacker = ev                              # keep ctx pointing at the evolved Active
    _shuffle(ctx)
    return ctx.base


@effect("If you go first, you can use this attack during your first turn. Search your deck for a card that evolves from this Pokémon and put it onto this Pokémon to evolve it. Then, shuffle your deck.")
def _evolve_self_first_turn(ctx):
    ev = _evolve_search(ctx.me, ctx.attacker)
    if ev is not None:
        ctx.attacker = ev
    _shuffle(ctx)
    return ctx.base


@effect("For each of your Benched Pokémon, search your deck for a card that evolves from that Pokémon and put it onto that Pokémon to evolve it. Then, shuffle your deck.")
def _evolve_all_bench(ctx):
    for m in list(ctx.me.bench):                       # snapshot: evolution replaces bench entries in place
        _evolve_search(ctx.me, m)
    _shuffle(ctx)
    return ctx.base


@effect("Choose up to 2 of your {D} Pokémon. For each of those Pokémon, search your deck for a card that evolves from that Pokémon and put it onto that Pokémon to evolve it. Then, shuffle your deck.")
def _evolve_2_dark(ctx):
    count = 0
    for m in list(ctx.me.all_mons()):                  # up to 2 Darkness-type mons that can actually evolve
        if count >= 2:
            break
        if m.card.ptype == 'Darkness' and _evolve_search(ctx.me, m) is not None:
            count += 1
    _shuffle(ctx)
    return ctx.base
