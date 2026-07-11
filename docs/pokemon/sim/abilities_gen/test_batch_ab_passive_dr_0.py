#!/usr/bin/env python3
"""Unit tests for ability batch ab_passive_dr_0 (passive damage-reduction auras).

Each registered passive_dr fn is exercised directly with the hook signature
    fn(dmg, atk, dfn, dfn_owner, game) -> int
where (matching the proof batch) atk = the attacker Mon, dfn = the defender Mon (opp.active), and
dfn_owner = the defender's Player (opp). Fns return raw dmg-N; reduce_damage() clamps at 0 upstream.
"""
from effects_testkit import mk, runner
import ability_effects as AB
import abilities_gen.batch_ab_passive_dr_0  # noqa: F401 (registers the batch's abilities on import)
from cards import load_cards

_BK, _BN = load_cards()


def _fn(key):
    e = AB.ABILITY_EFFECTS[AB.normalize(key)]
    assert e['kind'] == 'passive_dr', e['kind']
    return e['fn']


def _card_of_type(t):
    return next(c for c in _BK.values() if c.ptype == t and c.stage == 0)


FIRE = _card_of_type('Fire')
WATER = _card_of_type('Water')
GRASS = _card_of_type('Grass')
PYROAR = next(c for c in _BN['Pyroar'] if any(a['name'] == 'Intimidating Fang' for a in c.abilities))
CARBINK = next(c for c in _BN["Steven's Carbink"] if any(a['name'] == 'Stone Palace' for a in c.abilities))
STEVENS = _BN["Steven's Skarmory"][0]
DEWGONG = next(c for c in _BN['Dewgong'] if any(a['name'] == 'Thick Fat' for a in c.abilities))
BRONZONG = next(c for c in _BN['Bronzong'] if any(a['name'] == 'Protective Bell' for a in c.abilities))

THICK_FAT = "- This Pokémon takes 30 less damage from attacks from your opponent's {R} or {W} Pokémon (after applying Weakness and Resistance)."
PROT_BELL = "- All of your Pokémon take 10 less damage from attacks from your opponent's Pokémon (after applying Weakness and Resistance)."
GLOOMY = "- Attacks used by your opponent's Active Pokémon that has a Pokémon Tool attached do 20 less damage (before applying Weakness and Resistance)."
INTIM_FANG = "- As long as this Pokémon is in the Active Spot, attacks used by your opponent's Active Pokémon do 30 less damage (before applying Weakness and Resistance)."
STONE_PALACE = "- As long as this Pokémon is on your Bench, all of your Steven's Pokémon take 30 less damage from attacks from your opponent's Pokémon (after applying Weakness and Resistance). The effect of Stone Palace doesn't stack."


# ---- Thick Fat -----------------------------------------------------------------------------------
def t_thick_fat_fire_attacker():
    ctx, at, df, me, opp = mk()
    at.card = FIRE
    assert _fn(THICK_FAT)(100, at, df, opp, ctx.game) == 70


def t_thick_fat_water_attacker():
    ctx, at, df, me, opp = mk()
    at.card = WATER
    assert _fn(THICK_FAT)(100, at, df, opp, ctx.game) == 70


def t_thick_fat_other_type_no_reduction():
    ctx, at, df, me, opp = mk()
    at.card = GRASS                                  # not {R}/{W} -> full damage
    assert _fn(THICK_FAT)(100, at, df, opp, ctx.game) == 100


def t_thick_fat_returns_raw_below_zero():
    ctx, at, df, me, opp = mk()
    at.card = FIRE
    assert _fn(THICK_FAT)(20, at, df, opp, ctx.game) == -10   # raw; upstream reduce_damage clamps


# ---- Protective Bell -----------------------------------------------------------------------------
def t_protective_bell_flat_10():
    ctx, at, df, me, opp = mk()
    f = _fn(PROT_BELL)
    assert f(100, at, df, opp, ctx.game) == 90
    assert f(30, at, df, opp, ctx.game) == 20


