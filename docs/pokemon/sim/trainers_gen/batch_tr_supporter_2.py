#!/usr/bin/env python3
"""Generated trainer effects — batch tr_supporter_2 (14 Supporters).

Each effect is fn(tctx) -> bool (True if it changed the game state). Registered under the card's
EXACT rules text via @trainer('supporter', <text>). The exact-text keys are round-trip verified in
test_batch_tr_supporter_2.py against effects_work/trainer_batches.json.
"""
from trainer_effects import trainer, TrainerCtx
from engine import Mon
import effects


# --- Fennel --------------------------------------------------------------------------------------
@trainer('supporter', "Heal 40 damage from each of your Pokémon.")
def _fennel(t):
    return t.heal(40, each=True)


# --- Firebreather --------------------------------------------------------------------------------
@trainer('supporter', "Search your deck for up to 7 Basic {R} Energy cards, reveal them, and put them into your hand. Then, shuffle your deck.")
def _firebreather(t):
    # Basic {R} Energy = the ('E','Fire') token (special energy is an ('S',..) token, so excluded).
    got = t.game._search_deck_to_hand(t.me, lambda tok: tok[0] == 'E' and tok[1] == 'Fire', 7)
    return got > 0


# --- Grimsley's Move -----------------------------------------------------------------------------
@trainer('supporter', "Look at the top 7 cards of your deck and put a {D} Pokémon you find there onto your Bench. Shuffle the other cards and put them on the bottom of your deck. You can't use this card during your first turn.")
def _grimsleys_move(t):
    # NOTE: the "can't use during your first turn" clause is a play-timing legality constraint,
    # enforced at the play-decision layer, not in this effect.
    me = t.me
    if len(me.bench) >= 5:
        return False
    k = min(7, len(me.deck))
    if k == 0:
        return False
    region = me.deck[-k:]                       # top of deck = end of list
    # Prefer a Basic {D} Pokémon (legitimately benchable); fall back to any {D} Pokémon per the text.
    hit = next((tok for tok in reversed(region)
                if tok[0] == 'P' and tok[1].ptype == 'Darkness' and tok[1].stage == 0), None)
    if hit is None:
        hit = next((tok for tok in reversed(region)
                    if tok[0] == 'P' and tok[1].ptype == 'Darkness'), None)
    if hit is None:
        return False
    del me.deck[len(me.deck) - k:]              # remove the whole looked-at region
    region.remove(hit)
    me.bench.append(Mon(hit[1]))
    t.rng.shuffle(region)
    me.deck[0:0] = region                       # the other cards go on the bottom
    return True


# --- Harlequin -----------------------------------------------------------------------------------
@trainer('supporter', "Each player shuffles their hand into their deck. Then, flip a coin. If heads, you draw 5 cards, and your opponent draws 3 cards. If tails, you draw 3 cards, and your opponent draws 5 cards.")
def _harlequin(t):
    t.shuffle_hand_into_deck()
    t.opp.deck += t.opp.hand; t.opp.hand = []; t.rng.shuffle(t.opp.deck)
    if t.rng.random() < 0.5:                    # heads
        t.draw(5); t.opp.draw(3)
    else:                                       # tails
        t.draw(3); t.opp.draw(5)
    return True


# --- Hassel --------------------------------------------------------------------------------------
@trainer('supporter', "You can use this card only if any of your Pokémon were Knocked Out during your opponent's last turn.\n\nLook at the top 8 cards of your deck and put up to 3 of them into your hand. Shuffle the other cards back into your deck.")
def _hassel(t):
    me = t.me
    if me.last_ko_turn != t.game.turn - 1:      # a mon of mine KO'd on the opponent's last turn
        return False
    n = min(3, len(me.deck))
    if n == 0:
        return False
    for _ in range(n):                          # take up to 3 off the top 8
        me.hand.append(me.deck.pop())
    t.rng.shuffle(me.deck)                       # shuffle the rest back
    return True


# --- Hilda ---------------------------------------------------------------------------------------
@trainer('supporter', "Search your deck for an Evolution Pokémon and an Energy card, reveal them, and put them into your hand. Then, shuffle your deck.")
def _hilda(t):
    got_poke = t.search_pokemon(lambda c: c.stage >= 1, 1)                                    # Evolution = Stage 1/2
    got_nrg = t.game._search_deck_to_hand(t.me, lambda tok: tok[0] in ('E', 'S'), 1)          # any Energy card
    return (got_poke + got_nrg) > 0


