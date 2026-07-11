#!/usr/bin/env python3
"""Unit tests for batch coinflip_damage_0. Deterministic RNG: heads=0.0, tails=0.9 (cycles)."""
from collections import Counter
from effects_testkit import mk, run, runner
import attack_effects as AE
import effects_gen.batch_coinflip_damage_0   # noqa: F401  (registers the effects)

TESTS = []
def test(fn): TESTS.append(fn); return fn


def _call(text, ctx):
    return AE.ATTACK_EFFECTS[AE.normalize(text)](ctx)


# ---------------------------------------------------------------- Flip N coins: N × heads (base ignored)
@test
def t_f2_10():
    T = "10× Flip 2 coins. This attack does 10 damage for each heads."
    assert run(T, base=10, flips=(0.0,))[0] == 20          # HH
    assert run(T, base=10, flips=(0.0, 0.9))[0] == 10       # HT
    assert run(T, base=10, flips=(0.9,))[0] == 0            # TT (base ignored)


@test
def t_f3_10():
    T = "10× Flip 3 coins. This attack does 10 damage for each heads."
    assert run(T, base=10, flips=(0.0,))[0] == 30
    assert run(T, base=10, flips=(0.0, 0.0, 0.9))[0] == 20
    assert run(T, base=10, flips=(0.9,))[0] == 0


@test
def t_f4_10():
    T = "10× Flip 4 coins. This attack does 10 damage for each heads."
    assert run(T, base=10, flips=(0.0,))[0] == 40
    assert run(T, base=10, flips=(0.0, 0.0, 0.9, 0.9))[0] == 20   # HHTT (4 distinct values, no RNG cycle)
    assert run(T, base=10, flips=(0.9,))[0] == 0


@test
def t_f3_20():
    T = "20× Flip 3 coins. This attack does 20 damage for each heads."
    assert run(T, base=20, flips=(0.0,))[0] == 60
    assert run(T, base=20, flips=(0.0, 0.0, 0.9))[0] == 40   # HHT -> 2 heads (per-heads multiplier)
    assert run(T, base=20, flips=(0.9,))[0] == 0


@test
def t_f2_30():
    T = "30× Flip 2 coins. This attack does 30 damage for each heads."
    assert run(T, base=30, flips=(0.0,))[0] == 60
    assert run(T, base=30, flips=(0.0, 0.9))[0] == 30
    assert run(T, base=30, flips=(0.9,))[0] == 0


@test
def t_f3_30():
    T = "30× Flip 3 coins. This attack does 30 damage for each heads."
    assert run(T, base=30, flips=(0.0,))[0] == 90
    assert run(T, base=30, flips=(0.0, 0.0, 0.9))[0] == 60   # HHT -> 2 heads
    assert run(T, base=30, flips=(0.9,))[0] == 0


@test
def t_f5_30():
    T = "30× Flip 5 coins. This attack does 30 damage for each heads."
    assert run(T, base=30, flips=(0.0,))[0] == 150
    assert run(T, base=30, flips=(0.0, 0.0, 0.0, 0.9, 0.9))[0] == 90
    assert run(T, base=30, flips=(0.9,))[0] == 0


@test
def t_f2_40():
    T = "40× Flip 2 coins. This attack does 40 damage for each heads."
    assert run(T, base=40, flips=(0.0,))[0] == 80
    assert run(T, base=40, flips=(0.0, 0.9))[0] == 40
    assert run(T, base=40, flips=(0.9,))[0] == 0


@test
def t_f3_50():
    T = "50× Flip 3 coins. This attack does 50 damage for each heads."
    assert run(T, base=50, flips=(0.0,))[0] == 150
    assert run(T, base=50, flips=(0.0, 0.0, 0.9))[0] == 100   # HHT -> 2 heads
    assert run(T, base=50, flips=(0.9,))[0] == 0


