#!/usr/bin/env python3
"""Unit tests for batch ab_activated_1 (once-per-turn activated abilities). Each registered lambda is
run directly against real Mon/Player state via mk() + AB.ActivatedCtx; positive effect + a
condition/negative branch (Active-Spot gate, effect-shield, missing target, coin branch) covered.
Run: python3 -m abilities_gen.test_batch_ab_activated_1."""
from collections import Counter
from effects_testkit import mk, runner
import ability_effects as AB
import abilities_gen.batch_ab_activated_1  # noqa: F401  (registers the abilities)
from engine import Mon
from cards import load_cards

BK, BN = load_cards()
VANILLA = next(c for c in BK.values() if c.cat == 'cat-green' and c.stage == 0)   # Bulbasaur, 80 HP
PHANTUMP = next(c for c in BN['Phantump'] if c.set == 'ME04')                     # has Spiteful Evolution
TREVENANT = next(c for c in BN['Trevenant'] if c.set == 'ME04')                   # evolves from Phantump
TR_ORBEETLE = BN["Team Rocket's Orbeetle"][0]                                     # 130 HP, Rocket Brain
SHIINOTIC = BN['Shiinotic'][0]                                                    # Calming Light
INDEEDEE = BN['Indeedee'][0]                                                      # Obliging Heal
TATSUGIRI = BN['Tatsugiri'][0]                                                    # Attract Customers

SUP_TOK = ('T', {'name': 'Professor', 'trainerType': 'Supporter'})
ITEM_TOK = ('T', {'name': 'Potion', 'trainerType': 'Item'})

K_spite = "- Once during your turn, you may use this Ability. Choose a card in your hand that evolves from this Pokémon and put it onto this Pokémon to evolve it. If you do, place 2 damage counters on the Pokémon you evolved in this way. You can't use this Ability during your first turn."
K_evid = "- Once during your turn, you may use this Ability. Switch a card from your hand with the top card of your deck."
K_snack = "- Once during your turn, you may look at the top card of your deck. You may discard that card."
K_attract = "- Once during your turn, if this Pokémon is in the Active Spot, you may look at the top 6 cards of your deck, reveal a Supporter card you find there, and put it into your hand. Shuffle the other cards back into your deck."
K_oblige = "- When you play this Pokémon from your hand onto your Bench during your turn, you may heal 30 damage from your Active Pokémon and have it recover from a Special Condition."
K_rocket = "- As often as you like during your turn, you may move 1 damage counter from 1 of your Team Rocket's Pokémon to another of your Pokémon."
K_calm = "- Once during your turn, if this Pokémon is in the Active Spot, you may make your opponent's Active Pokémon Asleep."
K_prison = "- Once during your turn, when you play this Pokémon from your hand to evolve 1 of your Pokémon, you may use this Ability. Make your opponent's Active Pokémon Confused."
K_hammer = "- Once during your turn, when you play this Pokémon from your hand to evolve 1 of your Pokémon, you may use this Ability. Flip a coin. If heads, discard an Energy from your opponent's Active Pokémon."


def _fn(key):
    return AB.ABILITY_EFFECTS[AB.normalize(key)]['fn']


def _ctx(me, opp, mon, ctx):
    return AB.ActivatedCtx(me, opp, mon, ctx.game)


# ---------------------------------------------------------------- Spiteful Evolution
def t_spiteful_evolution():
    ctx, at, df, me, opp = mk()
    ph = Mon(PHANTUMP); ph.damage = 10; ph.energy = Counter({'Psychic': 1}); ph.turns = 2
    me.active = ph
    me.hand = [('P', TREVENANT)]
    assert _fn(K_spite)(_ctx(me, opp, ph, ctx)) is True
    assert me.active.card.name == 'Trevenant'             # evolved in place
    assert me.active.damage == 30                         # 10 carried + 20 (2 counters placed)
    assert me.active.energy['Psychic'] == 1               # attached energy carried over
    assert ('P', TREVENANT) not in me.hand                # evolution card consumed


