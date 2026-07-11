#!/usr/bin/env python3
"""Trainer batch tr_item_3 — 14 Items (search / disruption / switch / evolve / heal).

Each is registered by its EXACT card text (normalize() strips a leading "- " and collapses
whitespace, so with/without the bullet and the Special-Red-Card newlines all key identically).
An Item fn takes a TrainerCtx `t` and returns True iff it did something meaningful.

Conventions matched to trainer_effects.py / engine.py / effects.py:
* Deck TOP = end of the list (Player.draw pops from the end); "bottom of the deck" = the front.
* Coin flip: heads == t.rng.random() < 0.5 (matches effects._flip_heads / can_attack; the test RNG
  scripts heads=0.0, tails=0.9).
* Energy routing: basic pips discard into me.disc_energy; special-energy pseudo-types
  ('Wild'/'Colorless') pop a name off mon.special (the engine tracks special energy off-hand).
* Supporter/Tool deck tokens are ('T', dict) with dict['trainerType'] in ('Supporter','Tool').
* UNMODELED RIDER (no engine hook): Premium Power Pro's turn-scoped {F} damage buff is recorded
  turn-stamped for future wiring (batch_misc_0 precedent) — inert, never fires a wrong number.
"""
from trainer_effects import trainer, TrainerCtx  # noqa: F401  (TrainerCtx re-exported per header)


# ---------------------------------------------------------------- exact card texts (single source)
POKEGEAR = ("Look at the top 7 cards of your deck. You may reveal a Supporter card you find there "
            "and put it into your hand. Shuffle the other cards back into your deck.")
POKEMON_CATCHER = ("Flip a coin. If heads, switch in 1 of your opponent's Benched Pokémon to the "
                   "Active Spot.")
PREMIUM_POWER_PRO = ("During this turn, attacks used by your {F} Pokémon do 30 more damage to your "
                     "opponent's Active Pokémon (before applying Weakness and Resistance).")
RARE_CANDY = ("Choose 1 of your Basic Pokémon in play. If you have a Stage 2 card in your hand that "
              "evolves from that Pokémon, put that card onto the Basic Pokémon to evolve it, skipping "
              "the Stage 1. You can't use this card during your first turn or on a Basic Pokémon that "
              "was put into play this turn.")
REDEEMABLE_TICKET = ("Count your Prize cards, shuffle them, and put them on the bottom of your deck. "
                     "Then, take that many cards from the top of your deck and put them face down as "
                     "your Prize cards.")
REPEL = ("Switch out your opponent's Active Pokémon to the Bench. (Your opponent chooses the new "
         "Active Pokémon.)")
ROTO_STICK = ("Look at the top 4 cards of your deck. You may reveal any number of Supporter cards you "
              "find there and put them into your hand. Shuffle the other cards back into your deck.")
SACRED_ASH = "Shuffle up to 5 Pokémon from your discard pile into your deck."
SPECIAL_RED_CARD = ("You can use this card only if your opponent has 3 or fewer Prize cards "
                    "remaining.\n\nYour opponent shuffles their hand and puts it on the bottom of "
                    "their deck. If they put any cards on the bottom of their deck in this way, they "
                    "draw 3 cards.")
STRANGE_TIMEPIECE = ("Devolve 1 of your evolved {P} Pokémon by putting any number of Evolution cards "
                     "on it into your hand. (That Pokémon can't evolve this turn.)")
SUPER_POTION = ("Heal 60 damage from 1 of your Pokémon. If you healed any damage in this way, discard "
                "an Energy from that Pokémon.")
SWITCH = "Switch your Active Pokémon with 1 of your Benched Pokémon."
TM_MACHINE = ('Search your deck for up to 3 Pokémon Tool cards that have "Technical Machine" in their '
              'name, reveal them, and put them into your hand. Then, shuffle your deck.')
BOTHER_BOT = ("Turn 1 of your opponent's face-down Prize cards face up and choose a random card from "
              "your opponent's hand. Your opponent reveals that card. You may have your opponent "
              "switch those cards. (That Prize card remains face up for the rest of the game.)")


