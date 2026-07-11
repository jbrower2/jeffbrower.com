#!/usr/bin/env python3
"""Unit tests for batch_coinflip_damage_1. heads=0.0, tails=0.9 in the scripted RNG."""
from collections import Counter
from effects_testkit import mk, run, runner, VANILLA
import attack_effects as AE
import effects_gen.batch_coinflip_damage_1  # noqa: F401  (registers effects)


def _resolve(text, ctx):
    return AE.ATTACK_EFFECTS[AE.normalize(text)](ctx)


class _Ptype:
    """Minimal card stub exposing only .ptype (all the {D}-count effect reads)."""
    def __init__(self, ptype):
        self.ptype = ptype


# ---- 1. Zangoose: 3 coins stepped bonus ----
K1 = ("Flip 3 coins. If 1 of them is heads, this attack does 20 more damage. If 2 of them are heads, "
      "this attack does 50 more damage. If all of them are heads, this attack does 80 more damage.")


def t_zangoose_steps():
    assert run(K1, base=10, flips=(0.9,))[0] == 10             # 0 heads -> +0
    assert run(K1, base=10, flips=(0.0, 0.9, 0.9))[0] == 30    # 1 head  -> +20
    assert run(K1, base=10, flips=(0.0, 0.0, 0.9))[0] == 60    # 2 heads -> +50
    assert run(K1, base=10, flips=(0.0,))[0] == 90             # 3 heads -> +80


# ---- 2. Crawdaunt: mill top per heads ----
K2 = "Flip 2 coins. For each heads, discard the top card of your opponent's deck."


def t_crawdaunt_mill():
    d, ctx, at, df, me, opp = run(K2, base=40, flips=(0.0, 0.0))
    assert d == 40
    assert len(opp.deck) == 14                                 # 16 -> 14 (2 milled)
    assert sum(opp.disc_energy.values()) == 2                  # milled energy tokens tracked
    d2, _, _, _, _, opp2 = run(K2, base=40, flips=(0.9,))[:6]
    assert d2 == 40 and len(opp2.deck) == 16                   # both tails -> no mill


# ---- 3./14./18./21. flip-until-tails multipliers ----
def t_until_tails_variants():
    # heads,heads,tails -> 2 heads
    assert run("Flip a coin until you get tails. This attack does 30 damage for each heads.",
               base=30, flips=(0.0, 0.0, 0.9))[0] == 60
    assert run("Flip a coin until you get tails. This attack does 40 damage for each heads.",
               base=40, flips=(0.0, 0.0, 0.9))[0] == 80
    assert run("Flip a coin until you get tails. This attack does 50 damage for each heads.",
               base=50, flips=(0.0, 0.0, 0.9))[0] == 100
    assert run("Flip a coin until you get tails. This attack does 100 damage for each heads.",
               base=100, flips=(0.0, 0.0, 0.9))[0] == 200
    # immediate tails -> 0 heads -> 0 damage
    assert run("Flip a coin until you get tails. This attack does 30 damage for each heads.",
               base=30, flips=(0.9,))[0] == 0


# ---- 4./8./9./10./20. fixed-count "for each heads" multipliers ----
def t_fixed_count_multipliers():
    assert run("Flip 2 coins. This attack does 100 damage for each heads.", base=100, flips=(0.0,))[0] == 200
    assert run("Flip 2 coins. This attack does 100 damage for each heads.", base=100, flips=(0.0, 0.9))[0] == 100
    assert run("Flip 2 coins. This attack does 100 damage for each heads.", base=100, flips=(0.9,))[0] == 0
    assert run("Flip 3 coins. This attack does 120 damage for each heads.", base=120, flips=(0.0,))[0] == 360
    assert run("Flip 4 coins. This attack does 100 damage for each heads.", base=100, flips=(0.0,))[0] == 400
    assert run("Flip 2 coins. This attack does 80 damage for each heads.", base=80, flips=(0.0, 0.0))[0] == 160
    assert run("Flip 4 coins. This attack does 30 damage for each heads.", base=30, flips=(0.0, 0.0, 0.9, 0.9))[0] == 60
    # all-heads pins the coin count to exactly 4 (flips(2)->60, flips(3)->90 would both differ)
    assert run("Flip 4 coins. This attack does 30 damage for each heads.", base=30, flips=(0.0,))[0] == 120


