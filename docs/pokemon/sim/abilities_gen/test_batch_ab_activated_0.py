#!/usr/bin/env python3
"""Unit tests for batch ab_activated_0 (once-per-turn / on-play / on-move action abilities). Each
registered lambda is run directly against real Mon/Player state via mk() + ActivatedCtx; every test
covers the positive effect plus a condition/negative branch. Run:
    python3 -m abilities_gen.test_batch_ab_activated_0
"""
from collections import Counter
from effects_testkit import mk, runner
import ability_effects as AB
import abilities_gen.batch_ab_activated_0  # noqa: F401  (registers the abilities)
from engine import Mon
from cards import load_cards

BK, BN = load_cards()
VANILLA = BN['Bulbasaur'][0]                          # plain 80-HP Basic (identity holder)
PIDOVE = next(c for c in BN['Pidove'] if c.hp == 60)  # 60-HP Basic  (<=70)
ALOMOMOLA = BN['Alomomola'][0]                        # 110-HP Basic (>70, exclusion case)
ABRA = BN['Abra'][0]                                  # distinct Basic for deck-recycle assertions
MEGA_ANY = BN['Mega Kangaskhan ex'][0]                # Colorless Mega Evolution ex
MEGA_GRASS = BN['Mega Venusaur ex'][0]                # {G} Mega Evolution ex
MEGA_LATIAS = BN['Mega Latias ex'][0]

K_festival = "- If Festival Grounds is in play, this Pokémon may use an attack it has twice. If the first attack Knocks Out your opponent's Active Pokémon, you may attack again after your opponent chooses a new Active Pokémon."
K_sneaky = "- When you play this Pokémon from your hand to evolve 1 of your Pokémon during your turn, you may put 2 damage counters on 1 of your opponent's Pokémon."
K_wicked = "- When you play this Pokémon from your hand to evolve 1 of your Pokémon during your turn, you may flip 2 coins. For each heads, choose a random card from your opponent's hand. Your opponent reveals those cards and shuffles them into their deck."
K_heal_leaves = "- Once during your turn, you may heal 20 damage from your Active Pokémon."
K_excited_heal = "- Once during your turn, if you have any {G} Mega Evolution Pokémon ex in play, you may use this Ability. Heal 60 damage from 1 of your Pokémon."
K_gentle = "- Once during your turn, if this Pokémon is in the Active Spot, you may put a Basic Pokémon with 70 HP or less from your discard pile onto your Bench."
K_prey = "- Once during your turn, you may use this Ability. Your opponent reveals their hand, and you put a Basic Pokémon with 70 HP or less that you find there onto your opponent's Bench."
K_sky = "- Once during your turn, you may use this Ability. Flip a coin. If heads, discard a random card from your opponent's hand."
K_captivate = "- Once during your turn, you may flip a coin. If heads, switch in 1 of your opponent's Benched Pokémon to the Active Spot, and the new Active Pokémon is now Confused."
K_beckon = "- You must discard a Chill Teaser Toy card from your hand in order to use this Ability. Once during your turn, you may switch in 1 of your opponent's Benched Pokémon to the Active Spot."
K_dash = "- Once during your turn, if this Pokémon is on your Bench, and if you have any Mega Evolution Pokémon ex in play, you may use this Ability. Switch this Pokémon with your Active Pokémon."
K_flustered = "- Once during your turn, if this Pokémon is on your Bench, you may discard the bottom card of your deck. If you do, discard all cards from this Pokémon and put this Pokémon on top of your deck."
K_teleport = "- Once during your turn, if this Pokémon is in the Active Spot, you may shuffle it and all attached cards into your deck."
K_lustrous = "- Once during your turn, when your Mega Latias ex moves from your Bench to the Active Spot, you may use this Ability. Move any amount of Energy from your Benched Pokémon to your Active Pokémon."

TOY = ('T', {'name': 'Chill Teaser Toy', 'trainerType': 'Tool'})