# ---------------------------------------------------------------- module helpers
def _is_supporter(tok):
    return tok[0] == 'T' and tok[1].get('trainerType') == 'Supporter'


def _reveal_supporters(t, look, limit):
    """Pokégear/Roto-Stick core: reveal up to `limit` Supporters among the top `look` cards, put
    them into hand, then shuffle the deck. Returns how many were taken."""
    me = t.me
    cut = max(0, len(me.deck) - look)                 # top `look` cards = deck[cut:] (end = top)
    idxs = [i for i in range(len(me.deck) - 1, cut - 1, -1) if _is_supporter(me.deck[i])]
    moved = 0
    for i in idxs:                                    # descending indices -> safe to pop in order
        if moved >= limit:
            break
        me.hand.append(me.deck.pop(i))
        moved += 1
    t.rng.shuffle(me.deck)
    return moved


def _discard_one_energy(me, mon):
    """Discard 1 Energy from `mon`: basic pip -> me.disc_energy; special pseudo-pip -> pop a
    Special-Energy name. Mirrors the engine's retreat/discard routing (most-abundant type)."""
    if mon.total_energy() <= 0:
        return False
    typ = max(mon.energy, key=lambda k: mon.energy[k])
    mon.energy[typ] -= 1
    if mon.energy[typ] <= 0:
        del mon.energy[typ]
    if typ not in ('Wild', 'Colorless'):
        me.disc_energy[typ] += 1
    elif mon.special:
        mon.special.pop()
    return True


# ================================================================ deck-look / search Items
@trainer('item', POKEGEAR)
def _pokegear(t):
    # Look at top 7; reveal AT MOST ONE Supporter -> hand; shuffle the rest back.
    return _reveal_supporters(t, 7, 1) > 0


@trainer('item', ROTO_STICK)
def _roto_stick(t):
    # Look at top 4; reveal ANY NUMBER of Supporters -> hand; shuffle the rest back.
    return _reveal_supporters(t, 4, 4) > 0


@trainer('item', TM_MACHINE)
def _tm_machine(t):
    # Search deck for up to 3 Pokémon Tool cards named "...Technical Machine..." -> hand; shuffle.
    def pred(tok):
        return (tok[0] == 'T' and tok[1].get('trainerType') == 'Tool'
                and 'Technical Machine' in tok[1].get('name', ''))
    got = t.game._search_deck_to_hand(t.me, pred, 3)
    t.rng.shuffle(t.me.deck)
    return got > 0


@trainer('item', SACRED_ASH)
def _sacred_ash(t):
    # Shuffle up to 5 Pokémon from the discard pile back into the deck.
    me = t.me
    idxs = [i for i in range(len(me.discard)) if me.discard[i][0] == 'P'][:5]
    for i in reversed(idxs):                          # pop high->low to keep indices valid
        me.deck.append(me.discard.pop(i))
    if idxs:
        t.rng.shuffle(me.deck)
    return len(idxs) > 0


# ================================================================ switch / gust Items
@trainer('item', POKEMON_CATCHER)
def _pokemon_catcher(t):
    # Flip a coin; heads -> drag up an opponent's benched Pokémon (modeled as a KO-seeking gust).
    if t.rng.random() < 0.5:                          # heads
        return t.gust()
    return False


@trainer('item', REPEL)
def _repel(t):
    # Force the opponent's Active to the Bench; the OPPONENT picks the new Active from their existing
    # bench (readiest attacker), which must be a DIFFERENT Pokémon than the one just benched.
    opp = t.opp
    if not opp.active or not opp.bench:
        return False
    old = opp.active
    opp.bench.sort(key=lambda m: (m.total_energy(), m.card.hp), reverse=True)
    opp.active = opp.bench.pop(0)
    opp.active.came_from_bench = True
    opp.bench.append(old)
    return True


@trainer('item', SWITCH)
def _switch(t):
    # Switch your Active with 1 of your Benched Pokémon.
    return t.switch_self()


