#!/usr/bin/env python3
"""Unit tests for effect batch conditional_damage_1.

Each effect asserts the returned damage AND the key state change, covering both the condition-met
and condition-unmet branches wherever the effect is conditional/scaled.
"""
import os, sys, json
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # sim/ importable
from effects_testkit import mk, run, runner
import attack_effects as AE
import effects
from engine import BY_KEY, BY_NAME
import effects_gen.batch_conditional_damage_1 as B  # registers the effects

# -- sample real cards for state-dependent tests --
IVY = next(c for c in BY_KEY.values() if c.stage == 1)                                    # evolved (stage 1)
MEGA = next(c for c in BY_KEY.values() if c.stage == 2 and c.evolves_from in BY_NAME)      # stage 2 for devolve
R0 = next(c for c in BY_KEY.values() if c.retreat == 0 and c.stage == 0)                  # no retreat cost
R2 = next(c for c in BY_KEY.values() if c.retreat == 2)                                    # retreat 2
PSY = next(c for c in BY_KEY.values() if c.ptype == 'Psychic')                             # {P} Pokémon
TAUROS = BY_NAME['Paldean Tauros'][0]


def _fn(text):
    return AE.ATTACK_EFFECTS[AE.normalize(text)]


def _call(text, ctx):
    return _fn(text)(ctx)


# ---------------------------------------------------------------- registration integrity
def t_all_batch_keys_registered():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'effects_work', 'batches.json')
    batch = [x for x in json.load(open(path))['batches'] if x['id'] == 'conditional_damage_1'][0]
    for e in batch['effects']:
        assert AE.normalize(e['key']) in AE.ATTACK_EFFECTS, f"missing: {e['key']!r}"


# ---------------------------------------------------------------- 1. Basic defender can't attack
def t_basic_cant_attack():
    T = "If the Defending Pokémon is a Basic Pokémon, it can't attack during your opponent's next turn."
    # Basic defender (VANILLA Bulbasaur is stage 0): 90 damage + defender attack-lock next turn.
    ctx, at, df, me, opp = mk(base=90, text=T)
    assert _call(T, ctx) == 90
    assert df.cd_name == 'ALL' and df.cd_turn == ctx.game.turn - 1, (df.cd_name, df.cd_turn)
    # Evolved defender: 90 damage, no lock.
    ctx, at, df, me, opp = mk(base=90, text=T)
    df.card = IVY
    assert _call(T, ctx) == 90
    assert df.cd_name is None, df.cd_name


# ---------------------------------------------------------------- 2. per damaged "Tauros"
def t_tauros_damaged_x40():
    T = 'This attack does 40 damage for each of your Pokémon that has "Tauros" in its name that has any damage counters on it.'
    ctx, at, df, me, opp = mk(base=40, text=T)
    me.active.card = TAUROS; me.active.damage = 30      # counts
    me.bench[0].card = TAUROS; me.bench[0].damage = 0   # Tauros but undamaged: doesn't count
    assert _call(T, ctx) == 40
    me.bench[0].damage = 10                             # now both Tauros are damaged
    assert _call(T, ctx) == 80
    # A non-Tauros damaged mon must not count.
    ctx, at, df, me, opp = mk(base=40, text=T)
    me.active.damage = 50                               # VANILLA (Bulbasaur), damaged but not Tauros
    assert _call(T, ctx) == 0


# ---------------------------------------------------------------- 3. +50 vs Evolution
def t_evo_plus_50():
    T = "If your opponent's Active Pokémon is an Evolution Pokémon, this attack does 50 more damage."
    assert run(T, base=50, flips=(0.0,))[0] == 50                  # basic defender -> no bonus
    ctx, at, df, me, opp = mk(base=50, text=T); df.card = IVY
    assert _call(T, ctx) == 100                                    # evolution -> +50


# ---------------------------------------------------------------- 4. +30 per retreat {C}
def t_per_retreat_plus_30():
    T = "This attack does 30 more damage for each {C} in your opponent's Active Pokémon's Retreat Cost."
    ctx, at, df, me, opp = mk(base=10, text=T); df.card = R2      # retreat 2
    assert _call(T, ctx) == 10 + 60
    ctx, at, df, me, opp = mk(base=10, text=T); df.card = R0      # retreat 0
    assert _call(T, ctx) == 10
    # CURRENT retreat cost: Magnetic Metal Energy zeroes a printed-retreat-2 defender -> no bonus.
    ctx, at, df, me, opp = mk(base=10, text=T); df.card = R2; df.special = ['Magnetic Metal Energy']
    assert df.card.retreat == 2 and df.eff_retreat() == 0
    assert _call(T, ctx) == 10