def _fn(key):
    return AB.ABILITY_EFFECTS[AB.normalize(key)]['fn']


def _ctx(me, opp, mon, ctx):
    return AB.ActivatedCtx(me, opp, mon, ctx.game)


# ---------------------------------------------------------------- Festival Lead (no-op)
def t_festival_lead_noop():
    ctx, at, df, me, opp = mk()
    assert _fn(K_festival)(_ctx(me, opp, at, ctx)) is False   # out-of-pool -> never fires


# ---------------------------------------------------------------- Sneaky Bite
def t_sneaky_bite():
    ctx, at, df, me, opp = mk(opp_bench=1)
    opp.bench[0].damage = 30                              # softest target
    tgt = min(opp.all_mons(), key=lambda m: m.hp_left)
    d0 = tgt.damage
    assert _fn(K_sneaky)(_ctx(me, opp, at, ctx)) is True
    assert tgt.damage == d0 + 20                          # 2 counters = 20

def t_sneaky_bite_no_target():
    ctx, at, df, me, opp = mk()
    opp.active = None; opp.bench = []
    assert _fn(K_sneaky)(_ctx(me, opp, at, ctx)) is False


# ---------------------------------------------------------------- Wicked Tail
def t_wicked_tail_two_heads():
    ctx, at, df, me, opp = mk(flips=(0.0, 0.0))          # HH
    opp.hand = [('E', 'Fire'), ('E', 'Water'), ('E', 'Grass')]
    d0 = len(opp.deck)
    assert _fn(K_wicked)(_ctx(me, opp, at, ctx)) is True
    assert len(opp.hand) == 1 and len(opp.deck) == d0 + 2

def t_wicked_tail_tails():
    ctx, at, df, me, opp = mk(flips=(0.9, 0.9))          # TT -> nothing moves, still "used"
    opp.hand = [('E', 'Fire'), ('E', 'Water')]
    assert _fn(K_wicked)(_ctx(me, opp, at, ctx)) is True
    assert len(opp.hand) == 2

def t_wicked_tail_empty_hand():
    ctx, at, df, me, opp = mk()
    opp.hand = []
    assert _fn(K_wicked)(_ctx(me, opp, at, ctx)) is False


# ---------------------------------------------------------------- Healing Leaves
def t_healing_leaves():
    ctx, at, df, me, opp = mk()
    me.active.damage = 50
    assert _fn(K_heal_leaves)(_ctx(me, opp, me.active, ctx)) is True
    assert me.active.damage == 30

def t_healing_leaves_undamaged():
    ctx, at, df, me, opp = mk()
    me.active.damage = 0
    assert _fn(K_heal_leaves)(_ctx(me, opp, me.active, ctx)) is False


# ---------------------------------------------------------------- Excited Heal
def t_excited_heal():
    ctx, at, df, me, opp = mk()
    me.bench = [Mon(MEGA_GRASS)]
    me.active.damage = 70
    assert _fn(K_excited_heal)(_ctx(me, opp, me.active, ctx)) is True
    assert me.active.damage == 10                         # healed 60

def t_excited_heal_wrong_type():
    ctx, at, df, me, opp = mk()
    me.bench = [Mon(MEGA_ANY)]                            # Colorless Mega ex, not {G}
    me.active.damage = 70
    assert _fn(K_excited_heal)(_ctx(me, opp, me.active, ctx)) is False

def t_excited_heal_nothing_hurt():
    ctx, at, df, me, opp = mk()
    me.bench = [Mon(MEGA_GRASS)]
    me.active.damage = 0
    assert _fn(K_excited_heal)(_ctx(me, opp, me.active, ctx)) is False


# ---------------------------------------------------------------- Gentle Fin
def t_gentle_fin():
    ctx, at, df, me, opp = mk()
    me.bench = []
    me.discard = [('P', PIDOVE), ('P', ALOMOMOLA)]
    assert _fn(K_gentle)(_ctx(me, opp, me.active, ctx)) is True
    assert len(me.bench) == 1 and me.bench[0].card.name == 'Pidove'
    assert ('P', PIDOVE) not in me.discard
    assert ('P', ALOMOMOLA) in me.discard                 # 110 HP -> left behind

