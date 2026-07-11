#!/usr/bin/env python3
"""Unit tests for effects_gen/batch_discard_energy_1 (self-energy dump -> fixed snipe, from-hand fuel
gate, Special-Energy removal, and discard-pile Energy recursion/acceleration)."""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # put sim/ on path

from effects_testkit import mk, run, runner
import attack_effects as AE
import effects_gen.batch_discard_energy_1  # registers the batch's effects


def _fn(text):
    return AE.ATTACK_EFFECTS[AE.normalize(text)]


# exact effect keys (damage token already stripped)
K_SPIT = "Discard all Energy from this Pokémon. This attack does 120 damage to 1 of your opponent's Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)"
K_DROP = "Discard all Energy from this Pokémon, and this attack does 120 damage to 1 of your opponent's Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)"
K_CRIMSON = "Discard all {R} Energy from this Pokémon, and this attack does 180 damage to 1 of your opponent's Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)"
K_INFERNAL = "Discard 4 Basic {R} Energy cards from your hand. If you can't discard 4 cards in this way, this attack does nothing."
K_CURSED = "Discard all Special Energy from all of your opponent's Pokémon."
K_PICK = "Attach up to 2 Basic Energy cards from your discard pile to your Pokémon in any way you like."
K_MISCHIEF = "Attach up to 3 Energy cards from your opponent's discard pile to their Pokémon in any way you like."
K_METAL = "Attach a Basic {M} Energy card from your discard pile to this Pokémon."
K_TEA = "Put a Basic {G} Energy card from your discard pile into your hand."

TESTS = []
def test(fn): TESTS.append(fn); return fn


# ---------------------------------------------------------------- self-discard -> fixed 120 snipe
@test
def t_spit_shot_hits_active():
    # Full-HP Active (VANILLA 80 HP, attacker not its Weakness) -> 120 KOs it -> returned to engine.
    ctx, at, df, me, opp = mk(text=K_SPIT, atk_energy={'Fire': 3})
    at.special = ['Spiky Energy']
    d = _fn(K_SPIT)(ctx)
    assert d == 120, d
    assert at.total_energy() == 0, at.energy            # all Energy discarded
    assert at.special == [], at.special                 # Special Energy discarded too
    assert me.disc_energy['Fire'] == 3, me.disc_energy   # basic pips went to discard
    assert df.damage == 0, df.damage                     # Active hit is via the return, not .damage


@test
def t_spit_shot_snipes_bench():
    # No Active in play -> the 120 must land on a Benched Pokémon (no W&R), returning 0.
    ctx, at, df, me, opp = mk(text=K_SPIT, atk_energy={'Fire': 3}, opp_bench=1)
    opp.active = None
    d = _fn(K_SPIT)(ctx)
    assert d == 0, d
    assert opp.bench[0].damage == 120, opp.bench[0].damage
    assert at.total_energy() == 0, at.energy


@test
def t_drop_shot_hits_active():
    # Bombirdier's ", and" variant behaves identically: dump Energy, 120 to the Active.
    ctx, at, df, me, opp = mk(text=K_DROP, atk_energy={'Darkness': 2, 'Colorless': 1})
    d = _fn(K_DROP)(ctx)
    assert d == 120, d
    assert at.total_energy() == 0, at.energy
    assert me.disc_energy['Darkness'] == 2, me.disc_energy


# ---------------------------------------------------------------- discard-typed -> 180 bench snipe
@test
def t_crimson_blaster_bench_and_discard():
    # Discard all {R} (Fire) from the attacker, keep other Energy; 180 to a Benched Pokémon (no W&R).
    ctx, at, df, me, opp = mk(text=K_CRIMSON, atk_energy={'Fire': 2, 'Colorless': 1}, opp_bench=1)
    d = _fn(K_CRIMSON)(ctx)
    assert d == 0, d                                     # no Active hit
    assert opp.bench[0].damage == 180, opp.bench[0].damage
    assert at.energy.get('Fire', 0) == 0, at.energy      # all Fire discarded
    assert at.energy.get('Colorless', 0) == 1, at.energy  # non-Fire pips stay
    assert me.disc_energy['Fire'] == 2, me.disc_energy


