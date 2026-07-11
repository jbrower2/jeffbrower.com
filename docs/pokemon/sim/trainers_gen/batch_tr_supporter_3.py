#!/usr/bin/env python3
"""Generated trainer batch: tr_supporter_3 (14 Supporters).

Each effect is registered by its EXACT printed text via @trainer('supporter', text).
An action fn takes a TrainerCtx (tctx) and returns True if it did something.

Model reminders (see engine.py):
  - Deck/hand tokens: ('P', Card) | ('E', type_str) | ('T', trainer_dict) | ('S', special_dict).
  - Top of deck == END of the deck list (draw() does deck.pop()); bottom == index 0.
  - Discarded basic energy lives in player.disc_energy (a Counter); other cards in player.discard.
  - "Rule Box" in the pool == Pokémon ex (Card.is_ex); there are no V/other rule-box cards here.
  - "Ancient"/"Future" subtypes are NOT in the card data, so cards keyed on them are conservative no-ops.
"""
from trainer_effects import trainer, TrainerCtx
from engine import Mon
import effects

# type name -> attack-cost letter (local copy so this module needn't import engine's map)
_T2L = {'Grass': 'G', 'Fire': 'R', 'Water': 'W', 'Lightning': 'L', 'Psychic': 'P',
        'Fighting': 'F', 'Darkness': 'D', 'Metal': 'M', 'Colorless': 'C'}
# the 8 real basic-energy types (special-energy pseudo-types 'Wild'/'Colorless' are excluded here)
_BASIC_TYPES = {'Grass', 'Fire', 'Water', 'Lightning', 'Psychic', 'Fighting', 'Darkness', 'Metal'}


def _discard_token(me, tok):
    """Send a card to the discard, matching engine bookkeeping (basic energy -> disc_energy Counter)."""
    if tok[0] == 'E':
        me.disc_energy[tok[1]] += 1
    else:
        me.discard.append(tok)


def _atk_ceiling(card):
    return max((a['dmg'] for a in card.attacks), default=0)


# ---------------- Lana's Aid ----------------
@trainer('supporter', "Put up to 3 in any combination of Pokémon that don't have a Rule Box and Basic Energy cards from your discard pile into your hand. (Pokémon ex, Pokémon V, etc. have Rule Boxes.)")
def _lanas_aid(t):
    me = t.me
    got = 0
    # non-Rule-Box Pokémon (== non-ex) from the discard pile, best attackers first
    pokes = [x for x in me.discard if x[0] == 'P' and not x[1].is_ex]
    pokes.sort(key=lambda x: _atk_ceiling(x[1]), reverse=True)
    for tok in pokes:
        if got >= 3:
            break
        me.discard.remove(tok)
        me.hand.append(tok)
        got += 1
    # then Basic Energy cards from the discard pile
    for etype in list(me.disc_energy.keys()):
        while got < 3 and me.disc_energy.get(etype, 0) > 0:
            me.disc_energy[etype] -= 1
            me.hand.append(('E', etype))
            got += 1
        if me.disc_energy.get(etype, 0) <= 0:
            me.disc_energy.pop(etype, None)
    return got > 0


# ---------------- Larry's Skill ----------------
@trainer('supporter', "Discard your hand and search your deck for a Pokémon, a Supporter card, and a Basic Energy card, reveal them, and put them into your hand. Then, shuffle your deck.")
def _larrys_skill(t):
    me, g = t.me, t.game
    discarded = len(me.hand)
    for tok in list(me.hand):                      # discard your hand (energy -> disc_energy)
        _discard_token(me, tok)
    me.hand = []
    n = 0
    n += g._search_deck_to_hand(me, lambda x: x[0] == 'P', 1)                                       # a Pokémon
    n += g._search_deck_to_hand(me, lambda x: x[0] == 'T' and x[1].get('trainerType') == 'Supporter', 1)  # a Supporter
    n += g._search_deck_to_hand(me, lambda x: x[0] == 'E', 1)                                       # a Basic Energy
    t.rng.shuffle(me.deck)
    return (discarded + n) > 0