def t_spiteful_evolution_from_bench():
    ctx, at, df, me, opp = mk()
    ph = Mon(PHANTUMP)
    me.bench = [ph]
    me.hand = [('P', TREVENANT)]
    assert _fn(K_spite)(_ctx(me, opp, ph, ctx)) is True
    assert me.bench[0].card.name == 'Trevenant'           # benched holder evolves in its slot
    assert me.bench[0].damage == 20


def t_spiteful_evolution_no_target():
    ctx, at, df, me, opp = mk()
    ph = Mon(PHANTUMP)
    me.active = ph
    me.hand = [('E', 'Psychic'), ('P', VANILLA)]          # nothing that evolves from Phantump
    assert _fn(K_spite)(_ctx(me, opp, ph, ctx)) is False
    assert me.active.card.name == 'Phantump'


# ---------------------------------------------------------------- Evidence Gathering
def t_evidence_gathering():
    ctx, at, df, me, opp = mk()
    me.hand = [('E', 'Colorless'), ('P', VANILLA)]
    me.deck = [('P', VANILLA), ('P', TREVENANT)]          # top of deck = TREVENANT (deck[-1])
    assert _fn(K_evid)(_ctx(me, opp, at, ctx)) is True
    assert ('P', TREVENANT) in me.hand                    # old top pulled into hand now
    assert me.deck[-1] == ('E', 'Colorless')              # given spare energy is the new top
    assert len(me.hand) == 2 and len(me.deck) == 2        # sizes preserved (a swap, not a draw)


def t_evidence_gathering_empty_deck():
    ctx, at, df, me, opp = mk()
    me.hand = [('E', 'Colorless')]
    me.deck = []
    assert _fn(K_evid)(_ctx(me, opp, at, ctx)) is False   # no top card to switch with


def t_evidence_gathering_empty_hand():
    ctx, at, df, me, opp = mk()
    me.hand = []
    me.deck = [('P', VANILLA)]
    assert _fn(K_evid)(_ctx(me, opp, at, ctx)) is False   # nothing in hand to switch away
    assert me.deck == [('P', VANILLA)]                    # deck untouched


# ---------------------------------------------------------------- Snack Seek
def t_snack_seek_discards_energy():
    ctx, at, df, me, opp = mk()
    me.disc_energy = Counter()
    me.deck = [('P', VANILLA), ('E', 'Lightning')]        # top = Basic Energy -> discarded
    assert _fn(K_snack)(_ctx(me, opp, at, ctx)) is True
    assert me.disc_energy['Lightning'] == 1
    assert me.deck == [('P', VANILLA)]


def t_snack_seek_keeps_pokemon():
    ctx, at, df, me, opp = mk()
    me.deck = [('E', 'Lightning'), ('P', VANILLA)]        # top = Pokémon -> peeked, kept
    n = len(me.deck)
    assert _fn(K_snack)(_ctx(me, opp, at, ctx)) is False
    assert len(me.deck) == n                              # nothing discarded


# ---------------------------------------------------------------- Attract Customers
def t_attract_customers():
    ctx, at, df, me, opp = mk()
    me.active = Mon(TATSUGIRI)
    me.hand = []
    me.deck = [('P', VANILLA), ('P', VANILLA), SUP_TOK,   # SUP within the top 6 (deck[-6:])
               ('P', VANILLA), ('P', VANILLA), ('P', VANILLA), ('P', VANILLA)]
    assert _fn(K_attract)(_ctx(me, opp, me.active, ctx)) is True
    assert me.hand == [SUP_TOK]
    assert SUP_TOK not in me.deck


def t_attract_customers_ignores_non_supporter():
    ctx, at, df, me, opp = mk()
    me.active = Mon(TATSUGIRI)
    me.hand = []
    me.deck = [('P', VANILLA), ITEM_TOK]                  # an Item, not a Supporter -> no grab
    assert _fn(K_attract)(_ctx(me, opp, me.active, ctx)) is False
    assert me.hand == []


def t_attract_customers_too_deep():
    ctx, at, df, me, opp = mk()
    me.active = Mon(TATSUGIRI)
    me.hand = []
    me.deck = [SUP_TOK] + [('P', VANILLA)] * 6            # Supporter sits below the top 6
    assert _fn(K_attract)(_ctx(me, opp, me.active, ctx)) is False
    assert SUP_TOK in me.deck


