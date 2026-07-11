#!/usr/bin/env python3
"""Unit tests for batch 'misc_2' attack effects."""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # ensure sim/ importable

from effects_testkit import mk, run, runner, VANILLA
import attack_effects as AE
import effects_gen.batch_misc_2   # noqa: F401  (registers the effects)
from engine import Mon, BY_KEY, BY_NAME

HERE = os.path.dirname(os.path.abspath(__file__))
BATCHES = os.path.join(os.path.dirname(HERE), 'effects_work', 'batches.json')

# Exact keys from the batch (used to look effects up + assert registration).
K_RECOVER_TRAINER = "Put a Trainer card from your discard pile into your hand."
K_RETURN_FIRE = "Put 2 {R} Energy attached to this Pokémon into your hand."
K_CD_FLARE = "During your next turn, this Pokémon can't use Flare Strike."
K_CD_HAYMAKER = "During your next turn, this Pokémon can't use Haymaker."
K_WEAKNESS = ("Until the end of your next turn, the Defending Pokémon's Weakness is now {C}. "
              "(The amount of Weakness doesn't change.)")
K_CD_DRAGON = "During your next turn, this Pokémon can't use Dragon Strike."
K_RECOVER_POKE = "Put up to 2 Pokémon from your discard pile into your hand."
K_COST_MORE = ("During your opponent's next turn, attacks used by the Defending Pokémon cost {C} more, "
               "and its Retreat Cost is {C} more.")
K_LEAST_KO = ("Choose a Pokémon in play (yours or your opponent's) that has the least HP remaining, "
              "except for this Pokémon, and it is Knocked Out.")
K_LOOK_PRIZE = "Look at 1 of your opponent's face-down Prize cards."
K_CD_FROSTY = "During your next turn, this Pokémon can't use Frosty Typhoon."
K_SHUFFLE = "Shuffle this Pokémon and all attached cards into your deck."
K_COUNTER = "Place 1 damage counter on 1 of your opponent's Pokémon."
K_DEVOLVE = ("Devolve 1 of your opponent's evolved Pokémon by putting the highest Stage Evolution card "
             "on it into your opponent's hand.")
K_MAY_SHUFFLE = "You may shuffle this Pokémon and all attached cards into your deck."
K_MILL = "Discard the top 3 cards of your deck."
K_CD_ZEN = "During your next turn, this Pokémon can't use Zen Blade."
K_CD_OGRE = "During your next turn, this Pokémon can't use Ogre's Hammer."

COOLDOWN_KEYS = [K_CD_FLARE, K_CD_HAYMAKER, K_CD_DRAGON, K_CD_FROSTY, K_CD_ZEN, K_CD_OGRE]

TESTS = []
def test(fn): TESTS.append(fn); return fn


def _call(key, ctx):
    return AE.ATTACK_EFFECTS[AE.normalize(key)](ctx)


@test
def t_all_batch_keys_registered():
    """Every misc_2 key (exact bytes) must resolve to a registered effect."""
    b = next(x for x in json.load(open(BATCHES))['batches'] if x['id'] == 'misc_2')
    for e in b['effects']:
        assert AE.normalize(e['key']) in AE.ATTACK_EFFECTS, e['key']
    assert len(b['effects']) == 18, len(b['effects'])


@test
def t_recover_trainer():
    ctx, at, df, me, opp = mk(text=K_RECOVER_TRAINER, base=0)
    item = {'name': 'Nest Ball', 'trainerType': 'Item', 'effect': ''}
    sup = {'name': "Boss's Orders", 'trainerType': 'Supporter', 'effect': ''}
    me.discard += [('T', item), ('T', sup)]
    d = _call(K_RECOVER_TRAINER, ctx)
    assert d == 0
    assert ('T', sup) in me.hand and ('T', sup) not in me.discard   # prefers the Supporter
    assert ('T', item) in me.discard


@test
def t_recover_trainer_empty():
    ctx, at, df, me, opp = mk(text=K_RECOVER_TRAINER, base=0)
    d = _call(K_RECOVER_TRAINER, ctx)
    assert d == 0 and me.hand == []                                 # nothing to recover -> no crash


@test
def t_recover_2_pokemon():
    ctx, at, df, me, opp = mk(text=K_RECOVER_POKE, base=0)
    me.discard += [('P', VANILLA), ('P', VANILLA), ('P', VANILLA)]
    d = _call(K_RECOVER_POKE, ctx)
    assert d == 0
    assert me.hand.count(('P', VANILLA)) == 2                       # up to 2
    assert len([x for x in me.discard if x[0] == 'P']) == 1


