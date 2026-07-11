#!/usr/bin/env python3
"""Batch tr_item_1 — Item trainers (deck/energy manipulation, search, disruption).

All 14 are Items, registered into the exact-text trainer registry as immediate actions:
    fn(tctx) -> bool   (True if the play did something)

Board/deck model reminders used here:
  * draw() pops from the END of Player.deck, so the deck "top" = end of the list and the
    deck "bottom" = front of the list (index 0).
  * basic energy lives in the deck as ('E', <TypeName>) tokens and in the discard as the
    Player.disc_energy Counter; special energy is an ('S', {'special_energy': name}) token
    and, once attached, lives in Mon.special plus the pips SE.provides() puts in Mon.energy.
"""
from trainer_effects import trainer, TrainerCtx  # noqa: F401  (TrainerCtx per batch header spec)
import special_energy as SE

# the 8 real basic-energy element types (Colorless / Wild are special-energy pseudo-types)
BASIC_TYPES = ('Grass', 'Fire', 'Water', 'Lightning', 'Psychic', 'Fighting', 'Darkness', 'Metal')
_L2T = {'G': 'Grass', 'R': 'Fire', 'W': 'Water', 'L': 'Lightning', 'P': 'Psychic',
        'F': 'Fighting', 'D': 'Darkness', 'M': 'Metal'}


def _discard_token(pl, tok):
    """Send a hand token to its correct pile: basic energy -> disc_energy Counter, else discard list."""
    if tok[0] == 'E':
        pl.disc_energy[tok[1]] += 1
    else:
        pl.discard.append(tok)


def _needed_types(mon):
    """Element types that appear in any of `mon`'s attack costs (Colorless ignored)."""
    types = set()
    for a in mon.card.attacks:
        for L in a['cost']:
            if L in _L2T:
                types.add(_L2T[L])
    return types


@trainer('item', "Look at the top 3 cards of your deck and put them back in any order, or shuffle them and put them on the bottom of your deck.")
def _deduction_kit(t):
    # Pure look / rearrange with no board effect. The AI has no card-quality ranking, and both
    # branches are card-neutral (reordering is a no-op in expectation; burying to the bottom
    # without a signal could only hurt), so model it as a conservative "you looked" — no mutation.
    return len(t.me.deck) > 0


@trainer('item', "Heal 60 damage from your Active {N} Pokémon.")
def _dragon_elixir(t):
    a = t.me.active                                   # {N} = a Dragon-type Active
    if a and a.card.ptype == 'Dragon' and a.damage > 0:
        a.damage = max(0, a.damage - 60)
        return True
    return False


@trainer('item', "Look at the bottom 7 cards of your deck. You may reveal a Pokémon you find there and put it into your hand. Shuffle the other cards back into your deck.")
def _dusk_ball(t):
    bottom = t.me.deck[:7]                             # bottom of deck = front of the list
    hit = next((tok for tok in bottom if tok[0] == 'P'), None)
    if hit is not None:
        t.me.deck.remove(hit)
        t.me.hand.append(hit)
    t.rng.shuffle(t.me.deck)
    return hit is not None


@trainer('item', "You can use this card only if you discard another card from your hand.\n\nSearch your deck for up to 2 Basic Energy cards, reveal them, and put them into your hand. Then, shuffle your deck.")
def _earthen_vessel(t):
    me = t.me
    if not any(tok[0] == 'E' for tok in me.deck):
        return False                                  # nothing to fetch -> don't pay the discard cost
    discardable = [tok for tok in me.hand
                   if not (tok[0] == 'T' and isinstance(tok[1], dict) and tok[1].get('name') == 'Earthen Vessel')]
    if not discardable:
        return False                                  # no "another card" available to discard
    victim = discardable[0]
    me.hand.remove(victim)
    _discard_token(me, victim)
    t.search_energy(2)
    return True


@trainer('item', "Flip 2 coins. If both of them are heads, search your deck for a Basic Energy card and attach it to 1 of your Pokémon. Then, shuffle your deck.")
def _energy_coin(t):
    heads = (t.rng.random() < 0.5) and (t.rng.random() < 0.5)
    if not heads:
        return False
    tgt = t.primary()
    if tgt is None:
        t.rng.shuffle(t.me.deck)
        return False
    need = _needed_types(tgt)
    idx = next((i for i, tok in enumerate(t.me.deck) if tok[0] == 'E' and tok[1] in need), None)
    if idx is None:
        idx = next((i for i, tok in enumerate(t.me.deck) if tok[0] == 'E'), None)
    if idx is None:
        t.rng.shuffle(t.me.deck)
        return False                                  # both heads but no basic energy left in deck
    typ = t.me.deck.pop(idx)[1]
    tgt.energy[typ] += 1
    t.rng.shuffle(t.me.deck)
    return True


