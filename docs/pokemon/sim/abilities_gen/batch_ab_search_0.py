#!/usr/bin/env python3
"""Batch: ab_search_0 — deck-search abilities (all `activated`, fn(actx)->bool; True == used).

Every ability here is a once-per-turn (or once-per-play/evolve/move) deck search. The "once", "first
turn", "when you play/evolve/move this Pokémon", and "shuffle your deck" clauses are turn-flow bits the
caller owns; each lambda implements only the *search + placement*, gated on its own on-card condition.

Placement uses the Game search helpers where they fit:
  * search-to-hand  -> game._search_deck_to_hand(player, pred, n)  (pred takes a deck token)
  * search-to-bench -> a local put (these put NON-basics onto the bench, which the basic-only
    game helper can't do), and evolve/switch-in-place carry all attached state.

Pokémon-Tool attachment (Impromptu Carrier) is now modeled via mon.tools. Remaining engine gaps
noted inline: out-of-pool named cards (Ethan's Adventure supporter, Stadiums, Unfezant ex) — those
searches simply find nothing and no-op, so nothing fires unconditionally.
"""
from ability_effects import ability, ActivatedCtx
from engine import Mon


# ---------------------------------------------------------------- helpers
def _copy_state(mon, ev):
    """Carry a Pokémon's on-board state onto its replacement (evolve / switch-in-place):
    damage counters, attached basic + special energy, turns in play, and Special Conditions."""
    ev.damage = mon.damage
    ev.energy = mon.energy
    ev.special = mon.special
    ev.turns = mon.turns
    ev.status = mon.status
    ev.poison_amt = mon.poison_amt
    return ev


def _search_named_to_bench(actx, names):
    """Search the deck for a Pokémon whose name is in `names` and put it directly onto the Bench
    (bypasses the Basic-only rule — these abilities bench a Stage-1). One target, Bench must have room."""
    me = actx.me
    if len(me.bench) >= 5:
        return False
    for i in range(len(me.deck) - 1, -1, -1):
        t = me.deck[i]
        if t[0] == 'P' and t[1].name in names:
            me.bench.append(Mon(t[1]))
            me.deck.pop(i)
            return True
    return False


# ---------------------------------------------------------------- search deck -> hand
@ability('activated', "- Once during your first turn, you may search your deck for up to 3 {C} Pokémon with 100 HP or less, reveal them, and put them into your hand. Then, shuffle your deck. You can't use more than 1 Fan Call Ability during your turn.")
def _fan_call(actx):
    # {C} = Colorless on-card type; HP 100 or less. Up to 3, to hand. ("first turn"/1-per-turn = caller.)
    pred = lambda t: t[0] == 'P' and t[1].ptype == 'Colorless' and t[1].hp <= 100
    return actx.game._search_deck_to_hand(actx.me, pred, 3) > 0


@ability('activated', "- Once during your turn, you may search your deck for a Cynthia's Pokémon, reveal it, and put it into your hand. Then, shuffle your deck.")
def _champions_call(actx):
    pred = lambda t: t[0] == 'P' and t[1].name.startswith("Cynthia's")
    return actx.game._search_deck_to_hand(actx.me, pred, 1) > 0


@ability('activated', "- Once during your turn, you may use this Ability. Search your deck for an Erika's Pokémon, reveal it, and put it into your hand. Then, shuffle your deck.")
def _gathering_of_blossoms(actx):
    pred = lambda t: t[0] == 'P' and t[1].name.startswith("Erika's")
    return actx.game._search_deck_to_hand(actx.me, pred, 1) > 0


@ability('activated', "- Once during your turn, you may search your deck for an Ethan's Adventure card, reveal it, and put it into your hand. Then, shuffle your deck.")
def _bonded_by_the_journey(actx):
    # "Ethan's Adventure" is a Supporter (out-of-pool Trainer) — search finds it only if present, else no-op.
    pred = lambda t: t[0] == 'T' and t[1].get('name') == "Ethan's Adventure"
    return actx.game._search_deck_to_hand(actx.me, pred, 1) > 0


@ability('activated', "- Once during your turn, you may search your deck for a Stadium card, reveal it, and put it into your hand. Then, shuffle your deck.")
def _changing_seasons(actx):
    pred = lambda t: t[0] == 'T' and t[1].get('trainerType') == 'Stadium'
    return actx.game._search_deck_to_hand(actx.me, pred, 1) > 0


@ability('activated', "- Once during your turn, you may use this Ability. Search your deck for up to 2 Basic {P} Energy cards, reveal them, and put them into your hand. Then, shuffle your deck.")
def _scent_collection(actx):
    # {P} = Psychic. Up to 2 Basic Psychic Energy to hand.
    pred = lambda t: t == ('E', 'Psychic')
    return actx.game._search_deck_to_hand(actx.me, pred, 2) > 0


