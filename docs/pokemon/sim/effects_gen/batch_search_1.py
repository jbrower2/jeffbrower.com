#!/usr/bin/env python3
"""Effect batch: search_1.

Deck-search attacks: pull Pokémon onto the Bench, pull cards/Energy into the hand, or
search out Basic Energy and attach it. All of these are your-side setup with (mostly)
no damage; a couple also deal a printed base hit (Bewear 30, Boltund 50).

Modeling conventions (match the engine helpers + sibling batches):
- Bench-put of a BASIC Pokémon reuses the engine's `Game._search_basics_to_bench` (respects the
  5-Bench cap, pulls from the deck, stage-0 only). A few attacks bench a Stage-1 DIRECTLY
  (Charjabug SV07, Maushold SV08) — those use a local stage-agnostic bench helper.
- Search-to-hand reuses `Game._search_deck_to_hand(me, pred, n)` where `pred` takes a deck
  TOKEN: ('P', Card) | ('E', type-str) | ('T', trainer-dict) | ('S', special-energy-dict).
- Energy acceleration: pull a Basic-Energy token ('E', type) out of the deck and add a pip to the
  chosen Mon's `energy` Counter. "in any way you like" distributes each pulled pip to the target
  that best advances an unmet, on-type attack cost (falling back to the primary attacker / Active).
- "any number" / "up to N" are bounded by the real cap (Bench=5, 4 copies of a non-basic-energy
  card), so `n` is set to that ceiling.
- No speculative bonuses: every effect only moves cards the deck actually contains for the stated
  category; an empty search legitimately yields 0 (Player.draw / the helpers stop cleanly).

Data gap: Fletchling's "Pokémon with {F} Resistance" — the card database carries NO resistance
field (weakness only), so {F}-resistant targets are unidentifiable. Rather than over-grab
arbitrary Pokémon (the over-application anti-pattern), this search resolves to nothing. Flagged
uncertain.
"""
from attack_effects import effect, EffectCtx, STATUSES
from engine import Mon, L2T, T2L
import special_energy as SE


# ---------------------------------------------------------------- helpers

def _ceiling(mon):
    """Highest printed attack damage the Mon can threaten (its attacker 'ceiling')."""
    return max((a['dmg'] for a in mon.card.attacks), default=0)


def _cost_letters(ctx, mon):
    """The energy-cost letters of the Mon's cheapest damaging attack (e.g. 'FFC'), or ''."""
    return ctx.game._cheapest_cost(mon) or ''


def _cost_types(ctx, mon):
    """Set of non-Colorless basic-energy TYPES the Mon's cheapest attack needs, e.g. {'Fighting'}."""
    return {L2T[c] for c in _cost_letters(ctx, mon) if c in L2T and c != 'C'}


def _pull_basic_energy(ctx, allowed, k):
    """Remove up to `k` Basic-Energy tokens ('E', type) from the deck. `allowed` = a set of type
    strings, or None for any basic energy. Scans from the end (deck top). Returns the list of type
    strings actually pulled (so the caller attaches them)."""
    got = []
    deck = ctx.me.deck
    i = len(deck) - 1
    while i >= 0 and len(got) < k:
        tok = deck[i]
        if tok[0] == 'E' and (allowed is None or tok[1] in allowed):
            got.append(tok[1])
            deck.pop(i)
        i -= 1
    return got


def _attach_target_for_type(ctx, candidates, etype):
    """Choose which candidate Mon to give a pip of `etype`: prefer one whose cheapest attack needs
    that type (and is short on it), then the primary attacker, then the biggest threat."""
    if not candidates:
        return None
    prim = ctx.game.primary(ctx.me)
    letter = T2L.get(etype)

    def key(m):
        cost = _cost_letters(ctx, m)
        needs = bool(letter) and letter in cost
        deficit = (cost.count(letter) - m.energy.get(etype, 0)) if needs else -99
        return (needs, deficit, m is prim, _ceiling(m), m.total_energy())
    return max(candidates, key=key)


def _attach_target_general(ctx, candidates):
    """Choose a Mon for a free-choice attach: the primary attacker if it's eligible, else the
    biggest threat among the candidates."""
    if not candidates:
        return None
    prim = ctx.game.primary(ctx.me)
    if prim in candidates:
        return prim
    return max(candidates, key=lambda m: (_ceiling(m), m.total_energy()))