@test
def t_crimson_blaster_no_bench_still_discards():
    # No opponent Bench -> nothing to snipe, but the {R} discard is unconditional.
    ctx, at, df, me, opp = mk(text=K_CRIMSON, atk_energy={'Fire': 3})
    opp.bench = []
    d = _fn(K_CRIMSON)(ctx)
    assert d == 0, d
    assert at.energy.get('Fire', 0) == 0, at.energy
    assert me.disc_energy['Fire'] == 3, me.disc_energy


@test
def t_crimson_blaster_hits_exactly_one_bench():
    # "1 of your opponent's Benched Pokémon" -> exactly ONE benched Pokémon is damaged, not all.
    ctx, at, df, me, opp = mk(text=K_CRIMSON, atk_energy={'Fire': 2}, opp_bench=2)
    d = _fn(K_CRIMSON)(ctx)
    assert d == 0, d
    hit = [b for b in opp.bench if b.damage == 180]
    clean = [b for b in opp.bench if b.damage == 0]
    assert len(hit) == 1, [b.damage for b in opp.bench]      # only one target
    assert len(clean) == 1, [b.damage for b in opp.bench]    # the other is untouched
    assert df.damage == 0, df.damage                         # the Active is never hit


# ---------------------------------------------------------------- from-hand fuel gate
@test
def t_infernal_slash_enough_fire():
    # >=4 basic {R} in hand -> discard exactly 4, deal the printed 220.
    ctx, at, df, me, opp = mk(base=220, text=K_INFERNAL)
    me.hand = [('E', 'Fire')] * 4 + [('P', None)]
    d = _fn(K_INFERNAL)(ctx)
    assert d == 220, d
    assert sum(1 for t in me.hand if t == ('E', 'Fire')) == 0, me.hand   # 4 discarded
    assert me.disc_energy['Fire'] == 4, me.disc_energy
    assert ('P', None) in me.hand                                         # non-Fire untouched


@test
def t_infernal_slash_not_enough_fire():
    # <4 basic {R} in hand -> attack does nothing and NO Energy is discarded.
    ctx, at, df, me, opp = mk(base=220, text=K_INFERNAL)
    me.hand = [('E', 'Fire')] * 3
    d = _fn(K_INFERNAL)(ctx)
    assert d == 0, d
    assert sum(1 for t in me.hand if t == ('E', 'Fire')) == 3, me.hand   # unchanged
    assert me.disc_energy.get('Fire', 0) == 0, me.disc_energy


# ---------------------------------------------------------------- special-energy removal
@test
def t_cursed_edge_strips_all_special():
    ctx, at, df, me, opp = mk(text=K_CURSED, opp_bench=1)
    # Active: Prism (Wild:1 on a Basic) + a basic Darkness pip that must survive.
    opp.active.special = ['Prism Energy']
    opp.active.energy = Counter({'Wild': 1, 'Darkness': 1})
    # Bench: Nitro Fire (typed Fire:1) that must be stripped.
    opp.bench[0].special = ['Nitro Fire Energy']
    opp.bench[0].energy = Counter({'Fire': 1})
    # MY OWN Active also carries Special Energy — "all of your opponent's Pokémon" must NOT touch it.
    at.special = ['Spiky Energy']
    at.energy = Counter({'Colorless': 1, 'Fire': 2})
    d = _fn(K_CURSED)(ctx)
    assert d == 0, d
    assert opp.active.special == [], opp.active.special
    assert opp.active.energy.get('Wild', 0) == 0, opp.active.energy       # Prism pip gone
    assert opp.active.energy.get('Darkness', 0) == 1, opp.active.energy   # basic kept
    assert opp.bench[0].special == [], opp.bench[0].special
    assert opp.bench[0].energy.get('Fire', 0) == 0, opp.bench[0].energy   # Nitro pip gone
    # opponent-only: my Special Energy + all my basic pips are untouched
    assert at.special == ['Spiky Energy'], at.special
    assert at.energy.get('Colorless', 0) == 1 and at.energy.get('Fire', 0) == 2, at.energy


@test
def t_cursed_edge_basic_only_mon_untouched():
    # A Pokémon holding ONLY basic Energy (no Special) is left completely alone.
    ctx, at, df, me, opp = mk(text=K_CURSED, opp_bench=0)
    opp.active.special = []
    opp.active.energy = Counter({'Water': 2, 'Colorless': 1})
    d = _fn(K_CURSED)(ctx)
    assert d == 0, d
    assert opp.active.energy == Counter({'Water': 2, 'Colorless': 1}), opp.active.energy


