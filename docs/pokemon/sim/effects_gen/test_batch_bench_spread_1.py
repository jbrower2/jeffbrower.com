#!/usr/bin/env python3
"""Unit tests for effects_gen/batch_bench_spread_1 (bench snipe/spread, self-bench splash, energy &
damage-counter relocation, shuffle/pick-up, and Benched-Pokémon conditional/counting bonuses)."""
import json
import os, sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # ensure sim/ importable
from effects_testkit import mk, run, runner
from engine import Mon
import attack_effects as AE
import effects_gen.batch_bench_spread_1  # registers the batch's effects

HERE = os.path.dirname(os.path.abspath(__file__))
_BATCH = next(b for b in json.load(open(os.path.join(HERE, '..', 'effects_work', 'batches.json')))['batches']
              if b['id'] == 'bench_spread_1')
KEYS = [e['key'] for e in _BATCH['effects']]
RAW = {e['examples'][0]['card']: e['examples'][0]['raw'] for e in _BATCH['effects']}


def _fn(raw):
    return AE.ATTACK_EFFECTS[AE.normalize(raw)]


class _Stub:
    """Minimal stand-in Card for building precisely-named/typed test Mons."""
    def __init__(self, name='X', hp=100, ptype='Colorless', is_ex=False, stage=0, weakness=None):
        self.name = name; self.hp = hp; self.ptype = ptype
        self.is_ex = is_ex; self.stage = stage; self.weakness = weakness; self.retreat = 0


def _mon(name='X', hp=100, dmg=0, ptype='Colorless', is_ex=False, weak=None, energy=None):
    m = Mon(_Stub(name, hp, ptype, is_ex, weakness=weak))
    m.damage = dmg
    if energy:
        m.energy = Counter(energy)
    return m


TESTS = []
def test(fn): TESTS.append(fn); return fn


# ---- registration guard: every batch key resolves to a registered effect ----
@test
def t_all_keys_registered():
    missing = [k for k in KEYS if AE.normalize(k) not in AE.ATTACK_EFFECTS]
    assert not missing, f"unregistered keys: {missing}"
    assert len(KEYS) == 28, len(KEYS)


# 1. Manectric — also 40 to 1 of YOUR OWN Benched
@test
def t_manectric_self_bench():
    d, ctx, at, df, me, opp = run(RAW['Manectric'], base=120, my_bench=2)
    assert d == 120, d
    assert sum(m.damage for m in me.bench) == 40, [m.damage for m in me.bench]
    # empty bench: no crash, still 120
    d2 = run(RAW['Manectric'], base=120, my_bench=0)[0]
    assert d2 == 120, d2


# 2. Volbeat — +60 if Illumise benched
@test
def t_volbeat_illumise():
    ctx, at, df, me, opp = mk(base=20)
    me.bench = [_mon('Illumise')]
    assert _fn(RAW['Volbeat'])(ctx) == 80
    me.bench = [_mon('Ledyba')]
    assert _fn(RAW['Volbeat'])(ctx) == 20


# 3. Illumise — go-second-turn-1 shuffle an opp benched into their deck
@test
def t_illumise_turn1_shuffle():
    ctx, at, df, me, opp = mk(base=0)
    ctx.game.turn = 1
    a = _mon('Devo', energy={'Water': 2}); b = _mon('Basic')
    opp.bench = [a, b]
    assert _fn(RAW['Illumise'])(ctx) == 0
    assert opp.bench == [b], "the higher-energy bench mon should be shuffled away"
    assert ('P', a.card) in opp.deck
    assert opp.deck.count(('E', 'Water')) == 2
    # not turn 1 -> nothing happens
    ctx2, *_ , me2, opp2 = mk(base=0)
    ctx2.game.turn = 3
    opp2.bench = [_mon('Stay')]
    assert _fn(RAW['Illumise'])(ctx2) == 0
    assert len(opp2.bench) == 1
    # turn 1 but the opponent's Bench is empty -> nothing to shuffle, no crash
    ctx3, *_ , me3, opp3 = mk(base=0)
    ctx3.game.turn = 1
    opp3.bench = []
    assert _fn(RAW['Illumise'])(ctx3) == 0


