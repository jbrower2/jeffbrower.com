#!/usr/bin/env python3
"""Unit tests for batch ab_search_0 (deck-search abilities). Each ability's registered lambda is run
directly against real Mon/Player state via mk(); positive effect + a condition/negative branch are
covered. Run: python3 -m abilities_gen.test_batch_ab_search_0."""
from collections import Counter
from effects_testkit import mk, runner
import ability_effects as AB
import abilities_gen.batch_ab_search_0  # noqa: F401  (registers the abilities)
from engine import Mon
from cards import load_cards

BK, BN = load_cards()
FAN_ROTOM = BN['Fan Rotom'][0]                              # Colorless, 70 HP
FEAROW100 = next(c for c in BN['Fearow']                    # Colorless, exactly 100 HP (boundary)
                 if c.ptype == 'Colorless' and c.hp == 100)
UNFEZANT = BN['Unfezant'][0]                                # Colorless, 150 HP, Stage 2
DRILBUR = BN['Drilbur'][0]                                  # Fighting
CYN_GABITE = BN["Cynthia's Gabite"][0]
ERIKA_TANGELA = BN["Erika's Tangela"][0]
ERIKA_ODDISH = BN["Erika's Oddish"][0]                      # a 2nd Erika's (assert only 1 taken)
SILCOON = BN['Silcoon'][0]
CASCOON = BN['Cascoon'][0]
SHEDINJA = BN['Shedinja'][0]
PIDOVE = next(c for c in BN['Pidove'] if c.hp == 60)        # BLK Pidove, 60 HP
PALAFIN = next(c for c in BN['Palafin'] if c.set == 'SV06') # the Zero-to-Hero printing
PALAFIN_EX = BN['Palafin ex'][0]
GOLDEEN_FL = next(c for c in BK.values()                    # a real Festival Lead holder
                  if any(ab.get('name') == 'Festival Lead' for ab in c.abilities))
VANILLA = BN['Bulbasaur'][0]

STADIUM_TOK = ('T', {'name': 'Test Stadium', 'trainerType': 'Stadium'})
TOOL_TOK = ('T', {'name': 'Test Tool', 'trainerType': 'Tool'})
ADVENTURE_TOK = ('T', {'name': "Ethan's Adventure", 'trainerType': 'Supporter'})
OTHER_SUP = ('T', {'name': 'Professor', 'trainerType': 'Supporter'})

K_fan = "- Once during your first turn, you may search your deck for up to 3 {C} Pokémon with 100 HP or less, reveal them, and put them into your hand. Then, shuffle your deck. You can't use more than 1 Fan Call Ability during your turn."
K_champ = "- Once during your turn, you may search your deck for a Cynthia's Pokémon, reveal it, and put it into your hand. Then, shuffle your deck."
K_carrier = "- When you play this Pokémon from your hand onto your Bench during your turn, you may search your deck for a Pokémon Tool card and attach it to this Pokémon. Then, shuffle your deck."
K_blossom = "- Once during your turn, you may use this Ability. Search your deck for an Erika's Pokémon, reveal it, and put it into your hand. Then, shuffle your deck."
K_bonded = "- Once during your turn, you may search your deck for an Ethan's Adventure card, reveal it, and put it into your hand. Then, shuffle your deck."
K_cocoon = "- Once during your turn, when you play this Pokémon from your hand to evolve 1 of your Pokémon, you may use this Ability. Search your deck for a Silcoon or a Cascoon and put it onto your Bench. Then, shuffle your deck."
K_shell = "- Once during your turn, when you play this Pokémon from your hand to evolve 1 of your Pokémon, you may use this Ability. Search your deck for a Shedinja and put it onto your Bench. Then, shuffle your deck."
K_emerg = "- Once during your turn, if this Pokémon's remaining HP is 30 or less, you may search your deck for an Unfezant or Unfezant ex and put it onto this Pidove to evolve it. Then, shuffle your deck."
K_dig = "- When you play this Pokémon from your hand onto your Bench during your turn, you may search your deck for up to 3 Basic {F} Energy cards and discard them. Then, shuffle your deck."
K_season = "- Once during your turn, you may search your deck for a Stadium card, reveal it, and put it into your hand. Then, shuffle your deck."
K_scent = "- Once during your turn, you may use this Ability. Search your deck for up to 2 Basic {P} Energy cards, reveal them, and put them into your hand. Then, shuffle your deck."
K_boom = "- Once during your turn, if your Active Pokémon has the Festival Lead Ability, you may search your deck for a card and put it into your hand. Then, shuffle your deck."
K_zero = "- Once during your turn, when this Pokémon moves from the Active Spot to the Bench, you may search your deck for a Palafin ex and switch it with this Pokémon. Any attached cards, damage counters, Special Conditions, turns in play, and any other effects remain on the new Pokémon. If you switched a Pokémon in this way, put this card into your deck. Then, shuffle your deck."