# ---------------------------------------------------------------- discard-pile energy recursion
@test
def t_pick_and_stick_attaches_two():
    ctx, at, df, me, opp = mk(base=0, text=K_PICK)
    me.disc_energy = Counter({'Lightning': 3})
    before = sum(m.total_energy() for m in me.all_mons())
    d = _fn(K_PICK)(ctx)
    assert d == 0, d
    assert sum(m.total_energy() for m in me.all_mons()) == before + 2     # 2 attached to your Pokémon
    assert sum(me.disc_energy.values()) == 1, me.disc_energy               # 2 pulled from discard


@test
def t_pick_and_stick_capped_by_discard():
    # "up to 2" -> only 1 available means only 1 moves.
    ctx, at, df, me, opp = mk(base=0, text=K_PICK)
    me.disc_energy = Counter({'Lightning': 1})
    before = sum(m.total_energy() for m in me.all_mons())
    _fn(K_PICK)(ctx)
    assert sum(m.total_energy() for m in me.all_mons()) == before + 1
    assert sum(me.disc_energy.values()) == 0, me.disc_energy


@test
def t_mischievous_painting_loads_opponent():
    # Setup half of Grafaiai's combo: move up to 3 from the OPPONENT's discard onto THEIR Active.
    ctx, at, df, me, opp = mk(base=0, text=K_MISCHIEF)
    opp.disc_energy = Counter({'Darkness': 3})
    # MY discard + MY board must be untouched — the source is the OPPONENT's discard, target THEIR mons.
    me.disc_energy = Counter({'Fire': 2})
    my_mon_before = sum(m.total_energy() for m in me.all_mons())
    before = opp.active.total_energy()
    d = _fn(K_MISCHIEF)(ctx)
    assert d == 0, d
    assert opp.active.total_energy() == before + 3, opp.active.energy
    assert sum(opp.disc_energy.values()) == 0, opp.disc_energy
    assert sum(me.disc_energy.values()) == 2, me.disc_energy               # my discard untouched
    assert sum(m.total_energy() for m in me.all_mons()) == my_mon_before   # my mons not fueled


@test
def t_mischievous_painting_capped():
    ctx, at, df, me, opp = mk(base=0, text=K_MISCHIEF)
    opp.disc_energy = Counter({'Darkness': 1})
    before = opp.active.total_energy()
    _fn(K_MISCHIEF)(ctx)
    assert opp.active.total_energy() == before + 1, opp.active.energy
    assert sum(opp.disc_energy.values()) == 0, opp.disc_energy


# ---------------------------------------------------------------- single-energy recover
@test
def t_metal_coating_attaches_one():
    ctx, at, df, me, opp = mk(base=0, text=K_METAL, atk_energy={})
    me.disc_energy = Counter({'Metal': 2})
    d = _fn(K_METAL)(ctx)
    assert d == 0, d
    assert at.energy.get('Metal', 0) == 1, at.energy
    assert me.disc_energy['Metal'] == 1, me.disc_energy


@test
def t_metal_coating_none_in_discard():
    ctx, at, df, me, opp = mk(base=0, text=K_METAL, atk_energy={})
    me.disc_energy = Counter()
    _fn(K_METAL)(ctx)
    assert at.energy.get('Metal', 0) == 0, at.energy      # nothing to recover


@test
def t_tea_server_to_hand():
    ctx, at, df, me, opp = mk(base=0, text=K_TEA)
    me.hand = []
    me.disc_energy = Counter({'Grass': 2})
    d = _fn(K_TEA)(ctx)
    assert d == 0, d
    assert ('E', 'Grass') in me.hand, me.hand
    assert len(me.hand) == 1, me.hand
    assert me.disc_energy['Grass'] == 1, me.disc_energy    # went to hand, not attached
    assert at.energy.get('Grass', 0) == 0, at.energy       # NOT attached to the attacker


@test
def t_tea_server_no_grass_in_discard():
    # No basic {G} in the discard -> nothing to retrieve, hand stays empty, no crash.
    ctx, at, df, me, opp = mk(base=0, text=K_TEA)
    me.hand = []
    me.disc_energy = Counter({'Water': 3})   # wrong type only
    d = _fn(K_TEA)(ctx)
    assert d == 0, d
    assert me.hand == [], me.hand
    assert me.disc_energy['Water'] == 3, me.disc_energy    # unrelated energy untouched


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