# 4. Cynthia's Milotic — also 30 to 2 opp benched
@test
def t_milotic_bench_30x2():
    d, ctx, at, df, me, opp = run(RAW["Cynthia's Milotic"], base=60, opp_bench=2)
    assert d == 60
    assert all(m.damage == 30 for m in opp.bench), [m.damage for m in opp.bench]
    # only 1 benched -> just that one hit
    d2, ctx2, *_, opp2 = run(RAW["Cynthia's Milotic"], base=60, opp_bench=1)
    assert d2 == 60 and opp2.bench[0].damage == 30


# 5. Castform Sunny Form — move all energy to a benched mon
@test
def t_castform_move_all():
    ctx, at, df, me, opp = mk(base=50, atk_energy={'Fire': 2, 'Colorless': 1}, my_bench=1)
    at.special = ['Mist Energy']
    d = _fn(RAW['Castform Sunny Form'])(ctx)
    assert d == 50
    assert at.total_energy() == 0, at.energy
    assert me.bench[0].total_energy() == 3, me.bench[0].energy
    assert 'Mist Energy' in me.bench[0].special and at.special == []


# 6. Kecleon — 30 to any 1 opp Pokémon (bench-KO vs active chip)
@test
def t_kecleon_snipe_any_30():
    # bench KO available -> snipe bench, return 0
    ctx, at, df, me, opp = mk(base=0)
    opp.active = _mon('Boss', hp=200)
    opp.bench = [_mon('Weak', hp=30)]
    assert _fn(RAW['Kecleon'])(ctx) == 0
    assert opp.bench[0].damage == 30
    # no bench, healthy active -> chip the active (returned)
    ctx2, at2, df2, me2, opp2 = mk(base=0)
    opp2.active = _mon('Boss', hp=200); opp2.bench = []
    assert _fn(RAW['Kecleon'])(ctx2) == 30
    # Weakness-aware KO: the Active is lethal only AFTER Weakness doubling, and the Bench is
    # unkillable (60 HP > 30). The snipe must KO the Active (return pre-Weakness 30), not chip the Bench.
    ctx3, at3, df3, me3, opp3 = mk(base=0)
    opp3.active = _mon('Weakling', hp=50, weak=at3.card.ptype)
    opp3.bench = [_mon('Tank', hp=60)]
    assert _fn(RAW['Kecleon'])(ctx3) == 30           # engine doubles this to a lethal 60
    assert opp3.bench[0].damage == 0                  # Bench left untouched


# 7. Chimecho — shuffle 1 of YOUR benched into YOUR deck
@test
def t_chimecho_shuffle_own():
    ctx, at, df, me, opp = mk(base=0)
    hurt = _mon('Hurt', dmg=50, energy={'Grass': 1}); fine = _mon('Fine', dmg=0)
    me.bench = [hurt, fine]
    assert _fn(RAW['Chimecho'])(ctx) == 0
    assert me.bench == [fine]
    assert ('P', hurt.card) in me.deck and me.deck.count(('E', 'Grass')) == 1


# 8. Deoxys — 120 bench snipe only with >=2 extra energy over cost
@test
def t_deoxys_extra_energy():
    ctx, at, df, me, opp = mk(base=120, atk_energy={'Psychic': 5}, opp_bench=1)
    ctx.attack['cost'] = 'PPP'
    assert _fn(RAW['Deoxys'])(ctx) == 120
    assert opp.bench[0].damage == 120
    # only 1 extra (4 total, cost 3) -> no snipe
    ctx2, at2, df2, me2, opp2 = mk(base=120, atk_energy={'Psychic': 4}, opp_bench=1)
    ctx2.attack['cost'] = 'PPP'
    assert _fn(RAW['Deoxys'])(ctx2) == 120
    assert opp2.bench[0].damage == 0


