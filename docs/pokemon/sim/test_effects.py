#!/usr/bin/env python3
"""Unit tests for the attack-effect registry. Each effect is exercised against real engine Mon/Player
objects with a scripted RNG (so coin flips are deterministic) and its damage + state changes asserted.
Run: python3 test_effects.py   (exits non-zero on any failure)."""
from collections import Counter
from effects_testkit import mk, run
import attack_effects as AE

TESTS = []
def test(fn): TESTS.append(fn); return fn


@test
def t_self_damage():
    d, ctx, at, *_ = run("[30] This Pokémon also does 10 damage to itself.", base=30)
    assert d == 30 and at.damage == 10, (d, at.damage)


@test
def t_tails_nothing():
    assert run("[30] Flip a coin. If tails, this attack does nothing.", base=30, flips=(0.0,))[0] == 30
    assert run("[30] Flip a coin. If tails, this attack does nothing.", base=30, flips=(0.9,))[0] == 0


@test
def t_heads_plus_20():
    assert run("10+ Flip a coin. If heads, this attack does 20 more damage.", base=10, flips=(0.0,))[0] == 30
    assert run("10+ Flip a coin. If heads, this attack does 20 more damage.", base=10, flips=(0.9,))[0] == 10


@test
def t_two_coins_each_20():
    assert run("20× Flip 2 coins. This attack does 20 damage for each heads.", base=20, flips=(0.0, 0.0))[0] == 40
    assert run("20× Flip 2 coins. This attack does 20 damage for each heads.", base=20, flips=(0.0, 0.9))[0] == 20
    assert run("20× Flip 2 coins. This attack does 20 damage for each heads.", base=20, flips=(0.9, 0.9))[0] == 0


@test
def t_until_tails():
    # heads, heads, tails -> 2 heads -> 40
    assert run("20× Flip a coin until you get tails. This attack does 20 damage for each heads.",
               base=20, flips=(0.0, 0.0, 0.9))[0] == 40


@test
def t_heads_paralyze():
    _, _, _, df, *_ = run("[30] Flip a coin. If heads, your opponent's Active Pokémon is now Paralyzed.",
                          base=30, flips=(0.0,))
    assert df.status.get('Paralyzed')
    _, _, _, df2, *_ = run("[30] Flip a coin. If heads, your opponent's Active Pokémon is now Paralyzed.",
                           base=30, flips=(0.9,))
    assert not df2.status.get('Paralyzed')


@test
def t_status_plain():
    for text, key in [("Your opponent's Active Pokémon is now Poisoned.", 'Poisoned'),
                      ("Your opponent's Active Pokémon is now Confused.", 'Confused'),
                      ("Your opponent's Active Pokémon is now Asleep.", 'Asleep')]:
        _, _, _, df, *_ = run(text)
        assert df.status.get(key), text


@test
def t_status_shielded():
    # Mist Energy on the defender blocks the condition
    _, _, _, df, *_ = run("Your opponent's Active Pokémon is now Poisoned.", def_special=('Mist Energy',))
    assert not df.status.get('Poisoned')


@test
def t_heal():
    ctx, at, df, me, opp = mk(text="Heal 30 damage from this Pokémon.")
    at.damage = 50
    AE.ATTACK_EFFECTS[AE.normalize("Heal 30 damage from this Pokémon.")](ctx)
    assert at.damage == 20, at.damage


@test
def t_discard_self_energy():
    ctx, at, *_ = mk(text="Discard 2 Energy from this Pokémon.", atk_energy={'Fire': 3})
    before = at.total_energy()
    AE.ATTACK_EFFECTS[AE.normalize("Discard 2 Energy from this Pokémon.")](ctx)
    assert at.total_energy() == before - 2, at.total_energy()


@test
def t_discard_opp_energy_on_heads():
    ctx, at, df, *_ = mk(text="Flip a coin. If heads, discard an Energy from your opponent's Active Pokémon.",
                         flips=(0.0,))
    df.energy = Counter({'Water': 2})
    AE.ATTACK_EFFECTS[AE.normalize("Flip a coin. If heads, discard an Energy from your opponent's Active Pokémon.")](ctx)
    assert df.total_energy() == 1


@test
def t_cant_attack_next():
    _, ctx, at, *_ = run("[40] During your next turn, this Pokémon can't attack.", base=40)
    assert at.cd_name == 'ALL' and at.cd_turn == 3


@test
def t_defender_no_retreat():
    _, ctx, at, df, *_ = run("During your opponent's next turn, the Defending Pokémon can't retreat.")
    assert 'CantRetreat' in df.status


@test
def t_switch_opp():
    _, ctx, at, df, me, opp = run("Switch out your opponent's Active Pokémon to the Bench. (Your opponent chooses the new Active Pokémon.)")
    assert opp.active is not df                            # a benched mon was promoted


@test
def t_draw():
    _, ctx, at, df, me, opp = run("- Draw a card.")
    assert len(me.hand) == 1


@test
def t_fickle_spitting():
    txt = "If your opponent doesn't have exactly 3 or 4 Prize cards remaining, this attack does nothing."
    assert run(txt, base=120, opp_prizes=4)[0] == 120      # opp at 4 prizes -> fires
    assert run(txt, base=120, opp_prizes=3)[0] == 120      # opp at 3 prizes -> fires
    assert run(txt, base=120, opp_prizes=6)[0] == 0        # opp at 6 (game start) -> nothing
    assert run(txt, base=120, opp_prizes=1)[0] == 0        # opp closing out -> nothing


if __name__ == '__main__':
    import traceback
    passed = failed = 0
    for t in TESTS:
        try:
            t(); passed += 1
        except Exception:
            failed += 1
            print(f"FAIL {t.__name__}:")
            traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed  ({len(AE.ATTACK_EFFECTS)} effects registered)")
    raise SystemExit(1 if failed else 0)
