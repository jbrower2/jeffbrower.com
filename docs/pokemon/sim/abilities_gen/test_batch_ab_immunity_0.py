#!/usr/bin/env python3
"""Unit tests for ability batch ab_immunity_0. Each registered fn is exercised directly against real
Mon/Player objects from mk(); immunity fns are called with (atk, dfn, dfn_owner, game)."""
from effects_testkit import mk, runner, BK, BN
import ability_effects as AB
import abilities_gen.batch_ab_immunity_0  # noqa: F401  (registers the batch)


def fn_of(text):
    return AB.ABILITY_EFFECTS[AB.normalize(text)]['fn']


# real cards used to give a benched Mon the exact ability text / a Rule Box
MAGIKARP = next(c for c in BN["Misty's Magikarp"] if any(a['name'] == 'So Submerged' for a in c.abilities))
EXCARD = next(c for c in BK.values() if c.is_ex)          # any ex = has a Rule Box

K1 = ("- As long as this Pokémon is on your Bench, prevent all damage from and effects of attacks "
      "from your opponent's Pokémon done to this Pokémon.")
K2 = "- This Pokémon can't be Asleep."
K3 = "- Your opponent's Pokémon in play and all attached cards can't be put into your opponent's hand."
K4 = ("- Prevent all damage done to your Benched Pokémon that don't have a Rule Box by attacks "
      "from your opponent's Pokémon. (Pokémon ex, Pokémon V, etc. have Rule Boxes.)")
K5 = "- Damage counters on each Pokémon (both yours and your opponent's) can't be moved to other Pokémon."
K6 = ("- Prevent all damage from and effects of attacks from your opponent's Pokémon done to "
      "your Benched Pokémon.")


TESTS = []
def test(f): TESTS.append(f); return f


@test
def t_all_registered():
    # every batch key is registered under a valid kind
    for k, kind in ((K1, 'immunity'), (K2, 'between_turns'), (K3, 'immunity'),
                    (K4, 'immunity'), (K5, 'immunity'), (K6, 'immunity')):
        e = AB.ABILITY_EFFECTS[AB.normalize(k)]
        assert e['kind'] == kind, (k, e['kind'])


@test
def t_self_bench_shield():
    ctx, at, df, me, opp = mk(opp_bench=2)
    f = fn_of(K1)
    holder, plain = opp.bench[0], opp.bench[1]
    holder.card = MAGIKARP                                  # a benched holder
    assert f(at, holder, opp, ctx.game) is True            # benched holder -> immune
    assert f(at, plain, opp, ctx.game) is False            # benched teammate WITHOUT the ability -> not immune
    opp.active.card = MAGIKARP                              # holder promoted to Active
    assert f(at, opp.active, opp, ctx.game) is False       # shield only works while on the Bench


@test
def t_self_bench_shield_via_is_immune():
    # Integration: through the real engine query AB.is_immune (which calls each immunity fn with the
    # ATTACK TARGET as dfn and does NOT pass the holder). A benched holder must shield ITSELF only,
    # never a benched teammate — the exact anti-regression the _has_ability(dfn) self-check exists for.
    ctx, at, df, me, opp = mk(opp_bench=2)
    holder, teammate = opp.bench
    holder.card = MAGIKARP                                  # holder is in opp.all_mons() -> fn is live
    assert AB.is_immune(at, holder, opp, ctx.game) is True      # holder shields itself
    assert AB.is_immune(at, teammate, opp, ctx.game) is False   # teammate NOT shielded despite holder present
    assert AB.is_immune(at, opp.active, opp, ctx.game) is False  # Active holder-teammate not shielded
    opp.active.card = MAGIKARP                              # holder promoted to Active
    assert AB.is_immune(at, opp.active, opp, ctx.game) is False  # shield is bench-only, even via is_immune


@test
def t_team_bench_shield_gated_on_holder():
    # Integration: team bench-shields (Flower Curtain / Spherical Shield) only fire when the HOLDER is
    # in play, because is_immune sources immunity fns from dfn_owner.all_mons(). With no holder among a
    # team of vanilla Mons, a benched Pokémon is not immune.
    ctx, at, df, me, opp = mk(opp_bench=2)
    assert AB.is_immune(at, opp.bench[0], opp, ctx.game) is False  # no Shaymin/Rabsca in play -> no shield


@test
def t_insomnia_clears_asleep():
    ctx, at, df, me, opp = mk()
    f = fn_of(K2)
    at.status['Asleep'] = True
    at.status['Poisoned'] = True                           # unrelated status untouched
    f(at, me, ctx.game)
    assert 'Asleep' not in at.status
    assert at.status.get('Poisoned') is True
    f(at, me, ctx.game)                                     # idempotent when not asleep
    assert 'Asleep' not in at.status


@test
def t_mentally_calm_noop():
    ctx, at, df, me, opp = mk()
    f = fn_of(K3)
    assert f(at, df, opp, ctx.game) is False               # unmodeled disruption -> never immune


@test
def t_flower_curtain():
    ctx, at, df, me, opp = mk(opp_bench=2)
    f = fn_of(K4)
    reg, exmon = opp.bench[0], opp.bench[1]
    exmon.card = EXCARD                                     # benched Pokémon WITH a Rule Box
    assert f(at, reg, opp, ctx.game) is True               # non-Rule-Box benched -> shielded
    assert f(at, exmon, opp, ctx.game) is False            # Rule-Box (ex) benched -> NOT shielded
    assert f(at, opp.active, opp, ctx.game) is False       # Active is not a Benched Pokémon


@test
def t_watchful_eye_noop():
    ctx, at, df, me, opp = mk()
    f = fn_of(K5)
    assert f(at, df, opp, ctx.game) is False               # no counter-move mechanic -> never immune


@test
def t_spherical_shield():
    ctx, at, df, me, opp = mk(opp_bench=2)
    f = fn_of(K6)
    b0, b1 = opp.bench
    assert f(at, b0, opp, ctx.game) is True                # any benched teammate -> shielded
    assert f(at, b1, opp, ctx.game) is True
    b1.card = EXCARD                                        # no Rule-Box exclusion here
    assert f(at, b1, opp, ctx.game) is True                # a benched ex is still shielded
    assert f(at, opp.active, opp, ctx.game) is False       # Active is not shielded


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
