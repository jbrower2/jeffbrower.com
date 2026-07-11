#!/usr/bin/env python3
"""Unit tests for batch conditional_damage_0. Deterministic RNG (heads=0.0, tails=0.9).

Covers every effect's returned damage AND its key state change, exercising both branches of the
conditional/scaling effects. A coverage test asserts all 28 batch keys registered with exact text.
"""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # ensure sim/ importable
from collections import Counter
from effects_testkit import mk, run, runner
from engine import Mon
from cards import load_cards
import attack_effects as AE
import effects_gen.batch_conditional_damage_0   # noqa: F401  (registers the effects)

BK, BN = load_cards()
FILL = next(c for c in BK.values() if c.cat == 'cat-green' and c.stage == 0)   # Bulbasaur (VANILLA)
WIG = BN['Wigglytuff'][0]              # has 'Round' attack, stage 1
PAL = BN['Palpitoad'][0]              # has 'Round' attack
WEEZ = BN['Weezing'][0]               # 'Weezing' in name
KOFF = BN['Koffing'][0]               # 'Koffing' in name
IONO = BN["Iono's Voltorb"][0]        # Iono's family, pays Lightning
EXCARD = next(c for c in BK.values() if c.is_ex)
DARKCARD = next(c for c in BK.values() if c.ptype == 'Darkness')
WATERCARD = next(c for c in BK.values() if c.ptype == 'Water')
STAGE1CARD = next(c for c in BK.values() if c.stage == 1)

TESTS = []
def test(fn): TESTS.append(fn); return fn


def _call(text, ctx):
    return AE.ATTACK_EFFECTS[AE.normalize(text)](ctx)


# ---------------------------------------------------------------- coverage: every key registered
@test
def t_all_keys_registered():
    p = os.path.join(os.path.dirname(__file__), '..', 'effects_work', 'batches.json')
    b = next(x for x in json.load(open(p))['batches'] if x['id'] == 'conditional_damage_0')
    missing = [e['key'] for e in b['effects'] if AE.normalize(e['key']) not in AE.ATTACK_EFFECTS]
    assert not missing, f'unregistered keys: {missing}'
    assert len(b['effects']) == 28, len(b['effects'])


# ---------------------------------------------------------------- per-each scaling (×)
@test
def t_times_per_self_counter():
    T = "This attack does 10 damage for each damage counter on this Pokémon."
    ctx, at, *_ = mk(base=10)
    at.damage = 30
    assert _call(T, ctx) == 30, 'wrong: 3 counters × 10'
    at.damage = 0
    assert _call(T, ctx) == 0


@test
def t_times_per_opp_counter():
    T = "This attack does 20 damage for each damage counter on your opponent's Active Pokémon."
    ctx, at, df, *_ = mk(base=20)
    df.damage = 50
    assert _call(T, ctx) == 100          # 5 counters × 20
    df.damage = 0
    assert _call(T, ctx) == 0


@test
def t_times_per_round_mon():
    T = "This attack does 40 damage for each of your Pokémon in play that has the Round attack."
    ctx, at, df, me, opp = mk(base=40)
    me.bench = [Mon(WIG), Mon(PAL)]      # both have Round; active (FILL) does not
    opp.bench = [Mon(WIG)]              # opponent's Round mon must NOT count
    assert _call(T, ctx) == 80          # 2 of MY mons × 40
    me.bench = [Mon(FILL)]
    assert _call(T, ctx) == 0


@test
def t_times_per_round_mon_attacker_counts_itself():
    # Real play: the attacker (Wigglytuff/Palpitoad) IS a Round-mon and must count itself.
    T = "This attack does 40 damage for each of your Pokémon in play that has the Round attack."
    ctx, at, df, me, opp = mk(base=40)
    me.active = Mon(WIG)                 # attacker itself has the Round attack
    me.bench = [Mon(PAL), Mon(FILL)]     # PAL has Round; FILL does not
    assert _call(T, ctx) == 80           # WIG(self) + PAL = 2 × 40
    me.bench = [Mon(FILL)]
    assert _call(T, ctx) == 40           # only the attacker itself