@test
def t_f2_70():
    T = "70× Flip 2 coins. This attack does 70 damage for each heads."
    assert run(T, base=70, flips=(0.0,))[0] == 140
    assert run(T, base=70, flips=(0.0, 0.9))[0] == 70   # HT -> 1 head
    assert run(T, base=70, flips=(0.9,))[0] == 0


@test
def t_f4_70():
    T = "70× Flip 4 coins. This attack does 70 damage for each heads."
    assert run(T, base=70, flips=(0.0,))[0] == 280
    assert run(T, base=70, flips=(0.0, 0.0, 0.9, 0.9))[0] == 140   # HHTT -> 2 heads
    assert run(T, base=70, flips=(0.9,))[0] == 0


@test
def t_f4_80():
    T = "80× Flip 4 coins. This attack does 80 damage for each heads."
    assert run(T, base=80, flips=(0.0,))[0] == 320
    assert run(T, base=80, flips=(0.0, 0.0, 0.9, 0.9))[0] == 160   # HHTT -> 2 heads
    assert run(T, base=80, flips=(0.9,))[0] == 0


@test
def t_f2_90():
    T = "90× Flip 2 coins. This attack does 90 damage for each heads."
    assert run(T, base=90, flips=(0.0,))[0] == 180
    assert run(T, base=90, flips=(0.0, 0.9))[0] == 90
    assert run(T, base=90, flips=(0.9,))[0] == 0


# ---------------------------------------------------------------- Flip until tails: N × heads (base ignored)
@test
def t_ut_10():
    T = "10× Flip a coin until you get tails. This attack does 10 damage for each heads."
    assert run(T, base=10, flips=(0.0, 0.0, 0.9))[0] == 20  # 2 heads
    assert run(T, base=10, flips=(0.9,))[0] == 0            # immediate tails


@test
def t_ut_70():
    T = "70× Flip a coin until you get tails. This attack does 70 damage for each heads."
    assert run(T, base=70, flips=(0.0, 0.0, 0.0, 0.9))[0] == 210
    assert run(T, base=70, flips=(0.9,))[0] == 0


@test
def t_ut_90():
    T = "90× Flip a coin until you get tails. This attack does 90 damage for each heads."
    assert run(T, base=90, flips=(0.0, 0.9))[0] == 90
    assert run(T, base=90, flips=(0.9,))[0] == 0


# ---------------------------------------------------------------- Flip 1 coin: base + M more on heads
@test
def t_heads_plus_10():
    T = "10+ Flip a coin. If heads, this attack does 10 more damage."
    assert run(T, base=10, flips=(0.0,))[0] == 20
    assert run(T, base=10, flips=(0.9,))[0] == 10          # base kept on tails


@test
def t_heads_plus_40():
    T = "90+ Flip a coin. If heads, this attack does 40 more damage."
    assert run(T, base=90, flips=(0.0,))[0] == 130
    assert run(T, base=90, flips=(0.9,))[0] == 90


@test
def t_heads_plus_50():
    T = "20+ Flip a coin. If heads, this attack does 50 more damage."
    assert run(T, base=20, flips=(0.0,))[0] == 70
    assert run(T, base=20, flips=(0.9,))[0] == 20


@test
def t_heads_plus_60():
    T = "60+ Flip a coin. If heads, this attack does 60 more damage."
    assert run(T, base=60, flips=(0.0,))[0] == 120
    assert run(T, base=80, flips=(0.0,))[0] == 140         # base varies by card (Crustle 80)
    assert run(T, base=90, flips=(0.9,))[0] == 90          # tails -> base only (Druddigon 90)


# ---------------------------------------------------------------- Flip until tails: base + M more per heads
@test
def t_ut_plus_30():
    T = "10+ Flip a coin until you get tails. This attack does 30 more damage for each heads."
    assert run(T, base=10, flips=(0.0, 0.0, 0.9))[0] == 70  # 10 + 2*30
    assert run(T, base=10, flips=(0.9,))[0] == 10           # base only
    assert run(T, base=60, flips=(0.0, 0.9))[0] == 90       # Shiinotic 60 + 30