# ---------------------------------------------------------------- 5. 60x per {R} on all opp mons
def t_per_opp_fire_x60():
    T = "This attack does 60 damage for each {R} Energy attached to all of your opponent's Pokémon."
    ctx, at, df, me, opp = mk(base=60, text=T)
    opp.active.energy = Counter({'Fire': 1, 'Wild': 4})          # Wild must NOT count
    opp.bench[0].energy = Counter({'Fire': 2})
    assert _call(T, ctx) == 60 * 3
    # No Fire in play -> 0 damage (the 'Colorless' default on the active is not {R}).
    ctx, at, df, me, opp = mk(base=60, text=T)
    opp.active.energy = Counter({'Water': 2})
    assert _call(T, ctx) == 0


# ---------------------------------------------------------------- 6. +10 per defender counter
def t_per_def_counter_plus_10():
    T = "This attack does 10 more damage for each damage counter on your opponent's Active Pokémon."
    ctx, at, df, me, opp = mk(base=20, text=T); df.damage = 30
    assert _call(T, ctx) == 20 + 30
    ctx, at, df, me, opp = mk(base=20, text=T); df.damage = 0
    assert _call(T, ctx) == 20


# ---------------------------------------------------------------- 7. 40x per Stage 1
def t_per_stage1_x40():
    T = "This attack does 40 damage for each of your Stage 1 Pokémon in play."
    ctx, at, df, me, opp = mk(base=40, text=T)
    me.active.card = IVY; me.bench[0].card = IVY                 # 2 Stage 1
    assert _call(T, ctx) == 80
    ctx, at, df, me, opp = mk(base=40, text=T)                   # all Basic
    assert _call(T, ctx) == 0


# ---------------------------------------------------------------- 8. +90 if defender damaged
def t_def_damaged_plus_90():
    T = "If your opponent's Active Pokémon already has any damage counters on it, this attack does 90 more damage."
    ctx, at, df, me, opp = mk(base=90, text=T); df.damage = 10
    assert _call(T, ctx) == 180
    ctx, at, df, me, opp = mk(base=90, text=T); df.damage = 0
    assert _call(T, ctx) == 90


# ---------------------------------------------------------------- 9. Stadium +120 then discard
def t_stadium_plus_120_discard():
    T = "If a Stadium is in play, this attack does 120 more damage. Then, discard that Stadium."
    ctx, at, df, me, opp = mk(base=120, text=T)                  # no Stadium in play -> base
    assert _call(T, ctx) == 120
    ctx, at, df, me, opp = mk(base=120, text=T, stadium='Prism Tower')
    assert _call(T, ctx) == 240                                 # Stadium in play -> +120
    assert ctx.game.stadium is None                             # and it is discarded


# ---------------------------------------------------------------- 10. Rollout usage gate
def t_rollout_gate():
    T = "You can use this attack only if this Pokémon used Rollout during your last turn."
    ctx, at, df, me, opp = mk(base=100, text=T)                  # no prior Rollout -> attack does nothing
    assert _call(T, ctx) == 0
    at.last_atk = 'Rollout'; at.last_atk_turn = ctx.game.turn - 2
    assert _call(T, ctx) == 100                                  # used Rollout on my previous turn -> usable
    at.last_atk_turn = ctx.game.turn - 1                        # not my previous turn -> gate closed
    assert _call(T, ctx) == 0


# ---------------------------------------------------------------- 11. 70x per defender counter
def t_per_def_counter_x70():
    T = "This attack does 70 damage for each damage counter on your opponent's Active Pokémon."
    ctx, at, df, me, opp = mk(base=70, text=T); df.damage = 30
    assert _call(T, ctx) == 210
    ctx, at, df, me, opp = mk(base=70, text=T); df.damage = 0
    assert _call(T, ctx) == 0


# ---------------------------------------------------------------- 12. 80x per energy in opp hand
def t_per_hand_energy_x80():
    T = "Your opponent reveals their hand, and this attack does 80 damage for each Energy card you find there."
    ctx, at, df, me, opp = mk(base=80, text=T)
    opp.hand = [('E', 'Fire'), ('S', {'special_energy': 'Prism'}), ('P', TAUROS), ('T', {'name': 'X'})]
    assert _call(T, ctx) == 160                                 # 1 basic + 1 special = 2 energy cards
    opp.hand = [('P', TAUROS)]
    assert _call(T, ctx) == 0


# ---------------------------------------------------------------- 13. Stadium +70
def t_stadium_plus_70():
    T = "If a Stadium is in play, this attack does 70 more damage."
    assert run(T, base=70)[0] == 70                             # no Stadium in play
    assert run(T, base=70, stadium='Prism Tower')[0] == 140     # Stadium in play -> +70


