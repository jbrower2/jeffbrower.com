#!/usr/bin/env python3
"""Unit tests for trainer batch tr_stadium_0 (14 Stadiums).

Action stadiums (Academy at Night, Community Center, Levincia) run through a TrainerCtx over real
Player/Game objects and assert the state change. The 11 passive-aura / rules-mod stadiums expose no
per-turn action -> each is asserted to be a state-neutral no-op (the aura itself is an engine concern
applied off game.stadium, not this fn)."""
from effects_testkit import mk, runner
import trainer_effects as TE
import trainers_gen.batch_tr_stadium_0 as B


# ---- exact printed texts (registration keys) ----
ACADEMY   = "Once during each player's turn, that player may put a card from their hand on top of their deck."
ANGE      = "You can put this card into play only if you discard a Prism Tower in play, and you can put this card into play during the same turn you play Prism Tower.\nEach Mega Floette ex in play (both yours and your opponent's) gets +150 HP."
AREA      = "Each player who has any Tera Pokémon in play can have up to 8 Pokémon on their Bench.\n\nIf a player no longer has any Tera Pokémon in play, that player discards Pokémon from their Bench until they have 5. When this card leaves play, both players discard Pokémon from their Bench until they have 5, and the player who played this card discards first."
BATTLE    = "Prevent all damage counters from being placed on Benched Pokémon (both yours and your opponent's) by effects of attacks and Abilities from the opponent's Pokémon. (Damage from attacks is still taken.)"
COMMUNITY = "Once during each player's turn, if they played a Supporter card from their hand this turn, they may heal 10 damage from each of their Pokémon."
DIZZYING  = "Confused Pokémon (both yours and your opponent's) don't recover from that Special Condition when they evolve or devolve."
FESTIVAL  = "Each Pokémon that has any Energy attached (both yours and your opponent's) recovers from all Special Conditions and can't be affected by any Special Conditions."
FOREST    = "Each player's {G} Pokémon can evolve into {G} Pokémon during the turn they play those Pokémon, except during their first turn."
FULLMETAL = "{M} Pokémon (both yours and your opponent's) take 30 less damage from attacks from the opponent's Pokémon (after applying Weakness and Resistance)."
GRANITE   = "Steven's Pokémon (both yours and your opponent's) take 30 less damage from attacks from the opponent's Pokémon (after applying Weakness and Resistance)."
GRAVITY   = "Each Stage 2 Pokémon in play (both yours and your opponent's) gets -30 HP."
JAMMING   = "Pokémon Tools attached to each Pokémon (both yours and your opponent's) have no effect."
LEVINCIA  = "Once during each player's turn, that player may put up to 2 Basic {L} Energy cards from their discard pile into their hand."
LIVELY    = "Each Basic Pokémon in play (both yours and your opponent's) gets +30 HP."

ALL_TEXTS = [ACADEMY, ANGE, AREA, BATTLE, COMMUNITY, DIZZYING, FESTIVAL, FOREST,
             FULLMETAL, GRANITE, GRAVITY, JAMMING, LEVINCIA, LIVELY]
NOOPS = {'ange': ANGE, 'area': AREA, 'battle': BATTLE, 'dizzying': DIZZYING,
         'festival': FESTIVAL, 'forest': FOREST, 'fullmetal': FULLMETAL, 'granite': GRANITE,
         'gravity': GRAVITY, 'jamming': JAMMING, 'lively': LIVELY}


def fn(text):
    return TE.TRAINER_EFFECTS[TE.normalize(text)]['fn']


TESTS = []
def test(f): TESTS.append(f); return f


# ---- meta: every stadium is registered under the 'stadium' kind ----
@test
def t_all_registered_as_stadium():
    for text in ALL_TEXTS:
        e = TE.TRAINER_EFFECTS[TE.normalize(text)]
        assert e['kind'] == 'stadium', text[:32]