# 9. Prinplup — 70 to 1 opp benched, no active damage
@test
def t_prinplup_bench_70():
    d, ctx, at, df, me, opp = run(RAW['Prinplup'], base=0, opp_bench=1)
    assert d == 0 and opp.bench[0].damage == 70


# 10. Drifblim — 50x per Drifloon/Drifblim in play + 30 to each of them
@test
def t_drifblim_swarm():
    ctx, at, df, me, opp = mk(base=50)
    at.card = _Stub('Drifblim', hp=130)
    me.bench = [_mon('Drifloon', hp=90), _mon('Zubat', hp=60)]
    d = _fn(RAW['Drifblim'])(ctx)
    assert d == 100, d                       # attacker Drifblim + benched Drifloon = 2 -> 100
    assert at.damage == 30                    # attacker takes 30 too
    assert me.bench[0].damage == 30 and me.bench[1].damage == 0


# 11. Lopunny — 50 to 1 opp benched
@test
def t_lopunny_bench_50():
    d, ctx, at, df, me, opp = run(RAW['Lopunny'], base=0, opp_bench=1)
    assert d == 0 and opp.bench[0].damage == 50


# 12. Hippowdon — also 40 to each ALREADY-damaged benched (both sides)
@test
def t_hippowdon_damaged_bench():
    ctx, at, df, me, opp = mk(base=150, my_bench=2, opp_bench=2)
    me.bench[0].damage = 20; opp.bench[0].damage = 10
    d = _fn(RAW['Hippowdon'])(ctx)
    assert d == 150
    assert me.bench[0].damage == 60 and me.bench[1].damage == 0
    assert opp.bench[0].damage == 50 and opp.bench[1].damage == 0


# 13. Uxie — 2 counters (20) on each opp Pokémon
@test
def t_uxie_counters_each():
    d, ctx, at, df, me, opp = run(RAW['Uxie'], base=0, opp_bench=2)
    assert d == 0
    assert opp.active.damage == 20
    assert all(m.damage == 20 for m in opp.bench)


# 14. Mesprit — 160 only with Uxie AND Azelf benched
@test
def t_mesprit_needs_uxie_azelf():
    ctx, at, df, me, opp = mk(base=160)
    me.bench = [_mon('Uxie'), _mon('Azelf')]
    assert _fn(RAW['Mesprit'])(ctx) == 160
    me.bench = [_mon('Uxie')]
    assert _fn(RAW['Mesprit'])(ctx) == 0
    me.bench = [_mon('Uxie'), _mon('Pikachu')]
    assert _fn(RAW['Mesprit'])(ctx) == 0


# 15. Shaymin — 60 to 1 opp benched ex/V only
@test
def t_shaymin_bench_exv():
    ctx, at, df, me, opp = mk(base=0)
    opp.bench = [_mon('BigEx', hp=200, is_ex=True), _mon('Plain', hp=60)]
    assert _fn(RAW['Shaymin'])(ctx) == 0
    assert opp.bench[0].damage == 60 and opp.bench[1].damage == 0
    # no ex/V bench -> nothing
    ctx2, *_ , me2, opp2 = mk(base=0)
    opp2.bench = [_mon('Plain', hp=60)]
    assert _fn(RAW['Shaymin'])(ctx2) == 0
    assert opp2.bench[0].damage == 0


# 16. Gigalith — 20x total counters on your benched Fighting Pokémon
@test
def t_gigalith_bench_fighting_counters():
    ctx, at, df, me, opp = mk(base=20)
    me.bench = [_mon('F1', ptype='Fighting', dmg=30),
                _mon('F2', ptype='Fighting', dmg=10),
                _mon('Psy', ptype='Psychic', dmg=50)]
    assert _fn(RAW['Gigalith'])(ctx) == 80        # (3 + 1) counters * 20, Psychic excluded
    for m in me.bench:
        m.damage = 0
    assert _fn(RAW['Gigalith'])(ctx) == 0