@ability('activated', "- Once during your turn, if your Active Pokémon has the Festival Lead Ability, you may search your deck for a card and put it into your hand. Then, shuffle your deck.")
def _boom_boom_groove(actx):
    act = actx.me.active
    if not act or not any(ab.get('name') == 'Festival Lead' for ab in act.card.abilities):
        return False
    return actx.game._search_deck_to_hand(actx.me, lambda t: True, 1) > 0


@ability('activated', "- When you play this Pokémon from your hand onto your Bench during your turn, you may search your deck for a Pokémon Tool card and attach it to this Pokémon. Then, shuffle your deck.")
def _impromptu_carrier(actx):
    # Pokémon-Tool attachment is now modeled (mon.tools). Find a Tool in the deck, remove it, and
    # attach it to this Pokémon. Gated on a Tool being present in the deck.
    me = actx.me
    for i in range(len(me.deck) - 1, -1, -1):
        t = me.deck[i]
        if t[0] == 'T' and t[1].get('trainerType') == 'Tool':
            actx.mon.tools.append(t[1].get('name'))
            me.deck.pop(i)
            return True
    return False


# ---------------------------------------------------------------- search deck -> discard
@ability('activated', "- When you play this Pokémon from your hand onto your Bench during your turn, you may search your deck for up to 3 Basic {F} Energy cards and discard them. Then, shuffle your deck.")
def _dig_dig_dig(actx):
    # {F} on a Fighting-type Drilbur = Fighting Energy. Up to 3 from deck -> discard (feeds accel engines).
    me = actx.me
    got = 0
    for i in range(len(me.deck) - 1, -1, -1):
        if got >= 3:
            break
        if me.deck[i] == ('E', 'Fighting'):
            me.deck.pop(i)
            me.disc_energy['Fighting'] += 1
            got += 1
    return got > 0


# ---------------------------------------------------------------- search deck -> bench (non-basic put)
@ability('activated', "- Once during your turn, when you play this Pokémon from your hand to evolve 1 of your Pokémon, you may use this Ability. Search your deck for a Silcoon or a Cascoon and put it onto your Bench. Then, shuffle your deck.")
def _multiplying_cocoon(actx):
    return _search_named_to_bench(actx, ('Silcoon', 'Cascoon'))


@ability('activated', "- Once during your turn, when you play this Pokémon from your hand to evolve 1 of your Pokémon, you may use this Ability. Search your deck for a Shedinja and put it onto your Bench. Then, shuffle your deck.")
def _cast_off_shell(actx):
    return _search_named_to_bench(actx, ('Shedinja',))


# ---------------------------------------------------------------- search deck -> evolve/switch in place
@ability('activated', "- Once during your turn, if this Pokémon's remaining HP is 30 or less, you may search your deck for an Unfezant or Unfezant ex and put it onto this Pidove to evolve it. Then, shuffle your deck.")
def _emergency_evolution(actx):
    mon = actx.mon
    if mon.hp_left > 30:
        return False
    me = actx.me
    for i in range(len(me.deck) - 1, -1, -1):
        t = me.deck[i]
        if t[0] == 'P' and t[1].name in ('Unfezant', 'Unfezant ex'):
            ev = _copy_state(mon, Mon(t[1]))          # evolve Pidove -> Unfezant, skipping Tranquill
            if mon is me.active:
                me.active = ev
            elif mon in me.bench:
                me.bench[me.bench.index(mon)] = ev
            me.deck.pop(i)
            return True
    return False


@ability('activated', "- Once during your turn, when this Pokémon moves from the Active Spot to the Bench, you may search your deck for a Palafin ex and switch it with this Pokémon. Any attached cards, damage counters, Special Conditions, turns in play, and any other effects remain on the new Pokémon. If you switched a Pokémon in this way, put this card into your deck. Then, shuffle your deck.")
def _zero_to_hero(actx):
    # The Palafin-ex enabler: this Palafin has just moved Active->Bench; swap in Palafin ex from the
    # deck (all attached state carries over) and send this Palafin card back to the deck.
    me = actx.me
    mon = actx.mon
    if mon not in me.bench:
        return False
    for i in range(len(me.deck) - 1, -1, -1):
        t = me.deck[i]
        if t[0] == 'P' and t[1].name == 'Palafin ex':
            ev = _copy_state(mon, Mon(t[1]))
            me.bench[me.bench.index(mon)] = ev
            me.deck.pop(i)
            me.deck.append(('P', mon.card))
            return True
    return False
