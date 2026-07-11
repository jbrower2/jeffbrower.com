#!/usr/bin/env python3
"""Unit tests for trainer batch tr_supporter_2 (14 Supporters).

Item/Supporter actions run through a TrainerCtx over real Player/Game objects built by the mk()
harness; we exercise each effect and assert the concrete state change. A round-trip test also proves
every card's EXACT text (from effects_work/trainer_batches.json) is registered under the right kind.
"""
import json
import os
from collections import Counter

from effects_testkit import mk, runner
import trainer_effects as TE
import trainers_gen.batch_tr_supporter_2  # noqa: F401  (registers the effects)
from engine import Mon
from cards import load_cards

BK, _BN = load_cards()

# -- canonical card text, loaded straight from the batch spec so tests never re-type exact text --
_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = os.path.join(_HERE, '..', 'effects_work', 'trainer_batches.json')
_BATCH = [b for b in json.load(open(_SPEC))['batches'] if b['id'] == 'tr_supporter_2'][0]
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


# ---------------------------------------------------------------- Fennel
@test
def t_fennel():
    c, at, df, me, opp = mk(my_bench=1)
    at.damage = 40; me.bench[0].damage = 30
    did = fn('Fennel')(ctx(me, opp, c.game))
    assert did and at.damage == 0 and me.bench[0].damage == 0


@test
def t_fennel_noop_when_undamaged():
    c, at, df, me, opp = mk()
    assert fn('Fennel')(ctx(me, opp, c.game)) is False


# ---------------------------------------------------------------- Firebreather
@test
def t_firebreather():
    c, at, df, me, opp = mk()
    me.deck += [('E', 'Fire')] * 5
    did = fn('Firebreather')(ctx(me, opp, c.game))
    assert did and sum(1 for x in me.hand if x == ('E', 'Fire')) == 5
    assert all(x != ('E', 'Fire') for x in me.deck)


@test
def t_firebreather_none_available():
    c, at, df, me, opp = mk()          # default deck has no Fire energy
    assert fn('Firebreather')(ctx(me, opp, c.game)) is False


# ---------------------------------------------------------------- Grimsley's Move
@test
def t_grimsleys_move():
    c, at, df, me, opp = mk(my_bench=0)
    dark = card(lambda k: k.ptype == 'Darkness' and k.stage == 0)
    me.deck.append(('P', dark))        # a {D} Basic on top of the deck
    n_bench = len(me.bench)
    did = fn("Grimsley's Move")(ctx(me, opp, c.game))
    assert did
    assert len(me.bench) == n_bench + 1
    assert me.bench[-1].card.ptype == 'Darkness'
    assert ('P', dark) not in me.deck  # it left the deck (benched)


@test
def t_grimsleys_move_no_dark_in_top7():
    c, at, df, me, opp = mk()          # default top-7 are Colorless energy, no {D} Pokémon
    assert fn("Grimsley's Move")(ctx(me, opp, c.game)) is False


# ---------------------------------------------------------------- Harlequin
@test
def t_harlequin_heads():
    c, at, df, me, opp = mk(flips=(0.0,))   # heads
    did = fn('Harlequin')(ctx(me, opp, c.game))
    assert did and len(me.hand) == 5 and len(opp.hand) == 3


@test
def t_harlequin_tails():
    c, at, df, me, opp = mk(flips=(0.9,))   # tails
    fn('Harlequin')(ctx(me, opp, c.game))
    assert len(me.hand) == 3 and len(opp.hand) == 5


# ---------------------------------------------------------------- Hassel
@test
def t_hassel_conditional_met():
    c, at, df, me, opp = mk(ko_last=True)
    n_deck = len(me.deck)
    did = fn('Hassel')(ctx(me, opp, c.game))
    assert did and len(me.hand) == 3 and len(me.deck) == n_deck - 3


@test
def t_hassel_conditional_unmet():
    c, at, df, me, opp = mk()          # no KO on opponent's last turn
    assert fn('Hassel')(ctx(me, opp, c.game)) is False and len(me.hand) == 0


# ---------------------------------------------------------------- Hilda
@test
def t_hilda():
    c, at, df, me, opp = mk()
    evo = card(lambda k: k.stage >= 1)
    me.deck.append(('P', evo))
    did = fn('Hilda')(ctx(me, opp, c.game))
    assert did
    assert any(x[0] == 'P' and x[1].stage >= 1 for x in me.hand)   # got an Evolution
    assert any(x[0] == 'E' for x in me.hand)                       # got an Energy


