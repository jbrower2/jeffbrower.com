# -*- coding: utf-8 -*-
"""Generated trainer-effect batch: tr_item_0 (Items).

Faithful exact-text implementations for 14 Item cards. Registered by exact text; the 5
Antique Fossils share one identical effect text, so a single registration covers all five.
"""
from collections import Counter
from trainer_effects import trainer, TrainerCtx
from cards import Card
import special_energy as SE


# ---------------- shared helpers ----------------
def _basic_pips(mon):
    """The basic-energy pips on `mon` (its energy Counter minus what its attached Special
    Energy provides), so disruption removes real basics before touching special-energy pips."""
    special = Counter()
    for name in mon.special:
        for tp, c in SE.provides(name, mon.card).items():
            special[tp] += c
    basic = Counter(mon.energy)
    basic.subtract(special)
    return Counter({k: v for k, v in basic.items() if v > 0})


def _remove_special(player, mon, to_hand=False):
    """Remove one attached Special Energy card from `mon` (subtracting the pips it provided)."""
    if not mon.special:
        return False
    name = mon.special.pop()
    for tp, c in SE.provides(name, mon.card).items():
        mon.energy[tp] -= c
        if mon.energy[tp] <= 0:
            del mon.energy[tp]
    (player.hand if to_hand else player.discard).append(('S', {'special_energy': name}))
    return True


def _remove_one_energy(player, mon, to_hand=False):
    """Remove one Energy from `mon`: a basic pip (to `player`'s discard-energy or hand) if any,
    else one attached Special Energy card. Returns True if something was removed."""
    bp = _basic_pips(mon)
    if bp:
        typ = next((k for k in bp if k not in ('Colorless', 'Wild')), None) or next(iter(bp))
        mon.energy[typ] -= 1
        if mon.energy[typ] <= 0:
            del mon.energy[typ]
        if to_hand:
            player.hand.append(('E', typ))
        else:
            player.disc_energy[typ] += 1
        return True
    return _remove_special(player, mon, to_hand)


# ---- synthetic "Fossil Pokémon" card (a Fossil in play is a 60-HP Basic {C}) ----
_FOSSIL_NAMES = ('Antique Cover Fossil', 'Antique Jaw Fossil', 'Antique Plume Fossil',
                 'Antique Root Fossil', 'Antique Sail Fossil')
_FOSSIL_CARDS = {}


def _fossil_card(name):
    c = _FOSSIL_CARDS.get(name)
    if c is None:
        c = Card.__new__(Card)
        c.name = name; c.set = 'FOSSIL'; c.id = '0'
        c.cat = 'cat-green'; c.price = 0.0; c.is_ex = False
        c.energy = []; c.hp = 60; c.stage = 0; c.evolves_from = None
        c.ptype = 'Colorless'; c.weakness = None; c.retreat = 1
        c.attacks = []; c.abilities = []
        _FOSSIL_CARDS[name] = c
    return c


# ================================================================ ITEMS

@trainer('item', "Reveal the top 5 cards of your opponent's deck. You may choose any number of Basic Pokémon you find there and put those Pokémon onto their Bench. Your opponent shuffles the other cards back into their deck.")
def _accompanying_flute(t):
    opp = t.opp
    if not opp.deck:
        return False
    from engine import Mon
    five = [opp.deck.pop() for _ in range(min(5, len(opp.deck)))]   # top 5 (deck top = list end)
    benched = 0; rest = []
    for tok in five:
        if tok[0] == 'P' and tok[1].stage == 0 and len(opp.bench) < 5:
            opp.bench.append(Mon(tok[1])); benched += 1
        else:
            rest.append(tok)
    opp.deck.extend(rest)                                            # others shuffled back
    t.rng.shuffle(opp.deck)
    return benched > 0


# The 5 Antique Fossils share this exact text -> one registration covers all of them. The effect
# fn can't see which fossil was played, so it benches the fossil whose Stage-1 evolution THIS deck
# actually runs (so it can evolve into Lileep / Tyrunt / Archen / Amaura / Tirtouga). If the deck
# runs no Fossil evolution, the fossil is effectively dead (no-op). Special-condition immunity,
# the printed can't-retreat clause (approximated: it never holds Energy, so it can't pay retreat),
# and "discard this card at any time" are not separately modeled.
@trainer('item', "Play this card as if it were a 60-HP Basic {C} Pokémon. This card can't be affected by any Special Conditions and can't retreat.\n\nAt any time during your turn, you may discard this card from play.")
def _antique_fossil(t):
    me = t.me
    if len(me.bench) >= 5:
        return False
    evo_from = None
    for tok in me.deck + me.hand:
        if tok[0] == 'P' and getattr(tok[1], 'evolves_from', None) in _FOSSIL_NAMES:
            evo_from = tok[1].evolves_from; break
    if evo_from is None:
        return False
    from engine import Mon
    me.bench.append(Mon(_fossil_card(evo_from)))
    return True


