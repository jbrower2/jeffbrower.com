#!/usr/bin/env python3
"""Unit tests for trainer batch tr_stadium_1 (12 Stadiums). Each Stadium action runs through a real
TrainerCtx over Player/Game objects built by the shared harness. Action Stadiums assert the state
change; the six purely-passive Stadiums (no once-per-turn action) assert a conservative no-op."""
from effects_testkit import mk, runner
import effects_testkit as TK
from engine import Mon
import trainer_effects as TE
import trainers_gen.batch_tr_stadium_1   # noqa: F401  (registers the batch)

VANILLA = TK.VANILLA                                   # Bulbasaur (Grass, Basic)
BK = TK.BK
WATER = next(c for c in BK.values() if c.ptype == 'Water' and c.stage == 0)
PSY = next(c for c in BK.values() if c.ptype == 'Psychic' and c.stage == 0)
MARNIE = next(c for c in BK.values() if c.name.startswith("Marnie's"))


def run_action(text, setup=None, **kw):
    """Build harness state, optionally mutate it, then resolve the Stadium action by exact text."""
    ctx, at, df, me, opp = mk(**kw)
    if setup:
        setup(me, opp, at, df, ctx)
    did = TE.TRAINER_EFFECTS[TE.normalize(text)]['fn'](TE.TrainerCtx(me, opp, ctx.game))
    return did, me, opp, at, df, ctx


TESTS = []
def test(f):
    TESTS.append(f)
    return f


# ---- exact texts (must match registration) ----
LUMIOSE = "Once during each player's turn, that player may search their deck for a Basic Pokémon and put it onto their Bench. Then, that player shuffles their deck. If a player searches their deck in this way, their turn ends."
MYSTERY = "Once during each player's turn, that player may discard an Energy card from their hand in order to draw cards until they have as many cards in their hand as they have {P} Pokémon in play."
PRISM = "Once during each player's turn, that player may discard 2 cards from their hand in order to draw a card."
SPIKEMUTH = "Once during each player's turn, that player may search their deck for a Marnie's Pokémon, reveal it, and put it into their hand. Then, that player shuffles their deck."
SURFING = "Once during each player's turn, that player may switch their Active {W} Pokémon with 1 of their Benched {W} Pokémon."
FACTORY = 'Once during each player\'s turn, if they played a Supporter card that has "Team Rocket" in its name from their hand this turn, they may draw 2 cards.'
NSCASTLE = "N's Pokémon in play (both yours and your opponent's) have no Retreat Cost."
NIGHTMINE = "Attacks used by each Tera Pokémon in play (both yours and your opponent's) cost {C} more."
PERILOUS = "During Pokémon Checkup, put 2 more damage counters on each Poisoned non-{D} Pokémon (both yours and your opponent's)."
POSTWICK = "Attacks used by Hop's Pokémon (both yours and your opponent's) do 30 more damage to the opponent's Active Pokémon (before applying Weakness and Resistance)."
RISKY = "Whenever any player puts a Basic non-{D} Pokémon onto their Bench during their turn, place 2 damage counters on that Pokémon."
WATCHTOWER = "{C} Pokémon in play (both yours and your opponent's) have no Abilities."


# ================================================================ ACTION STADIUMS

@test
def t_lumiose_city():
    # default deck has 6 Basics; the action benches one (bench 1 -> 2).
    did, me, *_ = run_action(LUMIOSE)
    assert did
    assert len(me.bench) == 2


@test
def t_mystery_garden():
    # 2 {P} Pokémon in play, 1 Energy in hand -> discard it (hand 0), draw up to 2.
    def setup(me, opp, at, df, ctx):
        me.active = Mon(PSY)
        me.bench = [Mon(PSY)]
        me.hand = [('E', 'Colorless')]
    did, me, *_ = run_action(MYSTERY, setup=setup)
    assert did
    assert len(me.hand) == 2                     # drew up to the {P}-count target
    assert me.disc_energy['Colorless'] == 1      # the paid Energy went to the discard


@test
def t_mystery_garden_noop_no_energy():
    def setup(me, opp, at, df, ctx):
        me.active = Mon(PSY); me.bench = [Mon(PSY)]; me.hand = []
    did, me, *_ = run_action(MYSTERY, setup=setup)
    assert did is False and len(me.hand) == 0


@test
def t_mystery_garden_noop_selfharm_guard():
    # 0 {P} Pokémon -> drawing would be <=0, so it must NOT discard the Energy for nothing.
    def setup(me, opp, at, df, ctx):
        me.active = Mon(VANILLA); me.bench = []; me.hand = [('E', 'Colorless')]
    did, me, *_ = run_action(MYSTERY, setup=setup)
    assert did is False
    assert len(me.hand) == 1 and me.disc_energy['Colorless'] == 0   # Energy untouched


