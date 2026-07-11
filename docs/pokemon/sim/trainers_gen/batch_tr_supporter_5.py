#!/usr/bin/env python3
"""Generated trainer batch: tr_supporter_5 (3 Supporters).

Each effect is registered by its EXACT printed text via @trainer('supporter', text).
An action fn takes a TrainerCtx (tctx) and returns True if it did something.

Model reminders (see engine.py):
  - Deck/hand tokens: ('P', Card) | ('E', type_str) | ('T', trainer_dict) | ('S', special_dict).
  - Top of deck == END of the deck list (draw() does deck.pop()).
  - Discarded basic energy goes to player.disc_energy (a Counter); other cards to player.discard.
  - Attached Special Energy lives in Mon.special (list of names) plus the pips SE.provides()
    puts in Mon.energy; basic energy is the rest of the Mon.energy Counter.
"""
from trainer_effects import trainer, TrainerCtx
import special_energy as SE

# type name -> attack-cost letter
_T2L = {'Grass': 'G', 'Fire': 'R', 'Water': 'W', 'Lightning': 'L', 'Psychic': 'P',
        'Fighting': 'F', 'Darkness': 'D', 'Metal': 'M', 'Colorless': 'C'}


# ---------------- shared helpers ----------------
def _needed_letters(game, mon):
    """Cost letters of the mon's cheapest damaging attack (what energy it still wants)."""
    if mon is None:
        return []
    c = game._cheapest_cost(mon)
    return list(c) if c else []


def _discard_token(pl, tok):
    """Route a discarded hand token to its pile: basic energy -> disc_energy Counter, else discard."""
    if tok[0] == 'E':
        pl.disc_energy[tok[1]] += 1
    else:
        pl.discard.append(tok)


def _keep_priority(tok):
    """How much a player wants to KEEP a card when forced to discard (higher = keep).
    Basics can hit the board now, then evolutions, then energy, then situational Trainers."""
    k = tok[0]
    if k == 'P':
        return 4 if tok[1].stage == 0 else 3
    if k in ('E', 'S'):
        return 2
    return 1


# ---------------- Waitress ----------------
@trainer('supporter', "Look at the top 6 cards of your deck and attach a Basic Energy card you find there to 1 of your Pokémon. Shuffle the other cards back into your deck.")
def _waitress(t):
    me = t.me
    n = len(me.deck)
    top_idxs = range(max(0, n - 6), n)                          # the top 6 cards (end of the list)
    energy_idxs = [i for i in top_idxs if me.deck[i][0] == 'E']  # Basic Energy tokens among them
    if not energy_idxs:
        t.rng.shuffle(me.deck)                                  # looked, found none -> shuffle back
        return False
    tgt = t.primary()
    if tgt is None:
        t.rng.shuffle(me.deck)
        return False
    need = _needed_letters(t.game, tgt)
    energy_idxs.sort(key=lambda i: 0 if _T2L.get(me.deck[i][1]) in need else 1)  # prefer a needed type
    pick = energy_idxs[0]
    etype = me.deck[pick][1]
    me.deck.pop(pick)
    tgt.energy[etype] += 1                                      # attach it
    t.rng.shuffle(me.deck)                                      # "shuffle the other cards back"
    return True


# ---------------- Wally's Compassion ----------------
@trainer('supporter', "Heal all damage from 1 of your Mega Evolution Pokémon ex. If you healed any damage in this way, put all Energy attached to that Pokémon into your hand.")
def _wallys_compassion(t):
    # Mega Evolution Pokémon ex = name starts with "Mega " and is an ex. Only useful on a damaged one
    # (an undamaged target heals nothing, so the energy-return clause never triggers).
    megas = [m for m in t.me.all_mons()
             if m.card.name.startswith('Mega ') and m.card.is_ex and m.damage > 0]
    if not megas:
        return False
    mon = max(megas, key=lambda m: m.damage)
    mon.damage = 0                                              # heal all damage
    # put all Energy attached to that Pokémon into hand. Special energy first: return each as an
    # ('S', ...) token and net out the pips it provided (a 'typed' special like Magnetic Metal nets a
    # real pip out of the basic count; a colorless/wild special nets its pseudo-pip). Then return the
    # remaining REAL-typed pips as basic Energy. 'Wild'/'Colorless' are never basic Energy cards (all
    # basic energy is typed -- verified across the whole deck field), so any residual pseudo-pip is
    # dropped, not mis-returned: SE.provides is stage-dependent, so Prism's Wild pip (given while the
    # pre-evo was Basic) no longer matches once the mon has evolved into this Mega ex.
    while mon.special:
        name = mon.special.pop()
        for tp, c in SE.provides(name, mon.card).items():
            mon.energy[tp] -= c
        t.me.hand.append(('S', {'special_energy': name}))
    for tp, c in list(mon.energy.items()):
        if tp in ('Wild', 'Colorless'):                        # special-only pseudo-pip, never a basic card
            continue
        for _ in range(max(0, c)):
            t.me.hand.append(('E', tp))
    mon.energy.clear()
    return True


# ---------------- Xerosic's Machinations ----------------
@trainer('supporter', "Your opponent discards cards from their hand until they have 3 cards in their hand.")
def _xerosics_machinations(t):
    opp = t.opp
    if len(opp.hand) <= 3:
        return False
    # the opponent chooses what to discard, so they keep their 3 most useful cards.
    order = sorted(range(len(opp.hand)), key=lambda i: _keep_priority(opp.hand[i]))
    to_discard = order[:len(opp.hand) - 3]                      # the lowest-priority surplus
    for i in sorted(to_discard, reverse=True):
        _discard_token(opp, opp.hand.pop(i))
    return True
