#!/usr/bin/env python3
"""Unit tests for batch ab_retreat_mod_0 (retreat_mod abilities)."""
from effects_testkit import mk, runner, VANILLA
import ability_effects as AB
import abilities_gen.batch_ab_retreat_mod_0  # noqa: F401  (registers the batch)
from engine import Mon, BY_KEY


def fn_of(key):
    return AB.ABILITY_EFFECTS[AB.normalize(key)]['fn']


AGILE = "- If this Pokémon has no Energy attached, it has no Retreat Cost."
BIG_NET = "- Your opponent's Active Evolution Pokémon's Retreat Cost is {C} more."
SFP = "- As long as this Pokémon is on your Bench, your Active Pokémon's Retreat Cost is {C}{C} less."

CHARMANDER_AGILE = 'ME02:#011/094'   # Basic, Agile
ARIADOS_PLAIN = 'ME03:#002/088'      # Stage 1, no ability (generic Evolution mon)
ARIADOS_BIGNET = 'SV06:#005/167'     # Stage 1, Big Net
TOEDSCRUEL_SFP = 'SV09:#089/159'     # Stage 1, Secret Forest Path

TESTS = []
def test(f): TESTS.append(f); return f


# ---------------- Agile (self-referential) ----------------
@test
def t_agile_free_when_no_energy():
    ctx, at, df, me, opp = mk()
    m = Mon(BY_KEY[CHARMANDER_AGILE])
    assert m.total_energy() == 0
    assert fn_of(AGILE)(m, me, ctx.game) == -99          # no energy => free retreat sentinel


@test
def t_agile_no_discount_with_basic_energy():
    ctx, at, df, me, opp = mk()
    m = Mon(BY_KEY[CHARMANDER_AGILE]); m.energy['Fire'] += 1
    assert fn_of(AGILE)(m, me, ctx.game) == 0


@test
def t_agile_no_discount_with_special_energy():
    ctx, at, df, me, opp = mk()
    m = Mon(BY_KEY[CHARMANDER_AGILE])
    m.energy['Colorless'] += 1                            # special energy also increments mon.energy
    m.special.append('Some Special Energy')
    assert m.total_energy() == 1
    assert fn_of(AGILE)(m, me, ctx.game) == 0


# ---------------- Big Net (opponent debuff aura, +{C}) ----------------
@test
def t_big_net_plus_one_on_opp_active_evolution():
    ctx, at, df, me, opp = mk()
    ctx.game.players = [me, opp]
    me.active = Mon(BY_KEY[ARIADOS_PLAIN])               # affected: Active Evolution (stage 1)
    opp.active = Mon(BY_KEY[ARIADOS_BIGNET]); opp.bench = []   # holder in play (Active)
    assert fn_of(BIG_NET)(me.active, me, ctx.game) == 1


@test
def t_big_net_holder_may_be_benched():
    ctx, at, df, me, opp = mk()
    ctx.game.players = [me, opp]
    me.active = Mon(BY_KEY[ARIADOS_PLAIN])
    opp.active = Mon(VANILLA); opp.bench = [Mon(BY_KEY[ARIADOS_BIGNET])]  # Big Net has no location clause
    assert fn_of(BIG_NET)(me.active, me, ctx.game) == 1


@test
def t_big_net_stacks_with_two_holders():
    ctx, at, df, me, opp = mk()
    ctx.game.players = [me, opp]
    me.active = Mon(BY_KEY[ARIADOS_PLAIN])                    # affected: Active Evolution (stage 1)
    opp.active = Mon(BY_KEY[ARIADOS_BIGNET])
    opp.bench = [Mon(BY_KEY[ARIADOS_BIGNET])]                 # two Big Net holders in play
    assert fn_of(BIG_NET)(me.active, me, ctx.game) == 2       # {C} each => +2 (continuous abilities stack)


@test
def t_big_net_none_when_no_holder():
    ctx, at, df, me, opp = mk()
    ctx.game.players = [me, opp]
    me.active = Mon(BY_KEY[ARIADOS_PLAIN])
    opp.active = Mon(VANILLA); opp.bench = [Mon(VANILLA)]
    assert fn_of(BIG_NET)(me.active, me, ctx.game) == 0


@test
def t_big_net_none_when_affected_is_basic():
    ctx, at, df, me, opp = mk()
    ctx.game.players = [me, opp]
    me.active = Mon(BY_KEY[CHARMANDER_AGILE])            # Basic => not an Evolution, no debuff
    opp.active = Mon(BY_KEY[ARIADOS_BIGNET]); opp.bench = []
    assert fn_of(BIG_NET)(me.active, me, ctx.game) == 0


@test
def t_big_net_only_hits_the_active():
    ctx, at, df, me, opp = mk()
    ctx.game.players = [me, opp]
    me.active = Mon(VANILLA)
    benched_evo = Mon(BY_KEY[ARIADOS_PLAIN]); me.bench = [benched_evo]   # benched Evolution
    opp.active = Mon(BY_KEY[ARIADOS_BIGNET]); opp.bench = []
    assert fn_of(BIG_NET)(benched_evo, me, ctx.game) == 0   # only the opponent's ACTIVE is debuffed


# ---------------- Secret Forest Path (own-active buff from bench, -{C}{C}) ----------------
@test
def t_sfp_minus_two_with_bench_holder():
    ctx, at, df, me, opp = mk()
    me.active = Mon(BY_KEY[ARIADOS_PLAIN])
    me.bench = [Mon(BY_KEY[TOEDSCRUEL_SFP])]             # holder benched -> -{C}{C}
    assert fn_of(SFP)(me.active, me, ctx.game) == -2


@test
def t_sfp_stacks_with_two_bench_holders():
    ctx, at, df, me, opp = mk()
    me.active = Mon(BY_KEY[ARIADOS_PLAIN])
    me.bench = [Mon(BY_KEY[TOEDSCRUEL_SFP]), Mon(BY_KEY[TOEDSCRUEL_SFP])]  # two SFP holders benched
    assert fn_of(SFP)(me.active, me, ctx.game) == -4          # {C}{C} each => -4 (stacks)


@test
def t_sfp_none_without_bench_holder():
    ctx, at, df, me, opp = mk()
    me.active = Mon(BY_KEY[ARIADOS_PLAIN])
    me.bench = [Mon(VANILLA)]
    assert fn_of(SFP)(me.active, me, ctx.game) == 0


@test
def t_sfp_not_applied_to_benched_holder_itself():
    ctx, at, df, me, opp = mk()
    me.active = Mon(VANILLA)
    holder = Mon(BY_KEY[TOEDSCRUEL_SFP]); me.bench = [holder]
    assert fn_of(SFP)(holder, me, ctx.game) == 0          # the benched holder gets no discount on itself


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