# ---------------- Lillie's Determination ----------------
@trainer('supporter', "Shuffle your hand into your deck. Then, draw 6 cards. If you have exactly 6 Prize cards remaining, draw 8 cards instead.")
def _lillies_determination(t):
    t.shuffle_hand_into_deck()
    t.draw(8 if len(t.me.prizes) == 6 else 6)
    return True


# ---------------- Lisia's Appeal ----------------
@trainer('supporter', "Switch in 1 of your opponent's Benched Basic Pokémon to the Active Spot. If you do, the new Active Pokémon is now Confused.")
def _lisias_appeal(t):
    opp = t.opp
    basics = [m for m in opp.bench if m.card.stage == 0]
    if not basics:
        return False
    tgt = min(basics, key=lambda m: m.hp_left)      # drag up the easiest liability to exploit
    opp.bench.remove(tgt)
    if opp.active is not None:
        opp.bench.append(opp.active)
    opp.active = tgt
    effects.set_status(tgt, 'Confused')
    return True


# ---------------- Lt. Surge's Bargain ----------------
@trainer('supporter', "Ask your opponent if each player may take a Prize card. If yes, each player takes a Prize card. If no, you draw 4 cards.")
def _lt_surges_bargain(t):
    # The opponent decides. Modeled: they allow the mutual prize only when it favors them (they are
    # ahead in the prize race, so racing helps them); otherwise they decline and you draw 4.
    me, opp = t.me, t.opp
    if len(opp.prizes) < len(me.prizes):
        me.take_prize(1)
        opp.take_prize(1)
    else:
        t.draw(4)
    return True


# ---------------- Lucian ----------------
@trainer('supporter', "Each player shuffles their hand and puts it on the bottom of their deck. If either player put any cards on the bottom of their deck in this way, each player flips a coin. If heads, that player draws 6 cards. If tails, they draw 3 cards.")
def _lucian(t):
    put = 0
    for p in (t.me, t.opp):
        put += len(p.hand)
        hand = p.hand
        p.hand = []
        t.rng.shuffle(hand)
        p.deck[0:0] = hand                          # put on the bottom of the deck
    if put == 0:
        return False                                # nobody put any cards down -> no coin flips
    for p in (t.me, t.opp):
        p.draw(6 if t.rng.random() < 0.5 else 3)    # each player flips their own coin
    return True


# ---------------- Morty's Conviction ----------------
@trainer('supporter', "You can use this card only if you discard another card from your hand.\n\nDraw a card for each of your opponent's Benched Pokémon.")
def _mortys_conviction(t):
    me, opp = t.me, t.opp
    n = len(opp.bench)
    if n == 0 or not me.hand:                        # need a payoff and a card to pay the discard cost
        return False
    tok = next((x for x in me.hand if x[0] == 'E'), me.hand[-1])   # discard an energy if any, else a card
    me.hand.remove(tok)
    _discard_token(me, tok)
    me.draw(n)
    return True


# ---------------- N's Plan ----------------
@trainer('supporter', "Move up to 2 Energy from your Benched Pokémon to your Active Pokémon.")
def _ns_plan(t):
    me = t.me
    if not me.active or not me.bench:
        return False
    need = list(t.game._cheapest_cost(me.active) or '')          # cost letters the active still wants
    pips = []
    for m in me.bench:
        for etype, c in m.energy.items():
            for _ in range(c):
                pips.append((m, etype))
    if not pips:
        return False
    pips.sort(key=lambda pip: 0 if _T2L.get(pip[1]) in need else 1)   # move needed types first
    moved = 0
    for m, etype in pips[:2]:
        if m.energy.get(etype, 0) <= 0:
            continue
        m.energy[etype] -= 1
        if m.energy[etype] <= 0:
            del m.energy[etype]
        me.active.energy[etype] += 1
        moved += 1
    return moved > 0


