#!/usr/bin/env python3
"""Generated trainer-effect batch tr_item_4 (Items).

Coin convention matches attack_effects: rng.random() < 0.5 == heads.
Cost-discard cards (Techno Radar, Ultra Ball) assume the played card is NOT in
tctx.me.hand during resolution (the testkit/registry convention), so "another
card" / "2 other cards" are counted straight from the remaining hand.
"""
from trainer_effects import trainer, TrainerCtx


# ---- helpers -------------------------------------------------------------
def _atk_max(card):
    return max((a['dmg'] for a in card.attacks), default=0)


def _discard_n(me, n):
    """Discard n cards from hand to pay a cost, sacrificing the least useful first
    (basic energy -> special energy -> trainer -> Pokémon). Basic energy is routed
    to disc_energy so the accel accounting stays correct. Returns count discarded."""
    order = {'E': 0, 'S': 1, 'T': 2, 'P': 3}
    done = 0
    for _ in range(n):
        if not me.hand:
            break
        i = min(range(len(me.hand)), key=lambda j: order.get(me.hand[j][0], 4))
        tok = me.hand.pop(i)
        if tok[0] == 'E':
            me.disc_energy[tok[1]] += 1
        else:
            me.discard.append(tok)
        done += 1
    return done


# ---- trainers ------------------------------------------------------------
@trainer('item', "Flip a coin. If heads, search your deck for an Evolution Team Rocket's Pokémon, reveal it, and put it into your hand. If tails, search your deck for a Basic Team Rocket's Pokémon, reveal it, and put it into your hand. Then, shuffle your deck.")
def _tr_great_ball(t):
    heads = t.rng.random() < 0.5
    if heads:
        pred = lambda c: c.name.startswith("Team Rocket's") and c.stage > 0
    else:
        pred = lambda c: c.name.startswith("Team Rocket's") and c.stage == 0
    return t.search_pokemon(pred, 1) > 0


@trainer('item', "Search your deck for a Supporter card that has \"Team Rocket\" in its name, reveal it, and put it into your hand. Then, shuffle your deck.")
def _tr_transceiver(t):
    pred = lambda tok: (tok[0] == 'T' and tok[1].get('trainerType') == 'Supporter'
                        and 'Team Rocket' in tok[1].get('name', ''))
    return t.game._search_deck_to_hand(t.me, pred, 1) > 0


@trainer('item', "Flip a coin. If heads, put 2 damage counters on 1 of your opponent's Pokémon. If tails, put 2 damage counters on your Active Pokémon.")
def _tr_venture_bomb(t):
    heads = t.rng.random() < 0.5
    if heads:
        mons = [m for m in t.opp.all_mons() if m]
        if not mons:
            return False
        finish = [m for m in mons if 0 < m.hp_left <= 20]
        tgt = min(finish, key=lambda m: m.hp_left) if finish else (t.opp.active or mons[0])
    else:
        tgt = t.me.active
        if tgt is None:
            return False
    tgt.damage += 20   # 2 damage counters
    return True


@trainer('item', "You can use this card only if you discard another card from your hand.\n\nSearch your deck for up to 2 Future Pokémon, reveal them, and put them into your hand. Then, shuffle your deck.")
def _techno_radar(t):
    # "Future Pokémon" subtype is not modeled in the pool; approximate as the
    # "Iron ___" Paradox/Future line (the same heuristic effects.py uses).
    fut = lambda c: c.name.startswith('Iron ')
    if not t.me.hand:
        return False                                   # can't pay the discard cost
    if not any(tok[0] == 'P' and fut(tok[1]) for tok in t.me.deck):
        return False                                   # nothing to fetch -> don't waste the discard
    _discard_n(t.me, 1)
    return t.search_pokemon(fut, 2) > 0


@trainer('item', "Search your deck for a Tera Pokémon, reveal it, and put it into your hand. Then, shuffle your deck.")
def _tera_orb(t):
    # The "Tera" subtype is not modeled in the pool's card data, so this can't
    # identify a legal target. Conservative no-op rather than fetching a wrong card.
    return False


@trainer('item', "Choose up to 2 Pokémon Tools attached to Pokémon (yours or your opponent's) and discard them.")
def _tool_scrapper(t):
    # Useful play: strip the opponent's Tool buffs (up to 2). Discard the card to its owner's pile.
    removed = 0
    for m in t.opp.all_mons():
        while m.tools and removed < 2:
            nm = m.tools.pop(0)
            t.opp.discard.append(('T', {'name': nm, 'trainerType': 'Tool'}))
            removed += 1
    return removed > 0


@trainer('item', "You must play 2 Transformation Tome cards at once. (This effect works one time for 2 cards.)\n\nChoose a Basic Pokémon in your discard pile and switch it with 1 of your Basic Pokémon in play. Any attached cards, damage counters, Special Conditions, turns in play, and any other effects remain on the new Pokémon.")
def _transformation_tome(t):
    me = t.me
    disc_basics = [tok for tok in me.discard if tok[0] == 'P' and tok[1].stage == 0]
    in_play = [m for m in me.all_mons() if m and m.card.stage == 0]
    if not disc_basics or not in_play:
        return False
    best = max(disc_basics, key=lambda tok: _atk_max(tok[1]))
    weakest = min(in_play, key=lambda m: _atk_max(m.card))
    if _atk_max(best[1]) <= _atk_max(weakest.card):
        return False                                   # only a beneficial upgrade
    if best[1].hp <= weakest.damage:
        return False                                   # would arrive already Knocked Out
    me.discard.remove(best)
    me.discard.append(('P', weakest.card))
    weakest.card = best[1]                              # energy/damage/status/turns/tools/special stay on the Mon
    return True


@trainer('item', "You can use this card only if you discard 2 other cards from your hand.\n\nSearch your deck for a Pokémon, reveal it, and put it into your hand. Then, shuffle your deck.")
def _ultra_ball(t):
    if len(t.me.hand) < 2:
        return False                                   # can't pay the 2-card cost
    if not any(tok[0] == 'P' for tok in t.me.deck):
        return False                                   # nothing to fetch -> don't waste the discards
    _discard_n(t.me, 2)
    return t.search_pokemon(lambda c: True, 1) > 0


@trainer('item', "Attach a Basic {P} Energy card from your discard pile to 1 of your Benched {P} Pokémon.")
def _wondrous_patch(t):
    if t.me.disc_energy.get('Psychic', 0) <= 0:
        return False
    benched_psy = [m for m in t.me.bench if m.card.ptype == 'Psychic']
    if not benched_psy:
        return False
    tgt = max(benched_psy, key=lambda m: (m.total_energy(), m.card.hp))
    return t.accel_from_discard('Psychic', tgt, 1) > 0