@test
def t_ut_plus_50():
    T = "30+ Flip a coin until you get tails. This attack does 50 more damage for each heads."
    assert run(T, base=30, flips=(0.0, 0.0, 0.9))[0] == 130  # 30 + 2*50
    assert run(T, base=30, flips=(0.9,))[0] == 30


# ---------------------------------------------------------------- coins == energy on both Actives
@test
def t_both_actives_energy_60():
    T = "60× Flip a coin for each Energy attached to both Active Pokémon. This attack does 60 damage for each heads."
    # attacker 1 + defender 1 = 2 coins
    assert run(T, base=60, atk_energy={'Grass': 1}, def_energy={'Water': 1}, flips=(0.0,))[0] == 120
    assert run(T, base=60, atk_energy={'Grass': 1}, def_energy={'Water': 1}, flips=(0.0, 0.9))[0] == 60
    assert run(T, base=60, atk_energy={'Grass': 1}, def_energy={'Water': 1}, flips=(0.9,))[0] == 0
    # coin count scales with total energy: 2 + 1 = 3 coins -> HHT -> 2 heads
    assert run(T, base=60, atk_energy={'Grass': 2}, def_energy={'Water': 1}, flips=(0.0, 0.0, 0.9))[0] == 120


# ---------------------------------------------------------------- flip-driven disruption
@test
def t_f2_discard_opp_energy():
    T = "[50] Flip 2 coins. For each heads, discard an Energy from your opponent's Active Pokémon."
    ctx, at, df, me, opp = mk(text=T, base=50, def_energy={'Water': 3}, flips=(0.0,))
    dmg = _call(T, ctx)
    assert dmg == 50 and df.total_energy() == 1, (dmg, df.total_energy())   # 2 heads -> -2
    # tails: keep all energy, still deal base
    ctx2, at2, df2, *_ = mk(text=T, base=50, def_energy={'Water': 3}, flips=(0.9,))
    assert _call(T, ctx2) == 50 and df2.total_energy() == 3


@test
def t_f3_discard_opp_hand():
    T = "[50] Flip 3 coins. For each heads, discard a random card from your opponent's hand."
    ctx, at, df, me, opp = mk(text=T, base=50, flips=(0.0,))
    opp.hand = [('P', object()), ('E', 'Fire'), ('T', {'name': 'x'}), ('P', object())]
    dmg = _call(T, ctx)                                   # 3 heads -> discard 3
    assert dmg == 50 and len(opp.hand) == 1, (dmg, len(opp.hand))
    assert opp.disc_energy['Fire'] == 1                    # the discarded basic energy lands in disc_energy
    assert len(opp.discard) == 2                           # two non-energy cards to discard pile
    # tails -> no discard
    ctx2, _, _, _, opp2 = mk(text=T, base=50, flips=(0.9,))
    opp2.hand = [('P', object()), ('P', object())]
    assert _call(T, ctx2) == 50 and len(opp2.hand) == 2


@test
def t_f3_discard_opp_hand_empty():
    T = "[50] Flip 3 coins. For each heads, discard a random card from your opponent's hand."
    ctx, at, df, me, opp = mk(text=T, base=50, flips=(0.0,))
    opp.hand = []                                          # nothing to discard -> no crash, deals base
    assert _call(T, ctx) == 50 and opp.hand == []