def _grab_and_attach_one(ctx, target):
    """Search a single Basic Energy card and attach it to `target`, choosing a type that advances
    the target's cheapest attack cost, then its own type, else any basic energy. Returns True if a
    card was found and attached."""
    types = _cost_types(ctx, target)
    pulled = _pull_basic_energy(ctx, types, 1) if types else []
    if not pulled:
        pt = target.card.ptype
        if pt in L2T.values() and pt != 'Colorless':
            pulled = _pull_basic_energy(ctx, {pt}, 1)
    if not pulled:
        pulled = _pull_basic_energy(ctx, None, 1)
    if pulled:
        target.energy[pulled[0]] += 1
        return True
    return False


def _search_pokemon_to_bench(ctx, pred, n):
    """Put up to `n` Pokémon matching `pred` (a Card predicate, ANY stage) from the deck onto the
    Bench, respecting the 5-Bench cap. Used by attacks that bench a Stage-1 directly."""
    me = ctx.me
    got = 0
    i = len(me.deck) - 1
    while i >= 0 and got < n and len(me.bench) < 5:
        tok = me.deck[i]
        if tok[0] == 'P' and pred(tok[1]):
            me.bench.append(Mon(tok[1]))
            me.deck.pop(i)
            got += 1
        i -= 1
    return got


def _evolve_in_place(ctx, mon, newcard):
    """Replace an in-play `mon` with an evolved Mon (`newcard`), carrying over damage / energy /
    turns / status / poison / special (mirrors the engine's own evolve)."""
    me = ctx.me
    ev = Mon(newcard)
    ev.damage = mon.damage
    ev.energy = mon.energy
    ev.turns = mon.turns
    ev.status = mon.status
    ev.poison_amt = mon.poison_amt
    ev.special = mon.special
    if mon is me.active:
        me.active = ev
    elif mon in me.bench:
        me.bench[me.bench.index(mon)] = ev
    return ev


# ---------------------------------------------------------------- bench-put (Basic)

@effect('You may search your deck for any number of Pokémon that have "Rotom" in their name and put them onto your Bench. Then, shuffle your deck.')
def _bench_rotom(ctx):
    # Every "Rotom" printing is a Basic; "any number" is bounded by the 5-Bench cap.
    ctx.game._search_basics_to_bench(ctx.me, lambda c: 'Rotom' in c.name, 5)
    return ctx.base


@effect("Search your deck for up to 2 Froakie and put them onto your Bench. Then, shuffle your deck.")
def _bench_froakie(ctx):
    ctx.game._search_basics_to_bench(ctx.me, lambda c: c.name == 'Froakie', 2)
    return ctx.base


@effect("Search your deck for up to 2 Grubbin and put them onto your Bench. Then, shuffle your deck.")
def _bench_grubbin(ctx):
    ctx.game._search_basics_to_bench(ctx.me, lambda c: c.name == 'Grubbin', 2)
    return ctx.base


@effect("You may search your deck for any number of Basic Lillie's Pokémon and put them onto your Bench. Then, shuffle your deck.")
def _bench_lillies(ctx):
    ctx.game._search_basics_to_bench(ctx.me, lambda c: c.name.startswith("Lillie's "), 5)
    return ctx.base


# ---------------------------------------------------------------- bench-put (Stage-1 direct)

@effect("Search your deck for up to 3 Charjabug and put them onto your Bench. Then, shuffle your deck.")
def _bench_charjabug(ctx):
    # Charjabug is a Stage-1 (evolves from Grubbin) yet this attack benches it directly.
    _search_pokemon_to_bench(ctx, lambda c: c.name == 'Charjabug', 3)
    return ctx.base


@effect("Search your deck for up to 2 in any combination of Maushold and Maushold ex and put them onto your Bench. Then, shuffle your deck.")
def _bench_maushold(ctx):
    # Maushold is a Stage-1 (evolves from Tandemaus); benched directly by this attack.
    _search_pokemon_to_bench(ctx, lambda c: c.name in ('Maushold', 'Maushold ex'), 2)
    return ctx.base


