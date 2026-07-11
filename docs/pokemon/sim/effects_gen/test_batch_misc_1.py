#!/usr/bin/env python3
"""Unit tests for effect batch misc_1."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # ensure sim/ importable
from collections import Counter
from effects_testkit import mk, run, runner, VANILLA
from engine import Mon
from cards import load_cards
import attack_effects as AE
import effects_gen.batch_misc_1  # noqa: F401  (registers the effects)

BK, BN = load_cards()
STAGE2 = next((c for c in BK.values() if c.stage == 2), None)   # any real Stage 2 card

# mk() defaults: attacker energy {Colorless:3}, defender {Colorless:2}; VANILLA = Bulbasaur
# (Grass, HP 80, weakness Fire — so Weakness never fires attacker-vs-defender in tests);
# me.hand/opp.hand empty; me.deck/opp.deck = 6 Pokémon + 10 Colorless; game.turn = 3; heads=0.0.


def _fn(text):
    return AE.ATTACK_EFFECTS[AE.normalize(text)]


# ---------------------------------------------------------------- damage-counter placement
def t_place_3_on_active():
    d, ctx, at, df, me, opp = run("Place 3 damage counters on your opponent's Active Pokémon.", base=0)
    assert d == 0, d                                  # counters placed directly, not returned
    assert df.damage == 30, df.damage                 # 3 counters = 30 on the Active


def t_put_2_on_one_default():
    d, ctx, at, df, me, opp = run("Put 2 damage counters on 1 of your opponent's Pokémon.", base=0)
    assert d == 0, d
    assert df.damage == 20, df.damage                 # 2 counters on the (tie-broken) Active


def t_put_2_on_one_prefers_ko_bench():
    key = "Put 2 damage counters on 1 of your opponent's Pokémon."
    ctx, at, df, me, opp = mk(text=key, opp_bench=1)
    opp.bench[0].damage = 70                           # hp_left 10 -> 20 KOs it; Active can't be KO'd
    assert _fn(key)(ctx) == 0
    assert opp.bench[0].damage == 90, opp.bench[0].damage
    assert opp.active.damage == 0, opp.active.damage


def t_counters_until_hp_10():
    d, ctx, at, df, me, opp = run("Put damage counters on your opponent's Active Pokémon until its remaining HP is 10.", base=0)
    assert d == 0 and df.damage == 70 and df.hp_left == 10, (d, df.damage, df.hp_left)


def t_counters_until_hp_10_no_heal():
    key = "Put damage counters on your opponent's Active Pokémon until its remaining HP is 10."
    ctx, at, df, me, opp = mk(text=key)
    df.damage = 75                                     # already below 10 HP left -> unchanged
    _fn(key)(ctx)
    assert df.damage == 75, df.damage


def t_snipe_70_no_wr_active():
    d, ctx, at, df, me, opp = run("This attack does 70 damage to 1 of your opponent's Pokémon. This attack's damage isn't affected by Weakness or Resistance.", base=0)
    assert d == 0, d                                   # written directly (no Weakness) -> returns 0
    assert df.damage == 70, df.damage


def t_snipe_70_no_wr_bench_ko():
    key = "This attack does 70 damage to 1 of your opponent's Pokémon. This attack's damage isn't affected by Weakness or Resistance."
    ctx, at, df, me, opp = mk(text=key, opp_bench=1)
    opp.bench[0].damage = 20                            # hp_left 60 -> 70 KOs it; Active (80) can't
    assert _fn(key)(ctx) == 0
    assert opp.bench[0].damage == 90, opp.bench[0].damage
    assert opp.active.damage == 0, opp.active.damage


# ---------------------------------------------------------------- delayed / future-turn (base only)
def t_glaceon_delayed_9():
    assert run("At the end of your opponent's next turn, put 9 damage counters on the Defending Pokémon.", base=30)[0] == 30


def t_hypno_end_turn():
    assert run("During your opponent's next turn, if they attach an Energy card from their hand to the Defending Pokémon, their turn ends.", base=80)[0] == 80


def t_pachirisu_punish():
    assert run("During your opponent's next turn, whenever they attach an Energy card from their hand to the Defending Pokémon, place 8 damage counters on that Pokémon.", base=10)[0] == 10


def t_walrein_lock():
    assert run("During your opponent's next turn, Pokémon that have 2 or less Energy attached can't attack. (This includes new Pokémon that come into play.)", base=60)[0] == 60


def t_bronzong_lock():
    assert run("During your opponent's next turn, they can't play any Pokémon from their hand to evolve their Pokémon.", base=30)[0] == 30


def t_mr_mime_noop():
    assert run("Your opponent reveals their hand. You may use the effect of a Supporter card you find there as the effect of this attack.", base=0)[0] == 0


# ---------------------------------------------------------------- attach energy from hand (own)
def t_attach_1_basic():
    key = "Attach a Basic Energy card from your hand to 1 of your Pokémon."
    ctx, at, df, me, opp = mk(text=key, base=0)
    me.hand = [('E', 'Fire')]
    before = sum(m.total_energy() for m in me.all_mons())
    assert _fn(key)(ctx) == 0
    assert sum(m.total_energy() for m in me.all_mons()) == before + 1
    assert [t for t in me.hand if t[0] == 'E'] == []    # the Fire left the hand


def t_attach_2_psychic():
    key = "Attach up to 2 Basic {P} Energy cards from your hand to your Pokémon in any way you like."
    ctx, at, df, me, opp = mk(text=key, base=0)
    me.hand = [('E', 'Psychic'), ('E', 'Psychic'), ('E', 'Psychic'), ('E', 'Fire')]
    before = sum(m.total_energy() for m in me.all_mons())
    assert _fn(key)(ctx) == 0
    assert sum(m.total_energy() for m in me.all_mons()) == before + 2     # only 2 attached
    assert [t for t in me.hand if t == ('E', 'Psychic')] == [('E', 'Psychic')]  # 1 Psychic left
    assert ('E', 'Fire') in me.hand                     # non-Psychic untouched


def t_each_attach_3():
    key = "Each player may attach up to 3 Basic Energy cards from their hand to their Pokémon in any way they like. Your opponent does this first."
    ctx, at, df, me, opp = mk(text=key, base=0)
    me.hand = [('E', 'Fire')] * 4                        # 4 -> attach 3
    opp.hand = [('E', 'Water')] * 2                      # 2 -> attach 2
    mb = sum(m.total_energy() for m in me.all_mons())
    ob = sum(m.total_energy() for m in opp.all_mons())
    assert _fn(key)(ctx) == 0
    assert sum(m.total_energy() for m in me.all_mons()) == mb + 3
    assert sum(m.total_energy() for m in opp.all_mons()) == ob + 2
    assert len([t for t in me.hand if t[0] == 'E']) == 1
    assert len([t for t in opp.hand if t[0] == 'E']) == 0


# ---------------------------------------------------------------- move energy (own team)
def t_move_metal_own():
    key = "You may move any amount of {M} Energy from your Pokémon to your other Pokémon in any way you like."
    ctx, at, df, me, opp = mk(text=key, base=20, atk_energy={'Metal': 2, 'Colorless': 1})
    me.bench[0].energy = Counter({'Metal': 1, 'Grass': 1})
    dest = ctx.game.primary(me)                          # active (3 energy) is the ace
    assert _fn(key)(ctx) == 20
    assert dest is me.active
    assert me.active.energy['Metal'] == 3                # 2 + moved 1
    assert me.bench[0].energy.get('Metal', 0) == 0
    assert me.bench[0].energy.get('Grass', 0) == 1       # non-Metal stays put


def t_move_any_own():
    key = "You may move any amount of Energy from your Pokémon to your other Pokémon in any way you like."
    ctx, at, df, me, opp = mk(text=key, base=110, atk_energy={'Fire': 3})
    me.bench[0].energy = Counter({'Water': 2})
    assert _fn(key)(ctx) == 110
    assert me.active.total_energy() == 5                 # 3 Fire + 2 Water gathered
    assert me.bench[0].total_energy() == 0


# ---------------------------------------------------------------- opponent energy relocation / removal
def t_move_opp_energy():
    key = "Move an Energy from 1 of your opponent's Pokémon to another of their Pokémon."
    ctx, at, df, me, opp = mk(text=key, base=0, def_energy={'Water': 2}, opp_bench=1)
    assert _fn(key)(ctx) == 0
    assert opp.active.total_energy() == 1                # one stripped off the Active
    assert opp.bench[0].energy['Water'] == 1             # dumped on the bench


def t_move_opp_energy_no_bench():
    key = "Move an Energy from 1 of your opponent's Pokémon to another of their Pokémon."
    ctx, at, df, me, opp = mk(text=key, def_energy={'Water': 2}, opp_bench=0)
    _fn(key)(ctx)
    assert opp.active.total_energy() == 2                # nowhere to move it -> unchanged


def t_bounce_1_opp_energy():
    d, ctx, at, df, me, opp = run("You may put an Energy attached to your opponent's Active Pokémon into their hand.",
                                  base=20, def_energy={'Water': 2})
    assert d == 20
    assert df.total_energy() == 1
    assert opp.hand.count(('E', 'Water')) == 1           # returned to hand, not discarded


def t_bounce_2_stage2_positive():
    assert STAGE2 is not None
    key = "You may put 2 Energy attached to your opponent's Active Stage 2 Pokémon into their hand."
    ctx, at, df, me, opp = mk(text=key, base=30)
    opp.active = Mon(STAGE2)
    opp.active.energy = Counter({'Water': 3})
    assert _fn(key)(ctx) == 30
    assert opp.active.total_energy() == 1                # 2 bounced
    assert opp.hand.count(('E', 'Water')) == 2


def t_bounce_2_stage2_not_stage2():
    d, ctx, at, df, me, opp = run("You may put 2 Energy attached to your opponent's Active Stage 2 Pokémon into their hand.",
                                  base=30, def_energy={'Water': 3})
    assert d == 30
    assert df.total_energy() == 3                        # Active is a Basic -> nothing bounced
    assert opp.hand == []


# ---------------------------------------------------------------- hand disruption
def t_opp_discard_1():
    key = "Your opponent discards a card from their hand."
    ctx, at, df, me, opp = mk(text=key, base=10)
    opp.hand = [('E', 'Water')]
    assert _fn(key)(ctx) == 10
    assert opp.hand == [] and opp.disc_energy['Water'] == 1
    assert _fn(key)(ctx) == 10                           # empty hand -> still returns base


def t_discard_both_with_card():
    key = "Discard a card from your hand. If you do, your opponent discards a card from their hand."
    ctx, at, df, me, opp = mk(text=key, base=0)
    me.hand = [('E', 'Fire')]
    opp.hand = [('P', VANILLA)]
    assert _fn(key)(ctx) == 0
    assert me.hand == [] and me.disc_energy['Fire'] == 1
    assert opp.hand == [] and opp.discard == [('P', VANILLA)]


def t_discard_both_empty_own_hand():
    key = "Discard a card from your hand. If you do, your opponent discards a card from their hand."
    ctx, at, df, me, opp = mk(text=key, base=0)
    me.hand = []
    opp.hand = [('P', VANILLA)]
    _fn(key)(ctx)
    assert opp.hand == [('P', VANILLA)]                  # gate fails -> opponent keeps their card


def t_opp_discard_to_5():
    key = "Discard random cards from your opponent's hand until they have 5 cards in their hand."
    ctx, at, df, me, opp = mk(text=key, base=0)
    opp.hand = [('E', 'Colorless')] * 8
    assert _fn(key)(ctx) == 0
    assert len(opp.hand) == 5


def t_opp_discard_to_5_under():
    key = "Discard random cards from your opponent's hand until they have 5 cards in their hand."
    ctx, at, df, me, opp = mk(text=key)
    opp.hand = [('P', VANILLA)] * 3
    _fn(key)(ctx)
    assert len(opp.hand) == 3                            # already <=5 -> unchanged


def t_shuffle_random_opp_card():
    key = "Choose a random card from your opponent's hand, and your opponent reveals that card and shuffles it into their deck."
    ctx, at, df, me, opp = mk(text=key, base=20)
    opp.hand = [('P', VANILLA), ('E', 'Fire'), ('E', 'Water')]
    deck_before = len(opp.deck)
    assert _fn(key)(ctx) == 20
    assert opp.hand == [('E', 'Fire'), ('E', 'Water')]   # scripted RNG picks hand[0] (the Pokémon)
    assert len(opp.deck) == deck_before + 1


def t_bottom_deck_opp_card():
    key = "Your opponent reveals their hand, and you choose a card you find there and put it on the bottom of their deck."
    ctx, at, df, me, opp = mk(text=key, base=30)
    opp.hand = [('E', 'Fire'), ('P', VANILLA)]           # we choose the Pokémon over Basic Energy
    deck_before = len(opp.deck)
    assert _fn(key)(ctx) == 30
    assert opp.hand == [('E', 'Fire')]
    assert opp.deck[0] == ('P', VANILLA)                 # bottom of deck = index 0
    assert len(opp.deck) == deck_before + 1


# ---------------------------------------------------------------- attack cooldowns
def t_cd_slashing_strike():
    key = "During your next turn, this Pokémon can't use Slashing Strike."
    d, ctx, at, df, me, opp = run(key, base=60)
    assert d == 60
    assert at.cd_name == 'Slashing Strike' and at.cd_turn == 3
    # End-to-end on the real Scyther (Cut Up 10 / Slashing Strike 60): the effect's named cooldown
    # blocks ONLY Slashing Strike next turn (best_attack falls back to Cut Up); blocking the OTHER
    # attack instead leaves Slashing Strike usable -> selective, name-scoped disable.
    scy = next(c for c in BK.values()
               if any(a['name'] == 'Slashing Strike' and set(a['cost']) <= set('C') for a in c.attacks))
    ctx2, at2, df2, me2, opp2 = mk(text=key, base=60)
    w = Mon(scy); w.energy = Counter({'Colorless': 3}); me2.active = w; me2.bench = []; ctx2.attacker = w
    assert _fn(key)(ctx2) == 60                           # effect sets cd_name='Slashing Strike', turn 3
    g = ctx2.game; g.turn = 5                             # my next turn (3+2)
    picked = g.best_attack(me2, opp2, w, opp2.active)
    assert picked is not None and picked[0]['name'] != 'Slashing Strike'      # SS blocked -> Cut Up
    w.cd_name = 'Cut Up'                                  # block the other attack instead
    reopened = g.best_attack(me2, opp2, w, opp2.active)
    assert reopened is not None and reopened[0]['name'] == 'Slashing Strike'  # SS now usable & best


def t_cd_all_own():
    key = "During your next turn, your Pokémon can't attack. (This includes new Pokémon that come into play.)"
    d, ctx, at, df, me, opp = run(key, base=220, my_bench=2)
    assert d == 220
    assert len(me.all_mons()) == 3
    assert all(m.cd_name == 'ALL' and m.cd_turn == 3 for m in me.all_mons())
    # End-to-end: the 'ALL' cooldown actually stops best_attack on my NEXT turn (3+2) and only then
    # (usable on the opponent's turn 4 and again on turn 6). Validates the whole-team attack lock.
    atkr = next(c for c in BK.values()
                if c.stage == 0 and any(a['dmg'] > 0 and set(a['cost']) <= set('C') for a in c.attacks))
    cost = min((a['cost'] for a in atkr.attacks if a['dmg'] > 0 and set(a['cost']) <= set('C')), key=len)
    ctx2, at2, df2, me2, opp2 = mk(text=key, base=220)
    w = Mon(atkr); w.energy = Counter({'Colorless': max(1, len(cost))})
    me2.active = w; me2.bench = []; ctx2.attacker = w
    assert _fn(key)(ctx2) == 220                          # sets 'ALL' cd (turn 3) on w
    g = ctx2.game
    g.turn = 4; assert g.best_attack(me2, opp2, w, opp2.active) is not None    # opponent's turn: usable
    g.turn = 5; assert g.best_attack(me2, opp2, w, opp2.active) is None        # my next turn: blocked
    g.turn = 6; assert g.best_attack(me2, opp2, w, opp2.active) is not None    # turn after: usable


# ---------------------------------------------------------------- next-turn self buff
def t_buff_hyper_fang():
    key = "During your next turn, this Pokémon's Hyper Fang attack's base damage is 240."
    d, ctx, at, df, me, opp = run(key, base=0)
    assert d == 0
    assert at.ramp.get('Hyper Fang') == 240              # VANILLA has no Hyper Fang -> base 0 -> ramp 240
    # Real card (Watchog): Hyper Fang prints 80, so the ramp must be 240-80=160 -> the engine's
    # best_attack (printed base + ramp) reconstructs EXACTLY 240 next turn (SET-to-240, not +240).
    watchog = next(c for c in BK.values() if any(a.get('name') == 'Hyper Fang' for a in c.attacks))
    hf_base = next(a['dmg'] for a in watchog.attacks if a['name'] == 'Hyper Fang')
    assert hf_base > 0                                    # guard: the subtraction is actually exercised
    ctx2, at2, df2, me2, opp2 = mk(text=key, base=0)
    w = Mon(watchog); me2.active = w; ctx2.attacker = w
    assert _fn(key)(ctx2) == 0
    assert w.ramp.get('Hyper Fang') == 240 - hf_base     # 160, NOT 240 -> proves 240-cur, not +240
    assert hf_base + w.ramp['Hyper Fang'] == 240         # engine adds base+ramp -> 240 next turn


# ---------------------------------------------------------------- hand-size gate / win
def t_gate_hand_7():
    key = "If you don't have exactly 7 cards in your hand, this attack does nothing."
    ctx, at, df, me, opp = mk(text=key, base=150)
    me.hand = [('E', 'Colorless')] * 7
    assert _fn(key)(ctx) == 150
    me.hand = [('E', 'Colorless')] * 6
    assert _fn(key)(ctx) == 0
    me.hand = [('E', 'Colorless')] * 8
    assert _fn(key)(ctx) == 0


def t_win_at_1_prize():
    key = "If you use this attack when you have exactly 1 Prize card remaining, you win this game."
    d, ctx, at, df, me, opp = run(key, base=0, my_prizes=1)
    assert d == 0 and opp.lost is True
    d2, ctx2, at2, df2, me2, opp2 = run(key, base=0, my_prizes=2)
    assert d2 == 0 and opp2.lost is False


TESTS = [
    t_place_3_on_active,
    t_put_2_on_one_default,
    t_put_2_on_one_prefers_ko_bench,
    t_counters_until_hp_10,
    t_counters_until_hp_10_no_heal,
    t_snipe_70_no_wr_active,
    t_snipe_70_no_wr_bench_ko,
    t_glaceon_delayed_9,
    t_hypno_end_turn,
    t_pachirisu_punish,
    t_walrein_lock,
    t_bronzong_lock,
    t_mr_mime_noop,
    t_attach_1_basic,
    t_attach_2_psychic,
    t_each_attach_3,
    t_move_metal_own,
    t_move_any_own,
    t_move_opp_energy,
    t_move_opp_energy_no_bench,
    t_bounce_1_opp_energy,
    t_bounce_2_stage2_positive,
    t_bounce_2_stage2_not_stage2,
    t_opp_discard_1,
    t_discard_both_with_card,
    t_discard_both_empty_own_hand,
    t_opp_discard_to_5,
    t_opp_discard_to_5_under,
    t_shuffle_random_opp_card,
    t_bottom_deck_opp_card,
    t_cd_slashing_strike,
    t_cd_all_own,
    t_buff_hyper_fang,
    t_gate_hand_7,
    t_win_at_1_prize,
]

if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
