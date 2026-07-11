#!/usr/bin/env python3
"""Unit tests for trainer batch tr_item_2 (14 Items). Each Item action runs through a real
TrainerCtx over engine Player/Game objects; we assert the concrete state change."""
from effects_testkit import mk, runner
from engine import Mon
from cards import load_cards
import trainer_effects as TE
import trainers_gen.batch_tr_item_2   # noqa: F401  (registers the effects)

BK, _ = load_cards()


def _fn(text):
    return TE.TRAINER_EFFECTS[TE.normalize(text)]['fn']


def action(text, **kw):
    """Build state, run the Item's effect via TrainerCtx, return (did, me, opp, at, df, game)."""
    ctx, at, df, me, opp = mk(**kw)
    did = _fn(text)(TE.TrainerCtx(me, opp, ctx.game))
    return did, me, opp, at, df, ctx.game


# concrete cards for the named-family / typed tests
HOPS = next(c for c in BK.values() if c.name.startswith("Hop's") and c.stage == 0)
NS = next(c for c in BK.values() if c.name.startswith("N's") and c.stage == 0)
MEGA = next(c for c in BK.values() if c.name.startswith('Mega ') and c.is_ex)
METAL = next(c for c in BK.values() if c.ptype == 'Metal')
_ogres = []
for _c in BK.values():
    if _c.is_ex and 'Ogerpon' in _c.name and _c.name not in {o.name for o in _ogres}:
        _ogres.append(_c)
    if len(_ogres) == 2:
        break
OGRE1, OGRE2 = _ogres

TESTS = []
def test(f): TESTS.append(f); return f

T_HAND_TRIMMER = "Each player discards cards from their hand until they have 5 cards in their hand. Your opponent discards first. (If a player has 5 or fewer cards in their hand, they do not discard.)"
T_SHOVEL = "Discard the top 2 cards of your deck."
T_HOPS = "Search your deck for up to 2 Basic Hop's Pokémon and put them onto your Bench. Then, shuffle your deck."
T_IRON = "During your opponent's next turn, all of your {M} Pokémon take 30 less damage from attacks from your opponent's Pokémon (after applying Weakness and Resistance). (This includes new Pokémon that come into play.)"
T_JUMBO = "Heal 80 damage from your Active Pokémon that has 3 or more Energy attached."
T_LOVE = "Search your deck for a Pokémon with the same name as 1 of your opponent's Pokémon in play, reveal it, and put it into your hand. Then, shuffle your deck."
T_GALETTE = "Heal 20 damage and remove a Special Condition from your Active Pokémon."
T_MEMO = "Your opponent counts the cards in their hand, shuffles those cards, and puts them on the bottom of their deck. If they do, they draw that many cards."
T_MEGA_SIG = "Search your deck for a Mega Evolution Pokémon ex, reveal it, and put it into your hand. Then, shuffle your deck."
T_NS_PP = "Attach a Basic Energy card from your discard pile to 1 of your Benched N's Pokémon."
T_NIGHT = "Put a Pokémon or a Basic Energy card from your discard pile into your hand."
T_OGRE = 'Choose a Pokémon ex in your discard pile that has "Ogerpon" in its name, and switch it with 1 of your Pokémon ex in play that has "Ogerpon" in its name. Any attached cards, damage counters, Special Conditions, turns in play, and any other effects remain on the new Pokémon.'
T_POKEBALL = "Flip a coin. If heads, search your deck for a Pokémon, reveal it, and put it into your hand. Then, shuffle your deck."
T_POKEPAD = "Search your deck for a Pokémon that doesn't have a Rule Box, reveal it, and put it into your hand. Then, shuffle your deck. (Pokémon ex, Pokémon V, etc. have Rule Boxes.)"


