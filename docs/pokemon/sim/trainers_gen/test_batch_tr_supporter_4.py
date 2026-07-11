#!/usr/bin/env python3
"""Unit tests for trainer batch tr_supporter_4 (14 Supporters).

Supporter actions run through a TrainerCtx over real Player/Game objects built by the mk() harness;
each test asserts the concrete state change. A round-trip test also proves every card's EXACT text
(from effects_work/trainer_batches.json) is registered under the right kind.
"""
import json
import os
from collections import Counter

from effects_testkit import mk, runner
import trainer_effects as TE
import trainers_gen.batch_tr_supporter_4  # noqa: F401  (registers the effects)
from engine import Mon
from cards import load_cards
import special_energy as SE

BK, _BN = load_cards()

# -- canonical card text, loaded straight from the batch spec so tests never re-type exact text --
_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = os.path.join(_HERE, '..', 'effects_work', 'trainer_batches.json')
_BATCH = [b for b in json.load(open(_SPEC))['batches'] if b['id'] == 'tr_supporter_4'][0]
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


# ---------------------------------------------------------------- Professor's Research
@test
def t_professors_research():
    c, at, df, me, opp = mk()
    me.hand = [('E', 'Colorless'), ('P', at.card), ('T', {'name': 'X', 'trainerType': 'Item'})]
    did = fn("Professor's Research")(ctx(me, opp, c.game))
    assert did and len(me.hand) == 7                         # discarded 3, drew 7
    assert me.disc_energy['Colorless'] == 1                  # basic energy went to disc_energy
    assert ('P', at.card) in me.discard                      # Pokémon went to the discard pile
    assert any(x[0] == 'T' for x in me.discard)              # Trainer went to the discard pile


# ---------------------------------------------------------------- Raifort
@test
def t_raifort_orders_best_to_top():
    c, at, df, me, opp = mk()
    basic = card(lambda k: k.stage == 0)
    # top-5 (end of list) with a Basic Pokémon buried in the middle
    me.deck = [('E', 'Colorless')] * 3 + [('E', 'Colorless'), ('E', 'Colorless'),
                                          ('P', basic), ('E', 'Colorless'), ('E', 'Colorless')]
    did = fn('Raifort')(ctx(me, opp, c.game))
    assert did
    assert me.deck[-1] == ('P', basic)                       # highest-priority card is now drawn next
    assert len(me.deck) == 8                                 # nothing discarded


@test
def t_raifort_empty_deck():
    c, at, df, me, opp = mk()
    me.deck = []
    assert fn('Raifort')(ctx(me, opp, c.game)) is False


# ---------------------------------------------------------------- Rosa's Encouragement
@test
def t_rosas_encouragement():
    c, at, df, me, opp = mk(my_prizes=6, opp_prizes=4)             # more prizes remaining than opp
    s2 = card(lambda k: k.stage == 2)
    me.active = Mon(s2)
    me.disc_energy = Counter({'Water': 3})
    did = fn("Rosa's Encouragement")(ctx(me, opp, c.game))
    assert did and me.active.total_energy() == 2                   # attached up to 2 from the discard
    assert sum(me.disc_energy.values()) == 1                       # 3 -> 1


@test
def t_rosas_encouragement_not_behind():
    c, at, df, me, opp = mk(my_prizes=3, opp_prizes=6)             # not more prizes remaining
    me.active = Mon(card(lambda k: k.stage == 2))
    me.disc_energy = Counter({'Water': 3})
    assert fn("Rosa's Encouragement")(ctx(me, opp, c.game)) is False


@test
def t_rosas_encouragement_no_stage2():
    c, at, df, me, opp = mk(my_prizes=6, opp_prizes=4)             # condition met but active is a Basic
    me.disc_energy = Counter({'Water': 3})
    assert fn("Rosa's Encouragement")(ctx(me, opp, c.game)) is False


# ---------------------------------------------------------------- Roxie's Performance
@test
def t_roxies_performance():
    c, at, df, me, opp = mk()
    opp.active.status['Poisoned'] = True
    did = fn("Roxie's Performance")(ctx(me, opp, c.game))
    assert did and opp.active.status.get('CantRetreat') is True