# ---------------- Naveen ----------------
@trainer('supporter', "Draw cards until you have 5 cards in your hand. Before drawing cards, you may discard any number of cards from your hand. (If you can't draw any cards in this way, you can't use this card.)")
def _naveen(t):
    # Conservative: we do not model the optional pre-draw discard. If the hand is already >= 5 there is
    # nothing to draw (without discarding) -> the card can't be used.
    me = t.me
    if len(me.hand) >= 5:
        return False
    before = len(me.hand)
    while len(me.hand) < 5 and me.draw(1):
        pass
    return len(me.hand) > before


# ---------------- Perrin ----------------
@trainer('supporter', "Reveal up to 2 Pokémon in your hand and put them into your deck. If you do, search your deck for up to that many Pokémon, reveal them, and put them into your hand. Then, shuffle your deck.")
def _perrin(t):
    me = t.me
    hand_pokes = [x for x in me.hand if x[0] == 'P']
    if not hand_pokes:
        return False
    hand_pokes.sort(key=lambda x: x[1].stage, reverse=True)      # put back the least-playable (evolutions) first
    put = hand_pokes[:2]
    for tok in put:
        me.hand.remove(tok)
        me.deck.append(tok)
    n = len(put)
    got = t.game._search_deck_to_hand(me, lambda x: x[0] == 'P' and x[1].stage == 0, n)   # prefer Basics
    if got < n:
        got += t.game._search_deck_to_hand(me, lambda x: x[0] == 'P', n - got)            # then any Pokémon
    t.rng.shuffle(me.deck)
    return got > 0


# ---------------- Philippe ----------------
@trainer('supporter', "Attach up to 2 Basic {M} Energy cards from your discard pile to 1 of your {M} Pokémon.")
def _philippe(t):
    me = t.me
    metal = [m for m in me.all_mons() if m and m.card.ptype == 'Metal']    # all_mons() lists active first
    if not metal:
        return False
    p = t.primary()
    tgt = p if (p and p.card.ptype == 'Metal') else metal[0]
    return t.accel_from_discard('Metal', tgt, 2) > 0


# ---------------- Pokémon Center Lady ----------------
@trainer('supporter', "Heal 60 damage from 1 of your Pokémon, and it recovers from all Special Conditions.")
def _pokemon_center_lady(t):
    mons = [m for m in t.me.all_mons() if m]
    if not mons:
        return False

    def _nstatus(m):
        return sum(1 for s in effects.STATUSES if s in m.status)
    tgt = max(mons, key=lambda m: (_nstatus(m) > 0, m.damage))
    if tgt.damage <= 0 and _nstatus(tgt) == 0:
        return False
    tgt.damage = max(0, tgt.damage - 60)
    for s in effects.STATUSES:                       # recovers from all Special Conditions
        tgt.status.pop(s, None)
    return True


# ---------------- Professor Sada's Vitality ----------------
@trainer('supporter', "Choose up to 2 of your Ancient Pokémon and attach a Basic Energy card from your discard pile to each of them. If you attached any Energy in this way, draw 3 cards.")
def _professor_sadas_vitality(t):
    # "Ancient" is a Pokémon subtype the card data does not carry (printings.json has no subtype field),
    # so we can't identify Ancient Pokémon. Conservative no-op rather than firing on non-Ancient Pokémon.
    return False


# ---------------- Professor Turo's Scenario ----------------
@trainer('supporter', "Put 1 of your Pokémon in play into your hand. (Discard all cards attached to that Pokémon.)")
def _professor_turos_scenario(t):
    me = t.me
    mons = me.all_mons()
    if len(mons) < 2:
        return False                                 # can't return your only Pokémon (would empty the board)
    tgt = max(mons, key=lambda m: (m.damage, sum(1 for s in effects.STATUSES if s in m.status)))
    if tgt.damage <= 0 and not any(s in tgt.status for s in effects.STATUSES):
        return False                                 # only worth bouncing a damaged/statused Pokémon
    for etype, c in list(tgt.energy.items()):        # discard attached basic energy
        if etype in _BASIC_TYPES and c > 0:
            me.disc_energy[etype] += c
    if tgt is me.active:
        me.active = None
        me.promote()                                 # a Benched Pokémon must take the empty Active Spot
    else:
        me.bench.remove(tgt)
    me.hand.append(('P', tgt.card))
    return True