def t_gentle_fin_not_active():
    ctx, at, df, me, opp = mk()
    holder = Mon(VANILLA); me.bench = [holder]
    me.discard = [('P', PIDOVE)]
    assert _fn(K_gentle)(_ctx(me, opp, holder, ctx)) is False   # holder is Benched, not Active
    assert ('P', PIDOVE) in me.discard

def t_gentle_fin_bench_full():
    ctx, at, df, me, opp = mk()
    me.bench = [Mon(VANILLA) for _ in range(5)]
    me.discard = [('P', PIDOVE)]
    assert _fn(K_gentle)(_ctx(me, opp, me.active, ctx)) is False


# ---------------------------------------------------------------- Look for Prey
def t_look_for_prey():
    ctx, at, df, me, opp = mk(opp_bench=0)
    opp.bench = []
    opp.hand = [('P', PIDOVE), ('P', ALOMOMOLA)]
    assert _fn(K_prey)(_ctx(me, opp, at, ctx)) is True
    assert len(opp.bench) == 1 and opp.bench[0].card.name == 'Pidove'
    assert ('P', PIDOVE) not in opp.hand

def t_look_for_prey_none():
    ctx, at, df, me, opp = mk()
    opp.bench = []
    opp.hand = [('P', ALOMOMOLA), ('E', 'Water')]         # no Basic <=70 HP
    assert _fn(K_prey)(_ctx(me, opp, at, ctx)) is False
    assert opp.bench == []


# ---------------------------------------------------------------- Sky Hunt
def t_sky_hunt_heads():
    ctx, at, df, me, opp = mk(flips=(0.0,))
    opp.hand = [('E', 'Fire'), ('E', 'Water')]
    assert _fn(K_sky)(_ctx(me, opp, at, ctx)) is True
    assert len(opp.hand) == 1                             # one discarded on heads

def t_sky_hunt_tails():
    ctx, at, df, me, opp = mk(flips=(0.9,))
    opp.hand = [('E', 'Fire'), ('E', 'Water')]
    assert _fn(K_sky)(_ctx(me, opp, at, ctx)) is True     # used, but no discard on tails
    assert len(opp.hand) == 2

def t_sky_hunt_empty():
    ctx, at, df, me, opp = mk()
    opp.hand = []
    assert _fn(K_sky)(_ctx(me, opp, at, ctx)) is False


# ---------------------------------------------------------------- Captivating Invitation
def t_captivate_heads():
    ctx, at, df, me, opp = mk(flips=(0.0,))
    opp.active = Mon(VANILLA); opp.bench = [Mon(PIDOVE)]
    assert _fn(K_captivate)(_ctx(me, opp, at, ctx)) is True
    assert opp.active.card.name == 'Pidove'               # gusted up
    assert opp.active.status.get('Confused')

def t_captivate_tails():
    ctx, at, df, me, opp = mk(flips=(0.9,))
    active0 = Mon(VANILLA); opp.active = active0; opp.bench = [Mon(PIDOVE)]
    assert _fn(K_captivate)(_ctx(me, opp, at, ctx)) is True
    assert opp.active is active0                          # no switch on tails

def t_captivate_immune_no_confuse():
    ctx, at, df, me, opp = mk(flips=(0.0,))
    opp.active = Mon(VANILLA)
    tgt = Mon(PIDOVE); tgt.special = ['Bubbly Water Energy']  # blocks conditions
    opp.bench = [tgt]
    assert _fn(K_captivate)(_ctx(me, opp, at, ctx)) is True
    assert opp.active is tgt and not tgt.status.get('Confused')

