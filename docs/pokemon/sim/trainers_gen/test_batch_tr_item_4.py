#!/usr/bin/env python3
"""Unit tests for trainer batch tr_item_4 (Items)."""
from collections import Counter
from effects_testkit import mk, runner
from engine import Mon
from cards import load_cards
import trainer_effects as TE
import trainers_gen.batch_tr_item_4        # noqa: F401  (registers the effects)

BK, BN = load_cards()


def pick(name, pred=lambda c: True):
    return next(c for c in BN[name] if pred(c))


def fn(text):
    return TE.TRAINER_EFFECTS[TE.normalize(text)]['fn']


def tctx(me, opp, ctx):
    return TE.TrainerCtx(me, opp, ctx.game)


GREAT_BALL = ("Flip a coin. If heads, search your deck for an Evolution Team Rocket's Pokémon, reveal it, "
              "and put it into your hand. If tails, search your deck for a Basic Team Rocket's Pokémon, "
              "reveal it, and put it into your hand. Then, shuffle your deck.")
TRANSCEIVER = ("Search your deck for a Supporter card that has \"Team Rocket\" in its name, reveal it, "
               "and put it into your hand. Then, shuffle your deck.")
VENTURE_BOMB = ("Flip a coin. If heads, put 2 damage counters on 1 of your opponent's Pokémon. "
                "If tails, put 2 damage counters on your Active Pokémon.")
TECHNO_RADAR = ("You can use this card only if you discard another card from your hand.\n\n"
                "Search your deck for up to 2 Future Pokémon, reveal them, and put them into your hand. "
                "Then, shuffle your deck.")
TERA_ORB = "Search your deck for a Tera Pokémon, reveal it, and put it into your hand. Then, shuffle your deck."
TOOL_SCRAPPER = "Choose up to 2 Pokémon Tools attached to Pokémon (yours or your opponent's) and discard them."
TRANSFORM_TOME = ("You must play 2 Transformation Tome cards at once. (This effect works one time for 2 cards.)\n\n"
                  "Choose a Basic Pokémon in your discard pile and switch it with 1 of your Basic Pokémon in play. "
                  "Any attached cards, damage counters, Special Conditions, turns in play, and any other effects "
                  "remain on the new Pokémon.")
ULTRA_BALL = ("You can use this card only if you discard 2 other cards from your hand.\n\n"
              "Search your deck for a Pokémon, reveal it, and put it into your hand. Then, shuffle your deck.")
WONDROUS_PATCH = "Attach a Basic {P} Energy card from your discard pile to 1 of your Benched {P} Pokémon."

TESTS = []
def test(f): TESTS.append(f); return f


# ---------- Team Rocket's Great Ball ----------
@test
def t_great_ball_heads():                              # heads -> Evolution TR Pokémon
    ctx, at, df, me, opp = mk(flips=(0.0,))
    arbok = pick("Team Rocket's Arbok", lambda c: c.stage > 0)
    ekans = pick("Team Rocket's Ekans", lambda c: c.stage == 0)
    me.deck = [('P', arbok), ('P', ekans)]
    did = fn(GREAT_BALL)(tctx(me, opp, ctx))
    assert did and any(t[0] == 'P' and t[1].name == "Team Rocket's Arbok" for t in me.hand)


@test
def t_great_ball_tails():                              # tails -> Basic TR Pokémon
    ctx, at, df, me, opp = mk(flips=(0.9,))
    arbok = pick("Team Rocket's Arbok", lambda c: c.stage > 0)
    ekans = pick("Team Rocket's Ekans", lambda c: c.stage == 0)
    me.deck = [('P', arbok), ('P', ekans)]
    did = fn(GREAT_BALL)(tctx(me, opp, ctx))
    assert did and any(t[0] == 'P' and t[1].name == "Team Rocket's Ekans" for t in me.hand)
    assert not any(t[1].name == "Team Rocket's Arbok" for t in me.hand if t[0] == 'P')


# ---------- Team Rocket's Transceiver ----------
@test
def t_transceiver():
    ctx, at, df, me, opp = mk()
    tr_sup = {'name': "Team Rocket's Giovanni", 'trainerType': 'Supporter', 'effect': 'x'}
    other = {'name': 'Professor Oak', 'trainerType': 'Supporter', 'effect': 'y'}
    me.deck = [('T', tr_sup), ('T', other)]
    did = fn(TRANSCEIVER)(tctx(me, opp, ctx))
    assert did
    assert any(t[0] == 'T' and t[1]['name'] == "Team Rocket's Giovanni" for t in me.hand)
    assert not any(t[0] == 'T' and t[1]['name'] == 'Professor Oak' for t in me.hand)


@test
def t_transceiver_miss():                              # no TR supporter -> no-op
    ctx, at, df, me, opp = mk()
    me.deck = [('T', {'name': 'Professor Oak', 'trainerType': 'Supporter'})]
    assert fn(TRANSCEIVER)(tctx(me, opp, ctx)) is False


# ---------- Team Rocket's Venture Bomb ----------
@test
def t_venture_bomb_heads():                            # heads -> opponent takes 20
    ctx, at, df, me, opp = mk(flips=(0.0,), opp_bench=0)
    df.damage = 0
    did = fn(VENTURE_BOMB)(tctx(me, opp, ctx))
    assert did and opp.active.damage == 20 and at.damage == 0