# ---- Gloomy Garbage (Tool-gated DR: fires only vs a Tool-carrying attacker) ----------------------
def t_gloomy_garbage_tool_gated():
    ctx, at, df, me, opp = mk()
    assert _fn(GLOOMY)(100, at, df, opp, ctx.game) == 100     # attacker has no Tool -> full damage
    at.tools = ['Lucky Helmet']
    assert _fn(GLOOMY)(100, at, df, opp, ctx.game) == 80      # attacker carries a Tool -> -20


# ---- Intimidating Fang ---------------------------------------------------------------------------
def t_intimidating_fang_holder_active():
    ctx, at, df, me, opp = mk()
    df.card = PYROAR                                 # holder is the defending side's Active
    assert _fn(INTIM_FANG)(100, at, df, opp, ctx.game) == 70


def t_intimidating_fang_holder_benched_no_reduction():
    ctx, at, df, me, opp = mk(opp_bench=1)
    opp.bench[0].card = PYROAR                       # Pyroar benched, Active is vanilla -> no DR
    assert not any(a['name'] == 'Intimidating Fang' for a in opp.active.card.abilities)
    assert _fn(INTIM_FANG)(100, at, df, opp, ctx.game) == 100


# ---- Stone Palace --------------------------------------------------------------------------------
def t_stone_palace_stevens_defender_benched_holder():
    ctx, at, df, me, opp = mk(opp_bench=1)
    df.card = STEVENS                                # a Steven's Pokémon (not the Carbink itself)
    opp.bench[0].card = CARBINK                      # Stone Palace holder on the Bench
    assert _fn(STONE_PALACE)(100, at, df, opp, ctx.game) == 70


def t_stone_palace_no_benched_holder():
    ctx, at, df, me, opp = mk(opp_bench=1)
    df.card = STEVENS
    # bench holds only the default vanilla -> no Carbink holder -> aura inactive
    assert not any(a['name'] == 'Stone Palace' for a in opp.bench[0].card.abilities)
    assert _fn(STONE_PALACE)(100, at, df, opp, ctx.game) == 100


def t_stone_palace_non_stevens_defender_unprotected():
    ctx, at, df, me, opp = mk(opp_bench=1)
    df.card = GRASS                                  # not a Steven's Pokémon
    opp.bench[0].card = CARBINK                      # holder present, but defender isn't in the family
    assert _fn(STONE_PALACE)(100, at, df, opp, ctx.game) == 100


# ---- Stone Palace: branches the registry ACTUALLY reaches (holder Carbink is itself the defender) --
# The direct-call tests above feed a non-holder teammate as `dfn`, but reduce_damage only ever invokes
# a passive_dr fn when `dfn` is a holder (see registry-integration tests below). These cover that.
def t_stone_palace_holder_benched_self_protected():
    # Benched Carbink sniped: it is on the Bench (aura live) and is a Steven's Pokémon -> -30.
    ctx, at, df, me, opp = mk(opp_bench=1)
    opp.bench[0].card = CARBINK
    assert _fn(STONE_PALACE)(100, at, opp.bench[0], opp, ctx.game) == 70


def t_stone_palace_active_holder_no_benched_holder_off():
    # Active Carbink with no benched Carbink -> its own aura needs a benched holder -> full damage.
    ctx, at, df, me, opp = mk(opp_bench=1)
    df.card = CARBINK
    opp.bench[0].card = GRASS
    assert _fn(STONE_PALACE)(100, at, df, opp, ctx.game) == 100


def t_stone_palace_active_holder_second_benched_holder_protected():
    # Active Carbink WITH a second Carbink benched -> the benched holder's aura covers it -> -30.
    ctx, at, df, me, opp = mk(opp_bench=1)
    df.card = CARBINK
    opp.bench[0].card = CARBINK
    assert _fn(STONE_PALACE)(100, at, df, opp, ctx.game) == 70