@test
def t_times_per_tr_supporter():
    T = 'This attack does 20 damage for each Supporter card that has "Team Rocket" in its name in your discard pile.'
    ctx, at, df, me, opp = mk(base=20)
    me.discard = [
        ('T', {'name': "Team Rocket's Ariana", 'trainerType': 'Supporter'}),
        ('T', {'name': "Team Rocket's Archer", 'trainerType': 'Supporter'}),
        ('T', {'name': 'Iono', 'trainerType': 'Supporter'}),              # not Team Rocket
        ('T', {'name': "Team Rocket's Bother-Bot", 'trainerType': 'Item'}),  # not a Supporter
        ('P', FILL),                                                      # KO'd Pokémon
    ]
    assert _call(T, ctx) == 40          # exactly 2 TR Supporters × 20
    me.discard = []
    assert _call(T, ctx) == 0


@test
def t_times_per_all_opp_energy():
    T = "This attack does 40 damage for each Energy attached to all of your opponent's Pokémon."
    ctx, at, df, me, opp = mk(base=40)
    df.energy = Counter({'Water': 2})
    b = Mon(FILL); b.energy = Counter({'Fire': 1}); opp.bench = [b]
    assert _call(T, ctx) == 120         # (2 + 1) × 40


@test
def t_times_per_opp_active_energy():
    T = "This attack does 20 damage for each Energy attached to your opponent's Active Pokémon."
    ctx, at, df, *_ = mk(base=20)
    df.energy = Counter({'Psychic': 3})
    assert _call(T, ctx) == 60
    df.energy = Counter()
    assert _call(T, ctx) == 0


@test
def t_times_per_my_mons():
    T = "This attack does 20 damage for each of your Pokémon in play."
    assert run(T, base=20, my_bench=3)[0] == 80   # active + 3 bench = 4
    assert run(T, base=20, my_bench=0)[0] == 20   # active only


@test
def t_times_per_special_condition():
    T = "This attack does 100 damage for each Special Condition affecting your opponent's Active Pokémon."
    ctx, at, df, *_ = mk(base=100)
    df.status = {'Poisoned': True, 'Burned': True, 'CantRetreat': 3}  # CantRetreat is NOT a condition
    assert _call(T, ctx) == 200
    df.status = {}
    assert _call(T, ctx) == 0


@test
def t_times_per_koffing_weezing():
    T = 'This attack does 40 damage for each Pokémon in play that has "Koffing" or "Weezing" in its name (both yours and your opponent\'s).'
    ctx, at, df, me, opp = mk(base=40)
    me.bench = [Mon(WEEZ), Mon(FILL)]
    opp.bench = [Mon(KOFF)]
    assert _call(T, ctx) == 80          # Weezing (mine) + Koffing (opp) = 2 × 40
    me.bench = [Mon(FILL)]; opp.bench = [Mon(FILL)]
    assert _call(T, ctx) == 0


# ---------------------------------------------------------------- per-each scaling (+)
@test
def t_plus30_per_opp_active_energy():
    T = "This attack does 30 more damage for each Energy attached to your opponent's Active Pokémon."
    assert run(T, base=10, def_energy={'Water': 3})[0] == 100    # 10 + 30×3
    ctx, at, df, *_ = mk(base=10)
    df.energy = Counter()
    assert _call(T, ctx) == 10


@test
def t_plus10_per_self_counter():
    T = "This attack does 10 more damage for each damage counter on this Pokémon."
    ctx, at, *_ = mk(base=60)
    at.damage = 40
    assert _call(T, ctx) == 100          # 60 + 10×4
    at.damage = 0
    assert _call(T, ctx) == 60