# 17. Swoobat — pick up 1 of your benched into your hand
@test
def t_swoobat_pickup_hand():
    ctx, at, df, me, opp = mk(base=0)
    hurt = _mon('Hurt', dmg=50, energy={'Water': 1}); fine = _mon('Fine')
    me.bench = [hurt, fine]
    assert _fn(RAW['Swoobat'])(ctx) == 0
    assert me.bench == [fine]
    assert ('P', hurt.card) in me.hand and ('E', 'Water') in me.hand


# 18. Cinccino — +20 per your benched Pokémon
@test
def t_cinccino_per_bench():
    assert run(RAW['Cinccino'], base=20, my_bench=3)[0] == 80
    assert run(RAW['Cinccino'], base=20, my_bench=0)[0] == 20


# 19. Reuniclus — dig top 8, bench any Pokémon found
@test
def t_reuniclus_dig8():
    # top of deck = END (draw() pops from the end); ONLY the top 8 are searched.
    ctx, at, df, me, opp = mk(base=0, my_bench=1)
    deep, s1, s2, s3 = _Stub('Deep'), _Stub('B1'), _Stub('B2'), _Stub('B3')
    # deck bottom -> top. 'deep' is a Pokémon BELOW the top-8 window; it must stay in the deck.
    me.deck = ([('P', deep)] + [('E', 'Colorless')] * 4              # 5 below-window cards
               + [('E', 'Colorless')] * 5 + [('P', s1), ('P', s2), ('P', s3)])  # top 8 = 5 E + 3 Pokémon
    assert _fn(RAW['Reuniclus'])(ctx) == 0
    assert len(me.bench) == 4                        # 1 starting + 3 from the top 8
    assert ('P', deep) in me.deck                    # below-window Pokémon NOT benched (catches deck[:8] bug)
    assert all(('P', s) not in me.deck for s in (s1, s2, s3))  # the top-8 Pokémon left the deck
    assert sum(1 for t in me.deck if t[0] == 'P') == 1        # only 'deep' remains
    assert len(me.deck) == 10                        # 13 - 3 benched
    # 5-Bench cap: with 4 already benched, only 1 of the 3 found Pokémon fits.
    ctx2, at2, df2, me2, opp2 = mk(base=0, my_bench=4)
    p1, p2, p3 = _Stub('C1'), _Stub('C2'), _Stub('C3')
    me2.deck = [('E', 'Colorless')] * 5 + [('P', p1), ('P', p2), ('P', p3)]
    assert _fn(RAW['Reuniclus'])(ctx2) == 0
    assert len(me2.bench) == 5                        # capped at 5
    assert sum(1 for t in me2.deck if t[0] == 'P') == 2      # 2 that couldn't fit stayed in the deck


# 20. N's Vanilluxe — double opp counters
@test
def t_vanilluxe_double_counters():
    ctx, at, df, me, opp = mk(base=0, opp_bench=2)
    opp.active.damage = 30; opp.bench[0].damage = 20; opp.bench[1].damage = 0
    assert _fn(RAW["N's Vanilluxe"])(ctx) == 0
    assert opp.active.damage == 60
    assert opp.bench[0].damage == 40 and opp.bench[1].damage == 0


# 21. Emolga — also 10 to each benched (both sides)
@test
def t_emolga_10_each_bench():
    d, ctx, at, df, me, opp = run(RAW['Emolga'], base=10, my_bench=2, opp_bench=2)
    assert d == 10
    assert all(m.damage == 10 for m in me.bench + opp.bench)