@test
def t_hand_trimmer():
    ctx, at, df, me, opp = mk()
    me.hand = [('E', 'Fire')] * 7
    opp.hand = [('E', 'Fire')] * 8
    did = _fn(T_HAND_TRIMMER)(TE.TrainerCtx(me, opp, ctx.game))
    assert did and len(me.hand) == 5 and len(opp.hand) == 5
    assert me.disc_energy['Fire'] == 2 and opp.disc_energy['Fire'] == 3
    # no-op when both already at/under 5
    ctx2, *_ , me2, opp2 = mk()
    me2.hand = [('E', 'Fire')] * 3; opp2.hand = [('E', 'Fire')] * 5
    assert _fn(T_HAND_TRIMMER)(TE.TrainerCtx(me2, opp2, ctx2.game)) is False


@test
def t_hole_digging_shovel():
    did, me, opp, at, df, g = action(T_SHOVEL)
    # default deck top 2 are ('E','Colorless') -> routed to disc_energy
    assert did and len(me.deck) == 14 and me.disc_energy['Colorless'] == 2


@test
def t_hops_bag():
    ctx, at, df, me, opp = mk(my_bench=0)
    me.deck += [('P', HOPS), ('P', HOPS)]
    did = _fn(T_HOPS)(TE.TrainerCtx(me, opp, ctx.game))
    assert did and len(me.bench) == 2 and all(m.card.name.startswith("Hop's") for m in me.bench)


@test
def t_iron_defender():
    ctx, at, df, me, opp = mk(my_bench=0)
    me.active = Mon(METAL)                         # Metal-type active
    me.bench = [Mon(next(c for c in BK.values() if c.ptype != 'Metal' and c.stage == 0))]
    did = _fn(T_IRON)(TE.TrainerCtx(me, opp, ctx.game))
    assert did and me.active.dr_amount == 30 and me.active.dr_turn == ctx.game.turn
    assert me.bench[0].dr_turn == -9               # non-Metal not buffed


@test
def t_jumbo_ice_cream():
    ctx, at, df, me, opp = mk(atk_energy={'Colorless': 3})
    at.damage = 100
    assert _fn(T_JUMBO)(TE.TrainerCtx(me, opp, ctx.game)) and at.damage == 20
    # not enough energy -> no heal
    ctx2, at2, df2, me2, opp2 = mk(atk_energy={'Colorless': 2})
    at2.damage = 50
    assert _fn(T_JUMBO)(TE.TrainerCtx(me2, opp2, ctx2.game)) is False and at2.damage == 50


@test
def t_love_ball():
    ctx, at, df, me, opp = mk(opp_bench=0)
    opp.active = Mon(HOPS)                          # opponent's only in-play name
    me.deck += [('P', HOPS)]
    did = _fn(T_LOVE)(TE.TrainerCtx(me, opp, ctx.game))
    got = [x for x in me.hand if x[0] == 'P']
    assert did and any(x[1].name == HOPS.name for x in got)


@test
def t_lumiose_galette():
    ctx, at, df, me, opp = mk()
    at.damage = 50; at.status = {'Asleep': True}
    did = _fn(T_GALETTE)(TE.TrainerCtx(me, opp, ctx.game))
    assert did and at.damage == 30 and 'Asleep' not in at.status


@test
def t_lumiose_galette_single_condition():
    # Verified vs the real card (pokemon.com / Bulbapedia): "remove a Special Condition" is SINGULAR
    # (identical to Big Malasada). With two conditions present, exactly one is removed — the
    # attack-blocker (Asleep) — and the damage condition (Poisoned) remains.
    ctx, at, df, me, opp = mk()
    at.damage = 30; at.status = {'Asleep': True, 'Poisoned': True}
    did = _fn(T_GALETTE)(TE.TrainerCtx(me, opp, ctx.game))
    assert did and at.damage == 10
    assert 'Asleep' not in at.status and 'Poisoned' in at.status


