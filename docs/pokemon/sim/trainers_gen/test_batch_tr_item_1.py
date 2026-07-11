#!/usr/bin/env python3
"""Tests for batch tr_item_1 (Item trainers). Each item runs through a TrainerCtx over real
Player/Game objects (built by mk) and asserts the concrete state change it should make."""
from effects_testkit import mk, runner, BK
from engine import Mon
import trainer_effects as TE
import trainers_gen.batch_tr_item_1        # noqa: F401  (registers the batch effects on import)


def _fn(text):
    return TE.TRAINER_EFFECTS[TE.normalize(text)]['fn']


def _ctx(**kw):
    ctx, at, df, me, opp = mk(**kw)
    return TE.TrainerCtx(me, opp, ctx.game), me, opp


TESTS = []
def test(f): TESTS.append(f); return f


@test
def t_deduction_kit():
    t, me, opp = _ctx()
    n = len(me.deck)
    did = _fn("Look at the top 3 cards of your deck and put them back in any order, or shuffle them and put them on the bottom of your deck.")(t)
    assert did is True and len(me.deck) == n          # card-neutral look, deck size preserved


@test
def t_dragon_elixir():
    t, me, opp = _ctx()
    dragon = next(c for c in BK.values() if c.ptype == 'Dragon')
    me.active = Mon(dragon); me.active.damage = 60
    did = _fn("Heal 60 damage from your Active {N} Pokémon.")(t)
    assert did and me.active.damage == 0


@test
def t_dragon_elixir_non_dragon():
    t, me, opp = _ctx()
    me.active.damage = 60                             # VANILLA is not Dragon -> no heal
    did = _fn("Heal 60 damage from your Active {N} Pokémon.")(t)
    assert not did and me.active.damage == 60


@test
def t_dusk_ball():
    t, me, opp = _ctx()
    before = sum(1 for x in me.hand if x[0] == 'P')
    did = _fn("Look at the bottom 7 cards of your deck. You may reveal a Pokémon you find there and put it into your hand. Shuffle the other cards back into your deck.")(t)
    assert did and sum(1 for x in me.hand if x[0] == 'P') == before + 1


@test
def t_earthen_vessel():
    t, me, opp = _ctx()
    victim = ('P', BK[list(BK)[0]])
    me.hand = [victim]                                # one discardable non-Vessel card
    did = _fn("You can use this card only if you discard another card from your hand.\n\nSearch your deck for up to 2 Basic Energy cards, reveal them, and put them into your hand. Then, shuffle your deck.")(t)
    assert did and victim in me.discard and sum(1 for x in me.hand if x[0] == 'E') == 2


@test
def t_energy_coin():
    t, me, opp = _ctx(flips=(0.0,))                   # both coins heads
    before = sum(m.total_energy() for m in me.all_mons())
    did = _fn("Flip 2 coins. If both of them are heads, search your deck for a Basic Energy card and attach it to 1 of your Pokémon. Then, shuffle your deck.")(t)
    assert did and sum(m.total_energy() for m in me.all_mons()) == before + 1


@test
def t_energy_coin_tails():
    t, me, opp = _ctx(flips=(0.9,))                   # tails -> nothing
    before = sum(m.total_energy() for m in me.all_mons())
    did = _fn("Flip 2 coins. If both of them are heads, search your deck for a Basic Energy card and attach it to 1 of your Pokémon. Then, shuffle your deck.")(t)
    assert not did and sum(m.total_energy() for m in me.all_mons()) == before


@test
def t_energy_recycler():
    t, me, opp = _ctx()
    me.disc_energy['Fire'] = 7
    dn = len(me.deck)
    did = _fn("Shuffle up to 5 Basic Energy cards from your discard pile into your deck.")(t)
    assert did and me.disc_energy['Fire'] == 2 and len(me.deck) == dn + 5


@test
def t_energy_retrieval():
    t, me, opp = _ctx()
    me.disc_energy['Water'] = 3
    did = _fn("Put up to 2 Basic Energy cards from your discard pile into your hand.")(t)
    assert did and me.disc_energy['Water'] == 1 and sum(1 for x in me.hand if x == ('E', 'Water')) == 2


@test
def t_energy_search():
    t, me, opp = _ctx()
    did = _fn("Search your deck for a Basic Energy card, reveal it, and put it into your hand. Then, shuffle your deck.")(t)
    assert did and any(x[0] == 'E' for x in me.hand)


@test
def t_energy_swatter():
    t, me, opp = _ctx()
    opp.hand = [('E', 'Fire')]
    did = _fn("Your opponent reveals their hand, and you choose an Energy card you find there and put it on the bottom of their deck.")(t)
    assert did and ('E', 'Fire') not in opp.hand and opp.deck[0] == ('E', 'Fire')


@test
def t_energy_switch():
    t, me, opp = _ctx()
    me.bench[0].energy['Fighting'] += 1               # stranded basic energy on the bench
    did = _fn("Move a Basic Energy from 1 of your Pokémon to another of your Pokémon.")(t)
    assert did and me.active.energy.get('Fighting', 0) == 1 and me.bench[0].energy.get('Fighting', 0) == 0


@test
def t_enhanced_hammer():
    t, me, opp = _ctx(def_special=('Prism Energy',), def_energy={'Wild': 1})
    did = _fn("Discard a Special Energy from 1 of your opponent's Pokémon.")(t)
    assert did and 'Prism Energy' not in opp.active.special and opp.active.energy.get('Wild', 0) == 0


@test
def t_enhanced_hammer_none():
    t, me, opp = _ctx()                               # opponent has no special energy attached
    did = _fn("Discard a Special Energy from 1 of your opponent's Pokémon.")(t)
    assert not did


@test
def t_fighting_gong():
    t, me, opp = _ctx()
    fpk = next(c for c in BK.values() if c.ptype == 'Fighting' and c.stage == 0)
    me.deck.append(('P', fpk))                        # a Basic Fighting Pokémon on top
    did = _fn("Search your deck for a Basic {F} Energy card or a Basic {F} Pokémon, reveal it, and put it into your hand. Then, shuffle your deck.")(t)
    assert did and ('P', fpk) in me.hand


@test
def t_glass_trumpet():
    t, me, opp = _ctx()
    me.disc_energy['Water'] = 2
    did = _fn("You can use this card only if you have any Tera Pokémon in play.\n\nChoose up to 2 of your Benched {C} Pokémon and attach a Basic Energy card from your discard pile to each of them.")(t)
    assert not did and me.disc_energy['Water'] == 2   # Tera unmodeled -> conservative no-op


@test
def t_great_haul_net():
    t, me, opp = _ctx()
    wpk = next(c for c in BK.values() if c.ptype == 'Water')
    me.discard = [('P', wpk)]
    me.disc_energy['Water'] = 2
    dn = len(me.deck)
    did = _fn("Choose 1 or both:\n• Shuffle up to 3 {W} Pokémon from your discard pile into your deck.\n• Shuffle up to 3 Basic {W} Energy cards from your discard pile into your deck.")(t)
    assert did and ('P', wpk) in me.deck and me.disc_energy.get('Water', 0) == 0 and len(me.deck) == dn + 3


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