def t_captivate_no_bench():
    ctx, at, df, me, opp = mk(flips=(0.0,))
    opp.bench = []
    assert _fn(K_captivate)(_ctx(me, opp, at, ctx)) is False


# ---------------------------------------------------------------- Beckoning Tail
def t_beckoning_tail():
    ctx, at, df, me, opp = mk()
    me.hand = [TOY]
    opp.active = Mon(VANILLA); opp.bench = [Mon(PIDOVE)]
    assert _fn(K_beckon)(_ctx(me, opp, at, ctx)) is True
    assert opp.active.card.name == 'Pidove'
    assert TOY not in me.hand and TOY in me.discard

def t_beckoning_tail_no_toy():
    ctx, at, df, me, opp = mk()
    me.hand = []
    opp.bench = [Mon(PIDOVE)]
    assert _fn(K_beckon)(_ctx(me, opp, at, ctx)) is False

def t_beckoning_tail_no_bench():
    ctx, at, df, me, opp = mk()
    me.hand = [TOY]
    opp.bench = []
    assert _fn(K_beckon)(_ctx(me, opp, at, ctx)) is False
    assert TOY in me.hand                                 # cost not wasted


# ---------------------------------------------------------------- Excited Dash
def t_excited_dash():
    ctx, at, df, me, opp = mk()
    holder = Mon(VANILLA); old_active = Mon(VANILLA)
    me.active = old_active
    me.bench = [holder, Mon(MEGA_ANY)]                    # a Mega ex in play
    assert _fn(K_dash)(_ctx(me, opp, holder, ctx)) is True
    assert me.active is holder and holder.came_from_bench
    assert old_active in me.bench

def t_excited_dash_no_mega():
    ctx, at, df, me, opp = mk()
    holder = Mon(VANILLA)
    me.active = Mon(VANILLA); me.bench = [holder]         # no Mega ex
    assert _fn(K_dash)(_ctx(me, opp, holder, ctx)) is False
    assert holder in me.bench

def t_excited_dash_not_benched():
    ctx, at, df, me, opp = mk()
    holder = Mon(VANILLA)
    me.active = holder; me.bench = [Mon(MEGA_ANY)]        # holder is Active, not Bench
    assert _fn(K_dash)(_ctx(me, opp, holder, ctx)) is False


# ---------------------------------------------------------------- Flustered Leap
def t_flustered_leap():
    ctx, at, df, me, opp = mk()
    holder = Mon(ABRA); holder.energy = Counter({'Water': 1})
    me.bench = [holder]
    n0 = len(me.deck)
    assert _fn(K_flustered)(_ctx(me, opp, holder, ctx)) is True
    assert holder not in me.bench
    assert me.deck[-1] == ('P', ABRA)                     # on top of the deck
    assert me.disc_energy['Water'] == 1                   # attached energy discarded
    assert len(me.discard) == 1                           # bottom card milled
    assert len(me.deck) == n0                             # -1 milled, +1 self = net 0

def t_flustered_leap_not_benched():
    ctx, at, df, me, opp = mk()
    holder = Mon(ABRA); me.active = holder
    assert _fn(K_flustered)(_ctx(me, opp, holder, ctx)) is False

def t_flustered_leap_empty_deck():
    ctx, at, df, me, opp = mk()
    holder = Mon(ABRA); me.bench = [holder]; me.deck = []
    assert _fn(K_flustered)(_ctx(me, opp, holder, ctx)) is False
    assert holder in me.bench


# ---------------------------------------------------------------- Teleporter
def t_teleporter():
    ctx, at, df, me, opp = mk()
    holder = Mon(ABRA); holder.energy = Counter({'Psychic': 2})
    me.active = holder; me.bench = [Mon(VANILLA)]
    assert _fn(K_teleport)(_ctx(me, opp, holder, ctx)) is True
    assert me.active.card.name == 'Bulbasaur'             # Bench promoted
    assert ('P', ABRA) in me.deck                         # Abra shuffled into deck
    assert me.deck.count(('E', 'Psychic')) == 2           # attached energy returned to deck
    assert len(me.bench) == 0

