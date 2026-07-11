#!/usr/bin/env python3
"""Batch: coinflip_damage_0 — coin-flip variable/bonus damage attacks (+ a few flip-driven
disruption riders). Each effect is registered by its exact normalized attack text.

Damage-token conventions (matching the proof batch in attack_effects.py):
  - "N× ... does N damage for each heads"      -> pure variable: N * heads (base ignored, 0 on all tails)
  - "N+ ... does M more damage [for each heads]" -> base + M[*heads] (bonus stacks ON the printed base)
"""
from attack_effects import effect, EffectCtx, STATUSES


# ---------------------------------------------------------------- shared helpers
def _discard_token(player, tok):
    """Send a deck/hand token to the owner's discard pile. Basic energy ('E') is tracked in the
    disc_energy Counter (so accel-from-discard can see it); everything else goes to the discard list."""
    if tok[0] == 'E':
        player.disc_energy[tok[1]] += 1
    else:
        player.discard.append(tok)


# ================================================================ Flip N coins: N × heads (base ignored)
@effect("Flip 2 coins. This attack does 10 damage for each heads.")
def _f2_10(ctx):
    return 10 * ctx.flips(2)


@effect("Flip 3 coins. This attack does 10 damage for each heads.")
def _f3_10(ctx):
    return 10 * ctx.flips(3)


@effect("Flip 4 coins. This attack does 10 damage for each heads.")
def _f4_10(ctx):
    return 10 * ctx.flips(4)


@effect("Flip 3 coins. This attack does 20 damage for each heads.")
def _f3_20(ctx):
    return 20 * ctx.flips(3)


@effect("Flip 2 coins. This attack does 30 damage for each heads.")
def _f2_30(ctx):
    return 30 * ctx.flips(2)


@effect("Flip 3 coins. This attack does 30 damage for each heads.")
def _f3_30(ctx):
    return 30 * ctx.flips(3)


@effect("Flip 5 coins. This attack does 30 damage for each heads.")
def _f5_30(ctx):
    return 30 * ctx.flips(5)


@effect("Flip 2 coins. This attack does 40 damage for each heads.")
def _f2_40(ctx):
    return 40 * ctx.flips(2)


@effect("Flip 3 coins. This attack does 50 damage for each heads.")
def _f3_50(ctx):
    return 50 * ctx.flips(3)


@effect("Flip 2 coins. This attack does 70 damage for each heads.")
def _f2_70(ctx):
    return 70 * ctx.flips(2)


@effect("Flip 4 coins. This attack does 70 damage for each heads.")
def _f4_70(ctx):
    return 70 * ctx.flips(4)


@effect("Flip 4 coins. This attack does 80 damage for each heads.")
def _f4_80(ctx):
    return 80 * ctx.flips(4)


@effect("Flip 2 coins. This attack does 90 damage for each heads.")
def _f2_90(ctx):
    return 90 * ctx.flips(2)


# ================================================================ Flip until tails: N × heads (base ignored)
@effect("Flip a coin until you get tails. This attack does 10 damage for each heads.")
def _ut_10(ctx):
    return 10 * ctx.flips_until_tails()


@effect("Flip a coin until you get tails. This attack does 70 damage for each heads.")
def _ut_70(ctx):
    return 70 * ctx.flips_until_tails()


@effect("Flip a coin until you get tails. This attack does 90 damage for each heads.")
def _ut_90(ctx):
    return 90 * ctx.flips_until_tails()


# ================================================================ Flip 1 coin: base + M more on heads
@effect("Flip a coin. If heads, this attack does 10 more damage.")
def _heads_plus_10(ctx):
    return ctx.base + (10 if ctx.flip() else 0)


@effect("Flip a coin. If heads, this attack does 40 more damage.")
def _heads_plus_40(ctx):
    return ctx.base + (40 if ctx.flip() else 0)


@effect("Flip a coin. If heads, this attack does 50 more damage.")
def _heads_plus_50(ctx):
    return ctx.base + (50 if ctx.flip() else 0)


@effect("Flip a coin. If heads, this attack does 60 more damage.")
def _heads_plus_60(ctx):
    return ctx.base + (60 if ctx.flip() else 0)


# ================================================================ Flip until tails: base + M more per heads
@effect("Flip a coin until you get tails. This attack does 30 more damage for each heads.")
def _ut_plus_30(ctx):
    return ctx.base + 30 * ctx.flips_until_tails()


@effect("Flip a coin until you get tails. This attack does 50 more damage for each heads.")
def _ut_plus_50(ctx):
    return ctx.base + 50 * ctx.flips_until_tails()


# ================================================================ Flip coins == energy on both Actives
@effect("Flip a coin for each Energy attached to both Active Pokémon. This attack does 60 damage for each heads.")
def _both_actives_energy_60(ctx):
    coins = ctx.attacker.total_energy() + ctx.defender.total_energy()
    return 60 * ctx.flips(coins)


# ================================================================ Flip-driven disruption (energy/hand/deck)
@effect("Flip 2 coins. For each heads, discard an Energy from your opponent's Active Pokémon.")
def _f2_discard_opp_energy(ctx):
    heads = ctx.flips(2)
    for _ in range(heads):
        ctx.discard_energy_defender(1)
    return ctx.base


@effect("Flip 3 coins. For each heads, discard a random card from your opponent's hand.")
def _f3_discard_opp_hand(ctx):
    heads = ctx.flips(3)
    for _ in range(heads):
        if not ctx.opp.hand:
            break
        idx = ctx.rng.randint(0, len(ctx.opp.hand) - 1)
        _discard_token(ctx.opp, ctx.opp.hand.pop(idx))
    return ctx.base


@effect("Flip a coin until you get tails. For each heads, discard the top card of your opponent's deck.")
def _ut_mill_opp_deck(ctx):
    heads = ctx.flips_until_tails()
    for _ in range(heads):
        if not ctx.opp.deck:
            break
        _discard_token(ctx.opp, ctx.opp.deck.pop())   # top of deck == end of list (draw() pops the end)
    return ctx.base


# ================================================================ Iono's Electrode — self-destruct KO gamble
@effect("This Pokémon does 100 damage to itself. Flip a coin. If heads, your opponent's Active Pokémon is Knocked Out.")
def _selfdestruct_ko(ctx):
    ctx.self_damage(100)                              # unconditional recoil (engine reaps the self-KO)
    if ctx.flip():
        ctx.defender.damage = ctx.defender.max_hp     # direct KO: ignores HP/Weakness (no damage returned)
    return 0


# ================================================================ Tauros — Tauros-count stampede
@effect('Choose 1 of your opponent\'s Pokémon and flip a coin for each of your Pokémon in play that has "Tauros" in its name. This attack does 50 damage to the chosen Pokémon for each heads. (Don\'t apply Weakness and Resistance for Benched Pokémon.)')
def _tauros_stampede(ctx):
    coins = sum(1 for m in ctx.me.all_mons() if 'Tauros' in m.card.name)
    # Choose the opponent's Active as the target (a legal "choose 1" pick): return damage so the
    # engine applies Weakness normally for the Active.
    return 50 * ctx.flips(coins)