@test
def t_plus20_per_self_water():
    T = "This attack does 20 more damage for each {W} Energy attached to this Pokémon."
    assert run(T, base=60, atk_energy={'Water': 2})[0] == 100    # 60 + 20×2
    assert run(T, base=60, atk_energy={'Fire': 2})[0] == 60      # no Water


@test
def t_plus20_per_ionos_lightning():
    T = "This attack does 20 more damage for each {L} Energy attached to all of your Iono's Pokémon."
    ctx, at, df, me, opp = mk(base=20)
    me.active = Mon(IONO); me.active.energy = Counter({'Lightning': 2})
    b1 = Mon(IONO); b1.energy = Counter({'Lightning': 1})
    b2 = Mon(WIG); b2.energy = Counter({'Lightning': 5})            # not an Iono's mon -> ignored
    me.bench = [b1, b2]
    assert _call(T, ctx) == 80           # 20 + 20×(2+1)
    me.active = Mon(WIG); me.bench = [Mon(FILL)]
    assert _call(T, ctx) == 20           # no Iono's mon in play


@test
def t_plus30_per_self_grass():
    T = "This attack does 30 more damage for each {G} Energy attached to this Pokémon."
    assert run(T, base=60, atk_energy={'Grass': 2})[0] == 120     # 60 + 30×2
    assert run(T, base=60, atk_energy={'Water': 2})[0] == 60


# ---------------------------------------------------------------- if-condition bonus (+)
@test
def t_plus60_if_opp_damaged():
    T = "If your opponent's Active Pokémon already has any damage counters on it, this attack does 60 more damage."
    ctx, at, df, *_ = mk(base=60)
    df.damage = 10
    assert _call(T, ctx) == 120
    df.damage = 0
    assert _call(T, ctx) == 60


@test
def t_plus70_if_opp_ex():
    T = "If your opponent's Active Pokémon is a Pokémon ex, this attack does 70 more damage."
    assert run(T, base=50)[0] == 50                    # VANILLA defender: not ex
    ctx, at, df, *_ = mk(base=50)
    df.card = EXCARD
    assert _call(T, ctx) == 120


@test
def t_plus100_if_opp_dark():
    T = "If your opponent's Active Pokémon is a {D} Pokémon, this attack does 100 more damage."
    assert run(T, base=100)[0] == 100                  # VANILLA: Grass
    ctx, at, df, *_ = mk(base=100)
    df.card = DARKCARD
    assert _call(T, ctx) == 200


@test
def t_plus120_if_opp_has_water():
    T = "If your opponent has any {W} Pokémon in play, this attack does 120 more damage."
    assert run(T, base=40)[0] == 40                    # all opp mons Grass
    ctx, at, df, me, opp = mk(base=40)
    opp.bench = [Mon(WATERCARD)]
    assert _call(T, ctx) == 160


@test
def t_plus90_if_opp_stage1():
    T = "If your opponent's Active Pokémon is a Stage 1 Pokémon, this attack does 90 more damage."
    assert run(T, base=90)[0] == 90                    # VANILLA: stage 0
    ctx, at, df, *_ = mk(base=90)
    df.card = STAGE1CARD
    assert _call(T, ctx) == 180


@test
def t_plus140_two_extra_energy():
    T = "If this Pokémon has at least 2 extra Energy attached (in addition to this attack's cost), this attack does 140 more damage."
    # testkit cost is empty -> threshold is 2 total energy
    assert run(T, base=120, atk_energy={'Grass': 3})[0] == 260
    assert run(T, base=120, atk_energy={'Grass': 1})[0] == 120
    # real-cost path: cost 'GGCC' (len 4) -> needs >=6 total
    ctx, at, *_ = mk(base=120)
    ctx.attack['cost'] = 'GGCC'
    at.energy = Counter({'Grass': 5})
    assert _call(T, ctx) == 120          # 5 < 6
    at.energy = Counter({'Grass': 6})
    assert _call(T, ctx) == 260          # 6 >= 6