def t_attract_customers_not_active():
    ctx, at, df, me, opp = mk()
    tatsu = Mon(TATSUGIRI)
    me.active = Mon(VANILLA); me.bench = [tatsu]          # holder benched -> Active-Spot gate fails
    me.deck = [SUP_TOK]
    assert _fn(K_attract)(_ctx(me, opp, tatsu, ctx)) is False
    assert SUP_TOK in me.deck


# ---------------------------------------------------------------- Obliging Heal
def t_obliging_heal():
    ctx, at, df, me, opp = mk()
    me.active.damage = 50
    me.active.status = {'Poisoned': True}
    indee = Mon(INDEEDEE)
    me.bench = [indee]                                    # Indeedee benched; heals the Active
    assert _fn(K_oblige)(_ctx(me, opp, indee, ctx)) is True
    assert me.active.damage == 20                         # healed 30
    assert 'Poisoned' not in me.active.status             # recovered from a condition


def t_obliging_heal_nothing_to_do():
    ctx, at, df, me, opp = mk()
    me.active.damage = 0
    me.active.status = {}
    indee = Mon(INDEEDEE); me.bench = [indee]
    assert _fn(K_oblige)(_ctx(me, opp, indee, ctx)) is False   # undamaged + status-free -> no benefit


def t_obliging_heal_removes_exactly_one_blocker_first():
    ctx, at, df, me, opp = mk()
    me.active.damage = 30
    me.active.status = {'Poisoned': True, 'Asleep': True}  # "a Special Condition" = remove ONE only
    indee = Mon(INDEEDEE); me.bench = [indee]
    assert _fn(K_oblige)(_ctx(me, opp, indee, ctx)) is True
    assert me.active.damage == 0                           # healed 30
    assert 'Asleep' not in me.active.status               # cured the attack-blocker...
    assert me.active.status.get('Poisoned')               # ...but only ONE condition, Poison remains


def t_obliging_heal_status_only():
    ctx, at, df, me, opp = mk()
    me.active.damage = 0                                   # no damage, status only
    me.active.status = {'Paralyzed': True}
    indee = Mon(INDEEDEE); me.bench = [indee]
    assert _fn(K_oblige)(_ctx(me, opp, indee, ctx)) is True
    assert me.active.damage == 0                           # heal is a no-op, still used for the cure
    assert 'Paralyzed' not in me.active.status


# ---------------------------------------------------------------- Rocket Brain
def t_rocket_brain():
    ctx, at, df, me, opp = mk()
    src = Mon(TR_ORBEETLE); src.damage = 50               # hurt Team Rocket's Pokémon
    dst = Mon(VANILLA); dst.damage = 0                    # healthy 80-HP sponge
    me.active = src; me.bench = [dst]
    assert _fn(K_rocket)(_ctx(me, opp, src, ctx)) is True
    assert src.damage + dst.damage == 50                  # damage conserved (moved, not healed)
    assert src.damage < 50 and dst.damage > 0             # relocated some off the TR mon
    assert dst.damage < dst.max_hp                        # recipient never KO'd


def t_rocket_brain_no_tr_mon():
    ctx, at, df, me, opp = mk()
    me.active.damage = 40                                 # a NON-Team-Rocket's Pokémon is hurt
    me.bench = [Mon(VANILLA)]
    assert _fn(K_rocket)(_ctx(me, opp, me.active, ctx)) is False


def t_rocket_brain_recipient_would_ko():
    ctx, at, df, me, opp = mk()
    dst = Mon(VANILLA); dst.damage = dst.max_hp - 10      # 1 counter away from KO
    src = Mon(TR_ORBEETLE); src.damage = dst.max_hp + 20  # balance would pass, but the move KOs dst
    me.active = src; me.bench = [dst]
    assert src.damage < src.max_hp                        # sanity: source itself is alive
    assert _fn(K_rocket)(_ctx(me, opp, src, ctx)) is False
    assert dst.damage == dst.max_hp - 10 and src.damage == dst.max_hp + 20   # nothing moved