# ---- 5. Watchog: attacker chooses cards to shuffle away ----
K5 = ("Flip 3 coins. If any of them are heads, your opponent reveals their hand. For each heads, "
      "choose a card you find there and shuffle it into your opponent's deck.")


def t_watchog_choose():
    ctx, at, df, me, opp = mk(text=K5, base=0, flips=(0.0,))     # 3 heads
    opp.hand = [('E', 'Colorless'), ('P', VANILLA), ('P', VANILLA), ('E', 'Colorless')]
    before = len(opp.deck)
    d = _resolve(K5, ctx)
    assert d == 0
    assert len(opp.hand) == 1                                   # 3 shuffled away
    assert opp.hand[0][0] == 'E'                                # kept the energy, stripped Pokémon first
    assert len(opp.deck) == before + 3
    # 0 heads -> nothing moved
    ctx2, _, _, me2, opp2 = mk(text=K5, base=0, flips=(0.9,))
    opp2.hand = [('P', VANILLA), ('E', 'Colorless')]
    assert _resolve(K5, ctx2) == 0 and len(opp2.hand) == 2


# ---- 6. Scrafty: coin per {D} Pokémon in play ----
K6 = "Flip a coin for each {D} Pokémon you have in play. This attack does 60 damage for each heads."


def t_scrafty_dark_count():
    # 2 Darkness in play (active + 1 bench), both heads -> 120
    ctx, at, df, me, opp = mk(text=K6, base=60, flips=(0.0,), my_bench=1)
    at.card = _Ptype('Darkness')
    me.bench[0].card = _Ptype('Darkness')
    assert _resolve(K6, ctx) == 120
    # same board, both tails -> 0
    ctx2, at2, _, me2, _ = mk(text=K6, base=60, flips=(0.9,), my_bench=1)
    at2.card = _Ptype('Darkness'); me2.bench[0].card = _Ptype('Darkness')
    assert _resolve(K6, ctx2) == 0
    # no Darkness in play -> 0 coins -> 0 regardless of flips
    ctx3, at3, _, me3, _ = mk(text=K6, base=60, flips=(0.0,), my_bench=2)
    at3.card = _Ptype('Grass')
    for m in me3.bench:
        m.card = _Ptype('Grass')
    assert _resolve(K6, ctx3) == 0
    # 1 Darkness (active only), heads -> 60
    ctx4, at4, _, me4, _ = mk(text=K6, base=60, flips=(0.0,), my_bench=1)
    at4.card = _Ptype('Darkness'); me4.bench[0].card = _Ptype('Water')
    assert _resolve(K6, ctx4) == 60


# ---- 7. Vanilluxe: 90/head + paralyze if any heads ----
K7 = ("Flip 2 coins. This attack does 90 damage for each heads. If either of them is heads, "
      "your opponent's Active Pokémon is now Paralyzed.")


def t_vanilluxe():
    d, ctx, at, df, me, opp = run(K7, base=90, flips=(0.0, 0.9))   # 1 head
    assert d == 90 and df.status.get('Paralyzed')
    d2, _, _, df2, *_ = run(K7, base=90, flips=(0.9,))             # both tails
    assert d2 == 0 and not df2.status.get('Paralyzed')
    # Mist Energy shields the paralysis even on a head
    d3, _, _, df3, *_ = run(K7, base=90, flips=(0.0,), def_special=('Mist Energy',))
    assert d3 == 180 and not df3.status.get('Paralyzed')


# ---- 11. Slurpuff: 90/head + confuse if both tails ----
K11 = ("Flip 2 coins. This attack does 90 damage for each heads. If both of them are tails, "
       "your opponent's Active Pokémon is now Confused.")


def t_slurpuff():
    d, ctx, at, df, me, opp = run(K11, base=90, flips=(0.9,))      # both tails
    assert d == 0 and df.status.get('Confused')
    d2, _, _, df2, *_ = run(K11, base=90, flips=(0.0, 0.9))        # 1 head -> no confuse
    assert d2 == 90 and not df2.status.get('Confused')
    d3, _, _, df3, *_ = run(K11, base=90, flips=(0.0,))            # 2 heads
    assert d3 == 180 and not df3.status.get('Confused')


# ---- 12. Heliolisk: coin per energy attached ----
K12 = "Flip a coin for each Energy attached to this Pokémon. This attack does 70 damage for each heads."


