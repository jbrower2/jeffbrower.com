#!/usr/bin/env python3
"""Unit tests for ability batch ab_lock_0 (Damp)."""
from effects_testkit import mk, runner
from cards import load_cards
import ability_effects as AB
import abilities_gen.batch_ab_lock_0  # noqa: F401 (registers the batch's abilities on import)


DAMP = ("- Pokémon in play (both yours and your opponent's) lose any Ability that requires the "
        "Pokémon using it to Knock Out itself.")

# The two in-pool (cat-green) printings this batch is responsible for. NOTE: the MEP Psyduck/Golduck
# carry a DIFFERENT Damp wording ("lose all Abilities that require those Pokémon to be Knocked Out")
# but are cat-red (illegal, out of pool), so they are intentionally not registered here.
ASH_DAMP = [('ASH', '#039/217', 'Psyduck'), ('ASH', '#040/217', 'Golduck')]


def _entry(key=DAMP):
    return AB.ABILITY_EFFECTS[AB.normalize(key)]


def t_damp_registered_as_lock():
    # Registered under the exact (normalized) text, with the correct hook kind.
    e = _entry()
    assert e['kind'] == 'lock', e['kind']


def t_damp_active_from_active_spot():
    # Holder = me.active; lock signal is on -> True. Signature: fn(mon, owner, opp, game).
    ctx, at, df, me, opp = mk()
    f = _entry()['fn']
    assert f(at, me, opp, ctx.game) is True


def t_damp_active_from_bench():
    # Damp works from anywhere in play, including the bench — still active.
    ctx, at, df, me, opp = mk()
    f = _entry()['fn']
    holder = me.bench[0]
    assert f(holder, me, opp, ctx.game) is True


def t_damp_unconditional():
    # No game-state dependency: the lock is on regardless of prizes/energy/opponent board.
    ctx, at, df, me, opp = mk(opp_bench=0, atk_energy={}, opp_prizes=1)
    f = _entry()['fn']
    assert f(at, me, opp, ctx.game) is True


def t_damp_text_roundtrips_against_card_db():
    # Round-trip: the registered key must EXACTLY match the on-card ability text of the two
    # in-pool ASH printings, or the lock would silently never match these cards at runtime.
    BK, _ = load_cards()
    by_ref = {(c.set, c.id): c for c in BK.values()}
    reg_key = AB.normalize(DAMP)
    for st, cid, name in ASH_DAMP:
        c = by_ref.get((st, cid))
        assert c is not None, f'missing {name} {st}:{cid}'
        assert c.name == name, (c.name, name)
        assert c.cat == 'cat-green', (name, c.cat)                 # in-pool, needs coverage
        damp = [ab for ab in c.abilities if ab['name'] == 'Damp']
        assert len(damp) == 1, (name, [a['name'] for a in c.abilities])
        assert AB.normalize(damp[0]['text']) == reg_key, name      # card text == registered text
    assert reg_key in AB.ABILITY_EFFECTS                           # ... and that key is registered


TESTS = [
    t_damp_registered_as_lock,
    t_damp_active_from_active_spot,
    t_damp_active_from_bench,
    t_damp_unconditional,
    t_damp_text_roundtrips_against_card_db,
]

if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