# ---------------------------------------------------------------- Calming Light
def t_calming_light():
    ctx, at, df, me, opp = mk()
    shii = Mon(SHIINOTIC)
    me.active = shii                                      # holder is Active
    assert _fn(K_calm)(_ctx(me, opp, shii, ctx)) is True
    assert opp.active.status.get('Asleep')


def t_calming_light_benched():
    ctx, at, df, me, opp = mk()
    shii = Mon(SHIINOTIC)
    me.active = Mon(VANILLA); me.bench = [shii]           # holder benched -> Active-Spot gate fails
    assert _fn(K_calm)(_ctx(me, opp, shii, ctx)) is False
    assert not opp.active.status.get('Asleep')


def t_calming_light_shielded():
    ctx, at, df, me, opp = mk()
    shii = Mon(SHIINOTIC); me.active = shii
    opp.active.special = ['Bubbly Water Energy']          # opponent shields Special Conditions
    assert _fn(K_calm)(_ctx(me, opp, shii, ctx)) is False
    assert not opp.active.status.get('Asleep')


# ---------------------------------------------------------------- Prison Panic
def t_prison_panic():
    ctx, at, df, me, opp = mk()
    assert _fn(K_prison)(_ctx(me, opp, at, ctx)) is True
    assert opp.active.status.get('Confused')


def t_prison_panic_shielded():
    ctx, at, df, me, opp = mk()
    opp.active.special = ['Mist Energy']                  # effect-shielded target
    assert _fn(K_prison)(_ctx(me, opp, at, ctx)) is False
    assert not opp.active.status.get('Confused')


def t_prison_panic_no_active():
    ctx, at, df, me, opp = mk()
    opp.active = None
    assert _fn(K_prison)(_ctx(me, opp, at, ctx)) is False


# ---------------------------------------------------------------- Haphazard Hammer
def t_haphazard_hammer_heads():
    ctx, at, df, me, opp = mk(flips=(0.0,))               # heads
    opp.active.energy = Counter({'Metal': 2})
    opp.disc_energy = Counter()
    assert _fn(K_hammer)(_ctx(me, opp, at, ctx)) is True
    assert opp.active.energy['Metal'] == 1                # one Energy discarded
    assert opp.disc_energy['Metal'] == 1                  # into the opponent's discard pool


def t_haphazard_hammer_tails():
    ctx, at, df, me, opp = mk(flips=(0.9,))               # tails
    opp.active.energy = Counter({'Metal': 2})
    opp.disc_energy = Counter()
    assert _fn(K_hammer)(_ctx(me, opp, at, ctx)) is True  # ability still "used" (flip resolved)
    assert opp.active.energy['Metal'] == 2                # nothing discarded on tails
    assert opp.disc_energy['Metal'] == 0


def t_haphazard_hammer_no_active():
    ctx, at, df, me, opp = mk()
    opp.active = None
    assert _fn(K_hammer)(_ctx(me, opp, at, ctx)) is False


TESTS = [
    t_spiteful_evolution, t_spiteful_evolution_from_bench, t_spiteful_evolution_no_target,
    t_evidence_gathering, t_evidence_gathering_empty_deck, t_evidence_gathering_empty_hand,
    t_snack_seek_discards_energy, t_snack_seek_keeps_pokemon,
    t_attract_customers, t_attract_customers_ignores_non_supporter,
    t_attract_customers_too_deep, t_attract_customers_not_active,
    t_obliging_heal, t_obliging_heal_nothing_to_do,
    t_obliging_heal_removes_exactly_one_blocker_first, t_obliging_heal_status_only,
    t_rocket_brain, t_rocket_brain_no_tr_mon, t_rocket_brain_recipient_would_ko,
    t_calming_light, t_calming_light_benched, t_calming_light_shielded,
    t_prison_panic, t_prison_panic_shielded, t_prison_panic_no_active,
    t_haphazard_hammer_heads, t_haphazard_hammer_tails, t_haphazard_hammer_no_active,
]

if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
