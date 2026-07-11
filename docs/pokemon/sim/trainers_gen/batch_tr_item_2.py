#!/usr/bin/env python3
"""Trainer batch tr_item_2 — 14 Item cards (search / recover / heal / disruption / accel).
Each effect is registered by its EXACT printed text; fn(tctx)->bool (True if it changed state)."""
from trainer_effects import trainer, TrainerCtx

# ---- local helpers ----
_L2T = {'G': 'Grass', 'R': 'Fire', 'W': 'Water', 'L': 'Lightning',
        'P': 'Psychic', 'F': 'Fighting', 'D': 'Darkness', 'M': 'Metal'}
BASIC = set(_L2T.values())          # the 8 basic-energy types (Colorless/Wild are special-energy pseudo-types)


def _discard_tok(player, tok):
    """Route a hand/deck token to the right pile: basic energy -> disc_energy Counter, else -> discard list
    (mirrors the engine's KO/discard convention so accel-from-discard can see the energy)."""
    if tok[0] == 'E':
        player.disc_energy[tok[1]] += 1
    else:
        player.discard.append(tok)


def _trim_to(player, n):
    """Discard from the front of a player's hand until it holds n cards. Returns True if anything discarded."""
    did = False
    while len(player.hand) > n:
        _discard_tok(player, player.hand.pop(0)); did = True
    return did


# ================================================================ ITEMS

@trainer('item', "Each player discards cards from their hand until they have 5 cards in their hand. Your opponent discards first. (If a player has 5 or fewer cards in their hand, they do not discard.)")
def _hand_trimmer(t):
    a = _trim_to(t.opp, 5)          # opponent discards first
    b = _trim_to(t.me, 5)
    return a or b


@trainer('item', "Discard the top 2 cards of your deck.")
def _hole_digging_shovel(t):
    did = False
    for _ in range(2):
        if t.me.deck:
            _discard_tok(t.me, t.me.deck.pop()); did = True   # top of deck = end of list
    return did


@trainer('item', "Search your deck for up to 2 Basic Hop's Pokémon and put them onto your Bench. Then, shuffle your deck.")
def _hops_bag(t):
    # _search_basics_to_bench already enforces stage-0 ("Basic") and the 5-Bench cap
    return t.search_pokemon(lambda c: c.name.startswith("Hop's"), 2, to_bench=True) > 0


@trainer('item', "During your opponent's next turn, all of your {M} Pokémon take 30 less damage from attacks from your opponent's Pokémon (after applying Weakness and Resistance). (This includes new Pokémon that come into play.)")
def _iron_defender(t):
    # engine applies dr when dr_turn+1 == current turn, i.e. exactly during the opponent's next turn
    did = False
    for m in t.me.all_mons():
        if m.card.ptype == 'Metal':
            m.dr_amount = 30; m.dr_turn = t.game.turn; did = True
    return did


@trainer('item', "Heal 80 damage from your Active Pokémon that has 3 or more Energy attached.")
def _jumbo_ice_cream(t):
    m = t.me.active
    if m and m.total_energy() >= 3 and m.damage > 0:
        m.damage = max(0, m.damage - 80); return True
    return False


@trainer('item', "Search your deck for a Pokémon with the same name as 1 of your opponent's Pokémon in play, reveal it, and put it into your hand. Then, shuffle your deck.")
def _love_ball(t):
    names = {m.card.name for m in t.opp.all_mons()}
    return t.search_pokemon(lambda c: c.name in names, 1) > 0


@trainer('item', "Heal 20 damage and remove a Special Condition from your Active Pokémon.")
def _lumiose_galette(t):
    m = t.me.active
    if not m:
        return False
    did = False
    if m.damage > 0:
        m.damage = max(0, m.damage - 20); did = True
    for cond in ('Asleep', 'Paralyzed', 'Confused', 'Burned', 'Poisoned'):   # remove the single most impactful
        if cond in m.status:
            del m.status[cond]; did = True; break
    return did


@trainer('item', "Your opponent counts the cards in their hand, shuffles those cards, and puts them on the bottom of their deck. If they do, they draw that many cards.")
def _meddling_memo(t):
    opp = t.opp
    n = len(opp.hand)
    if n == 0:
        return False
    cards = opp.hand; opp.hand = []
    t.rng.shuffle(cards)
    opp.deck[:0] = cards            # bottom of deck = front (draw()/pop() takes from the end/top)
    opp.draw(n)
    return True


@trainer('item', "Search your deck for a Mega Evolution Pokémon ex, reveal it, and put it into your hand. Then, shuffle your deck.")
def _mega_signal(t):
    return t.search_pokemon(lambda c: c.is_ex and c.name.startswith('Mega '), 1) > 0


@trainer('item', "Attach a Basic Energy card from your discard pile to 1 of your Benched N's Pokémon.")
def _ns_pp_up(t):
    bench_ns = [m for m in t.me.bench if m.card.name.startswith("N's")]
    if not bench_ns:
        return False
    avail = [ty for ty, c in t.me.disc_energy.items() if c > 0 and ty in BASIC]
    if not avail:
        return False
    mon = bench_ns[0]
    need = {_L2T[L] for a in mon.card.attacks for L in a['cost'] if L in _L2T}
    etype = next((ty for ty in avail if ty in need), avail[0])   # prefer a type the mon can spend
    return t.accel_from_discard(etype, mon, 1) > 0


@trainer('item', "Put a Pokémon or a Basic Energy card from your discard pile into your hand.")
def _night_stretcher(t):
    if any(x[0] == 'P' for x in t.me.discard):                  # prefer recovering a Pokémon (scarcer)
        return t.recover_from_discard(lambda x: x[0] == 'P')
    for ty, c in list(t.me.disc_energy.items()):
        if c > 0 and ty in BASIC:
            t.me.disc_energy[ty] -= 1; t.me.hand.append(('E', ty)); return True
    return False


@trainer('item', 'Choose a Pokémon ex in your discard pile that has "Ogerpon" in its name, and switch it with 1 of your Pokémon ex in play that has "Ogerpon" in its name. Any attached cards, damage counters, Special Conditions, turns in play, and any other effects remain on the new Pokémon.')
def _ogres_mask(t):
    me = t.me
    disc = next((x for x in me.discard if x[0] == 'P' and x[1].is_ex and 'Ogerpon' in x[1].name), None)
    if not disc:
        return False
    mon = next((m for m in me.all_mons() if m.card.is_ex and 'Ogerpon' in m.card.name), None)
    if not mon:
        return False
    old = mon.card
    mon.card = disc[1]              # only the card identity changes; all Mon state (energy/damage/status/turns) stays
    me.discard.remove(disc)
    me.discard.append(('P', old))
    return True


@trainer('item', "Flip a coin. If heads, search your deck for a Pokémon, reveal it, and put it into your hand. Then, shuffle your deck.")
def _poke_ball(t):
    if t.rng.random() < 0.5:        # heads
        return t.search_pokemon(lambda c: True, 1) > 0
    return False


@trainer('item', "Search your deck for a Pokémon that doesn't have a Rule Box, reveal it, and put it into your hand. Then, shuffle your deck. (Pokémon ex, Pokémon V, etc. have Rule Boxes.)")
def _poke_pad(t):
    # in the H/I/J pool the only Rule-Box Pokémon are ex (no V/VMAX remain)
    return t.search_pokemon(lambda c: not c.is_ex, 1) > 0