@test
def t_prism_tower():
    # 2 Energy + 1 Basic in hand -> discard the 2 (least useful) Energy, draw 1.
    def setup(me, opp, at, df, ctx):
        me.hand = [('E', 'Colorless'), ('E', 'Colorless'), ('P', VANILLA)]
    did, me, *_ = run_action(PRISM, setup=setup)
    assert did
    assert len(me.hand) == 2                      # -2 discarded, +1 drawn
    assert me.disc_energy['Colorless'] == 2       # the 2 low-priority Energy discarded
    assert any(x[0] == 'P' for x in me.hand)      # the Basic was kept, not discarded


@test
def t_prism_tower_noop():
    def setup(me, opp, at, df, ctx):
        me.hand = [('E', 'Colorless')]            # only 1 card -> can't pay the 2-card cost
    did, me, *_ = run_action(PRISM, setup=setup)
    assert did is False and len(me.hand) == 1


@test
def t_spikemuth_gym():
    def setup(me, opp, at, df, ctx):
        me.deck.append(('P', MARNIE))
    did, me, *_ = run_action(SPIKEMUTH, setup=setup)
    assert did
    assert any(x[0] == 'P' and x[1].name.startswith("Marnie's") for x in me.hand)


@test
def t_spikemuth_gym_noop():
    # default deck has no Marnie's Pokémon -> nothing to fetch.
    did, me, *_ = run_action(SPIKEMUTH)
    assert did is False


@test
def t_surfing_beach():
    ctx, at, df, me, opp = mk()
    me.active = Mon(WATER); me.bench = [Mon(WATER)]
    orig = me.active
    did = TE.TRAINER_EFFECTS[TE.normalize(SURFING)]['fn'](TE.TrainerCtx(me, opp, ctx.game))
    assert did
    assert me.active is not orig                  # a Benched {W} was promoted
    assert orig in me.bench                        # the old Active went to the Bench
    assert me.active.came_from_bench is True


@test
def t_surfing_beach_noop_not_water():
    def setup(me, opp, at, df, ctx):
        me.active = Mon(VANILLA); me.bench = [Mon(WATER)]   # Active isn't {W}
    did, me, *_ = run_action(SURFING, setup=setup)
    assert did is False


@test
def t_surfing_beach_noop_no_bench_water():
    def setup(me, opp, at, df, ctx):
        me.active = Mon(WATER); me.bench = [Mon(VANILLA)]   # no Benched {W}
    did, me, *_ = run_action(SURFING, setup=setup)
    assert did is False


@test
def t_team_rockets_factory():
    did, me, *_ = run_action(FACTORY, played=["Team Rocket's Giovanni"])
    assert did and len(me.hand) == 2              # drew 2 after a Team Rocket Supporter


@test
def t_team_rockets_factory_noop():
    did, me, *_ = run_action(FACTORY, played=["Professor's Research"])
    assert did is False and len(me.hand) == 0


@test
def t_team_rockets_factory_noop_item():
    # a Team Rocket's ITEM (name also contains "Team Rocket") must NOT trigger: text requires a Supporter.
    did, me, *_ = run_action(FACTORY, played=["Team Rocket's Great Ball"])
    assert did is False and len(me.hand) == 0


@test
def t_team_rockets_factory_noop_own_stadium():
    # playing the Factory Stadium itself logs "Team Rocket's Factory" into me.played; it must NOT self-trigger.
    did, me, *_ = run_action(FACTORY, played=["Team Rocket's Factory"])
    assert did is False and len(me.hand) == 0


@test
def t_team_rockets_factory_any_tr_supporter():
    # every "Team Rocket's" Supporter in the pool triggers the draw.
    for nm in ("Team Rocket's Archer", "Team Rocket's Ariana", "Team Rocket's Petrel", "Team Rocket's Proton"):
        did, me, *_ = run_action(FACTORY, played=[nm])
        assert did and len(me.hand) == 2, nm


# ================================================================ PASSIVE STADIUMS (no-op actions)

@test
def t_ns_castle_passive_noop():
    did, *_ = run_action(NSCASTLE)
    assert did is False


@test
def t_nighttime_mine_passive_noop():
    did, *_ = run_action(NIGHTMINE)
    assert did is False


@test
def t_perilous_jungle_passive_noop():
    # must not place damage counters via the action hook (it's a checkup modifier).
    did, me, opp, *_ = run_action(PERILOUS)
    assert did is False
    assert all(m.damage == 0 for m in me.all_mons() + opp.all_mons())


@test
def t_postwick_passive_noop():
    did, *_ = run_action(POSTWICK)
    assert did is False


@test
def t_risky_ruins_passive_noop():
    # must not place damage counters via the action hook (it's a bench-placement trigger).
    did, me, opp, *_ = run_action(RISKY)
    assert did is False
    assert all(m.damage == 0 for m in me.all_mons() + opp.all_mons())


@test
def t_team_rockets_watchtower_passive_noop():
    did, *_ = run_action(WATCHTOWER)
    assert did is False


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
