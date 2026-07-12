#!/usr/bin/env python3
"""Integration tests for one-shot 'during your next turn, this attack does +N' buffs (the mon.ramp
channel) and their expiry via Game.ramp_bonus. These exercise the ENGINE read path — not just the
effect lambdas — because the whole point of the fix is that the buff applies on exactly the next turn
and expires if that turn is slept/passed through, rather than being banked forever (or accumulating)."""
import attack_effects as AE
from effects_testkit import mk, BK


def _card(cardname, atkname):
    c = next(x for x in BK.values() if x.name == cardname and any(a['name'] == atkname for a in x.attacks))
    a = next(x for x in c.attacks if x['name'] == atkname)
    return c, a


def drive(cardname, atkname, turns):
    """Use `atkname` on each turn number in `turns` (gaps = turns the attacker did NOT attack, e.g.
    asleep). Return the per-use damage the engine would apply (ramp_bonus captured BEFORE resolve,
    exactly as take_turn does)."""
    c, a = _card(cardname, atkname)
    base = a['dmg']
    ctx, at, df, me, opp = mk(base=base, text=a['text'])
    at.card = c
    ad = {'dmg': base, 'text': a['text'], 'cost': a.get('cost', []), 'name': atkname}
    g = ctx.game
    out = []
    for t in turns:
        g.turn = t
        at.status.pop('Asleep', None); df.status.pop('Asleep', None)   # isolate damage from the wake RNG
        pre = g.ramp_bonus(at, atkname)                                # engine reads BEFORE resolve
        raw = AE.resolve(me, opp, at, df, g, ad)                       # sets ramp + ramp_turn for next turn
        out.append((raw + pre) if raw > 0 else raw)
    return out


def t_slumbering_smack_ramps_then_holds():
    # 30 on first use; +100 on each immediately-following turn (Komala's only attack), flat (not runaway).
    assert drive('Komala', 'Slumbering Smack', [2, 4, 6]) == [30, 130, 130]


def t_slumbering_smack_expires_when_slept_through():
    # Buff set on turn 2 must EXPIRE if Komala doesn't attack on turn 4 (slept). Turn 6 is back to 30.
    assert drive('Komala', 'Slumbering Smack', [2, 6]) == [30, 30]


def t_meteor_mash_flat_not_cumulative():
    # "during your next turn, +60" is one-shot: 60 -> 120 -> 120, NOT 60 -> 120 -> 180.
    assert drive('Metagross', 'Meteor Mash', [2, 4, 6]) == [60, 120, 120]


def t_meteor_mash_expires_when_skipped():
    assert drive('Metagross', 'Meteor Mash', [2, 6]) == [60, 60]


TESTS = [t_slumbering_smack_ramps_then_holds, t_slumbering_smack_expires_when_slept_through,
         t_meteor_mash_flat_not_cumulative, t_meteor_mash_expires_when_skipped]

if __name__ == '__main__':
    import traceback
    p = f = 0
    for t in TESTS:
        try:
            t(); p += 1
        except Exception:
            f += 1; print(f"FAIL {t.__name__}"); traceback.print_exc()
    print(f"ramp-expiry: {p} passed, {f} failed")
    raise SystemExit(1 if f else 0)