def _fn(key):
    return AB.ABILITY_EFFECTS[AB.normalize(key)]['fn']


def _ctx(me, opp, mon, ctx):
    return AB.ActivatedCtx(me, opp, mon, ctx.game)


# ---------------------------------------------------------------- Fan Call
def t_fan_call():
    ctx, at, df, me, opp = mk()
    me.hand = []
    me.deck = [('P', FAN_ROTOM), ('P', UNFEZANT), ('P', DRILBUR), ('P', FAN_ROTOM), ('P', FEAROW100)]
    assert _fn(K_fan)(_ctx(me, opp, at, ctx)) is True
    names = [t[1].name for t in me.hand]
    assert names.count('Fan Rotom') == 2                    # both Colorless <=100 HP grabbed
    assert 'Fearow' in names                                # exactly 100 HP -> included (boundary of "or less")
    assert 'Unfezant' not in names                          # Colorless but 150 HP -> excluded
    assert ('P', DRILBUR) in me.deck                        # Fighting -> excluded, stays in deck


def t_fan_call_cap():
    ctx, at, df, me, opp = mk()
    me.hand = []
    me.deck = [('P', FAN_ROTOM)] * 4                        # 4 eligible, but "up to 3"
    assert _fn(K_fan)(_ctx(me, opp, at, ctx)) is True
    assert len(me.hand) == 3                                # capped at 3
    assert me.deck.count(('P', FAN_ROTOM)) == 1             # one left behind


def t_fan_call_none():
    ctx, at, df, me, opp = mk()
    me.hand = []
    me.deck = [('P', DRILBUR), ('E', 'Colorless')]          # no Colorless Pokémon
    assert _fn(K_fan)(_ctx(me, opp, at, ctx)) is False
    assert me.hand == []


# ---------------------------------------------------------------- Champion's Call
def t_champions_call():
    ctx, at, df, me, opp = mk()
    me.hand = []
    me.deck = [('P', DRILBUR), ('P', CYN_GABITE)]
    assert _fn(K_champ)(_ctx(me, opp, at, ctx)) is True
    assert [t[1].name for t in me.hand] == ["Cynthia's Gabite"]
    assert ('P', DRILBUR) in me.deck                        # only the one Cynthia's card taken


def t_champions_call_none():
    ctx, at, df, me, opp = mk()
    me.hand = []
    me.deck = [('P', DRILBUR)]
    assert _fn(K_champ)(_ctx(me, opp, at, ctx)) is False


# ---------------------------------------------------------------- Gathering of Blossoms
def t_gathering_of_blossoms():
    ctx, at, df, me, opp = mk()
    me.hand = []
    me.deck = [('P', ERIKA_TANGELA), ('P', ERIKA_ODDISH), ('P', DRILBUR)]   # 2 Erika's present
    assert _fn(K_blossom)(_ctx(me, opp, at, ctx)) is True
    grabbed = [t[1].name for t in me.hand]
    assert len(grabbed) == 1 and grabbed[0].startswith("Erika's")           # only ONE taken
    assert sum(1 for t in me.deck if t[1].name.startswith("Erika's")) == 1  # the other stays
    assert ('P', DRILBUR) in me.deck                                        # non-Erika's untouched


def t_gathering_of_blossoms_none():
    ctx, at, df, me, opp = mk()
    me.hand = []
    me.deck = [('P', DRILBUR)]                              # no Erika's Pokémon
    assert _fn(K_blossom)(_ctx(me, opp, at, ctx)) is False
    assert me.hand == []


# ---------------------------------------------------------------- Bonded by the Journey
def t_bonded_by_the_journey():
    ctx, at, df, me, opp = mk()
    me.hand = []
    me.deck = [OTHER_SUP, ADVENTURE_TOK]
    assert _fn(K_bonded)(_ctx(me, opp, at, ctx)) is True
    assert me.hand == [ADVENTURE_TOK]
    assert OTHER_SUP in me.deck                             # unrelated Supporter untouched


def t_bonded_by_the_journey_none():
    ctx, at, df, me, opp = mk()
    me.hand = []
    me.deck = [OTHER_SUP]                                   # no Ethan's Adventure present
    assert _fn(K_bonded)(_ctx(me, opp, at, ctx)) is False


