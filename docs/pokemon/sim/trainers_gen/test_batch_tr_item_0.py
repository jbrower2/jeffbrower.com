# -*- coding: utf-8 -*-
"""Unit tests for trainer batch tr_item_0 (Items)."""
from collections import Counter
from effects_testkit import mk, runner
import trainer_effects as TE
import trainers_gen.batch_tr_item_0          # noqa: F401  (registers the effects)
from cards import load_cards, Card
from engine import Mon

BK, BN = load_cards()
CATERPIE = BN['Caterpie'][0]        # 50 HP Basic
TYRUNT = BN['Tyrunt'][0]            # Stage1, evolves from "Antique Jaw Fossil"
BULBASAUR = BN['Bulbasaur'][0]      # 80 HP Basic, Grass

# exact registration texts
FLUTE = "Reveal the top 5 cards of your opponent's deck. You may choose any number of Basic Pokémon you find there and put those Pokémon onto their Bench. Your opponent shuffles the other cards back into their deck."
FOSSIL = "Play this card as if it were a 60-HP Basic {C} Pokémon. This card can't be affected by any Special Conditions and can't retreat.\n\nAt any time during your turn, you may discard this card from play."
SANDWICH = "Heal 30 damage from your Active Pokémon. If that Pokémon is an Arven's Pokémon, heal 100 damage from it instead."
BLOWTORCH = "You can use this card only if you discard a Basic {R} Energy card from your hand.\n\nDiscard a Pokémon Tool or Special Energy card from 1 of your opponent's Pokémon, or discard a Stadium in play."
BOXED = "Search your deck for up to 2 Item cards, reveal them, and put them into your hand. Then, shuffle your deck. Your turn ends."
POFFIN = "Search your deck for up to 2 Basic Pokémon with 70 HP or less and put them onto your Bench. Then, shuffle your deck."
BUGSET = "Look at the top 7 cards of your deck. You may reveal up to 2 in any combination of {G} Pokémon and Basic {G} Energy cards you find there and put them into your hand. Shuffle the other cards back into your deck."
CALLBELL = "You can use this card only if you go second, and only during your first turn.\n\nSearch your deck for a Supporter card, reveal it, and put it into your hand. Then, shuffle your deck."
CHILL = "You can use this card only if you go second, and only during your first turn.\n\nPut an Energy attached to 1 of your opponent's Pokémon into their hand."
HAMMER = "Flip a coin. If heads, discard an Energy from 1 of your opponent's Pokémon."


def fn(text):
    return TE.TRAINER_EFFECTS[TE.normalize(text)]['fn']


def build(**kw):
    ctx, at, df, me, opp = mk(**kw)
    return TE.TrainerCtx(me, opp, ctx.game), me, opp, ctx.game


def _mkcard(name, hp=200):
    c = Card.__new__(Card)
    c.name = name; c.set = 'X'; c.id = '0'; c.cat = 'cat-yellow'; c.price = 0.0; c.is_ex = True
    c.energy = []; c.hp = hp; c.stage = 0; c.evolves_from = None; c.ptype = 'Darkness'
    c.weakness = None; c.retreat = 2; c.attacks = []; c.abilities = []
    return c


TESTS = []
def test(f): TESTS.append(f); return f


@test
def t_accompanying_flute():
    t, me, opp, g = build()
    opp.deck = [('E', 'Colorless')] * 4 + [('P', BULBASAUR)]        # a Basic in the top 5
    before = len(opp.bench)
    assert fn(FLUTE)(t) and len(opp.bench) == before + 1
    # no basics in the top 5 -> nothing benched
    t2, me2, opp2, g2 = build()
    opp2.deck = [('E', 'Colorless')] * 5
    assert fn(FLUTE)(t2) is False


@test
def t_antique_fossil():
    t, me, opp, g = build()
    me.deck = me.deck + [('P', TYRUNT)]                             # deck runs a Fossil evolution
    before = len(me.bench)
    assert fn(FOSSIL)(t) and len(me.bench) == before + 1
    nm = me.bench[-1]
    assert nm.card.hp == 60 and nm.card.stage == 0
    assert nm.card.name == 'Antique Jaw Fossil'                     # matches Tyrunt.evolves_from
    assert TYRUNT.evolves_from == nm.card.name and TYRUNT.stage == nm.card.stage + 1
    # no Fossil evolution in deck -> effectively dead (no-op)
    t2, me2, opp2, g2 = build()
    me2.deck = [('E', 'Colorless')] * 5
    assert fn(FOSSIL)(t2) is False


@test
def t_arvens_sandwich():
    t, me, opp, g = build()
    me.active.damage = 50
    assert fn(SANDWICH)(t) and me.active.damage == 20              # non-Arven's: heal 30
    me.active.damage = 0
    assert fn(SANDWICH)(t) is False                                # undamaged: no-op
    # Arven's Pokémon heals 100 instead
    t2, me2, opp2, g2 = build()
    me2.active = Mon(_mkcard("Arven's Mabosstiff ex", hp=200))
    me2.active.damage = 100
    assert fn(SANDWICH)(t2) and me2.active.damage == 0