@trainer('item', "Shuffle up to 5 Basic Energy cards from your discard pile into your deck.")
def _energy_recycler(t):
    me = t.me
    moved = 0
    while moved < 5:
        typ = next((x for x in list(me.disc_energy) if me.disc_energy[x] > 0), None)
        if typ is None:
            break
        me.disc_energy[typ] -= 1
        if me.disc_energy[typ] <= 0:
            me.disc_energy.pop(typ, None)
        me.deck.append(('E', typ))
        moved += 1
    if moved:
        t.rng.shuffle(me.deck)
    return moved > 0


@trainer('item', "Put up to 2 Basic Energy cards from your discard pile into your hand.")
def _energy_retrieval(t):
    me = t.me
    moved = 0
    while moved < 2:
        typ = next((x for x in list(me.disc_energy) if me.disc_energy[x] > 0), None)
        if typ is None:
            break
        me.disc_energy[typ] -= 1
        if me.disc_energy[typ] <= 0:
            me.disc_energy.pop(typ, None)
        me.hand.append(('E', typ))
        moved += 1
    return moved > 0


@trainer('item', "Search your deck for a Basic Energy card, reveal it, and put it into your hand. Then, shuffle your deck.")
def _energy_search(t):
    return t.search_energy(1) > 0


@trainer('item', "Your opponent reveals their hand, and you choose an Energy card you find there and put it on the bottom of their deck.")
def _energy_swatter(t):
    opp = t.opp
    tok = next((x for x in opp.hand if x[0] in ('E', 'S')), None)   # basic or special energy card
    if tok is None:
        return False
    opp.hand.remove(tok)
    opp.deck.insert(0, tok)                           # bottom of their deck
    return True


@trainer('item', "Move a Basic Energy from 1 of your Pokémon to another of your Pokémon.")
def _energy_switch(t):
    mons = t.me.all_mons()
    if len(mons) < 2:
        return False
    tgt = t.primary() or t.me.active                  # consolidate onto the ace/active
    if tgt is None:
        return False
    for src in mons:
        if src is tgt:
            continue
        typ = next((x for x in src.energy if x in BASIC_TYPES and src.energy[x] > 0), None)
        if typ:
            src.energy[typ] -= 1
            if src.energy[typ] <= 0:
                src.energy.pop(typ, None)
            tgt.energy[typ] += 1
            return True
    return False


@trainer('item', "Discard a Special Energy from 1 of your opponent's Pokémon.")
def _enhanced_hammer(t):
    tgts = [m for m in t.opp.all_mons() if m and m.special]
    if not tgts:
        return False
    mon = tgts[0]                                     # all_mons() lists the Active first
    name = max(mon.special, key=lambda n: sum(SE.provides(n, mon.card).values()))   # strip the biggest
    mon.special.remove(name)
    for typ, c in SE.provides(name, mon.card).items():
        mon.energy[typ] = mon.energy.get(typ, 0) - c
        if mon.energy[typ] <= 0:
            mon.energy.pop(typ, None)
    t.opp.discard.append(('S', {'special_energy': name}))
    return True


@trainer('item', "Search your deck for a Basic {F} Energy card or a Basic {F} Pokémon, reveal it, and put it into your hand. Then, shuffle your deck.")
def _fighting_gong(t):
    me = t.me
    fe = lambda tok: tok[0] == 'E' and tok[1] == 'Fighting'
    fp = lambda tok: tok[0] == 'P' and tok[1].stage == 0 and tok[1].ptype == 'Fighting'
    want_poke = (me.active is None) or len(me.bench) < 2
    order = (fp, fe) if want_poke else (fe, fp)
    for pred in order:
        if t.game._search_deck_to_hand(me, pred, 1) > 0:
            return True
    return False


@trainer('item', "You can use this card only if you have any Tera Pokémon in play.\n\nChoose up to 2 of your Benched {C} Pokémon and attach a Basic Energy card from your discard pile to each of them.")
def _glass_trumpet(t):
    # Tera is not modeled (no Tera flag on cards), so the "only if you have a Tera Pokémon in play"
    # play condition can never be verified. Conservative no-op — never fire unconditionally.
    return False


@trainer('item', "Choose 1 or both:\n• Shuffle up to 3 {W} Pokémon from your discard pile into your deck.\n• Shuffle up to 3 Basic {W} Energy cards from your discard pile into your deck.")
def _great_haul_net(t):
    me = t.me
    moved = 0
    wp = [tok for tok in me.discard if tok[0] == 'P' and tok[1].ptype == 'Water']
    for tok in wp[:3]:
        me.discard.remove(tok)
        me.deck.append(tok)
        moved += 1
    n = min(3, me.disc_energy.get('Water', 0))
    for _ in range(n):
        me.disc_energy['Water'] -= 1
        me.deck.append(('E', 'Water'))
        moved += 1
    if me.disc_energy.get('Water', 0) <= 0:
        me.disc_energy.pop('Water', None)
    if moved:
        t.rng.shuffle(me.deck)
    return moved > 0
