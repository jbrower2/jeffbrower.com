#!/usr/bin/env python3
"""Unit tests for effect batch coinflip_effect_0.

Effect keys are pulled straight from effects_work/batches.json (indexed by each effect's first
example card), so a test never hand-copies a key — a registration/lookup mismatch fails loudly.
Coin RNG: heads=0.0, tails=0.9 (see effects_testkit.ScriptedRandom)."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # ensure sim/ importable
from collections import Counter
from types import SimpleNamespace
from effects_testkit import mk, run, runner, VANILLA
import attack_effects as AE
import effects
import effects_gen.batch_coinflip_effect_0 as B  # noqa: F401  (registers the effects)

_SIM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BATCH = [x for x in json.load(open(os.path.join(_SIM, 'effects_work/batches.json')))['batches']
          if x['id'] == 'coinflip_effect_0'][0]
# canonical effect key by first-example card name
K = {e['examples'][0]['card']: e['key'] for e in _BATCH['effects']}


def _fn(key):
    return AE.ATTACK_EFFECTS[AE.normalize(key)]


# ---- coverage guard: every canonical key in the batch is registered ---------------------------
def t_all_keys_registered():
    for e in _BATCH['effects']:
        assert AE.normalize(e['key']) in AE.ATTACK_EFFECTS, e['key']
    assert len(K) == 24, len(K)


# ---- 1/2. prevent-all-damage wall (heads) -----------------------------------------------------
def t_marill_wall_heads():
    d, ctx, at, df, me, opp = run(K['Marill'], base=30, flips=(0.0,))
    assert d == 30 and at.dr_amount == B._WALL and at.dr_turn == ctx.game.turn
    # end-to-end: next turn ANY incoming damage to `at` is prevented, then lapses.
    ctx.game.turn = at.dr_turn + 1
    assert effects.incoming_damage(250, df, at, me, ctx.game) == 0
    ctx.game.turn = at.dr_turn + 2
    assert effects.incoming_damage(60, df, at, me, ctx.game) == 60


def t_marill_wall_tails():
    d, ctx, at, df, me, opp = run(K['Marill'], base=30, flips=(0.9,))
    assert d == 30 and at.dr_amount == 0 and at.dr_turn == -9


def t_altaria_wall():
    d, ctx, at, df, me, opp = run(K['Altaria'], base=100, flips=(0.0,))
    assert d == 100 and at.dr_amount == B._WALL and at.dr_turn == ctx.game.turn
    d2, ctx2, at2, *_ = run(K['Altaria'], base=100, flips=(0.9,))
    assert d2 == 100 and at2.dr_amount == 0


# ---- 3/11. defender-must-flip-to-attack markers -----------------------------------------------
def t_sandslash_marker():
    d, ctx, at, df, me, opp = run(K['Sandslash'], base=50)
    assert d == 50 and df.status.get('CoinToAttack1') == ctx.game.turn
    # the marker is a deliberate under-model: it must be INERT — never wrongly disable the
    # defender's attacks (that would over-state a 50%-fizzle as a 100% lock) and never crash checkup.
    assert effects.can_attack(df, ctx.game.rng) is True
    effects.checkup(df, ctx.game.rng)            # must not raise on the non-condition status key


def t_octillery_marker():
    d, ctx, at, df, me, opp = run(K['Octillery'], base=30)
    assert d == 30 and df.status.get('CoinToAttack2') == ctx.game.turn
    assert effects.can_attack(df, ctx.game.rng) is True
    effects.checkup(df, ctx.game.rng)


# ---- 4. Team Rocket's Raticate: both-tails recoil ---------------------------------------------
def t_raticate_recoil():
    d, ctx, at, *_ = run(K["Team Rocket's Raticate"], base=90, flips=(0.9,))   # both tails
    assert d == 90 and at.damage == 90
    d2, ctx2, at2, *_ = run(K["Team Rocket's Raticate"], base=90, flips=(0.0,))  # both heads
    assert d2 == 90 and at2.damage == 0
    d3, ctx3, at3, *_ = run(K["Team Rocket's Raticate"], base=90, flips=(0.0, 0.9))  # one head
    assert at3.damage == 0


# ---- 5. Ekans: Confused + Poisoned on heads ---------------------------------------------------
def t_ekans():
    d, ctx, at, df, *_ = run(K['Ekans'], base=0, flips=(0.0,))
    assert d == 0 and df.status.get('Confused') and df.status.get('Poisoned')
    d2, ctx2, at2, df2, *_ = run(K['Ekans'], base=0, flips=(0.9,))
    assert not df2.status.get('Confused') and not df2.status.get('Poisoned')


# ---- 6. Team Rocket's Hypno: 80 x tails (per opp benched) --------------------------------------
def t_hypno():
    assert run(K["Team Rocket's Hypno"], base=80, flips=(0.9,), opp_bench=1)[0] == 80    # 1 tails
    assert run(K["Team Rocket's Hypno"], base=80, flips=(0.0,), opp_bench=1)[0] == 0     # 1 head
    assert run(K["Team Rocket's Hypno"], base=80, flips=(0.9, 0.9, 0.9), opp_bench=3)[0] == 240
    assert run(K["Team Rocket's Hypno"], base=80, flips=(0.0, 0.9, 0.9), opp_bench=3)[0] == 160
    assert run(K["Team Rocket's Hypno"], base=80, flips=(0.9,), opp_bench=0)[0] == 0     # no bench, no coins


# ---- 7. Magmar: Burned on heads ---------------------------------------------------------------
def t_magmar():
    d, ctx, at, df, *_ = run(K['Magmar'], base=30, flips=(0.0,))
    assert d == 30 and df.status.get('Burned')
    d2, ctx2, at2, df2, *_ = run(K['Magmar'], base=30, flips=(0.9,))
    assert not df2.status.get('Burned')


# ---- 8. Sylveon: shuffle 1 opp benched Pokémon into deck --------------------------------------
def t_sylveon():
    ctx, at, df, me, opp = mk(text=K['Sylveon'], base=0, flips=(0.0,), opp_bench=1)
    d0 = len(opp.deck)
    assert _fn(K['Sylveon'])(ctx) == 0
    assert len(opp.bench) == 0 and len(opp.deck) == d0 + 1        # benched mon returned as its card
    ctx2, at2, df2, me2, opp2 = mk(text=K['Sylveon'], base=0, flips=(0.9,), opp_bench=1)
    assert _fn(K['Sylveon'])(ctx2) == 0
    assert len(opp2.bench) == 1                                   # tails: no change


# ---- 9. Snorlax: attach #heads basic energy from deck to self ---------------------------------
def t_snorlax():
    d, ctx, at, df, me, opp = run(K['Snorlax'], base=0, flips=(0.0, 0.9))   # 1 head, then tails
    assert d == 0 and at.total_energy() == 4                       # started 3 + 1 from deck
    d2, ctx2, at2, *_ = run(K['Snorlax'], base=0, flips=(0.9,))    # 0 heads
    assert at2.total_energy() == 3


# ---- 10. Ethan's Sudowoodo: copy defender's best attack on heads ------------------------------
def t_sudowoodo():
    ctx, at, df, me, opp = mk(text=K["Ethan's Sudowoodo"], base=0, flips=(0.0,))
    df.card = SimpleNamespace(attacks=[{'dmg': 40}, {'dmg': 70}, {'dmg': 10}])
    assert _fn(K["Ethan's Sudowoodo"])(ctx) == 70                  # heads -> best copied damage
    ctx2, at2, df2, me2, opp2 = mk(text=K["Ethan's Sudowoodo"], base=0, flips=(0.9,))
    df2.card = SimpleNamespace(attacks=[{'dmg': 70}])
    assert _fn(K["Ethan's Sudowoodo"])(ctx2) == 0                  # tails -> nothing


# ---- 12. Smeargle: #heads basic energy from discard onto bench --------------------------------
def t_smeargle():
    ctx, at, df, me, opp = mk(text=K['Smeargle'], base=0, flips=(0.0,), my_bench=1)   # 3 heads
    me.disc_energy = Counter({'Fire': 3})
    assert _fn(K['Smeargle'])(ctx) == 0
    assert me.bench[0].total_energy() == 3 and me.disc_energy.get('Fire', 0) == 0
    ctx2, at2, df2, me2, opp2 = mk(text=K['Smeargle'], base=0, flips=(0.9,), my_bench=1)  # 0 heads
    me2.disc_energy = Counter({'Fire': 3})
    assert _fn(K['Smeargle'])(ctx2) == 0
    assert me2.bench[0].total_energy() == 0 and me2.disc_energy.get('Fire', 0) == 3


# ---- 13. Miltank: 2-heads full heal -----------------------------------------------------------
def t_miltank():
    ctx, at, df, me, opp = mk(text=K['Miltank'], base=0, flips=(0.0,))    # 2 heads
    at.damage = 70
    assert _fn(K['Miltank'])(ctx) == 0 and at.damage == 0
    ctx2, at2, df2, me2, opp2 = mk(text=K['Miltank'], base=0, flips=(0.9,))  # 0 heads
    at2.damage = 70
    assert _fn(K['Miltank'])(ctx2) == 0 and at2.damage == 70
    # boundary: exactly 1 head must NOT heal (guards `flips(2)==2` against a `>=1` regression).
    ctx3, at3, df3, me3, opp3 = mk(text=K['Miltank'], base=0, flips=(0.0, 0.9))  # 1 head, 1 tail
    at3.damage = 70
    assert _fn(K['Miltank'])(ctx3) == 0 and at3.damage == 70


# ---- 14. Shiftry: shuffle 1 opp Pokémon (Active or Bench) into deck ---------------------------
def t_shiftry():
    ctx, at, df, me, opp = mk(text=K['Shiftry'], base=0, flips=(0.0,), opp_bench=1)   # df has most energy
    d0 = len(opp.deck)
    assert _fn(K['Shiftry'])(ctx) == 0
    assert opp.active is not df and opp.active is not None        # Active shuffled -> bench promoted
    assert len(opp.deck) == d0 + 1
    ctx2, at2, df2, me2, opp2 = mk(text=K['Shiftry'], base=0, flips=(0.9,), opp_bench=1)
    assert _fn(K['Shiftry'])(ctx2) == 0 and opp2.active is df2    # tails: no change


# ---- 15/20. self can't attack next turn (tails) -----------------------------------------------
def t_nosepass():
    d, ctx, at, df, *_ = run(K['Nosepass'], base=60, flips=(0.9,))   # tails
    assert d == 60 and at.cd_name == 'ALL' and at.cd_turn == ctx.game.turn
    d2, ctx2, at2, *_ = run(K['Nosepass'], base=60, flips=(0.0,))    # heads
    assert at2.cd_name is None


def t_eternatus():
    d, ctx, at, df, *_ = run(K['Eternatus'], base=130, flips=(0.9,))  # tails
    assert d == 130 and at.cd_name == 'ALL' and at.cd_turn == ctx.game.turn
    d2, ctx2, at2, *_ = run(K['Eternatus'], base=130, flips=(0.0,))   # heads
    assert at2.cd_name is None


# ---- 16. Stoutland: #heads cards from discard to hand -----------------------------------------
def t_stoutland():
    ctx, at, df, me, opp = mk(text=K['Stoutland'], base=0, flips=(0.0,))   # 3 heads
    me.discard = [('P', VANILLA), ('P', VANILLA), ('P', VANILLA), ('P', VANILLA)]
    assert _fn(K['Stoutland'])(ctx) == 0
    assert len(me.hand) == 3 and len(me.discard) == 1
    ctx2, at2, df2, me2, opp2 = mk(text=K['Stoutland'], base=0, flips=(0.9,))  # 0 heads
    me2.discard = [('P', VANILLA)]
    assert _fn(K['Stoutland'])(ctx2) == 0
    assert len(me2.hand) == 0 and len(me2.discard) == 1


# ---- 17. Lilligant: heads Paralyzed+Poisoned / tails Confused ---------------------------------
def t_lilligant():
    d, ctx, at, df, *_ = run(K['Lilligant'], base=30, flips=(0.0,))   # heads
    # heads branch is Paralyzed+Poisoned ONLY — the tails-only Confused must not leak in
    assert d == 30 and df.status.get('Paralyzed') and df.status.get('Poisoned') and not df.status.get('Confused')
    d2, ctx2, at2, df2, *_ = run(K['Lilligant'], base=30, flips=(0.9,))  # tails
    # tails branch is Confused ONLY — not the heads-only Paralyzed/Poisoned
    assert (df2.status.get('Confused') and not df2.status.get('Paralyzed')
            and not df2.status.get('Poisoned'))


# ---- 18. Stunfisk: heads Paralyzed + discard 1 energy from defender ---------------------------
def t_stunfisk():
    d, ctx, at, df, me, opp = run(K['Stunfisk'], base=50, flips=(0.0,), def_energy={'Water': 2})
    assert d == 50 and df.status.get('Paralyzed') and df.total_energy() == 1
    d2, ctx2, at2, df2, *_ = run(K['Stunfisk'], base=50, flips=(0.9,), def_energy={'Water': 2})
    assert not df2.status.get('Paralyzed') and df2.total_energy() == 2


# ---- 19. Heatmor: discard 1 self energy per tails ---------------------------------------------
def t_heatmor():
    d, ctx, at, df, *_ = run(K['Heatmor'], base=130, flips=(0.9,), atk_energy={'Fire': 3})   # 3 tails
    assert d == 130 and at.total_energy() == 0
    d2, ctx2, at2, *_ = run(K['Heatmor'], base=130, flips=(0.0,), atk_energy={'Fire': 3})    # 0 tails
    assert d2 == 130 and at2.total_energy() == 3


# ---- 21. Oinkologne: heads -> Defending Pokémon can't attack next turn -------------------------
def t_oinkologne():
    d, ctx, at, df, *_ = run(K['Oinkologne'], base=50, flips=(0.0,))   # heads
    assert d == 50 and df.cd_name == 'ALL' and df.cd_turn == ctx.game.turn - 1
    d2, ctx2, at2, df2, *_ = run(K['Oinkologne'], base=50, flips=(0.9,))  # tails
    assert df2.cd_name is None


# ---- 22. Grafaiai: heads -> choose a Special Condition (Paralyzed) -----------------------------
def t_grafaiai():
    d, ctx, at, df, *_ = run(K['Grafaiai'], base=90, flips=(0.0,))
    assert d == 90 and df.status.get('Paralyzed')
    d2, ctx2, at2, df2, *_ = run(K['Grafaiai'], base=90, flips=(0.9,))
    assert not df2.status.get('Paralyzed')


# ---- 23. Glimmora: heads -> Paralyzed + Poisoned ----------------------------------------------
def t_glimmora():
    d, ctx, at, df, *_ = run(K['Glimmora'], base=0, flips=(0.0,))
    assert d == 0 and df.status.get('Paralyzed') and df.status.get('Poisoned')
    d2, ctx2, at2, df2, *_ = run(K['Glimmora'], base=0, flips=(0.9,))
    assert not df2.status.get('Paralyzed')


# ---- 24. Gholdengo: search #heads cards from deck to hand --------------------------------------
def t_gholdengo():
    d, ctx, at, df, me, opp = run(K['Gholdengo'], base=0, flips=(0.0, 0.0, 0.9))   # 2 heads
    assert d == 0 and len(me.hand) == 2
    d2, ctx2, at2, df2, me2, opp2 = run(K['Gholdengo'], base=0, flips=(0.9,))      # 0 heads
    assert len(me2.hand) == 0


TESTS = [
    t_all_keys_registered,
    t_marill_wall_heads, t_marill_wall_tails, t_altaria_wall,
    t_sandslash_marker, t_octillery_marker,
    t_raticate_recoil, t_ekans, t_hypno, t_magmar,
    t_sylveon, t_snorlax, t_sudowoodo, t_smeargle, t_miltank, t_shiftry,
    t_nosepass, t_eternatus, t_stoutland, t_lilligant, t_stunfisk, t_heatmor,
    t_oinkologne, t_grafaiai, t_glimmora, t_gholdengo,
]

if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