# ---------------------------------------------------------------- Iris's Fighting Spirit
@test
def t_iris_fighting_spirit():
    c, at, df, me, opp = mk()
    me.hand = [('E', 'Colorless'), ('P', at.card)]   # 2 cards; one gets discarded as the cost
    did = fn("Iris's Fighting Spirit")(ctx(me, opp, c.game))
    assert did and len(me.hand) == 6
    assert me.disc_energy['Colorless'] == 1          # the energy was the discarded card


@test
def t_iris_fighting_spirit_no_card_to_discard():
    c, at, df, me, opp = mk()
    me.hand = []
    assert fn("Iris's Fighting Spirit")(ctx(me, opp, c.game)) is False


# ---------------------------------------------------------------- Jacinthe
@test
def t_jacinthe():
    c, at, df, me, opp = mk()
    psychic = card(lambda k: k.ptype == 'Psychic')
    pm = Mon(psychic); pm.damage = 200; me.active = pm
    did = fn('Jacinthe')(ctx(me, opp, c.game))
    assert did and me.active.damage == 50


@test
def t_jacinthe_no_psychic():
    c, at, df, me, opp = mk()
    at.damage = 200                    # active is a non-Psychic VANILLA
    assert fn('Jacinthe')(ctx(me, opp, c.game)) is False and at.damage == 200


# ---------------------------------------------------------------- Janine's Secret Art
@test
def t_janines_secret_art():
    c, at, df, me, opp = mk()
    dark = card(lambda k: k.ptype == 'Darkness' and k.stage == 0)
    dm = Mon(dark); me.active = dm
    me.deck.append(('E', 'Darkness'))
    did = fn("Janine's Secret Art")(ctx(me, opp, c.game))
    assert did and me.active.energy['Darkness'] == 1
    assert 'Poisoned' in me.active.status          # attached to Active -> Poisoned


@test
def t_janines_no_dark_energy():
    c, at, df, me, opp = mk()
    dark = card(lambda k: k.ptype == 'Darkness' and k.stage == 0)
    me.active = Mon(dark)              # Darkness mon, but deck has no Basic {D} Energy
    assert fn("Janine's Secret Art")(ctx(me, opp, c.game)) is False


# ---------------------------------------------------------------- Jasmine's Gaze
@test
def t_jasmines_gaze():
    c, at, df, me, opp = mk(my_bench=2)
    did = fn("Jasmine's Gaze")(ctx(me, opp, c.game))
    assert did
    for m in me.all_mons():
        assert m.dr_amount == 30 and m.dr_turn == c.game.turn


# ---------------------------------------------------------------- Judge
@test
def t_judge():
    c, at, df, me, opp = mk()
    me.hand = [('E', 'Colorless')] * 3
    opp.hand = [('E', 'Colorless')] * 2
    did = fn('Judge')(ctx(me, opp, c.game))
    assert did and len(me.hand) == 4 and len(opp.hand) == 4


# ---------------------------------------------------------------- Kieran
@test
def t_kieran_switch():
    c, at, df, me, opp = mk(my_bench=1)
    benchmon = me.bench[0]
    benchmon.energy = Counter({'Colorless': 5})   # ensure promote() picks it over the active
    old_active = me.active
    did = fn('Kieran')(ctx(me, opp, c.game))
    assert did and me.active is benchmon and old_active in me.bench


@test
def t_kieran_no_bench():
    c, at, df, me, opp = mk(my_bench=0)
    assert fn('Kieran')(ctx(me, opp, c.game)) is False


# ---------------------------------------------------------------- Kofu
@test
def t_kofu():
    c, at, df, me, opp = mk()
    me.hand = [('E', 'Colorless')] * 3
    did = fn('Kofu')(ctx(me, opp, c.game))
    assert did and len(me.hand) == 5      # 3 - 2 put back + 4 drawn


@test
def t_kofu_too_few_cards():
    c, at, df, me, opp = mk()
    me.hand = [('E', 'Colorless')]        # only 1 card
    assert fn('Kofu')(ctx(me, opp, c.game)) is False


# ---------------------------------------------------------------- Lacey
@test
def t_lacey_draw4():
    c, at, df, me, opp = mk(opp_prizes=6)
    did = fn('Lacey')(ctx(me, opp, c.game))
    assert did and len(me.hand) == 4


@test
def t_lacey_draw8_when_opp_low():
    c, at, df, me, opp = mk(opp_prizes=3)
    fn('Lacey')(ctx(me, opp, c.game))
    assert len(me.hand) == 8


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