# ---------------------------------------------------------------- Impromptu Carrier
def t_impromptu_carrier():
    ctx, at, df, me, opp = mk()
    me.hand = []
    me.deck = [OTHER_SUP, TOOL_TOK]
    assert _fn(K_carrier)(_ctx(me, opp, at, ctx)) is True
    assert at.tools == ['Test Tool']                       # Tool attached to this Pokémon
    assert TOOL_TOK not in me.deck                          # pulled out of the deck
    assert me.hand == []                                   # attached, not put into hand
    assert OTHER_SUP in me.deck                             # unrelated card untouched


def t_impromptu_carrier_none():
    ctx, at, df, me, opp = mk()
    me.hand = []
    me.deck = [OTHER_SUP]
    assert _fn(K_carrier)(_ctx(me, opp, at, ctx)) is False
    assert at.tools == []                                  # no Tool found -> nothing attached


# ---------------------------------------------------------------- Changing Seasons
def t_changing_seasons():
    ctx, at, df, me, opp = mk()
    me.hand = []
    me.deck = [('P', DRILBUR), STADIUM_TOK]
    assert _fn(K_season)(_ctx(me, opp, at, ctx)) is True
    assert me.hand == [STADIUM_TOK]


def t_changing_seasons_none():
    ctx, at, df, me, opp = mk()
    me.hand = []
    me.deck = [('P', DRILBUR)]
    assert _fn(K_season)(_ctx(me, opp, at, ctx)) is False


# ---------------------------------------------------------------- Scent Collection
def t_scent_collection():
    ctx, at, df, me, opp = mk()
    me.hand = []
    me.deck = [('E', 'Psychic'), ('E', 'Fighting'), ('E', 'Psychic'), ('E', 'Psychic')]
    assert _fn(K_scent)(_ctx(me, opp, at, ctx)) is True
    assert [t for t in me.hand] == [('E', 'Psychic'), ('E', 'Psychic')]   # up to 2
    assert me.deck.count(('E', 'Psychic')) == 1            # one Psychic left behind


def t_scent_collection_none():
    ctx, at, df, me, opp = mk()
    me.hand = []
    me.deck = [('E', 'Fighting')]
    assert _fn(K_scent)(_ctx(me, opp, at, ctx)) is False


# ---------------------------------------------------------------- Boom Boom Groove
def t_boom_boom_groove():
    ctx, at, df, me, opp = mk()
    me.active = Mon(GOLDEEN_FL)                             # Active has Festival Lead
    me.hand = []
    me.deck = [('E', 'Colorless'), ('P', DRILBUR)]
    assert _fn(K_boom)(_ctx(me, opp, me.active, ctx)) is True
    assert len(me.hand) == 1                               # one card drawn to hand


def t_boom_boom_groove_no_festival():
    ctx, at, df, me, opp = mk()
    me.active = Mon(VANILLA)                                # no Festival Lead ability
    me.hand = []
    me.deck = [('P', DRILBUR)]
    assert _fn(K_boom)(_ctx(me, opp, me.active, ctx)) is False
    assert me.hand == []


# ---------------------------------------------------------------- Dig Dig Dig
def t_dig_dig_dig():
    ctx, at, df, me, opp = mk()
    me.disc_energy = Counter()
    me.deck = [('E', 'Fighting'), ('E', 'Colorless'), ('E', 'Fighting'),
               ('E', 'Fighting'), ('E', 'Fighting')]
    assert _fn(K_dig)(_ctx(me, opp, at, ctx)) is True
    assert me.disc_energy['Fighting'] == 3                 # up to 3 discarded
    assert me.deck.count(('E', 'Fighting')) == 1           # one Fighting left in deck
    assert ('E', 'Colorless') in me.deck                   # non-Fighting untouched


def t_dig_dig_dig_none():
    ctx, at, df, me, opp = mk()
    me.disc_energy = Counter()
    me.deck = [('E', 'Colorless')]
    assert _fn(K_dig)(_ctx(me, opp, at, ctx)) is False
    assert me.disc_energy['Fighting'] == 0


# ---------------------------------------------------------------- Multiplying Cocoon
def t_multiplying_cocoon():
    ctx, at, df, me, opp = mk()
    me.bench = []
    me.deck = [('P', DRILBUR), ('P', CASCOON)]
    assert _fn(K_cocoon)(_ctx(me, opp, at, ctx)) is True
    assert len(me.bench) == 1 and me.bench[0].card.name == 'Cascoon'   # Stage-1 benched directly
    assert ('P', CASCOON) not in me.deck


