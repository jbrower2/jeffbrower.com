#!/usr/bin/env python3
"""Unit tests for trainer batch tr_supporter_5 (3 Supporters).
Supporter actions run through a TrainerCtx over real Player/Game objects built by mk()."""
from collections import Counter
from effects_testkit import mk, runner, BK, VANILLA
import trainer_effects as TE
import trainers_gen.batch_tr_supporter_5  # noqa: F401  (registers the effects)
from engine import Mon

MEGA = next(c for c in BK.values() if c.name.startswith('Mega ') and c.is_ex)

W_WAITRESS = "Look at the top 6 cards of your deck and attach a Basic Energy card you find there to 1 of your Pokémon. Shuffle the other cards back into your deck."
W_WALLY = "Heal all damage from 1 of your Mega Evolution Pokémon ex. If you healed any damage in this way, put all Energy attached to that Pokémon into your hand."
W_XEROSIC = "Your opponent discards cards from their hand until they have 3 cards in their hand."


def fn(text):
    return TE.TRAINER_EFFECTS[TE.normalize(text)]['fn']


def ctx_of(me, opp, game):
    return TE.TrainerCtx(me, opp, game)


TESTS = []
def test(f): TESTS.append(f); return f


@test
def t_waitress():
    # Default deck: 6 Pokémon then 10 ('E','Colorless'); the top 6 are all Basic Energy.
    ctx, at, df, me, opp = mk()
    deck_n = len(me.deck)
    before = at.energy.get('Colorless', 0)
    did = fn(W_WAITRESS)(ctx_of(me, opp, ctx.game))
    assert did, "Waitress should attach a basic energy from the top 6"
    # one energy left the deck and landed on the primary attacker (the Active here)
    assert len(me.deck) == deck_n - 1
    assert at.energy.get('Colorless', 0) == before + 1
    # ...and no energy token leaked into the hand
    assert not any(t[0] == 'E' for t in me.hand)


@test
def t_waitress_no_energy_in_top6():
    ctx, at, df, me, opp = mk()
    me.deck = [('P', VANILLA)] * 8            # top 6 have no Basic Energy
    did = fn(W_WAITRESS)(ctx_of(me, opp, ctx.game))
    assert did is False and len(me.deck) == 8 and at.energy.get('Colorless', 0) == 3


@test
def t_wallys_compassion():
    ctx, at, df, me, opp = mk()
    mon = Mon(MEGA)
    mon.damage = 60
    mon.energy = Counter({'Fire': 2})
    me.active = mon
    me.bench = []
    did = fn(W_WALLY)(ctx_of(me, opp, ctx.game))
    assert did, "should heal + pick up energy from a damaged Mega Evolution ex"
    assert mon.damage == 0
    assert mon.total_energy() == 0
    assert me.hand.count(('E', 'Fire')) == 2   # all energy returned to hand


@test
def t_wallys_compassion_noop_on_undamaged_and_nonmega():
    # No-op when the only Mega ex has no damage...
    ctx, at, df, me, opp = mk()
    mon = Mon(MEGA); mon.damage = 0; mon.energy = Counter({'Fire': 2})
    me.active = mon; me.bench = []
    assert fn(W_WALLY)(ctx_of(me, opp, ctx.game)) is False
    assert mon.total_energy() == 2             # energy untouched
    # ...and when the damaged Pokémon is not a Mega ex.
    ctx2, at2, df2, me2, opp2 = mk()
    at2.damage = 60
    assert fn(W_WALLY)(ctx_of(me2, opp2, ctx2.game)) is False
    assert at2.damage == 60


@test
def t_wallys_compassion_prism_on_evolved_mega():
    # Prism Energy attached while the pre-evo was Basic gives a 'Wild' pip; SE.provides is
    # stage-dependent, so once the mon is a (stage>=1) Mega ex it reports Colorless. The residual
    # Wild pip must NOT be handed back as a bogus ('E','Wild') basic -- only the real Fire basic returns.
    MEGA_EVO = next(c for c in BK.values()
                    if c.name.startswith('Mega ') and c.is_ex and c.stage >= 1)
    ctx, at, df, me, opp = mk()
    mon = Mon(MEGA_EVO); mon.damage = 50
    mon.special = ['Prism Energy']
    mon.energy = Counter({'Wild': 1, 'Fire': 1})   # Wild from Prism@Basic + one real basic Fire
    me.active = mon; me.bench = []
    assert fn(W_WALLY)(ctx_of(me, opp, ctx.game)) is True
    assert mon.damage == 0 and mon.total_energy() == 0
    assert me.hand.count(('E', 'Fire')) == 1
    assert not any(t in (('E', 'Wild'), ('E', 'Colorless')) for t in me.hand)   # no bogus basic card
    assert me.hand.count(('S', {'special_energy': 'Prism Energy'})) == 1        # special returned


@test
def t_wallys_compassion_typed_special_not_double_counted():
    # A 'typed' special energy (Magnetic Metal -> a real Metal pip) must be returned once as its
    # ('S', ...) token, with its provided pip netted out of the basic count -- never double-returned.
    ctx, at, df, me, opp = mk()
    mon = Mon(MEGA); mon.damage = 40
    mon.special = ['Magnetic Metal Energy']
    mon.energy = Counter({'Metal': 2})             # 1 real basic Metal + 1 pip from the special
    me.active = mon; me.bench = []
    assert fn(W_WALLY)(ctx_of(me, opp, ctx.game)) is True
    assert mon.total_energy() == 0
    assert me.hand.count(('E', 'Metal')) == 1      # only the ONE real basic Metal, not two
    assert me.hand.count(('S', {'special_energy': 'Magnetic Metal Energy'})) == 1


@test
def t_xerosics_machinations():
    ctx, at, df, me, opp = mk()
    opp.hand = [('E', 'Fire'), ('E', 'Fire'), ('P', VANILLA), ('P', VANILLA), ('T', {'name': 'X'})]
    did = fn(W_XEROSIC)(ctx_of(me, opp, ctx.game))
    assert did and len(opp.hand) == 3
    # two surplus cards were discarded (a basic energy -> disc_energy, a Trainer -> discard)
    assert len(opp.discard) + sum(opp.disc_energy.values()) == 2
    # the opponent kept its two Basic Pokémon
    assert sum(1 for t in opp.hand if t[0] == 'P') == 2


@test
def t_xerosics_machinations_noop_at_or_below_3():
    ctx, at, df, me, opp = mk()
    opp.hand = [('E', 'Fire'), ('P', VANILLA)]     # already 2 cards
    assert fn(W_XEROSIC)(ctx_of(me, opp, ctx.game)) is False and len(opp.hand) == 2


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
