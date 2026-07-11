#!/usr/bin/env python3
"""Unit tests for effect batch misc_0.

mk() defaults: base=50, game.turn=3, heads=0.0/tails=0.9, opp_prizes=my_prizes=6,
attacker/defender = VANILLA (Bulbasaur, one 10-dmg attack 'Bind Down'), atk_energy={'Colorless':3},
def_energy={'Colorless':2}, me/opp hands empty, deck = 6 Pokémon + 10 Colorless energy, discard empty,
my_bench=opp_bench=1. The scripted RNG's randint(a,b) returns a -> _pick_random_index == 0.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # ensure sim/ importable
from collections import Counter
from effects_testkit import mk, run, runner
from effects import incoming_damage
import attack_effects as AE
import effects_gen.batch_misc_0  # noqa: F401  (registers the effects)


def _fn(text):
    return AE.ATTACK_EFFECTS[AE.normalize(text)]


def _gated(mon, atk_name, turn):
    """Replica of the engine's cooldown gate (engine.py best_attack): an attack is disabled iff
    `mon.cd_turn + 2 == turn and mon.cd_name in ('ALL', atk_name)`. Used to prove a lock lands on
    the correct turn (my next = T+2, opponent's next = T+1) and is scoped to the right attack name."""
    return mon.cd_turn + 2 == turn and mon.cd_name in ('ALL', atk_name)


# ---------------------------------------------------------------- "ignore ..." clauses
def t_ignore_resistance():
    d = run("[30] This attack's damage isn't affected by Resistance.", base=30)[0]
    assert d == 30, d


def t_ignore_defender_effects():
    txt = "This attack's damage isn't affected by any effects on your opponent's Active Pokémon."
    ctx, at, df, me, opp = mk(text=txt, base=40)
    df.dr_amount = 30
    df.dr_turn = ctx.game.turn - 1        # would reduce this hit via incoming_damage
    # precondition: WITHOUT the effect the real pipeline would knock 40 -> 10
    assert incoming_damage(40, at, df, opp, ctx.game) == 10, "dr should reduce before the effect runs"
    d = _fn(txt)(ctx)
    assert d == 40, d
    assert df.dr_amount == 0 and df.dr_turn == -9, (df.dr_amount, df.dr_turn)   # cleared
    # end-to-end: the same pipeline no longer reduces the hit
    assert incoming_damage(40, at, df, opp, ctx.game) == 40, "dr must be neutralized in incoming_damage"


# ---------------------------------------------------------------- Stadium clauses (Stadium tracked)
def t_discard_stadium():
    # No Stadium in play -> nothing to discard, deal base.
    d, ctx, at, df, me, opp = run("[90] Discard a Stadium in play.", base=90)
    assert d == 90 and ctx.game.stadium is None, (d, ctx.game.stadium)
    # A Stadium in play IS discarded (damage unchanged).
    d2, ctx2, *_ = run("[90] Discard a Stadium in play.", base=90, stadium='Prism Tower')
    assert d2 == 90, d2
    assert ctx2.game.stadium is None, ctx2.game.stadium   # discarded off the board


def t_may_discard_stadium():
    # No Stadium -> no-op, deal base.
    d, ctx, at, df, me, opp = run("[30] You may discard a Stadium in play.", base=30)
    assert d == 30 and ctx.game.stadium is None, (d, ctx.game.stadium)
    # Stadium present -> taken (beneficial disruption).
    d2, ctx2, *_ = run("[30] You may discard a Stadium in play.", base=30, stadium='Town Store')
    assert d2 == 30, d2
    assert ctx2.game.stadium is None, ctx2.game.stadium


def t_nothing_without_stadium():
    txt = "[70] If there is no Stadium in play, this attack does nothing."
    # No Stadium in play -> attack does nothing.
    assert run(txt, base=70)[0] == 0
    # A Stadium in play -> full damage.
    assert run(txt, base=70, stadium='Prism Tower')[0] == 70


# ---------------------------------------------------------------- self attack-locks
def t_self_lock_all():
    d, ctx, at, df, me, opp = run("[70] During your next turn, this Pokémon can't use attacks.", base=70)
    assert d == 70, d
    assert at.cd_name == 'ALL' and at.cd_turn == 3, (at.cd_name, at.cd_turn)
    # ALL lock disables EVERY attack on my next turn (T+2 == 5) — and only then.
    assert _gated(at, 'Anything', 5) and _gated(at, 'Whatever', 5), "all attacks locked my next turn"
    assert not _gated(at, 'Anything', 3), "not disabled the turn it was used"
    assert not _gated(at, 'Anything', 4), "a self-lock never lands on the opponent's turn"


def t_self_lock_accel_stab():
    d, ctx, at, df, me, opp = run("[30] During your next turn, this Pokémon can't use Accelerating Stab.", base=30)
    assert d == 30, d
    assert at.cd_name == 'Accelerating Stab' and at.cd_turn == 3, (at.cd_name, at.cd_turn)
    assert _gated(at, 'Accelerating Stab', 5), "the named attack is locked next turn"
    assert not _gated(at, 'Quick Attack', 5), "a differently-named attack stays usable"


def t_self_lock_flashing_bolt():
    d, ctx, at, df, me, opp = run("[160] During your next turn, this Pokémon can't use Flashing Bolt.", base=160)
    assert d == 160, d
    assert at.cd_name == 'Flashing Bolt' and at.cd_turn == 3, (at.cd_name, at.cd_turn)
    assert _gated(at, 'Flashing Bolt', 5), "the named attack is locked next turn"
    assert not _gated(at, 'Gigavolt', 5), "a differently-named attack stays usable"


def t_self_lock_zap_cannon():
    d, ctx, at, df, me, opp = run("[180] During your next turn, this Pokémon can't use Zap Cannon.", base=180)
    assert d == 180, d
    assert at.cd_name == 'Zap Cannon' and at.cd_turn == 3, (at.cd_name, at.cd_turn)
    # ONLY Zap Cannon is locked, on my next turn (T+2 == 5); other attacks still fire.
    assert _gated(at, 'Zap Cannon', 5), "Zap Cannon must be locked next turn"
    assert not _gated(at, 'Gigavolt', 5), "a different attack must NOT be locked"
    assert not _gated(at, 'Zap Cannon', 4), "self-lock never lands on the opponent's turn"


# ---------------------------------------------------------------- defender attack-locks (T+1)
def t_defender_lock_use_attacks():
    d, ctx, at, df, me, opp = run("[60] During your opponent's next turn, the Defending Pokémon can't use attacks.", base=60)
    assert d == 60, d
    assert df.cd_name == 'ALL' and df.cd_turn == 2, (df.cd_name, df.cd_turn)   # game.turn-1 == 2
    # The defender is locked on the OPPONENT'S next turn (T+1 == 4), not on my following turn (5).
    assert _gated(df, 'Anything', 4), "defender locked on the opponent's next turn"
    assert not _gated(df, 'Anything', 5), "must not bleed into my following turn"
    assert not _gated(df, 'Anything', 3), "not the turn the lock was applied"


def t_defender_lock_attack():
    d, ctx, at, df, me, opp = run("[50] During your opponent's next turn, the Defending Pokémon can't attack.", base=50)
    assert d == 50, d
    assert df.cd_name == 'ALL' and df.cd_turn == 2, (df.cd_name, df.cd_turn)
    assert _gated(df, 'Anything', 4) and not _gated(df, 'Anything', 5), "opp next turn only"


def t_defender_lock_one_attack():
    txt = ("[30] Choose 1 of your opponent's Active Pokémon's attacks. During your opponent's next turn, "
           "that Pokémon can't use that attack.")
    d, ctx, at, df, me, opp = run(txt, base=30)
    assert d == 30, d
    expected = max(df.card.attacks, key=lambda a: a['dmg'])['name']   # VANILLA -> 'Bind Down'
    assert df.cd_name == expected and df.cd_turn == 2, (df.cd_name, df.cd_turn, expected)
    # ONLY the chosen attack is locked, on the opponent's next turn (T+1 == 4).
    assert _gated(df, expected, 4), "chosen attack locked on the opponent's next turn"
    assert not _gated(df, 'Some Other Attack', 4), "a different attack stays usable"
    assert not _gated(df, expected, 5), "the lock does not persist to my turn"


# ---------------------------------------------------------------- copy attacks
def t_copy_opponent_attack():
    d, ctx, at, df, me, opp = run("- Choose 1 of your opponent's Active Pokémon's attacks and use it as this attack.", base=0)
    expected = max((a['dmg'] for a in df.card.attacks), default=0)   # VANILLA best base == 10
    assert d == expected and d == 10, (d, expected)


def t_copy_opponent_tera_attack():
    # No Tera detection -> does nothing regardless of the defender.
    d = run("- Choose 1 of your opponent's Active Tera Pokémon's attacks and use it as this attack.", base=0)[0]
    assert d == 0, d


# ---------------------------------------------------------------- hand disruption (opponent)
def t_opp_reveal_hand():
    ctx, at, df, me, opp = mk(text="Your opponent reveals their hand.", base=10)
    opp.hand = [('P', 'x'), ('E', 'Fire')]
    d = _fn("Your opponent reveals their hand.")(ctx)
    assert d == 10, d
    assert len(opp.hand) == 2, len(opp.hand)          # information only; hand untouched


def t_opp_random_to_deck():
    txt = "Choose a random card from your opponent's hand. Your opponent reveals that card and shuffles it into their deck."
    ctx, at, df, me, opp = mk(text=txt, base=20)
    opp.hand = [('P', 'a'), ('E', 'Fire')]            # random index 0 -> ('P','a') to deck
    deck_before = len(opp.deck)
    d = _fn(txt)(ctx)
    assert d == 20, d
    assert len(opp.hand) == 1 and opp.hand == [('E', 'Fire')], opp.hand
    assert len(opp.deck) == deck_before + 1, len(opp.deck)


def t_opp_random_to_deck_empty():
    txt = "Choose a random card from your opponent's hand. Your opponent reveals that card and shuffles it into their deck."
    ctx, at, df, me, opp = mk(text=txt, base=20)
    opp.hand = []
    deck_before = len(opp.deck)
    d = _fn(txt)(ctx)
    assert d == 20 and len(opp.deck) == deck_before, (d, len(opp.deck))   # no-op, no crash


def t_opp_discard_random_energy():
    txt = "Discard a random card from your opponent's hand."
    ctx, at, df, me, opp = mk(text=txt, base=0)
    opp.hand = [('E', 'Fire'), ('P', 'x')]            # index 0 -> ('E','Fire') routed to disc_energy
    d = _fn(txt)(ctx)
    assert d == 0, d
    assert len(opp.hand) == 1 and opp.disc_energy['Fire'] == 1, (opp.hand, dict(opp.disc_energy))


def t_opp_discard_random_pokemon():
    txt = "Discard a random card from your opponent's hand."
    ctx, at, df, me, opp = mk(text=txt, base=50)
    opp.hand = [('P', 'y')]                            # Pokémon token -> discard pile
    d = _fn(txt)(ctx)
    assert d == 50, d
    assert opp.hand == [] and opp.discard == [('P', 'y')], (opp.hand, opp.discard)


def t_opp_discard_2():
    txt = "Your opponent discards 2 cards from their hand."
    ctx, at, df, me, opp = mk(text=txt, base=40)
    opp.hand = [('E', 'Water'), ('P', 'a'), ('P', 'b')]
    d = _fn(txt)(ctx)
    assert d == 40, d
    assert opp.hand == [('E', 'Water')], opp.hand      # last 2 discarded
    assert opp.discard == [('P', 'b'), ('P', 'a')], opp.discard


def t_opp_shuffle_3():
    txt = "Your opponent chooses 3 cards from their hand and shuffles those cards into their deck."
    ctx, at, df, me, opp = mk(text=txt, base=0)
    opp.hand = [('P', 'a'), ('P', 'b'), ('P', 'c'), ('P', 'd')]
    deck_before = len(opp.deck)
    d = _fn(txt)(ctx)
    assert d == 0, d
    assert len(opp.hand) == 1 and len(opp.deck) == deck_before + 3, (len(opp.hand), len(opp.deck))


def t_opp_shuffle_3_fewer():
    txt = "Your opponent chooses 3 cards from their hand and shuffles those cards into their deck."
    ctx, at, df, me, opp = mk(text=txt, base=0)
    opp.hand = [('P', 'a')]                            # fewer than 3 -> shuffle what's there
    deck_before = len(opp.deck)
    _fn(txt)(ctx)
    assert len(opp.hand) == 0 and len(opp.deck) == deck_before + 1, (len(opp.hand), len(opp.deck))


def t_opp_item_lock():
    d, ctx, at, df, me, opp = run("[40] During your opponent's next turn, they can't play any Item cards from their hand.", base=40)
    assert d == 40, d
    assert opp.no_item_until == 4, getattr(opp, 'no_item_until', None)   # game.turn+1 == 4


# ---------------------------------------------------------------- energy bounce (to hand)
def t_bounce_2_opp_energy():
    txt = "You may put 2 Energy attached to your opponent's Active Pokémon into their hand."
    ctx, at, df, me, opp = mk(text=txt, base=70, def_energy={'Fire': 3})
    d = _fn(txt)(ctx)
    assert d == 70, d
    assert df.total_energy() == 1, df.total_energy()          # 3 - 2 == 1
    assert opp.hand.count(('E', 'Fire')) == 2, opp.hand       # 2 energy returned to opponent's hand


def t_bounce_1_self_energy():
    txt = "Put an Energy attached to this Pokémon into your hand."
    ctx, at, df, me, opp = mk(text=txt, base=140, atk_energy={'Fire': 2})
    d = _fn(txt)(ctx)
    assert d == 140, d
    assert at.total_energy() == 1, at.total_energy()          # 2 - 1 == 1
    assert me.hand.count(('E', 'Fire')) == 1, me.hand


# ---------------------------------------------------------------- self / card recursion
def t_bounce_self():
    txt = "Put this Pokémon and all attached cards into your hand."
    ctx, at, df, me, opp = mk(text=txt, base=30, atk_energy={'Fire': 2}, my_bench=1)
    d = _fn(txt)(ctx)
    assert d == 30, d
    assert ('P', at.card) in me.hand, me.hand
    assert me.hand.count(('E', 'Fire')) == 2, me.hand         # 2 attached energy returned to hand
    assert me.active is not at, "attacker should have left the Active spot"
    assert me.active is not None, "a benched Pokémon should have been promoted"


def t_bounce_self_no_bench():
    txt = "Put this Pokémon and all attached cards into your hand."
    ctx, at, df, me, opp = mk(text=txt, base=30, my_bench=0)
    d = _fn(txt)(ctx)
    assert d == 30, d
    assert ('P', at.card) in me.hand and me.active is None, (me.hand, me.active)   # no crash, no promote


def t_recover_supporter():
    txt = "Put a Supporter card from your discard pile into your hand."
    ctx, at, df, me, opp = mk(text=txt, base=0)
    sup = ('T', {'name': 'Iono', 'trainerType': 'Supporter'})
    me.discard = [('P', at.card), sup]
    d = _fn(txt)(ctx)
    assert d == 0, d
    assert sup in me.hand and sup not in me.discard, (me.hand, me.discard)


def t_recover_supporter_none():
    txt = "Put a Supporter card from your discard pile into your hand."
    ctx, at, df, me, opp = mk(text=txt, base=0)
    me.discard = [('P', at.card)]                     # no Supporter present -> no-op
    d = _fn(txt)(ctx)
    assert d == 0 and me.hand == [] and len(me.discard) == 1, (d, me.hand, me.discard)


def t_recover_pokemon():
    txt = "Put a Pokémon from your discard pile into your hand."
    ctx, at, df, me, opp = mk(text=txt, base=0)
    me.discard = [('P', at.card)]
    d = _fn(txt)(ctx)
    assert d == 0, d
    assert me.hand == [('P', at.card)] and me.discard == [], (me.hand, me.discard)


# ---------------------------------------------------------------- hand-size gate
def t_needs_exactly_3_in_hand():
    txt = "If you don't have exactly 3 cards in your hand, this attack does nothing."
    ctx, at, df, me, opp = mk(text=txt, base=120)
    me.hand = [('E', 'Fire'), ('E', 'Fire'), ('P', 'x')]      # exactly 3 -> full damage
    assert _fn(txt)(ctx) == 120, "exactly 3 in hand should deal full damage"
    ctx2, *_ = mk(text=txt, base=120)
    ctx2.me.hand = [('E', 'Fire'), ('P', 'x')]                # not 3 -> nothing
    assert _fn(txt)(ctx2) == 0, "hand != 3 should do nothing"


# ---------------------------------------------------------------- double KO
def t_both_active_ko():
    d, ctx, at, df, me, opp = run("- Both Active Pokémon are Knocked Out.", base=0)
    assert d == 0, d
    assert at.damage >= at.max_hp, (at.damage, at.max_hp)     # attacker marked lethal
    assert df.damage >= df.max_hp, (df.damage, df.max_hp)     # defender marked lethal
    # the engine's own KO check agrees for BOTH actives (each side loses its Active + takes a prize)
    assert ctx.game.is_ko(df, opp) and ctx.game.is_ko(at, me), "engine must see both actives as KO'd"


# ---------------------------------------------------------------- delayed discard (no engine hook)
def t_delayed_discard_defender():
    txt = "At the end of your opponent's next turn, discard the Defending Pokémon and all attached cards."
    d, ctx, at, df, me, opp = run(txt, base=0)
    assert d == 0, d
    assert df.status.get('DiscardEndOfOppNextTurn') == 3, df.status   # intent recorded (game.turn)
    assert df.damage == 0, "must NOT KO the defender immediately"


TESTS = [
    t_ignore_resistance,
    t_ignore_defender_effects,
    t_discard_stadium,
    t_may_discard_stadium,
    t_nothing_without_stadium,
    t_self_lock_all,
    t_self_lock_accel_stab,
    t_self_lock_flashing_bolt,
    t_self_lock_zap_cannon,
    t_defender_lock_use_attacks,
    t_defender_lock_attack,
    t_defender_lock_one_attack,
    t_copy_opponent_attack,
    t_copy_opponent_tera_attack,
    t_opp_reveal_hand,
    t_opp_random_to_deck,
    t_opp_random_to_deck_empty,
    t_opp_discard_random_energy,
    t_opp_discard_random_pokemon,
    t_opp_discard_2,
    t_opp_shuffle_3,
    t_opp_shuffle_3_fewer,
    t_opp_item_lock,
    t_bounce_2_opp_energy,
    t_bounce_1_self_energy,
    t_bounce_self,
    t_bounce_self_no_bench,
    t_recover_supporter,
    t_recover_supporter_none,
    t_recover_pokemon,
    t_needs_exactly_3_in_hand,
    t_both_active_ko,
    t_delayed_discard_defender,
]

if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