# ---------------------------------------------------------------- search-to-hand

@effect("Search your deck for up to 3 {D} Pokémon, reveal them, and put them into your hand. Then, shuffle your deck.")
def _hand_dark_pokemon(ctx):
    ctx.game._search_deck_to_hand(ctx.me, lambda x: x[0] == 'P' and x[1].ptype == 'Darkness', 3)
    return ctx.base


@effect("Search your deck for up to 3 in any combination of {R} Pokémon and Basic {R} Energy cards, reveal them, and put them into your hand. Then, shuffle your deck.")
def _hand_fire_mix(ctx):
    ctx.game._search_deck_to_hand(
        ctx.me,
        lambda x: (x[0] == 'P' and x[1].ptype == 'Fire') or (x[0] == 'E' and x[1] == 'Fire'),
        3)
    return ctx.base


@effect("You may search your deck for any number of Fennel cards, reveal them, and put them into your hand. Then, shuffle your deck.")
def _hand_fennel(ctx):
    # Fennel is a Supporter; "any number" is bounded by the 4-copy deck cap.
    ctx.game._search_deck_to_hand(ctx.me, lambda x: x[0] == 'T' and x[1].get('name') == 'Fennel', 4)
    return ctx.base


@effect("Search your deck for up to 3 Basic Energy cards, reveal them, and put them into your hand. Then, shuffle your deck.")
def _hand_basic_energy_3(ctx):
    ctx.game._search_deck_to_hand(ctx.me, lambda x: x[0] == 'E', 3)
    return ctx.base


@effect("Search your deck for up to 4 Energy cards, reveal them, and put them into your hand. Then, shuffle your deck.")
def _hand_energy_4(ctx):
    # "Energy cards" = Basic OR Special energy.
    ctx.game._search_deck_to_hand(ctx.me, lambda x: x[0] in ('E', 'S'), 4)
    return ctx.base


@effect("Search your deck for a Stadium card, reveal it, and put it into your hand. Then, shuffle your deck.")
def _hand_stadium(ctx):
    ctx.game._search_deck_to_hand(ctx.me, lambda x: x[0] == 'T' and x[1].get('trainerType') == 'Stadium', 1)
    return ctx.base


@effect("Search your deck for up to 2 Pokémon with {F} Resistance, reveal them, and put them into your hand. Then, shuffle your deck.")
def _hand_fighting_resist(ctx):
    # DATA GAP: the card database has no Resistance field, so {F}-resistant Pokémon can't be
    # identified. Grabbing arbitrary Pokémon would over-value the card (over-application), so this
    # resolves to nothing. (Fletchling's other attack, Peck 20, is what the AI actually uses.)
    return ctx.base


# ---------------------------------------------------------------- energy accel (attach)

@effect("Search your deck for an Energy card and attach it to 1 of your Benched {G} Pokémon. Then, shuffle your deck.")
def _accel_benched_grass(ctx):
    cands = [m for m in ctx.me.bench if m.card.ptype == 'Grass']
    target = _attach_target_general(ctx, cands)
    if target is not None:
        _grab_and_attach_one(ctx, target)
    return ctx.base


@effect("Search your deck for a Basic Energy card and attach it to this Pokémon. Then, shuffle your deck.")
def _accel_self_basic(ctx):
    # Bewear (base 30): attach to the attacker.
    _grab_and_attach_one(ctx, ctx.attacker)
    return ctx.base


@effect("Search your deck for up to 2 Basic {G} Energy cards and up to 2 Basic {L} Energy cards and attach them to your Pokémon in any way you like. Then, shuffle your deck.")
def _accel_g2_l2_any(ctx):
    pulled = _pull_basic_energy(ctx, {'Grass'}, 2) + _pull_basic_energy(ctx, {'Lightning'}, 2)
    for et in pulled:
        tgt = _attach_target_for_type(ctx, ctx.me.all_mons(), et)
        if tgt is not None:
            tgt.energy[et] += 1
    return ctx.base


@effect("Search your deck for up to 2 Basic {L} Energy cards and attach them to your Benched Pokémon in any way you like. Then, shuffle your deck.")
def _accel_l2_benched(ctx):
    # Boltund (base 50): Lightning onto the Bench only.
    cands = list(ctx.me.bench)
    if cands:
        for et in _pull_basic_energy(ctx, {'Lightning'}, 2):
            tgt = _attach_target_for_type(ctx, cands, et)
            if tgt is not None:
                tgt.energy[et] += 1
    return ctx.base