# ---- Academy at Night: stash a card on top of the deck ----
@test
def t_academy_at_night():
    ctx, at, df, me, opp = mk()
    energy = ('E', 'Colorless')
    item = ('T', {'name': 'Some Item', 'trainerType': 'Item'})
    me.hand = [energy, item]
    dlen = len(me.deck)
    did = fn(ACADEMY)(TE.TrainerCtx(me, opp, ctx.game))
    assert did is True
    assert len(me.hand) == 1 and len(me.deck) == dlen + 1
    assert me.deck[-1] == item          # least-useful (Trainer) put on TOP (== end of list)
    assert me.hand == [energy]          # the immediately-useful energy stays in hand


@test
def t_academy_empty_hand_noop():
    ctx, at, df, me, opp = mk()
    me.hand = []
    assert fn(ACADEMY)(TE.TrainerCtx(me, opp, ctx.game)) is False


# ---- Community Center: heal 10 from each mon IF a Supporter was played this turn ----
@test
def t_community_supporters_loaded():
    assert 'Judge' in B._SUPPORTER_NAMES and len(B._SUPPORTER_NAMES) > 20   # trainers.json loaded


@test
def t_community_center_heals_when_supporter_played():
    ctx, at, df, me, opp = mk(played=['Judge'])   # Judge is a Supporter
    at.damage = 50
    me.bench[0].damage = 30
    did = fn(COMMUNITY)(TE.TrainerCtx(me, opp, ctx.game))
    assert did is True
    assert at.damage == 40 and me.bench[0].damage == 20   # -10 from each of MY Pokémon


@test
def t_community_center_no_supporter_noop():
    ctx, at, df, me, opp = mk(played=[])          # nothing played
    at.damage = 50
    assert fn(COMMUNITY)(TE.TrainerCtx(me, opp, ctx.game)) is False
    assert at.damage == 50


@test
def t_community_center_item_played_is_not_supporter():
    ctx, at, df, me, opp = mk(played=['Energy Retrieval'])   # an Item, not a Supporter
    at.damage = 50
    assert fn(COMMUNITY)(TE.TrainerCtx(me, opp, ctx.game)) is False
    assert at.damage == 50


@test
def t_community_center_supporter_but_no_damage_noop():
    ctx, at, df, me, opp = mk(played=['Judge'])   # supporter played, but nothing is hurt
    for m in me.all_mons():
        m.damage = 0
    assert fn(COMMUNITY)(TE.TrainerCtx(me, opp, ctx.game)) is False


# ---- Levincia: up to 2 Basic {L} Energy from discard to hand ----
@test
def t_levincia_recovers_two_lightning():
    ctx, at, df, me, opp = mk()
    me.hand = []
    me.disc_energy['Lightning'] = 3
    did = fn(LEVINCIA)(TE.TrainerCtx(me, opp, ctx.game))
    assert did is True
    assert me.disc_energy['Lightning'] == 1                       # 2 removed from discard
    assert me.hand.count(('E', 'Lightning')) == 2                 # 2 added to hand


@test
def t_levincia_only_one_available():
    ctx, at, df, me, opp = mk()
    me.hand = []
    me.disc_energy['Lightning'] = 1
    did = fn(LEVINCIA)(TE.TrainerCtx(me, opp, ctx.game))
    assert did is True
    assert me.disc_energy['Lightning'] == 0
    assert me.hand.count(('E', 'Lightning')) == 1


@test
def t_levincia_none_in_discard_noop():
    ctx, at, df, me, opp = mk()
    me.hand = []
    me.disc_energy.clear()                                        # no Lightning to recover
    assert fn(LEVINCIA)(TE.TrainerCtx(me, opp, ctx.game)) is False
    assert me.hand == []


# ---- the 11 passive-aura / rules-mod stadiums: state-neutral no-ops ----
def _make_noop_test(name, text):
    def t():
        ctx, at, df, me, opp = mk()
        me.hand = [('E', 'Colorless')]
        at.damage = 40
        h0, d0, dmg0 = list(me.hand), list(me.deck), at.damage
        r = fn(text)(TE.TrainerCtx(me, opp, ctx.game))
        assert not r, f"{name}: expected no-op action"
        assert me.hand == h0 and me.deck == d0 and at.damage == dmg0, f"{name}: mutated state"
    t.__name__ = 't_noop_' + name
    return t


for _nm, _tx in NOOPS.items():
    TESTS.append(_make_noop_test(_nm, _tx))


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