def t_teleporter_not_active():
    ctx, at, df, me, opp = mk()
    holder = Mon(ABRA); me.active = Mon(VANILLA); me.bench = [holder]
    assert _fn(K_teleport)(_ctx(me, opp, holder, ctx)) is False

def t_teleporter_no_bench():
    ctx, at, df, me, opp = mk()
    holder = Mon(ABRA); me.active = holder; me.bench = []
    assert _fn(K_teleport)(_ctx(me, opp, holder, ctx)) is False


# ---------------------------------------------------------------- Lustrous Assist
def t_lustrous_assist():
    ctx, at, df, me, opp = mk()
    me.active = Mon(MEGA_LATIAS); me.active.came_from_bench = True   # moved Bench->Active this turn
    b1 = Mon(VANILLA); b1.energy = Counter({'Water': 2})
    b2 = Mon(VANILLA); b2.energy = Counter({'Psychic': 1})
    me.bench = [b1, b2]
    assert _fn(K_lustrous)(_ctx(me, opp, at, ctx)) is True
    assert me.active.energy['Water'] == 2 and me.active.energy['Psychic'] == 1
    assert b1.total_energy() == 0 and b2.total_energy() == 0

def t_lustrous_assist_not_moved():
    # Mega Latias ex is Active with benched energy, but it did NOT move up this turn -> must NOT
    # fire (guards the over-fire the real "when it moves Bench->Active" trigger forbids).
    ctx, at, df, me, opp = mk()
    me.active = Mon(MEGA_LATIAS); me.active.came_from_bench = False
    b1 = Mon(VANILLA); b1.energy = Counter({'Water': 2}); me.bench = [b1]
    assert _fn(K_lustrous)(_ctx(me, opp, at, ctx)) is False
    assert b1.total_energy() == 2                         # bench energy untouched

def t_lustrous_assist_wrong_active():
    ctx, at, df, me, opp = mk()
    me.active = Mon(VANILLA); me.active.came_from_bench = True   # moved, but not Mega Latias ex
    b1 = Mon(VANILLA); b1.energy = Counter({'Water': 2}); me.bench = [b1]
    assert _fn(K_lustrous)(_ctx(me, opp, at, ctx)) is False

def t_lustrous_assist_no_bench_energy():
    ctx, at, df, me, opp = mk()
    me.active = Mon(MEGA_LATIAS); me.active.came_from_bench = True
    me.bench = [Mon(VANILLA)]                             # moved up, but no benched energy to pull
    assert _fn(K_lustrous)(_ctx(me, opp, at, ctx)) is False


TESTS = [
    t_festival_lead_noop,
    t_sneaky_bite, t_sneaky_bite_no_target,
    t_wicked_tail_two_heads, t_wicked_tail_tails, t_wicked_tail_empty_hand,
    t_healing_leaves, t_healing_leaves_undamaged,
    t_excited_heal, t_excited_heal_wrong_type, t_excited_heal_nothing_hurt,
    t_gentle_fin, t_gentle_fin_not_active, t_gentle_fin_bench_full,
    t_look_for_prey, t_look_for_prey_none,
    t_sky_hunt_heads, t_sky_hunt_tails, t_sky_hunt_empty,
    t_captivate_heads, t_captivate_tails, t_captivate_immune_no_confuse, t_captivate_no_bench,
    t_beckoning_tail, t_beckoning_tail_no_toy, t_beckoning_tail_no_bench,
    t_excited_dash, t_excited_dash_no_mega, t_excited_dash_not_benched,
    t_flustered_leap, t_flustered_leap_not_benched, t_flustered_leap_empty_deck,
    t_teleporter, t_teleporter_not_active, t_teleporter_no_bench,
    t_lustrous_assist, t_lustrous_assist_not_moved,
    t_lustrous_assist_wrong_active, t_lustrous_assist_no_bench_energy,
]

if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