@test
def t_plus120_if_evo_magneton():
    T = "If this Pokémon evolved from Magneton during this turn, this attack does 120 more damage."
    ctx, at, *_ = mk(base=50)
    at.turns = 1                          # evolved-this-turn heuristic
    assert _call(T, ctx) == 170
    at.turns = 2
    assert _call(T, ctx) == 50
    at.turns = 0
    assert _call(T, ctx) == 50


@test
def t_plus80_if_evo_mistys_staryu():
    T = "If this Pokémon evolved from Misty's Staryu during this turn, this attack does 80 more damage."
    ctx, at, *_ = mk(base=60)
    at.turns = 1
    assert _call(T, ctx) == 140
    at.turns = 2
    assert _call(T, ctx) == 60


# ---------------------------------------------------------------- cross-turn history (now tracked)
@test
def t_ko_last_turn_bonus():
    T = "If any of your Pokémon were Knocked Out by damage from an attack during your opponent's last turn, this attack does 90 more damage."
    assert run(T, base=30)[0] == 30                     # no KO on the opponent's last turn -> base
    assert run(T, base=30, ko_last=True)[0] == 120      # a mon KO'd last turn -> +90


@test
def t_used_pervasive_gas_bonus():
    T = "If this Pokémon used Pervasive Gas during your last turn, this attack does 120 more damage."
    ctx, at, *_ = mk(base=50)
    assert _call(T, ctx) == 50                          # never used Pervasive Gas -> base
    at.last_atk = 'Pervasive Gas'; at.last_atk_turn = ctx.game.turn - 2
    assert _call(T, ctx) == 170                         # used it on my previous turn -> +120
    at.last_atk_turn = ctx.game.turn - 4               # older than my previous turn -> no bonus
    assert _call(T, ctx) == 50


@test
def t_ethans_ko_stays_conservative():
    # No KO'd-card identity is tracked, so this family-specific bonus must never fire from a generic KO.
    T = "If any of your Ethan's Pokémon were Knocked Out by damage from an attack during your opponent's last turn, this attack does 100 more damage."
    assert run(T, base=70)[0] == 70
    assert run(T, base=70, ko_last=True)[0] == 70       # a generic KO must NOT grant the +100


# ---------------------------------------------------------------- structural side effects
@test
def t_salazzle_discard():
    T = "Your opponent discards a card from their hand. If this Pokémon evolved from Salandit during this turn, your opponent discards 2 more cards."
    # not-evolved: opponent discards exactly 1
    ctx, at, df, me, opp = mk(base=0)
    opp.hand = [('P', FILL), ('E', 'Fire'), ('T', {'name': 'X'}), ('P', WIG)]
    at.turns = 0
    dmg = _call(T, ctx)
    assert dmg == 0
    assert len(opp.hand) == 3 and ('P', WIG) in opp.discard      # last card (a Pokémon) discarded
    # evolved-this-turn: opponent discards 3
    ctx, at, df, me, opp = mk(base=0)
    opp.hand = [('P', FILL), ('E', 'Fire'), ('T', {'name': 'X'}), ('P', WIG)]
    at.turns = 1
    _call(T, ctx)
    assert len(opp.hand) == 1
    assert opp.disc_energy.get('Fire', 0) == 1                   # the energy card routed to disc_energy


@test
def t_buff_next_turn_120():
    T = "During your next turn, attacks used by this Pokémon do 120 more damage to your opponent's Active Pokémon (before applying Weakness and Resistance)."
    d, ctx, at, *_ = run(T, base=20)
    assert d == 20                                # this turn deals only the printed base
    assert at.ramp.get('Bind Down') == 120        # payoff attack buffed for next turn (VANILLA's attack)


