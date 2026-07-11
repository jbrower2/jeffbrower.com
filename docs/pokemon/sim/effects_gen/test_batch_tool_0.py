#!/usr/bin/env python3
"""Unit tests for effect batch tool_0 (Pokémon-Tool interactions).

The engine now models Tool attachment (Mon.tools, via ctx.has_tool / ctx.count_tools /
ctx.discard_tools), so each effect is exercised on BOTH branches:
 - the no-Tool branch (empty `mon.tools`): scaling attacks -> 0, conditional bonuses -> base,
   discards -> no-op deal-base;
 - the Tool-present branch where we set a `tools` list on the relevant Mon(s) to prove the effect
   implements the real card text (counts the right side, discards the right pile, respects the
   "up to 2" cap). heads=0.0 / tails=0.9 (unused here — none of these flip coins)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # ensure sim/ importable
import json
from effects_testkit import mk, runner
import attack_effects as AE
import effects_gen.batch_tool_0  # noqa: F401  (registers the effects)


def fire(text, ctx):
    return AE.ATTACK_EFFECTS[AE.normalize(text)](ctx)


# exact registry keys for this batch
K_DISCARD_ACTIVE = "Before doing damage, discard all Pokémon Tools from your opponent's Active Pokémon."
K_PER_TOOL_MINE  = "This attack does 30 damage for each Pokémon Tool attached to all of your Pokémon."
K_PLUS80_OPP     = "If your opponent's Active Pokémon has a Pokémon Tool attached, this attack does 80 more damage."
K_PER_TOOL_ALL   = "This attack does 40 damage for each Pokémon Tool attached to all Pokémon."
K_REVEAL_HAND    = "Your opponent reveals their hand. Discard all Item cards and Pokémon Tool cards you find there."
K_DISCARD_UP2    = "Discard up to 2 Pokémon Tools from your opponent's Pokémon."
K_PLUS70_SELF    = "If this Pokémon has a Pokémon Tool attached, this attack does 70 more damage."

BATCH_KEYS = [K_DISCARD_ACTIVE, K_PER_TOOL_MINE, K_PLUS80_OPP, K_PER_TOOL_ALL,
              K_REVEAL_HAND, K_DISCARD_UP2, K_PLUS70_SELF]

TESTS = []
def test(fn): TESTS.append(fn); return fn


# ---------------------------------------------------------------- round-trip: keys registered exactly
@test
def t_all_batch_keys_registered():
    """Every effect key assigned to batch tool_0 must be registered by exactly the literal string in
    this module — catches any curly-vs-straight apostrophe / accent mismatch."""
    with open(os.path.join(os.path.dirname(__file__), '..', 'effects_work', 'batches.json')) as f:
        batch = [b for b in json.load(f)['batches'] if b['id'] == 'tool_0'][0]
    assigned = {e['key'] for e in batch['effects']}
    literal = {AE.normalize(k) for k in BATCH_KEYS}
    assert {AE.normalize(k) for k in assigned} == literal, (assigned ^ {k for k in BATCH_KEYS})
    for k in BATCH_KEYS:
        assert AE.normalize(k) in AE.ATTACK_EFFECTS, k


# ---------------------------------------------------------------- discard all tools from opp Active
@test
def t_discard_all_tools_opp_active():
    # with tools attached -> ONLY the opponent's Active is cleared; opp Bench + my Active spared
    ctx, at, df, me, opp = mk(text=K_DISCARD_ACTIVE, base=20, opp_bench=1)
    df.tools = ['Rescue Board', 'Lucky Helmet']
    opp.bench[0].tools = ['Bench Tool']          # opp Bench -> NOT this attack's target
    at.tools = ['My Tool']                        # my own Active -> never touched
    assert fire(K_DISCARD_ACTIVE, ctx) == 20
    assert df.tools == [], df.tools               # all tools stripped from opp Active
    assert opp.bench[0].tools == ['Bench Tool']   # bench spared ("Active Pokémon" only)
    assert at.tools == ['My Tool']                # attacker spared
    # current model (no tools) -> no crash, base dealt (a 50-dmg printing)
    ctx2, at2, df2, *_ = mk(text=K_DISCARD_ACTIVE, base=50)
    assert fire(K_DISCARD_ACTIVE, ctx2) == 50
    assert not _has(df2)


# ---------------------------------------------------------------- discard up to 2 tools from opp
@test
def t_discard_up_to_2_tools():
    # 3 tools across opp Active(2)+Bench(1); cap removes exactly 2, leaving 1
    ctx, at, df, me, opp = mk(text=K_DISCARD_UP2, base=0, opp_bench=1)
    opp.active.tools = ['A', 'B']
    opp.bench[0].tools = ['C']
    at.tools = ['MINE']                      # my own tool must be untouched
    assert fire(K_DISCARD_UP2, ctx) == 0
    remaining = len(opp.active.tools) + len(opp.bench[0].tools)
    assert remaining == 1, remaining         # 3 - 2 = 1
    assert at.tools == ['MINE']              # opponent-only
    # fewer than 2 present -> discards what's there, no error
    ctx2, at2, df2, me2, opp2 = mk(text=K_DISCARD_UP2, base=0)
    opp2.active.tools = ['only']
    assert fire(K_DISCARD_UP2, ctx2) == 0
    assert opp2.active.tools == []
    # none present -> clean no-op
    ctx3, *_ = mk(text=K_DISCARD_UP2, base=0)
    assert fire(K_DISCARD_UP2, ctx3) == 0


# ---------------------------------------------------------------- reveal hand, discard Items+Tools
@test
def t_reveal_discard_items_tools():
    ctx, at, df, me, opp = mk(text=K_REVEAL_HAND, base=0)
    item1 = ('T', {'name': 'Nest Ball', 'trainerType': 'Item'})
    item2 = ('T', {'name': 'Ultra Ball', 'trainerType': 'Item'})
    tool  = ('T', {'name': 'Rescue Board', 'trainerType': 'Tool'})
    sup   = ('T', {'name': "Boss's Orders", 'trainerType': 'Supporter'})
    stad  = ('T', {'name': 'Path', 'trainerType': 'Stadium'})
    nrg   = ('E', 'Fire')
    opp.hand = [item1, tool, sup, nrg, item2, stad]
    assert fire(K_REVEAL_HAND, ctx) == 0
    # Items + Tool gone; Supporter, Stadium, Energy kept
    assert item1 not in opp.hand and item2 not in opp.hand and tool not in opp.hand
    assert opp.hand == [sup, nrg, stad], opp.hand
    # my own hand is never touched
    me.hand = [item1]
    fire(K_REVEAL_HAND, ctx)
    assert me.hand == [item1]


# ---------------------------------------------------------------- 30x per tool on MY Pokémon
@test
def t_per_tool_mine_30():
    ctx, at, df, me, opp = mk(text=K_PER_TOOL_MINE, base=30, my_bench=1, opp_bench=1)
    at.tools = ['Lucky Helmet']                       # my Active: 1
    me.bench[0].tools = ['Rescue Board', 'Fan']       # my Bench: 2
    opp.active.tools = ['Helmet']                     # opponent's tool must NOT count
    opp.bench[0].tools = ['Helmet']
    assert fire(K_PER_TOOL_MINE, ctx) == 90           # 30 * 3 (my side only)
    # current model (no tools) -> 0 damage
    ctx2, *_ = mk(text=K_PER_TOOL_MINE, base=30)
    assert fire(K_PER_TOOL_MINE, ctx2) == 0


# ---------------------------------------------------------------- 40x per tool on ALL Pokémon
@test
def t_per_tool_all_40():
    ctx, at, df, me, opp = mk(text=K_PER_TOOL_ALL, base=40, my_bench=1, opp_bench=1)
    at.tools = ['Lucky Helmet']                       # my Active: 1
    me.bench[0].tools = ['Choice Band']               # my Bench: 1  (proves "all" spans my bench too)
    opp.active.tools = ['Rescue Board']               # opp Active: 1
    opp.bench[0].tools = ['Handheld Fan']             # opp Bench: 1
    assert fire(K_PER_TOOL_ALL, ctx) == 160           # 40 * 4 across BOTH sides, both zones
    # current model (no tools) -> 0 damage
    ctx2, *_ = mk(text=K_PER_TOOL_ALL, base=40)
    assert fire(K_PER_TOOL_ALL, ctx2) == 0


# ---------------------------------------------------------------- +80 if opp Active has a tool
@test
def t_plus_80_if_opp_tool():
    ctx, at, df, me, opp = mk(text=K_PLUS80_OPP, base=80)
    df.tools = ['Lucky Helmet']
    assert fire(K_PLUS80_OPP, ctx) == 160
    # no tool -> base only (never over-applies the bonus)
    ctx2, at2, df2, *_ = mk(text=K_PLUS80_OPP, base=80)
    assert fire(K_PLUS80_OPP, ctx2) == 80
    # tool on opp BENCH or on my own attacker must NOT trigger it (condition = opp *Active* only)
    ctx3, at3, df3, me3, opp3 = mk(text=K_PLUS80_OPP, base=80, opp_bench=1)
    opp3.bench[0].tools = ['Bench Tool']
    at3.tools = ['My Tool']
    assert fire(K_PLUS80_OPP, ctx3) == 80


# ---------------------------------------------------------------- +70 if THIS Pokémon has a tool
@test
def t_plus_70_if_self_tool():
    ctx, at, df, me, opp = mk(text=K_PLUS70_SELF, base=70)
    at.tools = ['Lucky Helmet']
    assert fire(K_PLUS70_SELF, ctx) == 140
    # opponent's tool is irrelevant; my own absence -> base only
    ctx2, at2, df2, me2, opp2 = mk(text=K_PLUS70_SELF, base=70)
    opp2.active.tools = ['Helmet']
    assert fire(K_PLUS70_SELF, ctx2) == 70


def _has(mon):
    tl = getattr(mon, 'tools', None)
    return bool(tl)


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
