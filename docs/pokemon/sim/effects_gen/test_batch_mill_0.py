#!/usr/bin/env python3
"""Unit tests for effect batch mill_0."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # ensure sim/ importable
import types
from collections import Counter
from effects_testkit import mk, run, runner
import attack_effects as AE
import effects_gen.batch_mill_0  # noqa: F401  (registers the effects)

# In mk(): me/opp.hand start empty; each deck has 16 tokens (6 Pokémon then 10 Colorless energy),
# so the TOP (deck[-1]) is a ('E','Colorless') token; heads=0.0, tails=0.9.

KEY_MILL1 = "Discard the top card of your opponent's deck."
KEY_MILL2 = "Discard the top 2 cards of your opponent's deck."
KEY_ANCIENT = ("Discard the top card of your opponent's deck. If you played an Ancient Supporter "
               "card from your hand during this turn, discard 3 more cards in this way.")
KEY_TARRAGON = ("If you played Tarragon from your hand during this turn, discard the top 3 cards "
                "of your opponent's deck.")
KEY_SELF1 = "Discard the top card of your deck."
KEY_LOOK5 = "Look at the top 5 cards of your opponent's deck and put them back in any order."
KEY_LOOKSELF = "Look at the top card of your deck. You may discard that card."
KEY_LOOKSHUF = "Look at the top card of your opponent's deck. You may have your opponent shuffle their deck."
KEY_NINETALES = ("Discard the top card of your deck, and if that card is a Supporter card, "
                 "use the effect of that card as the effect of this attack.")
KEY_SLOWKING = ("Discard the top card of your deck, and if that card is a Pokémon that doesn't have "
                "a Rule Box, choose 1 of its attacks and use it as this attack. "
                "(Pokémon ex, Pokémon V, etc. have Rule Boxes.)")


def _fn(text):
    return AE.ATTACK_EFFECTS[AE.normalize(text)]


# ---------------------------------------------------------------- mill the opponent

def t_mill_opp_1():
    d, ctx, at, df, me, opp = run("[10] " + KEY_MILL1, base=10)
    assert d == 10, d                                 # returns printed base (Larvitar/Spiritomb 10)
    assert len(opp.deck) == 15, len(opp.deck)         # one card gone from the top
    assert opp.disc_energy['Colorless'] == 1, opp.disc_energy   # milled basic energy -> disc_energy


def t_mill_opp_1_zero_base():
    d, ctx, at, df, me, opp = run("- " + KEY_MILL1, base=0)     # Drilbur: no damage
    assert d == 0, d
    assert len(opp.deck) == 15, len(opp.deck)


def t_mill_opp_1_empty_deck():
    ctx, at, df, me, opp = mk(text=KEY_MILL1, base=10)
    opp.deck = []                                     # empty deck -> mill is a clean no-op
    d = _fn(KEY_MILL1)(ctx)
    assert d == 10 and len(opp.deck) == 0, (d, len(opp.deck))


def t_mill_opp_2():
    d, ctx, at, df, me, opp = run("[150] " + KEY_MILL2, base=150)   # Coalossal 150
    assert d == 150, d
    assert len(opp.deck) == 14, len(opp.deck)         # two cards milled
    assert opp.disc_energy['Colorless'] == 2, opp.disc_energy


def t_mill_opp_2_zero_base():
    d, ctx, at, df, me, opp = run("- " + KEY_MILL2, base=0)         # Zweilous: no damage
    assert d == 0 and len(opp.deck) == 14, (d, len(opp.deck))


def t_mill_opp_1_pokemon_to_discard():
    # A NON-energy top card (Pokémon) mills into the discard LIST, never disc_energy.
    ctx, at, df, me, opp = mk(text=KEY_MILL1, base=10)
    poke = opp.deck[0]                                 # ('P', VANILLA) — put a copy on top
    opp.deck.append(poke)
    n0 = len(opp.deck)
    d = _fn(KEY_MILL1)(ctx)
    assert d == 10, d
    assert len(opp.deck) == n0 - 1, len(opp.deck)      # exactly one card milled
    assert poke in opp.discard, opp.discard            # Pokémon -> discard list
    assert opp.disc_energy == Counter(), opp.disc_energy   # NOT routed to disc_energy


# ---------------------------------------------------------------- gated mills (condition unobservable)

def t_ancient_baseline():
    # No Ancient-Supporter flag -> only 1 card milled (never the speculative +3).
    d, ctx, at, df, me, opp = run("- " + KEY_ANCIENT, base=0)
    assert d == 0, d
    assert len(opp.deck) == 15, len(opp.deck)


def t_ancient_boosted():
    # Flag set -> 1 + 3 = 4 cards milled.
    ctx, at, df, me, opp = mk(text=KEY_ANCIENT, base=0)
    me.played_ancient_supporter_this_turn = True
    d = _fn(KEY_ANCIENT)(ctx)
    assert d == 0, d
    assert len(opp.deck) == 12, len(opp.deck)         # 16 - 4


def t_tarragon_baseline():
    # Tarragon not played this turn -> base damage only, opponent's deck untouched.
    d, ctx, at, df, me, opp = run("[80] " + KEY_TARRAGON, base=80)
    assert d == 80, d
    assert len(opp.deck) == 16, len(opp.deck)


def t_tarragon_boosted():
    # Tarragon played from hand this turn (tracked in me.played) -> mill 3 off the opponent's deck.
    ctx, at, df, me, opp = mk(text=KEY_TARRAGON, base=80, played=['Tarragon'])
    d = _fn(KEY_TARRAGON)(ctx)
    assert d == 80, d                                 # damage unchanged
    assert len(opp.deck) == 13, len(opp.deck)         # 16 - 3 milled
    assert opp.disc_energy['Colorless'] == 3, opp.disc_energy   # milled basic energy -> disc_energy


# ---------------------------------------------------------------- discard from own deck

def t_mill_self_1():
    d, ctx, at, df, me, opp = run("[80] " + KEY_SELF1, base=80)     # Fraxure 80
    assert d == 80, d
    assert len(me.deck) == 15, len(me.deck)           # discards from MY deck, not opponent's
    assert len(opp.deck) == 16, len(opp.deck)
    assert me.disc_energy['Colorless'] == 1, me.disc_energy


# ---------------------------------------------------------------- look / reorder (non-destructive)

def t_look_opp_5():
    d, ctx, at, df, me, opp = run("- " + KEY_LOOK5, base=0)
    assert d == 0, d
    assert len(opp.deck) == 16, len(opp.deck)         # decks untouched
    assert opp.discard == [] and opp.disc_energy == Counter()


def t_look_self_may_discard():
    d, ctx, at, df, me, opp = run("- " + KEY_LOOKSELF, base=0)
    assert d == 0 and len(me.deck) == 16, (d, len(me.deck))
    assert me.discard == []


def t_look_opp_may_shuffle():
    d, ctx, at, df, me, opp = run("- " + KEY_LOOKSHUF, base=0)
    assert d == 0 and len(opp.deck) == 16, (d, len(opp.deck))


# ---------------------------------------------------------------- Ninetales: discard-and-use-supporter

def t_ninetales_supporter_top():
    # A Supporter on top of the deck is discarded, then its effect resolves (here: draw 2).
    ctx, at, df, me, opp = mk(text=KEY_NINETALES, base=0)
    sup = ('T', {'name': 'Professor', 'trainerType': 'Supporter', 'effect': 'Draw 2 cards.'})
    me.deck.append(sup)                               # place it on TOP (end of list)
    d = _fn(KEY_NINETALES)(ctx)
    assert d == 0, d
    assert sup in me.discard, me.discard              # supporter discarded
    assert len(me.hand) == 2, len(me.hand)            # its draw-2 effect resolved


def t_ninetales_nonsupporter_top():
    # Top card is basic energy -> discarded to disc_energy, no supporter effect, no draw.
    ctx, at, df, me, opp = mk(text=KEY_NINETALES, base=0)
    d = _fn(KEY_NINETALES)(ctx)
    assert d == 0, d
    assert me.disc_energy['Colorless'] == 1, me.disc_energy
    assert len(me.hand) == 0, len(me.hand)            # no supporter -> no effect


def t_ninetales_item_top_no_effect():
    # A non-Supporter Trainer (Item) on top -> discarded, but its effect is NOT used.
    # Guards the "if that card is a Supporter" condition from firing on ANY Trainer:
    # the Item's effect text is a live 'Draw 2 cards.' so a false positive would grow the hand.
    ctx, at, df, me, opp = mk(text=KEY_NINETALES, base=0)
    item = ('T', {'name': 'Fake Item', 'trainerType': 'Item', 'effect': 'Draw 2 cards.'})
    me.deck.append(item)                              # place on TOP (end of list)
    d = _fn(KEY_NINETALES)(ctx)
    assert d == 0, d
    assert item in me.discard, me.discard             # Item still discarded
    assert len(me.hand) == 0, me.hand                 # NOT a Supporter -> draw-2 never resolves


# ---------------------------------------------------------------- Slowking: discard-and-copy-attack

def t_slowking_copies_nonex():
    # Non-ex Pokémon on top -> its biggest attack becomes this attack's damage.
    ctx, at, df, me, opp = mk(text=KEY_SLOWKING, base=0)
    fake = types.SimpleNamespace(
        name='Fake', is_ex=False,
        attacks=[{'dmg': 10, 'text': '', 'cost': '', 'name': 'Poke'},
                 {'dmg': 30, 'text': '', 'cost': '', 'name': 'Tackle'}])
    me.deck.append(('P', fake))
    d = _fn(KEY_SLOWKING)(ctx)
    assert d == 30, d                                 # copies the 30-damage attack (the bigger one)
    assert ('P', fake) in me.discard, me.discard


def t_slowking_copies_effect_attack():
    # Copied attack carries a registered effect (heads +20) -> full effect resolves via the registry.
    ctx, at, df, me, opp = mk(text=KEY_SLOWKING, base=0, flips=(0.0,))
    fake = types.SimpleNamespace(
        name='Fake2', is_ex=False,
        attacks=[{'dmg': 10, 'text': 'Flip a coin. If heads, this attack does 20 more damage.',
                  'cost': '', 'name': 'Gamble'}])
    me.deck.append(('P', fake))
    d = _fn(KEY_SLOWKING)(ctx)
    assert d == 30, d                                 # 10 base + 20 on heads (scripted heads)


def t_slowking_ex_does_nothing():
    # A Rule-Box Pokémon (ex) on top -> discarded but NOT copied -> attack does 0.
    ctx, at, df, me, opp = mk(text=KEY_SLOWKING, base=0)
    exmon = types.SimpleNamespace(name='Fex', is_ex=True,
                                  attacks=[{'dmg': 100, 'text': '', 'cost': '', 'name': 'Big'}])
    me.deck.append(('P', exmon))
    d = _fn(KEY_SLOWKING)(ctx)
    assert d == 0, d
    assert ('P', exmon) in me.discard, me.discard     # still discarded


def t_slowking_energy_top_does_nothing():
    # Top card is energy (not a Pokémon) -> milled to disc_energy, attack does 0.
    ctx, at, df, me, opp = mk(text=KEY_SLOWKING, base=0)
    d = _fn(KEY_SLOWKING)(ctx)
    assert d == 0, d
    assert me.disc_energy['Colorless'] == 1, me.disc_energy


def t_slowking_trainer_top_does_nothing():
    # A Trainer (non-Pokémon) on top -> discarded, nothing to copy -> 0 damage.
    ctx, at, df, me, opp = mk(text=KEY_SLOWKING, base=0)
    tr = ('T', {'name': 'Fake Item', 'trainerType': 'Item', 'effect': ''})
    me.deck.append(tr)
    d = _fn(KEY_SLOWKING)(ctx)
    assert d == 0, d
    assert tr in me.discard, me.discard               # Trainer routed to discard, no attack copied


def t_slowking_nonex_no_attacks():
    # A non-ex Pokémon with NO attacks -> nothing to copy -> 0 damage, still discarded.
    ctx, at, df, me, opp = mk(text=KEY_SLOWKING, base=0)
    fake = types.SimpleNamespace(name='Blank', is_ex=False, attacks=[])
    me.deck.append(('P', fake))
    d = _fn(KEY_SLOWKING)(ctx)
    assert d == 0, d
    assert ('P', fake) in me.discard, me.discard


TESTS = [
    t_mill_opp_1,
    t_mill_opp_1_zero_base,
    t_mill_opp_1_empty_deck,
    t_mill_opp_1_pokemon_to_discard,
    t_mill_opp_2,
    t_mill_opp_2_zero_base,
    t_ancient_baseline,
    t_ancient_boosted,
    t_tarragon_baseline,
    t_tarragon_boosted,
    t_mill_self_1,
    t_look_opp_5,
    t_look_self_may_discard,
    t_look_opp_may_shuffle,
    t_ninetales_supporter_top,
    t_ninetales_nonsupporter_top,
    t_ninetales_item_top_no_effect,
    t_slowking_copies_nonex,
    t_slowking_copies_effect_attack,
    t_slowking_ex_does_nothing,
    t_slowking_energy_top_does_nothing,
    t_slowking_trainer_top_does_nothing,
    t_slowking_nonex_no_attacks,
]

if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
