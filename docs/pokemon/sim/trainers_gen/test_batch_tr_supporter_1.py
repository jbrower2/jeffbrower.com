#!/usr/bin/env python3
"""Unit tests for trainer batch tr_supporter_1. Each Supporter action runs through a real
TrainerCtx over Player/Game objects built by the shared harness; asserts the state change."""
from effects_testkit import mk, runner
import effects_testkit as TK
from engine import Mon
import trainer_effects as TE
import trainers_gen.batch_tr_supporter_1   # noqa: F401  (registers the batch)

VANILLA = TK.VANILLA
BK = TK.BK
LIGHT = next(c for c in BK.values() if c.ptype == 'Lightning' and c.stage == 0)   # e.g. Pikachu
STAGE1 = next(c for c in BK.values() if c.stage == 1)
STAGE2 = next(c for c in BK.values() if c.stage == 2)
EXCARD = next(c for c in BK.values() if c.is_ex)
ETHANMON = next(c for c in BK.values() if c.name.startswith("Ethan's"))


def run_action(text, setup=None, **kw):
    """Build harness state, optionally mutate it, then resolve the trainer by exact text."""
    ctx, at, df, me, opp = mk(**kw)
    if setup:
        setup(me, opp, at, df, ctx)
    did = TE.TRAINER_EFFECTS[TE.normalize(text)]['fn'](TE.TrainerCtx(me, opp, ctx.game))
    return did, me, opp, at, df, ctx


TESTS = []
def test(f):
    TESTS.append(f)
    return f


# ---- exact texts (must match registration) ----
CIPHER = "Search your deck for 2 cards, shuffle your deck, then put those cards on top of it in any order."
CLEMONT = "Heal 60 damage from each of your {L} Pokémon."
COLRESS = "Search your deck for a Stadium card and an Energy card, reveal them, and put them into your hand. Then, shuffle your deck."
COOK = "Heal 70 damage from your Active Pokémon."
CRISPIN = "Search your deck for up to 2 Basic Energy cards of different types, reveal them, and put 1 of them into your hand. Attach the other to 1 of your Pokémon. Then, shuffle your deck."
CYRANO = "Search your deck for up to 3 Pokémon ex, reveal them, and put them into your hand. Then, shuffle your deck."
DAWN = "Search your deck for a Basic Pokémon, a Stage 1 Pokémon, and a Stage 2 Pokémon, reveal them, and put them into your hand. Then, shuffle your deck."
DRASNA = "Shuffle your hand into your deck. Then, flip a coin. If heads, draw 8 cards. If tails, draw 3 cards."
DRAYTON = "Look at the top 7 cards of your deck. You may reveal a Pokémon and a Trainer card you find there and put them into your hand. Shuffle the other cards back into your deck."
EMCEE = "Draw 2 cards. If your opponent has 3 or fewer Prize cards remaining, draw 2 more cards."
EMMA = "Your opponent reveals their hand, and you draw a card for each Pokémon you find there."
ERI = "Your opponent reveals their hand, and you discard up to 2 Item cards you find there."
ETHAN = "Search your deck for up to 3 in any combination of Ethan's Pokémon and Basic {R} Energy cards, reveal them, and put them into your hand. Then, shuffle your deck."
EXPLORER = "Look at the top 6 cards of your deck and put 2 of them into your hand. Discard the other cards."


@test
def t_ciphermaniac():
    # 16-card deck (6 basics + 10 energy); the 2 chosen cards land on top (end of list), size unchanged.
    did, me, *_ = run_action(CIPHER)
    assert did
    assert len(me.deck) == 16
    assert me.deck[-1][0] == 'P' and me.deck[-2][0] == 'P'   # basics preferentially put on top


@test
def t_clemont():
    def setup(me, opp, at, df, ctx):
        me.active = Mon(LIGHT); me.active.damage = 60          # a {L} Pokémon, damaged
        me.bench = [Mon(VANILLA)]; me.bench[0].damage = 60     # a non-{L} Pokémon, damaged
    did, me, *_ = run_action(CLEMONT, setup=setup)
    assert did
    assert me.active.damage == 0            # healed 60
    assert me.bench[0].damage == 60         # non-Lightning untouched


@test
def t_clemont_noop():
    # no Lightning Pokémon in play -> nothing to heal
    def setup(me, opp, at, df, ctx):
        me.active = Mon(VANILLA); me.active.damage = 60
        me.bench = []
    did, me, *_ = run_action(CLEMONT, setup=setup)
    assert did is False and me.active.damage == 60


@test
def t_colress():
    def setup(me, opp, at, df, ctx):
        me.deck.append(('T', {'name': 'TestStadium', 'trainerType': 'Stadium'}))
    did, me, *_ = run_action(COLRESS, setup=setup)
    assert did
    assert any(x[0] == 'T' and x[1].get('trainerType') == 'Stadium' for x in me.hand)
    assert any(x[0] in ('E', 'S') for x in me.hand)


