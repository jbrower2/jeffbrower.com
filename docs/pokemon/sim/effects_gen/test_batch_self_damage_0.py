#!/usr/bin/env python3
"""Unit tests for effect batch self_damage_0.

Effect keys are pulled straight from effects_work/batches.json (indexed by each effect's first
example card) so a test never hand-copies a key — a registration/lookup mismatch fails loudly.
Coin RNG is irrelevant here (no flips); state is tuned via mk kwargs / direct field pokes."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # ensure sim/ importable
from effects_testkit import mk, run, runner, VANILLA, BK
from engine import Mon
import attack_effects as AE
import effects_gen.batch_self_damage_0 as B  # noqa: F401  (registers the effects)

_SIM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BATCH = [x for x in json.load(open(os.path.join(_SIM, 'effects_work/batches.json')))['batches']
          if x['id'] == 'self_damage_0'][0]
# canonical effect key by first-example card name
K = {e['examples'][0]['card']: e['key'] for e in _BATCH['effects']}


def _fn(key):
    return AE.ATTACK_EFFECTS[AE.normalize(key)]


# ---- coverage guard: every canonical key in the batch is registered ---------------------------
def t_all_keys_registered():
    for e in _BATCH['effects']:
        assert AE.normalize(e['key']) in AE.ATTACK_EFFECTS, e['key']
    assert len(_BATCH['effects']) == 6, len(_BATCH['effects'])


# ---- flat recoil: 40 / 50 / 60 / 70 -----------------------------------------------------------
def t_self_40():
    d, ctx, at, *_ = run(K['Alolan Golem'], base=160)   # "This Pokémon also does 40 damage to itself."
    assert d == 160 and at.damage == 40, (d, at.damage)


def t_self_50():
    d, ctx, at, *_ = run(K['Azumarill'], base=230)      # "...also does 50 damage to itself."
    assert d == 230 and at.damage == 50, (d, at.damage)


def t_self_60():
    d, ctx, at, *_ = run(K['Turtonator'], base=180)     # "...also does 60 damage to itself."
    assert d == 180 and at.damage == 60, (d, at.damage)


def t_self_70():
    d, ctx, at, *_ = run(K['Darmanitan'], base=210)     # "...also does 70 damage to itself."
    assert d == 210 and at.damage == 70, (d, at.damage)


# ---- recoil that stacks on pre-existing damage (flat is additive, not a set) -------------------
def t_self_50_adds_to_existing():
    ctx, at, df, me, opp = mk(text=K['Azumarill'], base=230)
    at.damage = 20                                       # already had 2 counters
    d = _fn(K['Azumarill'])(ctx)
    assert d == 230 and at.damage == 70, at.damage       # 20 + 50 recoil


# ---- counter-scaled recoil (Palafin): 10 per damage counter on itself -------------------------
def t_palafin_no_counters():
    # No damage on the attacker -> 0 recoil.
    d, ctx, at, *_ = run(K['Palafin'], base=130)
    assert d == 130 and at.damage == 0, (d, at.damage)


def t_palafin_with_counters():
    ctx, at, df, me, opp = mk(text=K['Palafin'], base=130)
    at.damage = 50                                       # 5 damage counters
    d = _fn(K['Palafin'])(ctx)
    assert d == 130 and at.damage == 100, at.damage      # 50 + 10*5 recoil = 50 more


def t_palafin_recoil_does_not_compound():
    # Recoil is computed from counters present BEFORE it lands (does not feed itself):
    # 30 damage (3 counters) -> +30 recoil -> 60, NOT a runaway.
    ctx, at, df, me, opp = mk(text=K['Palafin'], base=130)
    at.damage = 30
    d = _fn(K['Palafin'])(ctx)
    assert d == 130 and at.damage == 60, at.damage


# ---- optional recoil (Gurdurr): "you may do 30 more, then take 30" -----------------------------
def t_gurdurr_takes_extra_when_safe():
    # Attacker healthy (survives the 30 recoil), defender full HP so base (50) doesn't KO ->
    # opt in: 50 + 30 = 80 output, +30 recoil.
    d, ctx, at, df, me, opp = run(K['Gurdurr'], base=50)   # at.damage=0 (hp_left 80), df full HP
    assert d == 80 and at.damage == 30, (d, at.damage)


def t_gurdurr_skips_on_overkill():
    # Base 50 already KOs the defender (hp_left 40) -> no reason to take recoil: 50, no self-damage.
    ctx, at, df, me, opp = mk(text=K['Gurdurr'], base=50)
    df.damage = df.max_hp - 40                             # defender hp_left = 40
    d = _fn(K['Gurdurr'])(ctx)
    assert d == 50 and at.damage == 0, (d, at.damage)


def t_gurdurr_skips_when_suicidal_and_no_ko():
    # Attacker would die to the 30 recoil AND the +30 doesn't reach a KO -> decline: 50, no recoil.
    # Raise the defender's HP out of +30 KO range via Growing Grass Energy (+20 HP each).
    ctx, at, df, me, opp = mk(text=K['Gurdurr'], base=50,
                              def_special=('Growing Grass Energy',) * 3)  # max_hp 80+60=140
    at.damage = 60                                         # hp_left 20 -> 30 recoil would KO
    assert df.hp_left == 140 and (50 + 30) < df.hp_left    # +30 (=80) does not KO
    d = _fn(K['Gurdurr'])(ctx)
    assert d == 50 and at.damage == 60, (d, at.damage)


def t_gurdurr_takes_extra_to_secure_ko_even_if_suicidal():
    # Attacker would die to recoil, BUT the +30 converts a non-KO into a KO -> take the trade.
    ctx, at, df, me, opp = mk(text=K['Gurdurr'], base=50)
    at.damage = 60                                        # hp_left 20 -> recoil would KO the attacker
    df.damage = df.max_hp - 70                            # hp_left 70: base 50 no KO, base+30=80 KOs
    d = _fn(K['Gurdurr'])(ctx)
    assert d == 80 and at.damage == 90, (d, at.damage)    # committed +30 output and +30 recoil


def t_gurdurr_takes_chip_when_survives_no_ko():
    # Survives-branch IN ISOLATION (full_kos=False): attacker healthy, but the defender is too
    # bulky for +30 (=80) to reach a KO, so the +30 is taken purely for chip damage because the
    # attacker survives the 30 recoil. Distinct from t_gurdurr_takes_extra_when_safe, where +30
    # *also* KOs the 80-HP VANILLA (full_kos=True) and so doesn't exercise this branch alone.
    ctx, at, df, me, opp = mk(text=K['Gurdurr'], base=50,
                              def_special=('Growing Grass Energy',) * 3)  # df max_hp 80+60=140
    assert df.hp_left == 140 and (50 + 30) < df.hp_left    # +30 (=80) does NOT reach a KO
    assert at.hp_left == 80 and at.hp_left > 30            # attacker survives the 30 recoil
    d = _fn(K['Gurdurr'])(ctx)
    assert d == 80 and at.damage == 30, (d, at.damage)     # took +30 for chip; +30 recoil


def t_gurdurr_weakness_respected_in_ko_decision():
    # _weak_mult must actually gate the KO decision. Grass attacker (VANILLA=Bulbasaur, ptype Grass)
    # vs a Grass-WEAK 100-HP defender (Rhyhorn). base 50 ALONE (50 < 100) would not KO -> without
    # weakness the AI would take the +30 (survives-branch); WITH x2 weakness (50*2=100) the base is
    # already lethal, so the +30/recoil is declined as overkill. Passing proves weakness is consulted.
    ctx, at, df, me, opp = mk(text=K['Gurdurr'], base=50)
    rhy = next(c for c in BK.values() if c.name == 'Rhyhorn' and c.set == 'SV07')
    newdf = Mon(rhy)
    ctx.defender = newdf; opp.active = newdf               # swap in the real Grass-weak defender
    assert at.card.ptype == 'Grass' and newdf.card.weakness == 'Grass'
    assert newdf.hp_left == 100 and 50 < newdf.hp_left     # base alone (mult=1) would NOT KO
    d = _fn(K['Gurdurr'])(ctx)
    assert d == 50 and at.damage == 0, (d, at.damage)      # x2 weakness makes 50 lethal -> skip recoil


TESTS = [t_all_keys_registered,
         t_self_40, t_self_50, t_self_60, t_self_70, t_self_50_adds_to_existing,
         t_palafin_no_counters, t_palafin_with_counters, t_palafin_recoil_does_not_compound,
         t_gurdurr_takes_extra_when_safe, t_gurdurr_skips_on_overkill,
         t_gurdurr_skips_when_suicidal_and_no_ko, t_gurdurr_takes_extra_to_secure_ko_even_if_suicidal,
         t_gurdurr_takes_chip_when_survives_no_ko, t_gurdurr_weakness_respected_in_ko_decision]

if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