@test
def t_ut_mill_opp_deck():
    T = "- Flip a coin until you get tails. For each heads, discard the top card of your opponent's deck."
    ctx, at, df, me, opp = mk(text=T, base=0, flips=(0.0, 0.0, 0.9))
    before = len(opp.deck)                                 # testkit deck ends in ('E','Colorless') tokens
    dmg = _call(T, ctx)                                    # 2 heads -> mill 2
    assert dmg == 0 and len(opp.deck) == before - 2, (dmg, len(opp.deck))
    assert opp.disc_energy['Colorless'] == 2               # top 2 were basic energy -> disc_energy
    # immediate tails -> no mill
    ctx2, _, _, _, opp2 = mk(text=T, base=0, flips=(0.9,))
    b2 = len(opp2.deck)
    assert _call(T, ctx2) == 0 and len(opp2.deck) == b2


# ---------------------------------------------------------------- Iono's Electrode self-destruct
@test
def t_selfdestruct_ko_heads():
    T = "- This Pokémon does 100 damage to itself. Flip a coin. If heads, your opponent's Active Pokémon is Knocked Out."
    ctx, at, df, me, opp = mk(text=T, base=0, flips=(0.0,))
    dmg = _call(T, ctx)
    assert dmg == 0                                        # KO is direct, not returned damage
    assert at.damage == 100                                # unconditional self-damage
    assert df.damage >= df.max_hp and df.hp_left <= 0      # defender forced to a KO state
    assert ctx.game.is_ko(df, opp)


@test
def t_selfdestruct_ko_tails():
    T = "- This Pokémon does 100 damage to itself. Flip a coin. If heads, your opponent's Active Pokémon is Knocked Out."
    ctx, at, df, me, opp = mk(text=T, base=0, flips=(0.9,))
    dmg = _call(T, ctx)
    assert dmg == 0 and at.damage == 100                   # self-damage still happens on tails
    assert df.damage == 0 and not ctx.game.is_ko(df, opp)  # defender untouched


# ---------------------------------------------------------------- Tauros stampede (coins == "Tauros" mons)
class _NamedCard:
    """Minimal card stub: the effect only reads .card.name for the coin count."""
    def __init__(self, name):
        self.name = name


@test
def t_tauros_two_tauros_all_heads():
    T = ('Choose 1 of your opponent\'s Pokémon and flip a coin for each of your Pokémon in play that '
         'has "Tauros" in its name. This attack does 50 damage to the chosen Pokémon for each heads. '
         '(Don\'t apply Weakness and Resistance for Benched Pokémon.)')
    ctx, at, df, me, opp = mk(text=T, base=0, flips=(0.0,), my_bench=1)
    at.card = _NamedCard('Tauros')                         # attacker (= me.active) counts
    me.bench[0].card = _NamedCard('Paldean Tauros')        # substring "Tauros" also counts
    assert _call(T, ctx) == 100                            # 2 coins, both heads -> 2*50


@test
def t_tauros_one_tauros_heads():
    T = ('Choose 1 of your opponent\'s Pokémon and flip a coin for each of your Pokémon in play that '
         'has "Tauros" in its name. This attack does 50 damage to the chosen Pokémon for each heads. '
         '(Don\'t apply Weakness and Resistance for Benched Pokémon.)')
    ctx, at, df, me, opp = mk(text=T, base=0, flips=(0.0,), my_bench=1)
    at.card = _NamedCard('Tauros')                         # only the attacker is a Tauros
    me.bench[0].card = _NamedCard('Bidoof')                # a non-Tauros bench mon -> only 1 coin
    assert _call(T, ctx) == 50


@test
def t_tauros_all_tails():
    T = ('Choose 1 of your opponent\'s Pokémon and flip a coin for each of your Pokémon in play that '
         'has "Tauros" in its name. This attack does 50 damage to the chosen Pokémon for each heads. '
         '(Don\'t apply Weakness and Resistance for Benched Pokémon.)')
    ctx, at, df, me, opp = mk(text=T, base=0, flips=(0.9,), my_bench=1)
    at.card = _NamedCard('Tauros')
    me.bench[0].card = _NamedCard('Tauros')
    assert _call(T, ctx) == 0                              # 2 coins, both tails -> 0


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