@test
def t_cook():
    def setup(me, opp, at, df, ctx):
        me.active.damage = 90
    did, me, *_ = run_action(COOK, setup=setup)
    assert did and me.active.damage == 20   # healed 70


@test
def t_crispin():
    def setup(me, opp, at, df, ctx):
        me.deck.append(('E', 'Fire'))       # ensure a 2nd, different energy type is available
        for m in me.all_mons():
            m.energy.clear()
    did, me, *_ = run_action(CRISPIN, setup=setup, atk_energy={'Colorless': 0})
    assert did
    assert sum(m.total_energy() for m in me.all_mons()) == 1   # one energy attached
    assert sum(1 for x in me.hand if x[0] == 'E') == 1         # the other put into hand


@test
def t_cyrano():
    def setup(me, opp, at, df, ctx):
        me.deck.append(('P', EXCARD))
    did, me, *_ = run_action(CYRANO, setup=setup)
    assert did
    assert any(x[0] == 'P' and x[1].is_ex for x in me.hand)


@test
def t_dawn():
    def setup(me, opp, at, df, ctx):
        me.deck.append(('P', STAGE1)); me.deck.append(('P', STAGE2))   # a Basic already exists (VANILLA)
    did, me, *_ = run_action(DAWN, setup=setup)
    assert did
    stages = {x[1].stage for x in me.hand if x[0] == 'P'}
    assert stages == {0, 1, 2}


@test
def t_drasna_heads():
    # empty hand; scripted flip default 0.0 == heads -> draw 8
    did, me, *_ = run_action(DRASNA)
    assert did and len(me.hand) == 8


@test
def t_drasna_tails():
    did, me, *_ = run_action(DRASNA, flips=(0.9,))   # 0.9 == tails -> draw 3
    assert did and len(me.hand) == 3


@test
def t_drayton():
    def setup(me, opp, at, df, ctx):
        me.deck.append(('P', VANILLA))                                   # a Pokémon in the top 7
        me.deck.append(('T', {'name': 'X', 'trainerType': 'Item'}))      # a Trainer in the top 7
    did, me, *_ = run_action(DRAYTON, setup=setup)
    assert did
    assert any(x[0] == 'P' for x in me.hand)
    assert any(x[0] == 'T' for x in me.hand)


@test
def t_emcee_low_prizes():
    did, me, *_ = run_action(EMCEE, opp_prizes=3)    # opp at 3 prizes -> draw 2 + 2
    assert did and len(me.hand) == 4


@test
def t_emcee_high_prizes():
    did, me, *_ = run_action(EMCEE, opp_prizes=6)    # opp at 6 prizes -> draw just 2
    assert did and len(me.hand) == 2


@test
def t_emma():
    def setup(me, opp, at, df, ctx):
        opp.hand = [('P', VANILLA), ('P', VANILLA), ('E', 'Colorless')]
    did, me, *_ = run_action(EMMA, setup=setup)
    assert did and len(me.hand) == 2     # 2 Pokémon in opp hand -> draw 2


@test
def t_eri():
    def setup(me, opp, at, df, ctx):
        opp.hand = [('T', {'name': 'A', 'trainerType': 'Item'}),
                    ('T', {'name': 'B', 'trainerType': 'Item'}),
                    ('T', {'name': 'C', 'trainerType': 'Item'}),
                    ('E', 'Colorless')]
    did, me, opp, *_ = run_action(ERI, setup=setup)
    assert did
    assert sum(1 for x in opp.hand if x[0] == 'T' and x[1]['trainerType'] == 'Item') == 1   # 2 discarded
    assert len(opp.discard) == 2


@test
def t_ethans_adventure():
    def setup(me, opp, at, df, ctx):
        me.deck.append(('P', ETHANMON)); me.deck.append(('E', 'Fire'))
    did, me, *_ = run_action(ETHAN, setup=setup)
    assert did
    assert any(x[0] == 'P' and x[1].name.startswith("Ethan's") for x in me.hand)
    assert any(x == ('E', 'Fire') for x in me.hand)


@test
def t_explorers_guidance():
    def setup(me, opp, at, df, ctx):
        me.deck.append(('P', VANILLA))   # a Pokémon in the top 6 should be preferentially kept
    did, me, *_ = run_action(EXPLORER, setup=setup)
    assert did
    assert len(me.hand) == 2
    assert len(me.deck) == 11            # started 16, +1 appended, -6 looked at
    assert any(x[0] == 'P' for x in me.hand)
    assert me.disc_energy['Colorless'] == 4   # the 4 non-kept energy discarded


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