# 22. Ferrothorn — 20x energy attached, to any 1 opp Pokémon
@test
def t_ferrothorn_per_energy():
    # 3 energy -> 60, bench KO available -> snipe bench
    ctx, at, df, me, opp = mk(base=0, atk_energy={'Metal': 3})
    opp.active = _mon('Boss', hp=200); opp.bench = [_mon('Weak', hp=40)]
    assert _fn(RAW['Ferrothorn'])(ctx) == 0
    assert opp.bench[0].damage == 60
    # 3 energy, no bench -> chip active for 60
    ctx2, at2, df2, me2, opp2 = mk(base=0, atk_energy={'Metal': 3})
    opp2.active = _mon('Boss', hp=200); opp2.bench = []
    assert _fn(RAW['Ferrothorn'])(ctx2) == 60
    # 0 energy -> 0 damage
    ctx3, at3, df3, me3, opp3 = mk(base=0)
    at3.energy = Counter()                          # truly energy-less attacker
    opp3.active = _mon('Boss', hp=200); opp3.bench = []
    assert _fn(RAW['Ferrothorn'])(ctx3) == 0


# 23. Durant — +20 if Durant benched
@test
def t_durant_bench():
    ctx, at, df, me, opp = mk(base=20)
    me.bench = [_mon('Durant')]
    assert _fn(RAW['Durant'])(ctx) == 40
    me.bench = [_mon('Heatmor')]
    assert _fn(RAW['Durant'])(ctx) == 20


# 24. Pangoro — +120 if a benched Pancham is damaged
@test
def t_pangoro_pancham():
    ctx, at, df, me, opp = mk(base=80)
    me.bench = [_mon('Pancham', dmg=10)]
    assert _fn(RAW['Pangoro'])(ctx) == 200
    me.bench = [_mon('Pancham', dmg=0)]
    assert _fn(RAW['Pangoro'])(ctx) == 80
    me.bench = [_mon('Zorua', dmg=50)]
    assert _fn(RAW['Pangoro'])(ctx) == 80


# 25. Meowstic — move an energy off opp active to their bench
@test
def t_meowstic_move_opp_energy():
    ctx, at, df, me, opp = mk(base=80)
    opp.active = _mon('Act', energy={'Psychic': 2})
    b1 = _mon('B1'); b2 = _mon('B2', energy={'Water': 1})
    opp.bench = [b1, b2]
    assert _fn(RAW['Meowstic'])(ctx) == 80
    assert opp.active.total_energy() == 1
    assert b1.energy.get('Psychic', 0) == 1        # parked on least-developed bench mon
    # no bench -> nothing to move
    ctx2, at2, df2, me2, opp2 = mk(base=80)
    opp2.active = _mon('Act', energy={'Psychic': 2}); opp2.bench = []
    assert _fn(RAW['Meowstic'])(ctx2) == 80
    assert opp2.active.total_energy() == 2


# 26. Hawlucha — +60 if any benched of yours is damaged
@test
def t_hawlucha_bench_damaged():
    ctx, at, df, me, opp = mk(base=30, my_bench=1)
    me.bench[0].damage = 20
    assert _fn(RAW['Hawlucha'])(ctx) == 90
    me.bench[0].damage = 0
    assert _fn(RAW['Hawlucha'])(ctx) == 30


# 27. Yveltal — 2 counters on each ALREADY-damaged opp Pokémon
@test
def t_yveltal_counters_damaged():
    ctx, at, df, me, opp = mk(base=0, opp_bench=2)
    opp.active.damage = 10; opp.bench[0].damage = 20; opp.bench[1].damage = 0
    assert _fn(RAW['Yveltal'])(ctx) == 0
    assert opp.active.damage == 30
    assert opp.bench[0].damage == 40 and opp.bench[1].damage == 0


# 28. Vikavolt — +80 per benched Charjabug
@test
def t_vikavolt_charjabug():
    ctx, at, df, me, opp = mk(base=120)
    me.bench = [_mon('Charjabug'), _mon('Charjabug')]
    assert _fn(RAW['Vikavolt'])(ctx) == 280
    me.bench = [_mon('Grubbin')]
    assert _fn(RAW['Vikavolt'])(ctx) == 120


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