@test
def t_buff_next_turn_120_real_card_targets_payoff():
    # On the real card (Donphan ME04: 'No Reprieve' [20] setup + 'Smashing Headbutt' [180] payoff),
    # firing the setup attack buffs the PAYOFF hit +120 for next turn and does NOT re-buff itself
    # (the modeled scope: the mon's OTHER attacks, not the small setup attack). Verifies amount+target.
    T = "During your next turn, attacks used by this Pokémon do 120 more damage to your opponent's Active Pokémon (before applying Weakness and Resistance)."
    donphan = next(c for c in BN['Donphan'] if c.set == 'ME04')
    ctx, at, df, me, opp = mk(base=20)
    at.card = donphan
    ctx.attack = next(a for a in donphan.attacks if a['name'] == 'No Reprieve')
    d = _call(T, ctx)
    assert d == 20                                # this turn: printed base only
    assert at.ramp.get('Smashing Headbutt') == 120   # the payoff attack is buffed +120
    assert at.ramp.get('No Reprieve', 0) == 0        # the setup attack itself is not buffed


@test
def t_poliwrath_commit():
    T = "You may do 120 more damage. If you do, shuffle this Pokémon and all attached cards into your deck."
    ctx, at, df, me, opp = mk(base=120, my_bench=1, atk_energy={'Water': 2})
    hp_card = next(c for c in BK.values()
                   if 150 <= c.hp <= 230 and c.weakness != at.card.ptype)
    newdf = Mon(hp_card); newdf.energy = Counter()
    opp.active = newdf; ctx.defender = newdf                     # ~150 HP: base 120 won't KO, 240 will
    deck_before = len(me.deck)
    dmg = _call(T, ctx)
    assert dmg == 240
    assert me.active is not at                                   # attacker left the Active spot
    assert me.bench == []                                        # its one bench mon was promoted
    assert ('P', at.card) in me.deck                             # attacker shuffled into deck
    assert me.deck.count(('E', 'Water')) == 2                    # its 2 attached energy returned to deck
    assert len(me.deck) == deck_before + 3                       # +1 Pokémon, +2 energy


@test
def t_poliwrath_decline_base_kos():
    T = "You may do 120 more damage. If you do, shuffle this Pokémon and all attached cards into your deck."
    ctx, at, df, me, opp = mk(base=120)                          # VANILLA defender ~80 HP: base already KOs
    dmg = _call(T, ctx)
    assert dmg == 120
    assert me.active is at                                       # no self-shuffle


@test
def t_poliwrath_decline_no_bench():
    T = "You may do 120 more damage. If you do, shuffle this Pokémon and all attached cards into your deck."
    ctx, at, df, me, opp = mk(base=120, my_bench=0)
    hp_card = next(c for c in BK.values()
                   if 150 <= c.hp <= 230 and c.weakness != at.card.ptype)
    newdf = Mon(hp_card); newdf.energy = Counter()
    opp.active = newdf; ctx.defender = newdf
    dmg = _call(T, ctx)
    assert dmg == 120                                            # can't sacrifice the last Pokémon
    assert me.active is at


@test
def t_poliwrath_weakness_aware_commit():
    # Weakness-doubled: defender is weak to the attacker's type, ~250-300 HP. base 120×2=240 does NOT
    # KO, but the full (120+120)×2=480 does -> the extra converts a non-KO into a KO -> commit + shuffle.
    # (No existing test exercises the mult=2 branch of the KO decision.)
    T = "You may do 120 more damage. If you do, shuffle this Pokémon and all attached cards into your deck."
    ctx, at, df, me, opp = mk(base=120, my_bench=1)
    wk = next(c for c in BK.values() if c.weakness == at.card.ptype and 250 <= c.hp <= 300)
    nd = Mon(wk); nd.energy = Counter()
    opp.active = nd; ctx.defender = nd
    dmg = _call(T, ctx)
    assert dmg == 240                                            # base+120 committed
    assert me.active is not at                                   # weakness-aware KO -> self-shuffle
    assert ('P', at.card) in me.deck


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