def t_heliolisk():
    assert run(K12, base=70, atk_energy={'Colorless': 3}, flips=(0.0,))[0] == 210
    assert run(K12, base=70, atk_energy={'Colorless': 3}, flips=(0.9,))[0] == 0
    # all-energy count includes Wild/special pips
    assert run(K12, base=70, atk_energy={'Water': 1, 'Wild': 1}, flips=(0.0,))[0] == 140


# ---- 13. Volcanion: coin per {W} energy attached (basic Water only) ----
K13 = "Flip a coin for each {W} Energy attached to this Pokémon. This attack does 90 damage for each heads."


def t_volcanion():
    assert run(K13, base=90, atk_energy={'Water': 2}, flips=(0.0,))[0] == 180
    assert run(K13, base=90, atk_energy={'Water': 2}, flips=(0.9,))[0] == 0
    # Wild (rainbow) does NOT count toward {W} — only the single basic Water does
    assert run(K13, base=90, atk_energy={'Water': 1, 'Wild': 3}, flips=(0.0,))[0] == 90
    # no Water at all -> 0 coins
    assert run(K13, base=90, atk_energy={'Fire': 2}, flips=(0.0,))[0] == 0


# ---- 15. Bewear: +100 only if both heads ----
K15 = "Flip 2 coins. If both of them are heads, this attack does 100 more damage."


def t_bewear():
    assert run(K15, base=100, flips=(0.0,))[0] == 200          # both heads
    assert run(K15, base=100, flips=(0.0, 0.9))[0] == 100      # one head -> no bonus
    assert run(K15, base=100, flips=(0.9,))[0] == 100          # both tails -> no bonus


# ---- 16./17. single-flip flat bonus ----
def t_single_flip_bonus():
    assert run("Flip a coin. If heads, this attack does 80 more damage.", base=80, flips=(0.0,))[0] == 160
    assert run("Flip a coin. If heads, this attack does 80 more damage.", base=80, flips=(0.9,))[0] == 80
    assert run("Flip a coin. If heads, this attack does 70 more damage.", base=70, flips=(0.0,))[0] == 140
    assert run("Flip a coin. If heads, this attack does 70 more damage.", base=70, flips=(0.9,))[0] == 70


# ---- 19. Floragato: heads -> +30 and heal 30 ----
K19 = "Flip a coin. If heads, this attack does 30 more damage, and heal 30 damage from this Pokémon."


def t_floragato():
    ctx, at, df, me, opp = mk(text=K19, base=30, flips=(0.0,))
    at.damage = 50
    assert _resolve(K19, ctx) == 60 and at.damage == 20        # +30 dmg, healed 30 off self
    ctx2, at2, *_ = mk(text=K19, base=30, flips=(0.9,))
    at2.damage = 50
    assert _resolve(K19, ctx2) == 30 and at2.damage == 50      # tails: no bonus, no heal


# ---- 22. Houndstone: base 30 + random hand-to-deck per heads ----
K22 = ("Flip a coin until you get tails. For each heads, choose a random card from your opponent's hand. "
       "Your opponent reveals those cards and shuffles them into their deck.")


def t_houndstone():
    ctx, at, df, me, opp = mk(text=K22, base=30, flips=(0.0, 0.0, 0.9))  # 2 heads
    opp.hand = [('P', VANILLA), ('E', 'Colorless'), ('P', VANILLA)]
    before = len(opp.deck)
    d = _resolve(K22, ctx)
    assert d == 30
    assert len(opp.hand) == 1                                    # 2 random cards removed
    assert len(opp.deck) == before + 2
    # immediate tails -> no cards moved, still base damage
    ctx2, _, _, me2, opp2 = mk(text=K22, base=30, flips=(0.9,))
    opp2.hand = [('P', VANILLA), ('E', 'Colorless')]
    assert _resolve(K22, ctx2) == 30 and len(opp2.hand) == 2


TESTS = [t_zangoose_steps, t_crawdaunt_mill, t_until_tails_variants, t_fixed_count_multipliers,
         t_watchog_choose, t_scrafty_dark_count, t_vanilluxe, t_slurpuff, t_heliolisk, t_volcanion,
         t_bewear, t_single_flip_bonus, t_floragato, t_houndstone]

if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