@test
def t_blowtorch():
    # discard a Tool from an opponent's Pokémon (paying a basic Fire)
    t, me, opp, g = build()
    me.hand.append(('E', 'Fire'))
    opp.active.tools = ['Rescue Board']
    assert fn(BLOWTORCH)(t) and not opp.active.tools and me.disc_energy['Fire'] == 1
    # can't use without a basic Fire in hand
    t2, me2, opp2, g2 = build()
    opp2.active.tools = ['Rescue Board']
    assert fn(BLOWTORCH)(t2) is False
    # Fire in hand but no legal target -> don't play (Fire stays)
    t3, me3, opp3, g3 = build()
    me3.hand.append(('E', 'Fire'))
    assert fn(BLOWTORCH)(t3) is False and ('E', 'Fire') in me3.hand
    # discard a Stadium in play
    t4, me4, opp4, g4 = build(stadium='Prism Tower')
    me4.hand.append(('E', 'Fire'))
    assert fn(BLOWTORCH)(t4) and g4.stadium is None
    # discard a Special Energy from an opponent's Pokémon
    t5, me5, opp5, g5 = build()
    me5.hand.append(('E', 'Fire'))
    opp5.active.special = ['Prism Energy']
    opp5.active.energy = Counter({'Wild': 1})
    assert fn(BLOWTORCH)(t5) and not opp5.active.special


@test
def t_boxed_order():
    t, me, opp, g = build()
    me.deck.append(('T', {'name': 'Nest Ball', 'trainerType': 'Item'}))
    me.deck.append(('T', {'name': 'Ultra Ball', 'trainerType': 'Item'}))
    assert fn(BOXED)(t)
    assert sum(1 for x in me.hand if x[0] == 'T' and x[1]['trainerType'] == 'Item') == 2
    # no Items in deck -> nothing
    t2, me2, opp2, g2 = build()
    assert fn(BOXED)(t2) is False


@test
def t_buddy_buddy_poffin():
    t, me, opp, g = build()
    me.deck.append(('P', CATERPIE))                                # 50 HP basic
    before = len(me.bench)
    assert fn(POFFIN)(t) and len(me.bench) == before + 1
    assert me.bench[-1].card.name == 'Caterpie'
    # default deck's only basics are Bulbasaur (80 HP) -> none qualify
    t2, me2, opp2, g2 = build()
    assert fn(POFFIN)(t2) is False


@test
def t_bug_catching_set():
    t, me, opp, g = build()
    me.deck = [('E', 'Colorless')] * 5 + [('P', BULBASAUR), ('E', 'Grass')]   # top 7 has both
    assert fn(BUGSET)(t)
    assert ('P', BULBASAUR) in me.hand and ('E', 'Grass') in me.hand
    # non-grass top 7 -> nothing
    t2, me2, opp2, g2 = build()
    me2.deck = [('E', 'Colorless')] * 7
    assert fn(BUGSET)(t2) is False


@test
def t_call_bell():
    t, me, opp, g = build()
    g.turn = 1                                                     # going-2nd player's first turn
    me.deck.append(('T', {'name': 'Professor', 'trainerType': 'Supporter'}))
    assert fn(CALLBELL)(t) and any(x[0] == 'T' and x[1]['trainerType'] == 'Supporter' for x in me.hand)
    # not the first turn (going second) -> can't use
    t2, me2, opp2, g2 = build()
    g2.turn = 3
    me2.deck.append(('T', {'name': 'Professor', 'trainerType': 'Supporter'}))
    assert fn(CALLBELL)(t2) is False


@test
def t_chill_teaser_toy():
    t, me, opp, g = build()
    g.turn = 1
    opp.active.energy = Counter({'Fire': 1})
    assert fn(CHILL)(t) and opp.active.total_energy() == 0
    assert ('E', 'Fire') in opp.hand                               # energy bounced to opp's hand
    # wrong turn -> can't use
    t2, me2, opp2, g2 = build()
    g2.turn = 3
    opp2.active.energy = Counter({'Fire': 1})
    assert fn(CHILL)(t2) is False


@test
def t_crushing_hammer_heads():
    t, me, opp, g = build(flips=(0.0,))                            # heads
    opp.active.energy = Counter({'Fire': 2})
    assert fn(HAMMER)(t)
    assert opp.active.energy['Fire'] == 1 and opp.disc_energy['Fire'] == 1


@test
def t_crushing_hammer_tails():
    t, me, opp, g = build(flips=(0.9,))                            # tails
    opp.active.energy = Counter({'Fire': 2})
    assert fn(HAMMER)(t) is False and opp.active.energy['Fire'] == 2


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f"{p} pass {f} fail")
    raise SystemExit(1 if f else 0)