# ---------------------------------------------------------------- 14. 50x per your damaged mon
def t_per_own_damaged_x50():
    T = "This attack does 50 damage for each of your Pokémon that has any damage counters on it."
    ctx, at, df, me, opp = mk(base=50, text=T)
    me.active.damage = 10                                       # 1 damaged (bench undamaged)
    assert _call(T, ctx) == 50
    me.bench[0].damage = 20
    assert _call(T, ctx) == 100
    ctx, at, df, me, opp = mk(base=50, text=T)                  # none damaged
    assert _call(T, ctx) == 0


# ---------------------------------------------------------------- 15. same energy +120
def t_same_energy_plus_120():
    T = "If this Pokémon and your opponent's Active Pokémon have the same amount of Energy attached, this attack does 120 more damage."
    assert run(T, base=50, atk_energy={'Fighting': 2}, def_energy={'Water': 2})[0] == 170
    assert run(T, base=50, atk_energy={'Fighting': 2}, def_energy={'Water': 3})[0] == 50


# ---------------------------------------------------------------- 16. more energy +160
def t_more_energy_plus_160():
    T = "If this Pokémon has more Energy attached than your opponent's Active Pokémon, this attack does 160 more damage."
    assert run(T, base=10, atk_energy={'Darkness': 3}, def_energy={'Water': 2})[0] == 170
    assert run(T, base=10, atk_energy={'Darkness': 2}, def_energy={'Water': 2})[0] == 10   # equal: no bonus
    assert run(T, base=10, atk_energy={'Darkness': 1}, def_energy={'Water': 2})[0] == 10   # fewer: no bonus


# ---------------------------------------------------------------- 17. defender vulnerable next turn
def t_defender_vuln_50():
    T = "During your next turn, the Defending Pokémon takes 50 more damage from attacks (after applying Weakness and Resistance)."
    ctx, at, df, me, opp = mk(base=0, text=T)
    assert _call(T, ctx) == 0
    assert df.dr_amount == -50 and df.dr_turn == ctx.game.turn + 1, (df.dr_amount, df.dr_turn)
    # End-to-end: during the attacker's next turn (dr_turn+1), the defender takes +50.
    ctx.game.turn = df.dr_turn + 1
    assert effects.incoming_damage(100, at, df, opp, ctx.game) == 150
    # Off that turn, no vulnerability.
    ctx.game.turn = df.dr_turn + 2
    assert effects.incoming_damage(100, at, df, opp, ctx.game) == 100


# ---------------------------------------------------------------- 18. cost discount (damage always 130)
def t_damaged_cost_discount():
    T = "If this Pokémon has any damage counters on it, this attack can be used for {D}."
    assert run(T, base=130)[0] == 130                           # undamaged
    ctx, at, df, me, opp = mk(base=130, text=T); at.damage = 40
    assert _call(T, ctx) == 130                                 # damaged: same damage (only cost changes)


# ---------------------------------------------------------------- 19. devolve
def t_devolve_if_evolved():
    T = "If your opponent's Active Pokémon is an evolved Pokémon, devolve it by putting the highest Stage Evolution card on it into your opponent's hand."
    ctx, at, df, me, opp = mk(base=50, text=T)
    df.card = MEGA; df.energy = Counter({'Grass': 2}); df.damage = 30
    assert _call(T, ctx) == 50
    assert df.card.name == MEGA.evolves_from and df.card.stage == 1, (df.card.name, df.card.stage)
    assert opp.hand[-1] == ('P', MEGA)                          # top evolution card to hand
    assert df.energy == Counter({'Grass': 2}) and df.damage == 30   # damage/energy stay
    # Basic defender: no devolution, hand untouched.
    ctx, at, df, me, opp = mk(base=50, text=T)
    before = df.card
    assert _call(T, ctx) == 50
    assert df.card is before and opp.hand == []


# ---------------------------------------------------------------- 20. >=3 {D} in play +50
def t_three_dark_plus_50():
    T = "If you have at least 3 {D} Energy in play, this attack does 50 more damage."
    ctx, at, df, me, opp = mk(base=20, text=T)
    me.active.energy = Counter({'Darkness': 2, 'Wild': 5}); me.bench[0].energy = Counter({'Darkness': 1})
    assert _call(T, ctx) == 70                                  # 3 basic {D} (Wild excluded)
    ctx, at, df, me, opp = mk(base=20, text=T)
    me.active.energy = Counter({'Darkness': 2}); me.bench[0].energy = Counter({'Wild': 5})
    assert _call(T, ctx) == 20                                  # only 2 {D}


# ---------------------------------------------------------------- 21. Meteor Mash self-ramp
def t_meteor_mash_ramp():
    T = "During your next turn, this Pokémon's Meteor Mash attack does 60 more damage (before applying Weakness and Resistance)."
    ctx, at, df, me, opp = mk(base=60, text=T)
    assert _call(T, ctx) == 60
    assert at.ramp[ctx.attack['name']] == 60
    assert at.ramp_turn[ctx.attack['name']] == ctx.game.turn    # stamped so the engine expires it after 1 turn
    assert _call(T, ctx) == 60                                  # one-shot: a repeat use does NOT accumulate
    assert at.ramp[ctx.attack['name']] == 60                    # flat +60 (was 120 under the += bug)


