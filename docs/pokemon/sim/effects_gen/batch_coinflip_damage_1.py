#!/usr/bin/env python3
"""Attack-effect batch: coinflip_damage_1 — coin-flip-scaled / coin-flip-bonus damage attacks
(plus a few flip-gated disruption riders: deck-mill, hand-to-deck shuffle, status on all-tails/any-heads).

Conventions (matched to effects.py eval_count for consistency):
  - "for each {W} Energy attached to this Pokémon" counts basic Water only (NOT rainbow 'Wild').
  - "for each Energy attached to this Pokémon" uses total_energy() (Wild/Colorless included).
  - "for each {D} Pokémon you have in play" counts your in-play mons whose card.ptype == 'Darkness'.
  - "N×" attacks: damage is per-heads * heads (0 heads -> 0 damage). "N+" attacks: base + conditional bonus.
"""
from attack_effects import effect, EffectCtx, STATUSES


# ---------------------------------------------------------------- module-level helpers
def _discard_token(player, tok):
    """Route a milled/discarded deck token to the right pile (basic energy -> disc_energy Counter)."""
    if tok[0] == 'E':
        player.disc_energy[tok[1]] += 1
    else:
        player.discard.append(tok)


def _mill_top(player, n):
    """Discard the top n cards of `player`'s deck (deck top = last element, next to be drawn)."""
    milled = 0
    for _ in range(n):
        if not player.deck:
            break
        _discard_token(player, player.deck.pop())
        milled += 1
    return milled


def _shuffle_hand_to_deck_choose(player, n, rng):
    """Attacker CHOOSES n cards from opponent's hand -> shuffle into their deck.
    Choice heuristic: strip the opponent's engine first (Pokémon/Trainers) over basic energy."""
    if n <= 0 or not player.hand:
        return 0

    def prio(tok):
        k = tok[0]
        if k in ('P', 'T'):
            return 0                    # Pokémon / Trainers: most disruptive to remove
        if k == 'S':
            return 1                    # special energy
        return 2                        # basic energy: least valuable to strip
    order = sorted(range(len(player.hand)), key=lambda i: prio(player.hand[i]))
    picks = set(order[:n])
    moved = [player.hand[i] for i in sorted(picks)]
    player.hand = [t for i, t in enumerate(player.hand) if i not in picks]
    for tok in moved:
        player.deck.append(tok)
    rng.shuffle(player.deck)
    return len(moved)


def _shuffle_hand_to_deck_random(player, n, rng):
    """Choose n RANDOM cards from opponent's hand -> shuffle into their deck."""
    moved = 0
    for _ in range(n):
        if not player.hand:
            break
        idx = rng.randint(0, len(player.hand) - 1)
        player.deck.append(player.hand.pop(idx))
        moved += 1
    if moved:
        rng.shuffle(player.deck)
    return moved


# ================================================================ EFFECTS

@effect("Flip 3 coins. If 1 of them is heads, this attack does 20 more damage. If 2 of them are heads, this attack does 50 more damage. If all of them are heads, this attack does 80 more damage.")
def _f3_20_50_80(ctx):
    # Zangoose (base 10): stepped bonus by number of heads.
    bonus = {0: 0, 1: 20, 2: 50, 3: 80}[ctx.flips(3)]
    return ctx.base + bonus


@effect("Flip 2 coins. For each heads, discard the top card of your opponent's deck.")
def _f2_mill(ctx):
    # Crawdaunt (base 40): mill opponent's deck 1-per-head, full base damage regardless.
    _mill_top(ctx.opp, ctx.flips(2))
    return ctx.base


@effect("Flip a coin until you get tails. This attack does 30 damage for each heads.")
def _until_tails_30(ctx):
    return 30 * ctx.flips_until_tails()


@effect("Flip 2 coins. This attack does 100 damage for each heads.")
def _f2_100(ctx):
    return 100 * ctx.flips(2)