# --- Iris's Fighting Spirit ----------------------------------------------------------------------
@trainer('supporter', "You can use this card only if you discard another card from your hand.\n\nDraw cards until you have 6 cards in your hand.")
def _iris_fighting_spirit(t):
    me = t.me
    if not me.hand:                             # need another card to pay the discard cost
        return False
    tok = next((x for x in me.hand if x[0] == 'E'), me.hand[-1])   # discard an energy if any, else a card
    me.hand.remove(tok)
    if tok[0] == 'E':
        me.disc_energy[tok[1]] += 1
    else:
        me.discard.append(tok)
    while len(me.hand) < 6 and me.draw(1):
        pass
    return True


# --- Jacinthe ------------------------------------------------------------------------------------
@trainer('supporter', "Heal 150 damage from 1 of your {P} Pokémon.")
def _jacinthe(t):
    psy = [m for m in t.me.all_mons() if m and m.card.ptype == 'Psychic' and m.damage > 0]
    if not psy:
        return False
    tgt = max(psy, key=lambda m: m.damage)
    tgt.damage = max(0, tgt.damage - 150)
    return True


# --- Janine's Secret Art -------------------------------------------------------------------------
@trainer('supporter', "Choose up to 2 of your {D} Pokémon. For each of those Pokémon, search your deck for a Basic {D} Energy card and attach it to that Pokémon. Then, shuffle your deck. If you attached Energy to your Active Pokémon in this way, it is now Poisoned.")
def _janines_secret_art(t):
    me = t.me
    dark = [m for m in me.all_mons() if m and m.card.ptype == 'Darkness']   # all_mons = active first
    did = False
    poisoned_active = False
    for m in dark[:2]:                          # choose up to 2 {D} Pokémon
        idx = next((i for i in range(len(me.deck)) if me.deck[i] == ('E', 'Darkness')), None)
        if idx is None:
            continue                            # no Basic {D} Energy left in deck for this one
        me.deck.pop(idx)
        m.energy['Darkness'] += 1
        did = True
        if m is me.active:
            poisoned_active = True
    if did:
        t.rng.shuffle(me.deck)
    if poisoned_active and me.active:
        effects.set_status(me.active, 'Poisoned')
    return did


# --- Jasmine's Gaze ------------------------------------------------------------------------------
@trainer('supporter', "During your opponent's next turn, all of your Pokémon take 30 less damage from attacks from your opponent's Pokémon (after applying Weakness and Resistance). (This includes new Pokémon that come into play.)")
def _jasmines_gaze(t):
    # Engine models per-mon "-N next turn" via dr_amount/dr_turn (checked when dr_turn+1 == the turn
    # the mon is attacked). Set it on every current mon so whichever is Active next turn is shielded.
    # New Pokémon that come into play during the opponent's turn are not covered (engine limitation).
    did = False
    for m in t.me.all_mons():
        if m:
            m.dr_amount = 30
            m.dr_turn = t.game.turn
            did = True
    return did


# --- Judge ---------------------------------------------------------------------------------------
@trainer('supporter', "Each player shuffles their hand into their deck and draws 4 cards.")
def _judge(t):
    t.shuffle_hand_into_deck()
    t.opp.deck += t.opp.hand; t.opp.hand = []; t.rng.shuffle(t.opp.deck)
    t.draw(4); t.opp.draw(4)
    return True


# --- Kieran --------------------------------------------------------------------------------------
@trainer('supporter', "Choose 1:\n\n• Switch your Active Pokémon with 1 of your Benched Pokémon.\n\n• During this turn, attacks used by your Pokémon do 30 more damage to your opponent's Active Pokémon ex and Active Pokémon V (before applying Weakness and Resistance).")
def _kieran(t):
    # Mode 1 (switch) is fully modelable. Mode 2 (this-turn +30 vs Active ex/V) needs a transient
    # damage-buff flag the engine doesn't track, so we take the switch — a concrete, correct choice.
    return t.switch_self()


# --- Kofu ----------------------------------------------------------------------------------------
@trainer('supporter', "Put 2 cards from your hand on the bottom of your deck in any order. If you put 2 cards on the bottom of your deck in this way, draw 4 cards. (If you can't put 2 cards from your hand on the bottom of your deck, you can't use this card.)")
def _kofu(t):
    me = t.me
    if len(me.hand) < 2:                        # can't put 2 on the bottom -> can't use the card
        return False
    for _ in range(2):
        me.deck.insert(0, me.hand.pop(0))       # bottom of deck = index 0
    me.draw(4)
    return True


# --- Lacey ---------------------------------------------------------------------------------------
@trainer('supporter', "Shuffle your hand into your deck. Then, draw 4 cards. If your opponent has 3 or fewer Prize cards remaining, draw 8 cards instead.")
def _lacey(t):
    t.shuffle_hand_into_deck()
    n = 8 if len(t.opp.prizes) <= 3 else 4
    t.draw(n)
    return True