@test
def t_meddling_memo():
    ctx, at, df, me, opp = mk()
    tag = ('T', {'name': 'MEMO_TAG'})
    opp.hand = [tag, tag, tag]
    before_deck = len(opp.deck)
    did = _fn(T_MEMO)(TE.TrainerCtx(me, opp, ctx.game))
    assert did and len(opp.hand) == 3 and len(opp.deck) == before_deck
    assert not any(x[0] == 'T' and x[1].get('name') == 'MEMO_TAG' for x in opp.hand)  # old hand went to bottom


@test
def t_mega_signal():
    ctx, at, df, me, opp = mk()
    me.deck += [('P', MEGA)]
    did = _fn(T_MEGA_SIG)(TE.TrainerCtx(me, opp, ctx.game))
    assert did and any(x[0] == 'P' and x[1].name.startswith('Mega ') and x[1].is_ex for x in me.hand)


@test
def t_ns_pp_up():
    ctx, at, df, me, opp = mk(my_bench=0)
    me.bench = [Mon(NS)]
    me.disc_energy['Darkness'] = 1
    did = _fn(T_NS_PP)(TE.TrainerCtx(me, opp, ctx.game))
    assert did and me.bench[0].energy['Darkness'] == 1 and me.disc_energy['Darkness'] == 0
    # no N's Pokémon on bench -> no-op
    ctx2, at2, df2, me2, opp2 = mk()
    me2.disc_energy['Fire'] = 1
    assert _fn(T_NS_PP)(TE.TrainerCtx(me2, opp2, ctx2.game)) is False


@test
def t_night_stretcher():
    # prefers a Pokémon when one is in the discard
    ctx, at, df, me, opp = mk()
    vanilla = next(x for x in me.deck if x[0] == 'P')
    me.discard = [vanilla]
    did = _fn(T_NIGHT)(TE.TrainerCtx(me, opp, ctx.game))
    assert did and any(x[0] == 'P' for x in me.hand) and not me.discard
    # falls back to a basic energy from disc_energy
    ctx2, at2, df2, me2, opp2 = mk()
    me2.discard = []; me2.disc_energy['Fire'] = 1
    did2 = _fn(T_NIGHT)(TE.TrainerCtx(me2, opp2, ctx2.game))
    assert did2 and ('E', 'Fire') in me2.hand and me2.disc_energy['Fire'] == 0


@test
def t_ogres_mask():
    ctx, at, df, me, opp = mk()
    me.active = Mon(OGRE1)
    me.active.energy['Grass'] = 2; me.active.damage = 40
    me.discard = [('P', OGRE2)]
    did = _fn(T_OGRE)(TE.TrainerCtx(me, opp, ctx.game))
    assert did and me.active.card.name == OGRE2.name
    assert me.active.energy['Grass'] == 2 and me.active.damage == 40      # state preserved
    assert ('P', OGRE1) in me.discard and ('P', OGRE2) not in me.discard  # old swapped into discard
    # no Ogerpon in play -> conservative no-op
    ctx2, at2, df2, me2, opp2 = mk()
    me2.discard = [('P', OGRE2)]
    assert _fn(T_OGRE)(TE.TrainerCtx(me2, opp2, ctx2.game)) is False


@test
def t_poke_ball():
    did, me, opp, at, df, g = action(T_POKEBALL, flips=(0.0,))   # heads
    assert did and any(x[0] == 'P' for x in me.hand)
    did2, me2, *_ = action(T_POKEBALL, flips=(0.9,))            # tails
    assert did2 is False


@test
def t_poke_pad():
    did, me, opp, at, df, g = action(T_POKEPAD)                 # default deck is all non-ex
    assert did and any(x[0] == 'P' and not x[1].is_ex for x in me.hand)
    # rejects Rule-Box (ex) Pokémon: an all-ex deck yields nothing
    ex = next(c for c in BK.values() if c.is_ex)
    ctx2, at2, df2, me2, opp2 = mk()
    me2.deck = [('P', ex)] * 3
    assert _fn(T_POKEPAD)(TE.TrainerCtx(me2, opp2, ctx2.game)) is False


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f"{p} pass {f} fail")
    raise SystemExit(1 if f else 0)