def _accel_fixed_type_one(ctx, etype):
    """Ogerpon: search one Basic {etype} Energy and attach it to the best of your Pokémon."""
    if _pull_basic_energy(ctx, {etype}, 1):
        tgt = _attach_target_for_type(ctx, ctx.me.all_mons(), etype)
        if tgt is not None:
            tgt.energy[etype] += 1
    return ctx.base


@effect("Search your deck for a Basic {F} Energy card and attach it to 1 of your Pokémon. Then, shuffle your deck.")
def _accel_fighting_one(ctx):
    return _accel_fixed_type_one(ctx, 'Fighting')


@effect("Search your deck for a Basic {R} Energy card and attach it to 1 of your Pokémon. Then, shuffle your deck.")
def _accel_fire_one(ctx):
    return _accel_fixed_type_one(ctx, 'Fire')


@effect("Search your deck for a Basic {G} Energy card and attach it to 1 of your Pokémon. Then, shuffle your deck.")
def _accel_grass_one(ctx):
    return _accel_fixed_type_one(ctx, 'Grass')


@effect("Search your deck for a Basic {W} Energy card and attach it to 1 of your Pokémon. Then, shuffle your deck.")
def _accel_water_one(ctx):
    return _accel_fixed_type_one(ctx, 'Water')


# ---------------------------------------------------------------- evolve-from-deck

@effect("Search your deck for a card that evolves from 1 of your Pokémon and put it onto that Pokémon to evolve it. Then, shuffle your deck.")
def _evolve_one_of_yours(ctx):
    me = ctx.me
    # Prefer evolving the primary attacker, then the Active, then the Bench.
    order = []
    prim = ctx.game.primary(me)
    if prim is not None:
        order.append(prim)
    if me.active is not None and me.active not in order:
        order.append(me.active)
    for m in me.bench:
        if m not in order:
            order.append(m)
    for mon in order:
        for i in range(len(me.deck) - 1, -1, -1):
            tok = me.deck[i]
            if tok[0] == 'P' and tok[1].evolves_from == mon.card.name and tok[1].stage == mon.card.stage + 1:
                _evolve_in_place(ctx, mon, tok[1])
                me.deck.pop(i)
                return ctx.base
    return ctx.base


# ---------------------------------------------------------------- recycle-self + search

@effect("Put this Pokémon and all attached cards into your deck. If you do, search your deck for up to 3 cards and put them into your hand. Then, shuffle your deck.")
def _recycle_self_search_3(ctx):
    me, at = ctx.me, ctx.attacker
    # 1) put this Pokémon + all attached cards into the deck.
    self_tok = ('P', at.card)
    me.deck.append(self_tok)
    # Each attached Special Energy returns as its OWN card. A *typed* special (Growing Grass,
    # Nitro Fire, ...) also stamped a real-type pip into `energy`, so subtract every special's
    # provided pips first — otherwise that pip is re-added a SECOND time as a phantom basic-energy
    # card (Growing Grass -> 1 special card + 1 bogus {G} basic = card duplication).
    basic = dict(at.energy)
    for name in at.special:
        me.deck.append(('S', {'special_energy': name}))
        for typ, cnt in SE.provides(name, at.card).items():
            basic[typ] = basic.get(typ, 0) - cnt
    for t, n in basic.items():
        if t in ('Wild', 'Colorless'):          # leftover pseudo-pips are special-derived, not cards
            continue
        for _ in range(max(0, n)):
            me.deck.append(('E', t))
    # remove this Pokémon from play (promote a Bench replacement if it was Active)
    if me.active is at:
        me.active = None
        me.promote()
    elif at in me.bench:
        me.bench.remove(at)
    # 2) search up to 3 cards -> hand (a rational player never re-grabs the just-shuffled self)
    skip = {id(self_tok)}
    ctx.game._search_deck_to_hand(me, lambda x: id(x) not in skip, 3)
    ctx.rng.shuffle(me.deck)
    return ctx.base