# ---------------------------------------------------------------- 22. +20 per defender energy
def t_per_def_energy_plus_20():
    T = "This attack does 20 more damage for each Energy attached to your opponent's Active Pokémon."
    assert run(T, base=80, def_energy={'Psychic': 2, 'Colorless': 1})[0] == 140   # 3 energy -> +60
    ctx, at, df, me, opp = mk(base=80, text=T); df.energy = Counter()              # no energy -> no bonus
    assert _call(T, ctx) == 80


# ---------------------------------------------------------------- 23. +30 vs {P}
def t_psychic_def_plus_30():
    T = "If your opponent's Active Pokémon is a {P} Pokémon, this attack does 30 more damage."
    ctx, at, df, me, opp = mk(base=10, text=T); df.card = PSY
    assert _call(T, ctx) == 40
    assert run(T, base=10)[0] == 10                             # VANILLA is Grass -> no bonus


# ---------------------------------------------------------------- 24. +90 vs Evolution
def t_evo_plus_90():
    T = "If your opponent's Active Pokémon is an Evolution Pokémon, this attack does 90 more damage."
    assert run(T, base=90)[0] == 90                             # basic defender
    ctx, at, df, me, opp = mk(base=90, text=T); df.card = IVY
    assert _call(T, ctx) == 180


# ---------------------------------------------------------------- 25. +80 if no retreat cost
def t_no_retreat_plus_80():
    T = "If your opponent's Active Pokémon has no Retreat Cost, this attack does 80 more damage."
    ctx, at, df, me, opp = mk(base=80, text=T); df.card = R0    # retreat 0
    assert _call(T, ctx) == 160
    ctx, at, df, me, opp = mk(base=80, text=T); df.card = R2    # retreat 2
    assert _call(T, ctx) == 80
    # CURRENT retreat cost: a printed-retreat-2 defender carrying Magnetic Metal has retreat 0 -> +80.
    ctx, at, df, me, opp = mk(base=80, text=T); df.card = R2; df.special = ['Magnetic Metal Energy']
    assert df.card.retreat == 2 and df.eff_retreat() == 0
    assert _call(T, ctx) == 160


# ---------------------------------------------------------------- 26. 2+ {G} attached +120
def t_two_grass_plus_120():
    T = "If this Pokémon has 2 or more {G} Energy attached, this attack does 120 more damage."
    assert run(T, base=120, atk_energy={'Grass': 2})[0] == 240
    assert run(T, base=120, atk_energy={'Grass': 1, 'Wild': 5})[0] == 120   # Wild is not {G}


# ---------------------------------------------------------------- 27. +10 per counter on all opp
def t_per_all_opp_counters_plus_10():
    T = "This attack does 10 more damage for each damage counter on all of your opponent's Pokémon."
    ctx, at, df, me, opp = mk(base=10, text=T)
    opp.active.damage = 20; opp.bench[0].damage = 10           # 2 + 1 = 3 counters
    assert _call(T, ctx) == 40
    ctx, at, df, me, opp = mk(base=10, text=T)
    assert _call(T, ctx) == 10                                 # none damaged


# ---------------------------------------------------------------- 28. +230 vs Tera
def t_tera_plus_230():
    T = "If your opponent's Active Pokémon is a Tera Pokémon, this attack does 230 more damage."
    assert run(T, base=100)[0] == 100                          # Tera not detectable -> no bonus
    orig = B._is_tera
    try:
        B._is_tera = lambda card: True                        # simulate a Tera defender
        ctx, at, df, me, opp = mk(base=100, text=T)
        assert _call(T, ctx) == 330
    finally:
        B._is_tera = orig


TESTS = [
    t_all_batch_keys_registered,
    t_basic_cant_attack, t_tauros_damaged_x40, t_evo_plus_50, t_per_retreat_plus_30,
    t_per_opp_fire_x60, t_per_def_counter_plus_10, t_per_stage1_x40, t_def_damaged_plus_90,
    t_stadium_plus_120_discard, t_rollout_gate, t_per_def_counter_x70, t_per_hand_energy_x80,
    t_stadium_plus_70, t_per_own_damaged_x50, t_same_energy_plus_120, t_more_energy_plus_160,
    t_defender_vuln_50, t_damaged_cost_discount, t_devolve_if_evolved, t_three_dark_plus_50,
    t_meteor_mash_ramp, t_per_def_energy_plus_20, t_psychic_def_plus_30, t_evo_plus_90,
    t_no_retreat_plus_80, t_two_grass_plus_120, t_per_all_opp_counters_plus_10, t_tera_plus_230,
]

if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
