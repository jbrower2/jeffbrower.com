#!/usr/bin/env python3
"""Unit tests for trainer batch tr_supporter_3 (14 Supporters).

Supporter actions run through a TrainerCtx over real Player/Game objects built by the mk() harness;
each effect is exercised and its concrete state change asserted. A round-trip test also proves every
card's EXACT text (from effects_work/trainer_batches.json) is registered under the right kind.
"""
import json
import os
from collections import Counter

from effects_testkit import mk, runner
import trainer_effects as TE
import trainers_gen.batch_tr_supporter_3  # noqa: F401  (registers the effects)
from engine import Mon
from cards import load_cards

BK, _BN = load_cards()

# -- canonical card text, loaded straight from the batch spec so tests never re-type exact text --
_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = os.path.join(_HERE, '..', 'effects_work', 'trainer_batches.json')
_BATCH = [b for b in json.load(open(_SPEC))['batches'] if b['id'] == 'tr_supporter_3'][0]
TXT = {t['name']: t['text'] for t in _BATCH['trainers']}
KIND = {t['name']: t['kind'] for t in _BATCH['trainers']}


def fn(name):
    return TE.TRAINER_EFFECTS[TE.normalize(TXT[name])]['fn']


def ctx(me, opp, g):
    return TE.TrainerCtx(me, opp, g)


def card(pred):
    return next(c for c in BK.values() if pred(c))


TESTS = []
def test(f): TESTS.append(f); return f


# ---------------------------------------------------------------- round-trip registration guard
@test
def t_all_registered_exact_text():
    for name, text in TXT.items():
        key = TE.normalize(text)
        assert key in TE.TRAINER_EFFECTS, f"{name}: exact text not registered"
        assert TE.TRAINER_EFFECTS[key]['kind'] == KIND[name], f"{name}: wrong kind"


# ---------------------------------------------------------------- Lana's Aid
@test
def t_lanas_aid():
    c, at, df, me, opp = mk()
    nonex = card(lambda k: not k.is_ex and k.stage == 0)
    me.discard = [('P', nonex)]
    me.disc_energy = Counter({'Fire': 2})
    did = fn("Lana's Aid")(ctx(me, opp, c.game))
    assert did
    assert ('P', nonex) in me.hand                       # recovered the non-Rule-Box Pokémon
    assert sum(1 for x in me.hand if x == ('E', 'Fire')) == 2   # + 2 Basic Energy (3 total)
    assert me.disc_energy.get('Fire', 0) == 0


@test
def t_lanas_aid_excludes_ex_and_noops():
    c, at, df, me, opp = mk()
    ex = card(lambda k: k.is_ex)
    me.discard = [('P', ex)]                              # an ex has a Rule Box -> not recoverable
    me.disc_energy = Counter()
    assert fn("Lana's Aid")(ctx(me, opp, c.game)) is False
    assert ('P', ex) not in me.hand


# ---------------------------------------------------------------- Larry's Skill
@test
def t_larrys_skill():
    c, at, df, me, opp = mk()
    poke = card(lambda k: k.stage == 0)
    sup = ('T', {'name': 'TestSup', 'trainerType': 'Supporter', 'effect': ''})
    me.deck += [('P', poke), sup, ('E', 'Fire')]
    me.hand = [('E', 'Colorless'), ('E', 'Colorless')]   # 2 junk cards, discarded as part of the play
    did = fn("Larry's Skill")(ctx(me, opp, c.game))
    assert did
    assert me.disc_energy['Colorless'] == 2              # hand discarded (energy -> disc_energy)
    assert any(x[0] == 'P' for x in me.hand)             # searched a Pokémon
    assert any(x[0] == 'T' and x[1].get('trainerType') == 'Supporter' for x in me.hand)  # a Supporter
    assert any(x == ('E', 'Fire') for x in me.hand)      # a Basic Energy


# ---------------------------------------------------------------- Lillie's Determination
@test
def t_lillies_determination_draw8():
    c, at, df, me, opp = mk(my_prizes=6)
    me.hand = [('E', 'Colorless')] * 2
    did = fn("Lillie's Determination")(ctx(me, opp, c.game))
    assert did and len(me.hand) == 8                     # exactly 6 prizes -> draw 8