@test
def t_return_fire_to_hand():
    ctx, at, df, me, opp = mk(text=K_RETURN_FIRE, base=130, atk_energy={'Fire': 3})
    d = _call(K_RETURN_FIRE, ctx)
    assert d == 130
    assert at.energy.get('Fire', 0) == 1                           # 3 - 2 returned
    assert me.hand.count(('E', 'Fire')) == 2                       # to HAND, not discard
    assert me.disc_energy.get('Fire', 0) == 0


@test
def t_return_fire_short():
    ctx, at, df, me, opp = mk(text=K_RETURN_FIRE, base=130, atk_energy={'Fire': 1})
    d = _call(K_RETURN_FIRE, ctx)
    assert d == 130 and me.hand.count(('E', 'Fire')) == 1 and at.energy.get('Fire', 0) == 0


@test
def t_return_fire_only_pulls_fire():
    # {R} == Fire only: other attached energy types must be left untouched (not scooped up as filler).
    ctx, at, df, me, opp = mk(text=K_RETURN_FIRE, base=130, atk_energy={'Fire': 3, 'Water': 2})
    d = _call(K_RETURN_FIRE, ctx)
    assert d == 130
    assert at.energy.get('Fire', 0) == 1                          # 3 - 2 returned
    assert at.energy.get('Water', 0) == 2                         # untouched
    assert me.hand.count(('E', 'Fire')) == 2
    assert me.hand.count(('E', 'Water')) == 0                     # never grabbed a non-Fire energy


@test
def t_cooldowns_named():
    for key in COOLDOWN_KEYS:
        d, ctx, at, *_ = run(key, base=120)
        assert d == 120, (key, d)
        assert at.cd_name == 'TestAtk', (key, at.cd_name)          # blocks the attack's own name
        assert at.cd_turn == ctx.game.turn == 3, (key, at.cd_turn)


@test
def t_shuffle_self_mandatory():
    ctx, at, df, me, opp = mk(text=K_SHUFFLE, base=150, atk_energy={'Fire': 2}, my_bench=1)
    before = len(me.deck)
    d = _call(K_SHUFFLE, ctx)
    assert d == 150
    assert me.active is not at                                     # attacker left play, bench promoted
    assert me.active is not None
    assert len(me.deck) == before + 3                             # 1 Pokémon + 2 Fire energy
    assert me.deck.count(('E', 'Fire')) == 2


@test
def t_shuffle_self_no_bench_wipes_active():
    ctx, at, df, me, opp = mk(text=K_SHUFFLE, base=150, my_bench=0)
    d = _call(K_SHUFFLE, ctx)
    assert d == 150 and me.active is None                          # forced shuffle with empty bench


@test
def t_may_shuffle_declines_when_healthy():
    ctx, at, df, me, opp = mk(text=K_MAY_SHUFFLE, base=100, my_bench=0)
    at.damage = 0
    d = _call(K_MAY_SHUFFLE, ctx)
    assert d == 100 and me.active is at                            # no bench + healthy -> keep attacking


@test
def t_may_shuffle_when_dying():
    ctx, at, df, me, opp = mk(text=K_MAY_SHUFFLE, base=100, my_bench=1)
    at.damage = at.max_hp - 10                                     # hp_left = 10 <= 60
    d = _call(K_MAY_SHUFFLE, ctx)
    assert d == 100 and me.active is not at                        # shuffled back, bench promoted


@test
def t_may_shuffle_healthy_with_bench_declines():
    # Isolates the HP gate specifically: a bench IS available (so the earlier decline test's empty-bench
    # short-circuit doesn't fire), but a healthy attacker (hp_left 80 > 60) must still keep attacking.
    ctx, at, df, me, opp = mk(text=K_MAY_SHUFFLE, base=100, my_bench=1)
    at.damage = 0                                                  # hp_left = 80 > 60
    before = len(me.deck)
    d = _call(K_MAY_SHUFFLE, ctx)
    assert d == 100
    assert me.active is at                                         # kept in play despite an open bench
    assert len(me.deck) == before                                 # nothing shuffled back in


@test
def t_mill_top_3():
    ctx, at, df, me, opp = mk(text=K_MILL, base=130)
    before = len(me.deck)
    d = _call(K_MILL, ctx)
    assert d == 130
    assert len(me.deck) == before - 3
    moved = len(me.discard) + sum(me.disc_energy.values())
    assert moved == 3                                             # top 3 (Colorless energy) milled


