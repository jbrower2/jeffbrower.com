#!/usr/bin/env python3
"""Generated trainer batch: tr_supporter_1 (14 Supporters).

Each effect is registered by its EXACT printed text via @trainer('supporter', text).
An action fn takes a TrainerCtx (tctx) and returns True if it did something.

Model reminders (see engine.py):
  - Deck/hand tokens: ('P', Card) | ('E', type_str) | ('T', trainer_dict) | ('S', special_dict).
  - Top of deck == END of the deck list (draw() does deck.pop()).
  - Discarded basic energy goes to player.disc_energy (a Counter); other cards to player.discard.
"""
from trainer_effects import trainer, TrainerCtx

# type name -> attack-cost letter (local copy so this module needn't import engine)
_T2L = {'Grass': 'G', 'Fire': 'R', 'Water': 'W', 'Lightning': 'L', 'Psychic': 'P',
        'Fighting': 'F', 'Darkness': 'D', 'Metal': 'M', 'Colorless': 'C'}


# ---------------- shared helpers ----------------
def _tok_priority(tok):
    """Generic 'how useful to draw' ranking for cards we get to choose (top-of-deck / dig)."""
    k = tok[0]
    if k == 'P':
        return 4 if tok[1].stage == 0 else 3      # a basic can hit the board immediately
    if k in ('E', 'S'):
        return 2
    return 1                                       # Trainers are situational


def _discard_token(me, tok):
    """Send a card from deck/hand to the discard, matching engine bookkeeping."""
    if tok[0] == 'E':
        me.disc_energy[tok[1]] += 1               # basic energy lives in the disc_energy Counter
    else:
        me.discard.append(tok)


def _needed_letters(game, mon):
    if mon is None:
        return []
    c = game._cheapest_cost(mon)                   # cost letters of the mon's cheapest damaging attack
    return list(c) if c else []


# ---------------- Ciphermaniac's Codebreaking ----------------
@trainer('supporter', "Search your deck for 2 cards, shuffle your deck, then put those cards on top of it in any order.")
def _ciphermaniac(t):
    deck = t.me.deck
    if not deck:
        return False
    order = sorted(range(len(deck)), key=lambda i: -_tok_priority(deck[i]))
    picks = order[:2]
    toks = [deck[i] for i in picks]
    for i in sorted(picks, reverse=True):
        deck.pop(i)
    t.rng.shuffle(deck)                            # "...shuffle your deck, then put those cards on top"
    deck.extend(reversed(toks))                    # best-of-the-two ends on top (drawn first)
    return True


# ---------------- Clemont's Quick Wit ----------------
@trainer('supporter', "Heal 60 damage from each of your {L} Pokémon.")
def _clemonts_quick_wit(t):
    did = False
    for m in t.me.all_mons():
        if m.card.ptype == 'Lightning' and m.damage > 0:
            m.damage = max(0, m.damage - 60)
            did = True
    return did


# ---------------- Colress's Tenacity ----------------
@trainer('supporter', "Search your deck for a Stadium card and an Energy card, reveal them, and put them into your hand. Then, shuffle your deck.")
def _colresss_tenacity(t):
    g, me = t.game, t.me
    a = g._search_deck_to_hand(me, lambda tok: tok[0] == 'T' and tok[1].get('trainerType') == 'Stadium', 1)
    b = g._search_deck_to_hand(me, lambda tok: tok[0] in ('E', 'S'), 1)
    return (a + b) > 0


# ---------------- Cook ----------------
@trainer('supporter', "Heal 70 damage from your Active Pokémon.")
def _cook(t):
    a = t.me.active
    if a and a.damage > 0:
        a.damage = max(0, a.damage - 70)
        return True
    return False


# ---------------- Crispin ----------------
@trainer('supporter', "Search your deck for up to 2 Basic Energy cards of different types, reveal them, and put 1 of them into your hand. Attach the other to 1 of your Pokémon. Then, shuffle your deck.")
def _crispin(t):
    deck = t.me.deck
    seen, idxs = [], []
    for i in range(len(deck) - 1, -1, -1):
        tok = deck[i]
        if tok[0] == 'E' and tok[1] not in seen:   # basic energy of a not-yet-picked type
            seen.append(tok[1])
            idxs.append(i)
            if len(idxs) == 2:
                break
    if not idxs:
        return False
    got = [deck.pop(i) for i in sorted(idxs, reverse=True)]
    if len(got) >= 2:
        tgt = t.primary()
        need = _needed_letters(t.game, tgt)
        got.sort(key=lambda tok: 0 if _T2L.get(tok[1]) in need else 1)   # attach a needed type if possible
        if tgt is not None:
            tgt.energy[got[0][1]] += 1             # attach one
        else:
            t.me.hand.append(got[0])
        t.me.hand.append(got[1])                   # the other goes to hand
    else:
        t.me.hand.append(got[0])                   # only 1 found -> it goes to hand
    return True


