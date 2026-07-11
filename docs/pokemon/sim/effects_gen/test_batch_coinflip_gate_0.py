#!/usr/bin/env python3
"""Unit tests for effect batch coinflip_gate_0."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # ensure sim/ importable
from effects_testkit import mk, run, runner
import attack_effects as AE
import effects
import effects_gen.batch_coinflip_gate_0  # noqa: F401  (registers the effects)

TEXT = ("Flip a coin. If tails, this attack does nothing. If heads, during your opponent's next turn, "
        "prevent all damage from and effects of attacks done to this Pokémon.")


def t_heads_deals_damage_and_walls():
    # Heads (0.0): full base damage AND a wall scheduled for the opponent's next turn.
    d, ctx, at, df, me, opp = run(TEXT, base=40, flips=(0.0,))
    assert d == 40, d
    assert at.dr_amount > 0, at.dr_amount
    assert at.dr_turn == ctx.game.turn, (at.dr_turn, ctx.game.turn)


def t_heads_wall_prevents_all_damage_next_turn():
    # End-to-end through the real engine hook: during the opponent's next turn (dr_turn+1),
    # ANY incoming attack damage to the attacker is reduced to 0.
    d, ctx, at, df, me, opp = run(TEXT, base=40, flips=(0.0,))
    assert d == 40
    # Timing guard: on the SAME turn the wall is set (our turn), it is NOT yet active — the text
    # protects only during the opponent's *next* turn, so a hit here must land in full.
    assert ctx.game.turn == at.dr_turn
    assert effects.incoming_damage(200, df, at, me, ctx.game) == 200
    ctx.game.turn = at.dr_turn + 1                       # opponent's next turn
    # df (opponent's mon) attacks at (our walled Pokémon); me owns `at`.
    assert effects.incoming_damage(200, df, at, me, ctx.game) == 0
    # Wall lapses after that single turn: damage passes through again.
    ctx.game.turn = at.dr_turn + 2
    assert effects.incoming_damage(70, df, at, me, ctx.game) == 70


def t_tails_does_nothing():
    # Tails (0.9): zero damage AND no wall (dr fields stay at their Mon defaults).
    d, ctx, at, df, me, opp = run(TEXT, base=40, flips=(0.9,))
    assert d == 0, d
    assert at.dr_amount == 0, at.dr_amount
    assert at.dr_turn == -9, at.dr_turn
    # Confirm no protection leaked: a hit during any turn lands in full.
    ctx.game.turn = ctx.game.turn + 1
    assert effects.incoming_damage(70, df, at, me, ctx.game) == 70


TESTS = [
    t_heads_deals_damage_and_walls,
    t_heads_wall_prevents_all_damage_next_turn,
    t_tails_does_nothing,
]

if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