@test
def t_least_hp_ko_opponent():
    ctx, at, df, me, opp = mk(text=K_LEAST_KO, base=0, opp_bench=1, my_bench=1)
    df.damage = df.max_hp - 10                                    # opp active is the lowest HP
    prizes_before = len(me.prizes)
    d = _call(K_LEAST_KO, ctx)
    assert d == 0
    assert opp.active is not df                                   # the low-HP active was KO'd + replaced
    assert ('P', df.card) in opp.discard
    assert len(me.prizes) == prizes_before - 1                    # attacker's player took a prize


@test
def t_least_hp_ko_excludes_self():
    # Attacker is the single lowest-HP Pokémon; it must be excluded, so a full-HP other mon is chosen.
    ctx, at, df, me, opp = mk(text=K_LEAST_KO, base=0, opp_bench=0, my_bench=0)
    at.damage = at.max_hp - 5                                     # attacker lowest, but excluded
    d = _call(K_LEAST_KO, ctx)
    assert d == 0
    assert me.active is at                                        # attacker survived (not chosen)
    assert opp.active is not df                                   # the only other mon (opp active) KO'd


@test
def t_least_hp_ko_targets_own_lowest():
    # "(yours or your opponent's)": when MY OWN benched mon is the strict global minimum (and isn't the
    # attacker), it is the one KO'd -- and because it's mine, the OPPONENT takes the prize.
    ctx, at, df, me, opp = mk(text=K_LEAST_KO, base=0, opp_bench=1, my_bench=1)
    at.damage = 0                                                 # attacker healthy (and excluded anyway)
    own = me.bench[0]
    own.damage = own.max_hp - 5                                   # my bench mon = global min (hp_left 5)
    own_card = own.card
    opp_prizes_before = len(opp.prizes)
    d = _call(K_LEAST_KO, ctx)
    assert d == 0
    assert own not in me.bench                                    # my own low-HP mon was chosen + removed
    assert ('P', own_card) in me.discard
    assert len(opp.prizes) == opp_prizes_before - 1              # KO of MY mon -> OPPONENT takes a prize
    assert me.active is at and opp.active is df                  # attacker excluded; opp active untouched


@test
def t_place_counter():
    ctx, at, df, me, opp = mk(text=K_COUNTER, base=0, opp_bench=1)
    d = _call(K_COUNTER, ctx)
    assert d == 0
    assert df.damage == 10                                        # 1 counter on opp active (ties -> active)


@test
def t_place_counter_kos_bench():
    ctx, at, df, me, opp = mk(text=K_COUNTER, base=0, opp_bench=1)
    bench = opp.bench[0]
    bench.damage = bench.max_hp - 10                              # a bench mon 1 counter from KO -> targeted
    prizes_before = len(me.prizes)
    d = _call(K_COUNTER, ctx)
    assert d == 0
    assert bench not in opp.bench                                 # bench mon KO'd + removed
    assert len(me.prizes) == prizes_before - 1
    assert df.damage == 0                                         # active untouched


@test
def t_devolve():
    ctx, at, df, me, opp = mk(text=K_DEVOLVE, base=0)
    ev_card = next(c for c in BY_KEY.values()
                   if c.stage == 1 and c.evolves_from and BY_NAME.get(c.evolves_from))
    opp.active = Mon(ev_card)
    opp.bench = []
    d = _call(K_DEVOLVE, ctx)
    assert d == 0
    assert opp.active.card.name == ev_card.evolves_from          # reverted one stage
    assert ('P', ev_card) in opp.hand                            # top card returned to opponent's hand


@test
def t_devolve_none_evolved():
    ctx, at, df, me, opp = mk(text=K_DEVOLVE, base=0)       # all mons are basic VANILLA -> no target
    d = _call(K_DEVOLVE, ctx)
    assert d == 0 and opp.active is df and opp.hand == []


@test
def t_look_at_prize_noop():
    d, ctx, at, df, me, opp = run(K_LOOK_PRIZE, base=0)
    assert d == 0 and len(opp.prizes) == 6                       # pure no-op


@test
def t_weakness_marker():
    d, ctx, at, df, *_ = run(K_WEAKNESS, base=0)
    assert d == 0
    assert getattr(df, 'weakness_override', None) == 'Colorless'
    assert getattr(df, 'weakness_override_turn', None) == 3


@test
def t_cost_more_marker():
    d, ctx, at, df, *_ = run(K_COST_MORE, base=60)
    assert d == 60
    assert getattr(df, 'attack_cost_bonus', 0) == 1
    assert getattr(df, 'retreat_bonus', 0) == 1
    assert getattr(df, 'cost_debuff_turn', None) == 3


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