def t_multiplying_cocoon_bench_full():
    ctx, at, df, me, opp = mk()
    me.bench = [Mon(VANILLA) for _ in range(5)]            # no room
    me.deck = [('P', SILCOON)]
    assert _fn(K_cocoon)(_ctx(me, opp, at, ctx)) is False
    assert ('P', SILCOON) in me.deck


# ---------------------------------------------------------------- Cast-Off Shell
def t_cast_off_shell():
    ctx, at, df, me, opp = mk()
    me.bench = []
    me.deck = [('P', DRILBUR), ('P', SHEDINJA)]
    assert _fn(K_shell)(_ctx(me, opp, at, ctx)) is True
    assert len(me.bench) == 1 and me.bench[0].card.name == 'Shedinja'
    assert ('P', SHEDINJA) not in me.deck


def t_cast_off_shell_none():
    ctx, at, df, me, opp = mk()
    me.bench = []
    me.deck = [('P', DRILBUR)]                              # no Shedinja
    assert _fn(K_shell)(_ctx(me, opp, at, ctx)) is False
    assert me.bench == []


# ---------------------------------------------------------------- Emergency Evolution
def t_emergency_evolution():
    ctx, at, df, me, opp = mk()
    pid = Mon(PIDOVE); pid.damage = 40; pid.energy = Counter({'Colorless': 1})  # hp_left 20 <= 30
    me.active = pid
    me.deck = [('P', UNFEZANT)]
    assert _fn(K_emerg)(_ctx(me, opp, pid, ctx)) is True
    assert me.active.card.name == 'Unfezant'               # evolved in place (skipped Tranquill)
    assert me.active.damage == 40                          # damage carried over
    assert me.active.energy['Colorless'] == 1              # attached energy carried
    assert ('P', UNFEZANT) not in me.deck


def t_emergency_evolution_healthy():
    ctx, at, df, me, opp = mk()
    pid = Mon(PIDOVE); pid.damage = 0                       # hp_left 60 > 30 -> condition fails
    me.active = pid
    me.deck = [('P', UNFEZANT)]
    assert _fn(K_emerg)(_ctx(me, opp, pid, ctx)) is False
    assert me.active.card.name == 'Pidove'
    assert ('P', UNFEZANT) in me.deck


# ---------------------------------------------------------------- Zero to Hero
def t_zero_to_hero():
    ctx, at, df, me, opp = mk()
    pal = Mon(PALAFIN); pal.damage = 30; pal.energy = Counter({'Water': 2}); pal.turns = 3
    me.bench = [pal]
    me.deck = [('P', PALAFIN_EX)]
    assert _fn(K_zero)(_ctx(me, opp, pal, ctx)) is True
    assert me.bench[0].card.name == 'Palafin ex'           # swapped into the same Bench slot
    assert me.bench[0].damage == 30 and me.bench[0].turns == 3
    assert me.bench[0].energy['Water'] == 2                # attached cards remain
    assert ('P', PALAFIN_EX) not in me.deck
    assert ('P', PALAFIN) in me.deck                       # this Palafin card returned to deck


def t_zero_to_hero_not_benched():
    ctx, at, df, me, opp = mk()
    pal = Mon(PALAFIN)
    me.active = pal; me.bench = []                          # still Active -> ability doesn't trigger
    me.deck = [('P', PALAFIN_EX)]
    assert _fn(K_zero)(_ctx(me, opp, pal, ctx)) is False
    assert ('P', PALAFIN_EX) in me.deck


def t_zero_to_hero_no_target():
    ctx, at, df, me, opp = mk()
    pal = Mon(PALAFIN)
    me.bench = [pal]
    me.deck = [('P', DRILBUR)]                              # no Palafin ex in deck
    assert _fn(K_zero)(_ctx(me, opp, pal, ctx)) is False


TESTS = [
    t_fan_call, t_fan_call_cap, t_fan_call_none,
    t_champions_call, t_champions_call_none,
    t_gathering_of_blossoms, t_gathering_of_blossoms_none,
    t_bonded_by_the_journey, t_bonded_by_the_journey_none,
    t_impromptu_carrier, t_impromptu_carrier_none,
    t_changing_seasons, t_changing_seasons_none,
    t_scent_collection, t_scent_collection_none,
    t_boom_boom_groove, t_boom_boom_groove_no_festival,
    t_dig_dig_dig, t_dig_dig_dig_none,
    t_multiplying_cocoon, t_multiplying_cocoon_bench_full,
    t_cast_off_shell, t_cast_off_shell_none,
    t_emergency_evolution, t_emergency_evolution_healthy,
    t_zero_to_hero, t_zero_to_hero_not_benched, t_zero_to_hero_no_target,
]

if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