@effect("Flip 3 coins. If any of them are heads, your opponent reveals their hand. For each heads, choose a card you find there and shuffle it into your opponent's deck.")
def _f3_hand_shuffle_choose(ctx):
    # Watchog (0 damage): pure hand disruption — shuffle away one chosen card per heads.
    _shuffle_hand_to_deck_choose(ctx.opp, ctx.flips(3), ctx.rng)
    return ctx.base


@effect("Flip a coin for each {D} Pokémon you have in play. This attack does 60 damage for each heads.")
def _f_per_dark_60(ctx):
    n = sum(1 for m in ctx.me.all_mons() if m.card.ptype == 'Darkness')
    return 60 * ctx.flips(n)


@effect("Flip 2 coins. This attack does 90 damage for each heads. If either of them is heads, your opponent's Active Pokémon is now Paralyzed.")
def _f2_90_para_any(ctx):
    h = ctx.flips(2)
    if h >= 1:                          # "either of them is heads" -> at least one head
        ctx.status('Paralyzed')
    return 90 * h


@effect("Flip 3 coins. This attack does 120 damage for each heads.")
def _f3_120(ctx):
    return 120 * ctx.flips(3)


@effect("Flip 4 coins. This attack does 100 damage for each heads.")
def _f4_100(ctx):
    return 100 * ctx.flips(4)


@effect("Flip 2 coins. This attack does 80 damage for each heads.")
def _f2_80(ctx):
    return 80 * ctx.flips(2)


@effect("Flip 2 coins. This attack does 90 damage for each heads. If both of them are tails, your opponent's Active Pokémon is now Confused.")
def _f2_90_confuse_alltails(ctx):
    h = ctx.flips(2)
    if h == 0:                          # "both of them are tails" -> zero heads
        ctx.status('Confused')
    return 90 * h


@effect("Flip a coin for each Energy attached to this Pokémon. This attack does 70 damage for each heads.")
def _f_per_energy_70(ctx):
    return 70 * ctx.flips(ctx.attacker.total_energy())


@effect("Flip a coin for each {W} Energy attached to this Pokémon. This attack does 90 damage for each heads.")
def _f_per_water_90(ctx):
    # Match effects.py convention: {W} counts basic Water only (not rainbow 'Wild').
    n = ctx.attacker.energy.get('Water', 0)
    return 90 * ctx.flips(n)


@effect("Flip a coin until you get tails. This attack does 40 damage for each heads.")
def _until_tails_40(ctx):
    return 40 * ctx.flips_until_tails()


@effect("Flip 2 coins. If both of them are heads, this attack does 100 more damage.")
def _f2_both_plus_100(ctx):
    return ctx.base + (100 if ctx.flips(2) == 2 else 0)


@effect("Flip a coin. If heads, this attack does 80 more damage.")
def _heads_plus_80(ctx):
    return ctx.base + (80 if ctx.flip() else 0)


@effect("Flip a coin. If heads, this attack does 70 more damage.")
def _heads_plus_70(ctx):
    return ctx.base + (70 if ctx.flip() else 0)


@effect("Flip a coin until you get tails. This attack does 50 damage for each heads.")
def _until_tails_50(ctx):
    return 50 * ctx.flips_until_tails()


@effect("Flip a coin. If heads, this attack does 30 more damage, and heal 30 damage from this Pokémon.")
def _heads_plus_30_heal_30(ctx):
    if ctx.flip():
        ctx.heal(30)                    # heal self (attacker)
        return ctx.base + 30
    return ctx.base


@effect("Flip 4 coins. This attack does 30 damage for each heads.")
def _f4_30(ctx):
    return 30 * ctx.flips(4)


@effect("Flip a coin until you get tails. This attack does 100 damage for each heads.")
def _until_tails_100(ctx):
    return 100 * ctx.flips_until_tails()


@effect("Flip a coin until you get tails. For each heads, choose a random card from your opponent's hand. Your opponent reveals those cards and shuffles them into their deck.")
def _until_tails_hand_shuffle_random(ctx):
    # Houndstone (base 30): base damage + shuffle a random card per heads into opp's deck.
    _shuffle_hand_to_deck_random(ctx.opp, ctx.flips_until_tails(), ctx.rng)
    return ctx.base