@test
def t_venture_bomb_tails():                            # tails -> your Active takes 20
    ctx, at, df, me, opp = mk(flips=(0.9,))
    at.damage = 0
    did = fn(VENTURE_BOMB)(tctx(me, opp, ctx))
    assert did and at.damage == 20 and df.damage == 0


# ---------- Techno Radar ----------
@test
def t_techno_radar():                                  # discard 1, fetch up to 2 Future ("Iron") Pokémon
    ctx, at, df, me, opp = mk()
    iron = pick('Iron Hands', lambda c: c.stage == 0)
    me.deck = [('P', iron)]
    me.hand = [('E', 'Colorless')]                     # the "another card" to discard
    did = fn(TECHNO_RADAR)(tctx(me, opp, ctx))
    assert did
    assert any(t[0] == 'P' and t[1].name == 'Iron Hands' for t in me.hand)
    assert me.disc_energy['Colorless'] == 1            # cost paid
    assert not any(t[0] == 'E' for t in me.hand)


@test
def t_techno_radar_no_cost():                          # empty hand -> can't pay -> no-op
    ctx, at, df, me, opp = mk()
    me.deck = [('P', pick('Iron Hands', lambda c: c.stage == 0))]
    me.hand = []
    assert fn(TECHNO_RADAR)(tctx(me, opp, ctx)) is False


# ---------- Tera Orb ----------
@test
def t_tera_orb_noop():                                 # Tera subtype unmodeled -> conservative no-op
    ctx, at, df, me, opp = mk()
    before = list(me.hand)
    assert fn(TERA_ORB)(tctx(me, opp, ctx)) is False
    assert me.hand == before


# ---------- Tool Scrapper ----------
@test
def t_tool_scrapper():                                 # strip up to 2 opponent Tools, leave mine
    ctx, at, df, me, opp = mk(opp_bench=1)
    df.tools = ['Defender']
    opp.bench[0].tools = ['Muscle Band']
    at.tools = ['MyTool']                              # my own Tool must survive
    did = fn(TOOL_SCRAPPER)(tctx(me, opp, ctx))
    assert did
    assert df.tools == [] and opp.bench[0].tools == []
    assert at.tools == ['MyTool']
    assert len(opp.discard) == 2


@test
def t_tool_scrapper_none():                            # opponent has no Tools -> no-op
    ctx, at, df, me, opp = mk()
    assert fn(TOOL_SCRAPPER)(tctx(me, opp, ctx)) is False


# ---------- Transformation Tome ----------
@test
def t_transformation_tome():                           # swap a stronger Basic from discard onto an in-play Basic, keep state
    ctx, at, df, me, opp = mk()
    strong = pick('Iron Bundle', lambda c: c.stage == 0)   # 200-dmg attacker, 100 HP
    old_card = at.card
    at.energy = Counter({'Water': 2})
    at.damage = 10
    me.discard = [('P', strong)]
    did = fn(TRANSFORM_TOME)(tctx(me, opp, ctx))
    assert did
    assert at.card.name == 'Iron Bundle'               # identity swapped in
    assert at.energy == Counter({'Water': 2})          # energy preserved
    assert at.damage == 10                             # damage counters preserved
    assert ('P', old_card) in me.discard               # old Basic sent to discard
    assert not any(t[1].name == 'Iron Bundle' for t in me.discard if t[0] == 'P')


@test
def t_transformation_tome_empty():                     # nothing in discard -> no-op
    ctx, at, df, me, opp = mk()
    me.discard = []
    assert fn(TRANSFORM_TOME)(tctx(me, opp, ctx)) is False


# ---------- Ultra Ball ----------
@test
def t_ultra_ball():                                    # discard 2, fetch any Pokémon
    ctx, at, df, me, opp = mk()
    poke = pick('Iron Hands', lambda c: c.stage == 0)
    me.deck = [('P', poke)]
    me.hand = [('E', 'Colorless'), ('E', 'Colorless')]
    did = fn(ULTRA_BALL)(tctx(me, opp, ctx))
    assert did
    assert any(t[0] == 'P' for t in me.hand)
    assert me.disc_energy['Colorless'] == 2            # 2-card cost paid
    assert not any(t[0] == 'E' for t in me.hand)


@test
def t_ultra_ball_no_cost():                            # fewer than 2 other cards -> no-op
    ctx, at, df, me, opp = mk()
    me.deck = [('P', pick('Iron Hands', lambda c: c.stage == 0))]
    me.hand = [('E', 'Colorless')]
    assert fn(ULTRA_BALL)(tctx(me, opp, ctx)) is False


# ---------- Wondrous Patch ----------
@test
def t_wondrous_patch():                                # move a basic Psychic energy from discard to a benched Psychic mon
    ctx, at, df, me, opp = mk()
    clef = pick('Clefairy', lambda c: c.ptype == 'Psychic' and c.stage == 0)
    me.bench = [Mon(clef)]
    me.disc_energy = Counter({'Psychic': 2})
    did = fn(WONDROUS_PATCH)(tctx(me, opp, ctx))
    assert did
    assert me.bench[0].energy['Psychic'] == 1
    assert me.disc_energy['Psychic'] == 1


@test
def t_wondrous_patch_no_energy():                      # no Psychic energy in discard -> no-op
    ctx, at, df, me, opp = mk()
    clef = pick('Clefairy', lambda c: c.ptype == 'Psychic' and c.stage == 0)
    me.bench = [Mon(clef)]
    me.disc_energy = Counter()
    assert fn(WONDROUS_PATCH)(tctx(me, opp, ctx)) is False


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
