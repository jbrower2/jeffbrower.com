#!/usr/bin/env python3
"""Shared test harness for attack-effect unit tests (used by test_effects.py and every
effects_gen/test_batch_*.py). Builds real engine Mon/Player/Game objects with a scripted RNG so
coin flips are deterministic, then runs a registered effect and hands back the damage + state."""
from collections import Counter
from cards import load_cards
from engine import Mon, Player, Game
import attack_effects as AE

BK, BN = load_cards()
VANILLA = next(c for c in BK.values() if c.cat == 'cat-green' and c.stage == 0)   # plain Basic for test Mons


class ScriptedRandom:
    """Deterministic RNG. random() returns the next scripted value (cycles). heads=0.0, tails=0.9."""
    def __init__(self, vals=(0.0,)):
        self.vals = list(vals); self.i = 0
    def random(self):
        v = self.vals[self.i % len(self.vals)]; self.i += 1; return v
    def shuffle(self, x): pass
    def choice(self, x): return x[0]
    def randint(self, a, b): return a
    def sample(self, pop, k): return list(pop)[:k]


def mk(base=50, text='', flips=(0.0,), opp_prizes=6, my_prizes=6,
       atk_energy=None, def_energy=None, def_special=(), opp_bench=1, my_bench=1,
       stadium=None, played=(), ko_last=False, def_tools=(), atk_tools=()):
    """Build (ctx, attacker, defender, me, opp) for one effect test. Tune state via kwargs.
    Tracker kwargs: stadium=name, played=[trainer names this turn], ko_last=True (a mon KO'd on opp's
    last turn), def_tools/atk_tools=[tool names]. Set attacker.last_atk / .evolved_turn directly as needed."""
    rng = ScriptedRandom(flips)
    g = Game.__new__(Game); g.rng = rng; g.turn = 3; g.verbose = False; g.stats = None
    g.stadium = (stadium, 0) if stadium else None
    me = Player.__new__(Player); opp = Player.__new__(Player)
    for p in (me, opp):
        p.rng = rng; p.hand = []; p.bench = []; p.discard = []
        p.disc_energy = Counter(); p.deck = [('P', VANILLA)] * 6 + [('E', 'Colorless')] * 10
        p.prizes = [('E', 'Colorless')] * 6; p.prizes_taken = 0; p.lost = False
        p.last_ko_turn = -9; p.played = []
    me.prizes = [('E', 'Colorless')] * my_prizes
    opp.prizes = [('E', 'Colorless')] * opp_prizes
    me.played = list(played)
    if ko_last:
        me.last_ko_turn = g.turn - 1                       # a mon of mine was KO'd on the opponent's last turn
    attacker = Mon(VANILLA); defender = Mon(VANILLA)
    attacker.energy = Counter(atk_energy or {'Colorless': 3})
    defender.energy = Counter(def_energy or {'Colorless': 2})
    defender.special = list(def_special)
    defender.tools = list(def_tools); attacker.tools = list(atk_tools)
    me.active = attacker; opp.active = defender
    me.bench = [Mon(VANILLA) for _ in range(my_bench)]
    opp.bench = [Mon(VANILLA) for _ in range(opp_bench)]
    attack = {'dmg': base, 'text': text, 'cost': [], 'name': 'TestAtk'}
    return AE.EffectCtx(me, opp, attacker, defender, g, attack), attacker, defender, me, opp


def run(text, **kw):
    """Resolve the effect registered under `text` and return (damage, ctx, attacker, defender, me, opp)."""
    ctx, at, df, me, opp = mk(text=text, **kw)
    fn = AE.ATTACK_EFFECTS[AE.normalize(text)]
    return fn(ctx), ctx, at, df, me, opp


def runner(tests):
    """Run a list of test fns; print failures; return (passed, failed)."""
    import traceback
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception:
            failed += 1
            print(f"FAIL {t.__name__}:"); traceback.print_exc()
    return passed, failed