@test
def t_lillies_determination_draw6():
    c, at, df, me, opp = mk(my_prizes=5)
    me.hand = [('E', 'Colorless')] * 2
    fn("Lillie's Determination")(ctx(me, opp, c.game))
    assert len(me.hand) == 6                             # not exactly 6 prizes -> draw 6


# ---------------------------------------------------------------- Lisia's Appeal
@test
def t_lisias_appeal():
    c, at, df, me, opp = mk(opp_bench=2)
    old_active = opp.active
    did = fn("Lisia's Appeal")(ctx(me, opp, c.game))
    assert did
    assert opp.active is not old_active                  # a benched Basic switched in
    assert opp.active.card.stage == 0
    assert 'Confused' in opp.active.status
    assert old_active in opp.bench


@test
def t_lisias_appeal_no_basic():
    c, at, df, me, opp = mk(opp_bench=0)
    evo = card(lambda k: k.stage >= 1)
    opp.bench = [Mon(evo)]                                # only an Evolution on the bench, no Basic
    assert fn("Lisia's Appeal")(ctx(me, opp, c.game)) is False


# ---------------------------------------------------------------- Lt. Surge's Bargain
@test
def t_lt_surges_bargain_draw4():
    c, at, df, me, opp = mk(my_prizes=6, opp_prizes=6)   # opp not ahead -> they decline, you draw 4
    did = fn("Lt. Surge's Bargain")(ctx(me, opp, c.game))
    assert did and len(me.hand) == 4
    assert me.prizes_taken == 0 and opp.prizes_taken == 0


@test
def t_lt_surges_bargain_prize_trade():
    c, at, df, me, opp = mk(my_prizes=6, opp_prizes=2)   # opp ahead -> they take the mutual prize
    did = fn("Lt. Surge's Bargain")(ctx(me, opp, c.game))
    assert did
    assert me.prizes_taken == 1 and opp.prizes_taken == 1
    assert len(me.prizes) == 5 and len(opp.prizes) == 1
    assert len(me.hand) == 1                             # my taken prize went to hand (no draw-4)


# ---------------------------------------------------------------- Lucian
@test
def t_lucian():
    c, at, df, me, opp = mk(flips=(0.0, 0.9))            # me: heads (6); opp: tails (3)
    me.hand = [('E', 'Colorless')] * 2
    opp.hand = [('P', df.card)]
    did = fn('Lucian')(ctx(me, opp, c.game))
    assert did and len(me.hand) == 6 and len(opp.hand) == 3


@test
def t_lucian_noop_when_hands_empty():
    c, at, df, me, opp = mk()
    me.hand = []
    opp.hand = []
    assert fn('Lucian')(ctx(me, opp, c.game)) is False   # nobody put cards down -> no coin flips
    assert len(me.hand) == 0 and len(opp.hand) == 0


# ---------------------------------------------------------------- Morty's Conviction
@test
def t_mortys_conviction():
    c, at, df, me, opp = mk(opp_bench=3)
    me.hand = [('E', 'Colorless'), ('P', at.card)]       # a card to discard as the cost
    did = fn("Morty's Conviction")(ctx(me, opp, c.game))
    assert did
    assert me.disc_energy['Colorless'] == 1              # paid the discard cost (energy preferred)
    assert len(me.hand) == 4                             # (2 - 1 discarded) + 3 drawn for 3 bench


@test
def t_mortys_conviction_no_bench_noop():
    c, at, df, me, opp = mk(opp_bench=0)
    me.hand = [('E', 'Colorless')]
    assert fn("Morty's Conviction")(ctx(me, opp, c.game)) is False
    assert me.disc_energy.get('Colorless', 0) == 0       # cost not paid when there's no payoff


# ---------------------------------------------------------------- N's Plan
@test
def t_ns_plan():
    c, at, df, me, opp = mk(my_bench=2)
    me.active.energy = Counter()
    me.bench[0].energy = Counter({'Fire': 2})
    me.bench[1].energy = Counter({'Water': 1})
    did = fn("N's Plan")(ctx(me, opp, c.game))
    assert did
    assert me.active.total_energy() == 2                 # moved up to 2 onto the active
    assert me.bench[0].total_energy() + me.bench[1].total_energy() == 1   # 3 started, 2 moved