@test
def t_roxies_performance_no_poison():
    c, at, df, me, opp = mk()
    assert fn("Roxie's Performance")(ctx(me, opp, c.game)) is False


# ---------------------------------------------------------------- Ruffian
@test
def t_ruffian():
    c, at, df, me, opp = mk()
    sname = next(iter(SE.SPECIAL_ENERGY))
    prov = SE.provides(sname, opp.active.card)
    for typ, n in prov.items():
        opp.active.energy[typ] += n
    opp.active.special = [sname]
    opp.active.tools = ['Rescue Board']
    before = opp.active.total_energy()
    did = fn('Ruffian')(ctx(me, opp, c.game))
    assert did
    assert opp.active.tools == [] and opp.active.special == []
    assert opp.active.total_energy() == before - sum(prov.values())     # special-energy pips removed
    assert any(x[0] == 'T' for x in opp.discard) and any(x[0] == 'S' for x in opp.discard)


@test
def t_ruffian_nothing_to_discard():
    c, at, df, me, opp = mk()                                # no tools / special energy anywhere
    assert fn('Ruffian')(ctx(me, opp, c.game)) is False


# ---------------------------------------------------------------- Salvatore
@test
def t_salvatore_evolves_fresh_mon():
    c, at, df, me, opp = mk()
    base, evo = _evo_pair()
    me.active = Mon(base); me.active.turns = 0               # a Pokémon put into play this turn
    me.deck.append(('P', evo))
    did = fn('Salvatore')(ctx(me, opp, c.game))
    assert did and me.active.card is evo                     # evolved despite turns == 0
    assert ('P', evo) not in me.deck


@test
def t_salvatore_no_target():
    c, at, df, me, opp = mk()                                # nothing in deck evolves from the active
    assert fn('Salvatore')(ctx(me, opp, c.game)) is False


def _evo_pair():
    """A (Basic card, Stage-1 evolution with no abilities) pair from the real pool."""
    for c in BK.values():
        if c.stage == 1 and not c.abilities and c.evolves_from:
            base = next((b for b in BK.values() if b.name == c.evolves_from and b.stage == 0), None)
            if base:
                return base, c
    raise AssertionError('no ability-less Stage-1 evolution pair found')


# ---------------------------------------------------------------- Surfer
@test
def t_surfer():
    c, at, df, me, opp = mk(my_bench=1)
    benchmon = me.bench[0]
    benchmon.energy = Counter({'Colorless': 5})             # ensure promote() picks it over the active
    old_active = me.active
    me.hand = []
    did = fn('Surfer')(ctx(me, opp, c.game))
    assert did and me.active is benchmon and old_active in me.bench
    assert len(me.hand) == 5                                 # drew up to 5


@test
def t_surfer_no_bench():
    c, at, df, me, opp = mk(my_bench=0)
    me.hand = []
    assert fn('Surfer')(ctx(me, opp, c.game)) is False and len(me.hand) == 0


# ---------------------------------------------------------------- Tarragon
@test
def t_tarragon():
    c, at, df, me, opp = mk()
    fight = card(lambda k: k.ptype == 'Fighting')
    me.discard = [('P', fight), ('P', fight)]
    me.disc_energy = Counter({'Fighting': 5})
    did = fn('Tarragon')(ctx(me, opp, c.game))
    assert did
    assert sum(1 for x in me.hand if x[0] == 'P' and x[1].ptype == 'Fighting') == 2
    assert sum(1 for x in me.hand if x == ('E', 'Fighting')) == 2       # 2 poke + 2 energy = 4 total
    assert me.disc_energy['Fighting'] == 3                              # 5 - 2


@test
def t_tarragon_nothing():
    c, at, df, me, opp = mk()                                # empty discard, no {F} energy
    assert fn('Tarragon')(ctx(me, opp, c.game)) is False


# ---------------------------------------------------------------- Team Rocket's Archer
@test
def t_team_rockets_archer():
    c, at, df, me, opp = mk(ko_last=True)
    me.hand = [('E', 'Colorless')] * 2
    opp.hand = [('E', 'Colorless')] * 2
    did = fn("Team Rocket's Archer")(ctx(me, opp, c.game))
    assert did and len(me.hand) == 5 and len(opp.hand) == 3