@trainer('item', "Heal 30 damage from your Active Pokémon. If that Pokémon is an Arven's Pokémon, heal 100 damage from it instead.")
def _arvens_sandwich(t):
    m = t.me.active
    if not m or m.damage <= 0:
        return False
    amt = 100 if m.card.name.startswith("Arven's") else 30
    m.damage = max(0, m.damage - amt)
    return True


@trainer('item', "You can use this card only if you discard a Basic {R} Energy card from your hand.\n\nDiscard a Pokémon Tool or Special Energy card from 1 of your opponent's Pokémon, or discard a Stadium in play.")
def _blowtorch(t):
    fire = next((x for x in t.me.hand if x[0] == 'E' and x[1] == 'Fire'), None)
    if fire is None:                                                # cost: discard a basic {R}
        return False
    tool_mon = next((m for m in t.opp.all_mons() if m.tools), None)
    spec_mon = next((m for m in t.opp.all_mons() if m.special), None)
    has_stadium = t.game.stadium is not None
    if not (tool_mon or spec_mon or has_stadium):                  # no legal target -> don't play
        return False
    t.me.hand.remove(fire); t.me.disc_energy['Fire'] += 1
    if tool_mon:
        nm = tool_mon.tools.pop(0)
        t.opp.discard.append(('T', {'name': nm}))
    elif spec_mon:
        _remove_special(t.opp, spec_mon, to_hand=False)
    else:
        t.game.stadium = None
    return True


@trainer('item', "Search your deck for up to 2 Item cards, reveal them, and put them into your hand. Then, shuffle your deck. Your turn ends.")
def _boxed_order(t):
    # NOTE: the "Your turn ends" drawback is not modeled (the immediate-action contract has no
    # turn-end signal); only the search is applied.
    got = t.game._search_deck_to_hand(
        t.me, lambda tok: tok[0] == 'T' and tok[1].get('trainerType') == 'Item', 2)
    if got:
        t.rng.shuffle(t.me.deck)
    return got > 0


@trainer('item', "Search your deck for up to 2 Basic Pokémon with 70 HP or less and put them onto your Bench. Then, shuffle your deck.")
def _buddy_buddy_poffin(t):
    got = t.search_pokemon(lambda c: c.stage == 0 and c.hp <= 70, 2, to_bench=True)
    if got:
        t.rng.shuffle(t.me.deck)
    return got > 0


@trainer('item', "Look at the top 7 cards of your deck. You may reveal up to 2 in any combination of {G} Pokémon and Basic {G} Energy cards you find there and put them into your hand. Shuffle the other cards back into your deck.")
def _bug_catching_set(t):
    deck = t.me.deck
    seven = [deck.pop() for _ in range(min(7, len(deck)))]         # top 7 (deck top = list end)
    taken = 0; rest = []
    for tok in seven:
        is_grass = ((tok[0] == 'P' and getattr(tok[1], 'ptype', None) == 'Grass')
                    or (tok[0] == 'E' and tok[1] == 'Grass'))
        if taken < 2 and is_grass:
            t.me.hand.append(tok); taken += 1
        else:
            rest.append(tok)
    deck.extend(rest)
    t.rng.shuffle(deck)
    return taken > 0


@trainer('item', "You can use this card only if you go second, and only during your first turn.\n\nSearch your deck for a Supporter card, reveal it, and put it into your hand. Then, shuffle your deck.")
def _call_bell(t):
    if t.game.turn != 1:                                            # turn index 1 = the going-2nd player's 1st turn
        return False
    got = t.game._search_deck_to_hand(
        t.me, lambda tok: tok[0] == 'T' and tok[1].get('trainerType') == 'Supporter', 1)
    if got:
        t.rng.shuffle(t.me.deck)
    return got > 0


@trainer('item', "You can use this card only if you go second, and only during your first turn.\n\nPut an Energy attached to 1 of your opponent's Pokémon into their hand.")
def _chill_teaser_toy(t):
    if t.game.turn != 1:
        return False
    cand = [m for m in t.opp.all_mons() if m.total_energy() > 0]
    if not cand:
        return False
    m = max(cand, key=lambda x: x.total_energy())                  # hit their most-invested Pokémon
    return _remove_one_energy(t.opp, m, to_hand=True)


@trainer('item', "Flip a coin. If heads, discard an Energy from 1 of your opponent's Pokémon.")
def _crushing_hammer(t):
    if t.rng.random() >= 0.5:                                       # tails -> no effect
        return False
    cand = [m for m in t.opp.all_mons() if m.total_energy() > 0]
    if not cand:
        return False
    m = max(cand, key=lambda x: x.total_energy())
    return _remove_one_energy(t.opp, m, to_hand=False)