# ================================================================ evolve / devolve Items
@trainer('item', RARE_CANDY)
def _rare_candy(t):
    # Evolve a Basic in play straight to a Stage-2 in hand (engine helper enforces "in play >=1 turn").
    return t.game._rare_candy(t.me)


@trainer('item', STRANGE_TIMEPIECE)
def _strange_timepiece(t):
    # Devolve one of your evolved {P}(Psychic) Pokémon by one stage: the evolution card returns to
    # hand and the Pokémon becomes a printing of its named pre-evolution. The sim keeps no evolution
    # STACK on a Mon, so we devolve exactly one stage (the faithful minimal case) and block re-evolving
    # this turn (turns->0, so it can evolve again only next turn).
    from engine import BY_NAME
    me = t.me
    for mon in me.all_mons():
        if mon.card.stage >= 1 and mon.card.ptype == 'Psychic' and mon.card.evolves_from:
            pre = BY_NAME.get(mon.card.evolves_from)
            if not pre:
                continue
            me.hand.append(('P', mon.card))           # evolution card -> hand
            mon.card = pre[0]                         # devolve one stage
            mon.evolved_turn = -9
            mon.turns = 0                             # "can't evolve this turn"
            return True
    return False


# ================================================================ heal Item
@trainer('item', SUPER_POTION)
def _super_potion(t):
    # Heal 60 from your most-damaged Pokémon; if any damage was healed, discard 1 Energy from it.
    me = t.me
    tgt = max(me.all_mons(), key=lambda m: m.damage, default=None)
    if not tgt or tgt.damage <= 0:
        return False
    tgt.damage = max(0, tgt.damage - 60)
    _discard_one_energy(me, tgt)
    return True


# ================================================================ prize / hand disruption Items
@trainer('item', REDEEMABLE_TICKET)
def _redeemable_ticket(t):
    # Shuffle your Prizes to the bottom of the deck, then set out that many fresh Prizes off the top.
    me = t.me
    n = len(me.prizes)
    if n == 0:
        return False
    prizes = me.prizes
    me.prizes = []
    t.rng.shuffle(prizes)
    me.deck = prizes + me.deck                        # bottom of deck (front of the list)
    new = []
    for _ in range(n):
        if me.deck:
            new.append(me.deck.pop())                 # top of deck (end of the list)
    me.prizes = new
    return True


@trainer('item', SPECIAL_RED_CARD)
def _special_red_card(t):
    # Playable only when the opponent has <=3 Prize cards remaining. Opponent shuffles their hand to
    # the bottom of their deck; if any cards went down, they draw 3.
    opp = t.opp
    if len(opp.prizes) > 3:
        return False
    hand = opp.hand
    if not hand:
        return False
    opp.hand = []
    t.rng.shuffle(hand)
    opp.deck = hand + opp.deck                        # bottom of deck
    opp.draw(3)
    return True


@trainer('item', BOTHER_BOT)
def _bother_bot(t):
    # Face-up Prize tracking is cosmetic (no engine state). Model the mechanical option: swap 1 random
    # card from the opponent's hand with 1 of their Prize cards ("you may" resolved as disruption yes).
    opp = t.opp
    if not opp.hand or not opp.prizes:
        return False
    hi = t.rng.randint(0, len(opp.hand) - 1)
    pi = t.rng.randint(0, len(opp.prizes) - 1)
    opp.hand[hi], opp.prizes[pi] = opp.prizes[pi], opp.hand[hi]
    return True


# ================================================================ turn-scoped damage buff (rider)
@trainer('item', PREMIUM_POWER_PRO)
def _premium_power_pro(t):
    # +30 damage to the opponent's Active for your {F}(Fighting) Pokémon's attacks THIS turn (before
    # Weakness/Resistance). No damage-calc hook exists for trainer-played buffs, so record it
    # turn-stamped (a future team_attack_bonus-style reader keys off this flag / me.played, both of
    # which reset each turn -> naturally turn-scoped). Inert until wired; never applies a wrong number.
    t.me.premium_power_pro_turn = t.game.turn
    return True