@test
def t_team_rockets_archer_no_ko():
    c, at, df, me, opp = mk()                                # no KO on the opponent's last turn
    assert fn("Team Rocket's Archer")(ctx(me, opp, c.game)) is False


# ---------------------------------------------------------------- Team Rocket's Ariana
@test
def t_team_rockets_ariana_all_tr_draws_8():
    c, at, df, me, opp = mk()
    tr = card(lambda k: k.name.startswith("Team Rocket's"))
    me.active = Mon(tr); me.bench = []                       # every in-play Pokémon is Team Rocket's
    me.hand = []
    fn("Team Rocket's Ariana")(ctx(me, opp, c.game))
    assert len(me.hand) == 8


@test
def t_team_rockets_ariana_mixed_draws_5():
    c, at, df, me, opp = mk()                                # default active is a non-TR VANILLA
    me.hand = []
    fn("Team Rocket's Ariana")(ctx(me, opp, c.game))
    assert len(me.hand) == 5


# ---------------------------------------------------------------- Team Rocket's Giovanni
@test
def t_team_rockets_giovanni():
    c, at, df, me, opp = mk(my_bench=0, opp_bench=1)
    tr = card(lambda k: k.name.startswith("Team Rocket's") and k.stage == 0)
    me.active = Mon(tr)
    bench_tr = Mon(tr); me.bench = [bench_tr]
    old_active = me.active
    old_opp_active = opp.active
    opp_target = opp.bench[0]
    did = fn("Team Rocket's Giovanni")(ctx(me, opp, c.game))
    assert did
    assert me.active is bench_tr and old_active in me.bench          # my TR self-switch
    assert opp.active is opp_target and old_opp_active in opp.bench  # dragged up an opponent's benched


@test
def t_team_rockets_giovanni_active_not_tr():
    c, at, df, me, opp = mk(my_bench=1)                      # active is a non-TR VANILLA
    assert fn("Team Rocket's Giovanni")(ctx(me, opp, c.game)) is False


# ---------------------------------------------------------------- Team Rocket's Petrel
@test
def t_team_rockets_petrel():
    c, at, df, me, opp = mk()
    trn = ('T', {'name': 'Some Trainer', 'trainerType': 'Item'})
    me.deck.append(trn)
    did = fn("Team Rocket's Petrel")(ctx(me, opp, c.game))
    assert did and trn in me.hand and trn not in me.deck


@test
def t_team_rockets_petrel_none():
    c, at, df, me, opp = mk()                                # default deck has no Trainer tokens
    assert fn("Team Rocket's Petrel")(ctx(me, opp, c.game)) is False


# ---------------------------------------------------------------- Team Rocket's Proton
@test
def t_team_rockets_proton():
    c, at, df, me, opp = mk()
    tr = card(lambda k: k.stage == 0 and k.name.startswith("Team Rocket's"))
    me.deck.append(('P', tr))
    did = fn("Team Rocket's Proton")(ctx(me, opp, c.game))
    assert did and any(x[0] == 'P' and x[1] is tr for x in me.hand)


@test
def t_team_rockets_proton_none():
    c, at, df, me, opp = mk()                                # default deck: no Basic TR Pokémon
    assert fn("Team Rocket's Proton")(ctx(me, opp, c.game)) is False


# ---------------------------------------------------------------- Tyme
@test
def t_tyme_you_draw():
    c, at, df, me, opp = mk(flips=(0.9,))                    # opponent guesses wrong -> you draw 4
    me.hand = [('P', at.card)]
    did = fn('Tyme')(ctx(me, opp, c.game))
    assert did and len(me.hand) == 5 and len(opp.hand) == 0


@test
def t_tyme_opp_draws():
    c, at, df, me, opp = mk(flips=(0.0,))                    # opponent guesses right -> they draw 4
    me.hand = [('P', at.card)]
    opp.hand = []
    did = fn('Tyme')(ctx(me, opp, c.game))
    assert did and len(opp.hand) == 4 and len(me.hand) == 1     # named Pokémon returns to hand


@test
def t_tyme_no_pokemon():
    c, at, df, me, opp = mk()
    me.hand = [('E', 'Colorless')]                          # no Pokémon to name
    assert fn('Tyme')(ctx(me, opp, c.game)) is False


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