# ---- Registry-integration tests: drive AB.reduce_damage (the ACTUAL hook), not the fn in isolation.
# reduce_damage scans ONLY the defender's own passive_dr abilities (contrast is_immune/hp_bonus, which
# scan all_mons). So self/holder DR reduces, but a team aura on a benched holder does NOT reach a
# non-holder teammate through the registry -- team DR is handled separately in effects.py. Pin both.
def t_reg_thick_fat_self_reduces_and_type_gated():
    ctx, at, df, me, opp = mk()
    df.card = DEWGONG                                # holder is the defender
    at.card = FIRE
    assert AB.reduce_damage(100, at, df, opp, ctx.game) == 70     # {R} attacker -> -30
    at.card = GRASS
    assert AB.reduce_damage(100, at, df, opp, ctx.game) == 100    # non-{R}/{W} attacker -> unreduced


def t_reg_non_holder_defender_unreduced():
    ctx, at, df, me, opp = mk()
    at.card = FIRE                                   # df is vanilla (no passive_dr ability)
    assert AB.reduce_damage(100, at, df, opp, ctx.game) == 100    # registry never invokes a DR fn


def t_reg_protective_bell_holder_self():
    ctx, at, df, me, opp = mk()
    df.card = BRONZONG
    assert AB.reduce_damage(100, at, df, opp, ctx.game) == 90


def t_reg_intimidating_fang_holder_active():
    ctx, at, df, me, opp = mk()
    df.card = PYROAR                                 # holder is the Active defender
    assert AB.reduce_damage(100, at, df, opp, ctx.game) == 70


def t_reg_stone_palace_holder_benched_reduces():
    ctx, at, df, me, opp = mk(opp_bench=1)
    opp.bench[0].card = CARBINK                      # benched Carbink is both holder and (sniped) defender
    assert AB.reduce_damage(100, at, opp.bench[0], opp, ctx.game) == 70


def t_reg_stone_palace_team_aura_reaches_teammate():
    # Team aura (fixed contract): a benched Carbink DOES protect a non-holder Steven's teammate,
    # because reduce_damage now scans the whole defending team for 'team'-scoped DR.
    ctx, at, df, me, opp = mk(opp_bench=1)
    df.card = STEVENS                                # Steven's teammate is Active and attacked
    opp.bench[0].card = CARBINK
    assert AB.reduce_damage(100, at, df, opp, ctx.game) == 70


def t_reg_gloomy_garbage_holder():
    ctx, at, df, me, opp = mk()
    df.card = next(c for c in _BN['Garbodor'] if any(a['name'] == 'Gloomy Garbage' for a in c.abilities))
    assert AB.reduce_damage(100, at, df, opp, ctx.game) == 100    # attacker has no Tool -> no reduction
    at.tools = ['Lucky Helmet']
    assert AB.reduce_damage(100, at, df, opp, ctx.game) == 80     # Tool-carrying attacker -> -20


TESTS = [
    t_thick_fat_fire_attacker,
    t_thick_fat_water_attacker,
    t_thick_fat_other_type_no_reduction,
    t_thick_fat_returns_raw_below_zero,
    t_protective_bell_flat_10,
    t_gloomy_garbage_tool_gated,
    t_intimidating_fang_holder_active,
    t_intimidating_fang_holder_benched_no_reduction,
    t_stone_palace_stevens_defender_benched_holder,
    t_stone_palace_no_benched_holder,
    t_stone_palace_non_stevens_defender_unprotected,
    t_stone_palace_holder_benched_self_protected,
    t_stone_palace_active_holder_no_benched_holder_off,
    t_stone_palace_active_holder_second_benched_holder_protected,
    t_reg_thick_fat_self_reduces_and_type_gated,
    t_reg_non_holder_defender_unreduced,
    t_reg_protective_bell_holder_self,
    t_reg_intimidating_fang_holder_active,
    t_reg_stone_palace_holder_benched_reduces,
    t_reg_stone_palace_team_aura_reaches_teammate,
    t_reg_gloomy_garbage_holder,
]

if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