# ---------------- Cyrano ----------------
@trainer('supporter', "Search your deck for up to 3 Pokémon ex, reveal them, and put them into your hand. Then, shuffle your deck.")
def _cyrano(t):
    return t.search_pokemon(lambda c: c.is_ex, 3) > 0


# ---------------- Dawn ----------------
@trainer('supporter', "Search your deck for a Basic Pokémon, a Stage 1 Pokémon, and a Stage 2 Pokémon, reveal them, and put them into your hand. Then, shuffle your deck.")
def _dawn(t):
    n = 0
    n += t.search_pokemon(lambda c: c.stage == 0, 1)
    n += t.search_pokemon(lambda c: c.stage == 1, 1)
    n += t.search_pokemon(lambda c: c.stage == 2, 1)
    return n > 0


# ---------------- Drasna ----------------
@trainer('supporter', "Shuffle your hand into your deck. Then, flip a coin. If heads, draw 8 cards. If tails, draw 3 cards.")
def _drasna(t):
    t.shuffle_hand_into_deck()
    t.draw(8 if t.rng.random() < 0.5 else 3)
    return True


# ---------------- Drayton ----------------
@trainer('supporter', "Look at the top 7 cards of your deck. You may reveal a Pokémon and a Trainer card you find there and put them into your hand. Shuffle the other cards back into your deck.")
def _drayton(t):
    deck = t.me.deck
    if not deck:
        return False
    top = deck[-7:]
    rest = deck[:-7]
    poke = next((x for x in top if x[0] == 'P'), None)
    trn = next((x for x in top if x[0] == 'T'), None)
    got = False
    for pick in (poke, trn):
        if pick is not None:
            top.remove(pick)
            t.me.hand.append(pick)
            got = True
    t.me.deck = rest + top
    t.rng.shuffle(t.me.deck)                        # "shuffle the other cards back"
    return got


# ---------------- Emcee's Hype ----------------
@trainer('supporter', "Draw 2 cards. If your opponent has 3 or fewer Prize cards remaining, draw 2 more cards.")
def _emcees_hype(t):
    t.draw(2)
    if len(t.opp.prizes) <= 3:
        t.draw(2)
    return True


# ---------------- Emma ----------------
@trainer('supporter', "Your opponent reveals their hand, and you draw a card for each Pokémon you find there.")
def _emma(t):
    n = sum(1 for x in t.opp.hand if x[0] == 'P')
    if n:
        t.draw(n)
        return True
    return False


# ---------------- Eri ----------------
@trainer('supporter', "Your opponent reveals their hand, and you discard up to 2 Item cards you find there.")
def _eri(t):
    items = [x for x in t.opp.hand if x[0] == 'T' and x[1].get('trainerType') == 'Item'][:2]
    for tok in items:
        t.opp.hand.remove(tok)
        t.opp.discard.append(tok)
    return len(items) > 0


# ---------------- Ethan's Adventure ----------------
@trainer('supporter', "Search your deck for up to 3 in any combination of Ethan's Pokémon and Basic {R} Energy cards, reveal them, and put them into your hand. Then, shuffle your deck.")
def _ethans_adventure(t):
    def pred(tok):
        if tok[0] == 'P':
            return tok[1].name.startswith("Ethan's")
        if tok[0] == 'E':
            return tok[1] == 'Fire'                 # {R} == Fire
        return False
    return t.game._search_deck_to_hand(t.me, pred, 3) > 0


# ---------------- Explorer's Guidance ----------------
@trainer('supporter', "Look at the top 6 cards of your deck and put 2 of them into your hand. Discard the other cards.")
def _explorers_guidance(t):
    deck = t.me.deck
    if not deck:
        return False
    top = deck[-6:]
    t.me.deck = deck[:-6]
    keep = set(sorted(range(len(top)), key=lambda i: -_tok_priority(top[i]))[:2])   # 2 most useful
    got = False
    for i, tok in enumerate(top):
        if i in keep:
            t.me.hand.append(tok)
            got = True
        else:
            _discard_token(t.me, tok)
    return got