@test
def t_ns_plan_no_bench():
    c, at, df, me, opp = mk(my_bench=0)
    assert fn("N's Plan")(ctx(me, opp, c.game)) is False


# ---------------------------------------------------------------- Naveen
@test
def t_naveen_draws_to_five():
    c, at, df, me, opp = mk()
    me.hand = [('E', 'Colorless')]                       # 1 card -> draw up to 5
    did = fn('Naveen')(ctx(me, opp, c.game))
    assert did and len(me.hand) == 5


@test
def t_naveen_noop_when_hand_full():
    c, at, df, me, opp = mk()
    me.hand = [('E', 'Colorless')] * 5                   # already 5 -> can't draw without discarding
    assert fn('Naveen')(ctx(me, opp, c.game)) is False


# ---------------------------------------------------------------- Perrin
@test
def t_perrin():
    c, at, df, me, opp = mk()
    evo = card(lambda k: k.stage >= 1)
    me.hand = [('P', evo), ('P', evo)]                   # 2 evolutions to swap back
    did = fn('Perrin')(ctx(me, opp, c.game))
    assert did
    pokes = [x for x in me.hand if x[0] == 'P']
    assert len(pokes) == 2                               # put 2 back, drew 2
    assert all(x[1].stage == 0 for x in pokes)           # traded up for Basics


@test
def t_perrin_no_pokemon_in_hand():
    c, at, df, me, opp = mk()
    me.hand = [('E', 'Colorless')]
    assert fn('Perrin')(ctx(me, opp, c.game)) is False


# ---------------------------------------------------------------- Philippe
@test
def t_philippe():
    c, at, df, me, opp = mk()
    metal = card(lambda k: k.ptype == 'Metal')
    me.active = Mon(metal)
    me.disc_energy = Counter({'Metal': 3})
    did = fn('Philippe')(ctx(me, opp, c.game))
    assert did
    assert me.active.energy['Metal'] == 2                # attached up to 2 from discard
    assert me.disc_energy['Metal'] == 1


@test
def t_philippe_no_metal_mon():
    c, at, df, me, opp = mk()                            # active is a non-Metal VANILLA
    me.disc_energy = Counter({'Metal': 3})
    assert fn('Philippe')(ctx(me, opp, c.game)) is False


# ---------------------------------------------------------------- Pokémon Center Lady
@test
def t_pokemon_center_lady():
    c, at, df, me, opp = mk()
    at.damage = 100
    at.status['Asleep'] = True
    did = fn("Pokémon Center Lady")(ctx(me, opp, c.game))
    assert did
    assert at.damage == 40                               # healed 60
    assert 'Asleep' not in at.status                     # recovered from all Special Conditions


@test
def t_pokemon_center_lady_noop():
    c, at, df, me, opp = mk()                            # undamaged, no conditions
    assert fn("Pokémon Center Lady")(ctx(me, opp, c.game)) is False


# ---------------------------------------------------------------- Professor Sada's Vitality
@test
def t_professor_sadas_vitality_conservative_noop():
    c, at, df, me, opp = mk()
    metal = card(lambda k: k.ptype == 'Metal')
    me.active = Mon(metal)
    me.disc_energy = Counter({'Metal': 3})
    # "Ancient" subtype is not in the card data -> conservative no-op (never fires on non-Ancient mons)
    assert fn("Professor Sada's Vitality")(ctx(me, opp, c.game)) is False
    assert me.active.total_energy() == 0


# ---------------------------------------------------------------- Professor Turo's Scenario
@test
def t_professor_turos_scenario():
    c, at, df, me, opp = mk(my_bench=1)
    at.damage = 150
    at.energy = Counter({'Fire': 2})
    old_card = at.card
    did = fn("Professor Turo's Scenario")(ctx(me, opp, c.game))
    assert did
    assert ('P', old_card) in me.hand                    # the Pokémon returned to hand
    assert me.disc_energy['Fire'] == 2                   # attached energy discarded
    assert me.active is not None                         # a bench Pokémon was promoted into the gap


@test
def t_professor_turos_scenario_only_pokemon():
    c, at, df, me, opp = mk(my_bench=0)
    at.damage = 150
    assert fn("Professor Turo's Scenario")(ctx(me, opp, c.game)) is False   # can't return your only mon


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
