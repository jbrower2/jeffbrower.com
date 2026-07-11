#!/usr/bin/env python3
"""Attack-effect batch: coinflip_effect_0 — coin-flip attacks whose branch performs a
side effect (damage prevention wall, special conditions, energy/card manipulation, board
disruption) rather than (only) scaling damage. Each effect is keyed by its exact
(damage-stripped) card text and returns the raw damage to the defender's Active.

Conventions (matched to the sibling batches + effects.py):
  - Damage-prevention "wall" reuses Mon.dr_amount/dr_turn (see _wall_next_turn), the same hook
    batch_coinflip_gate_0 uses; incoming_damage() applies it only on the opponent's next turn.
  - "this Pokémon can't attack/use attacks next turn" reuses the engine cooldown gate
    (cd_name='ALL' / cd_turn) that best_attack() honours via `cd_turn + 2 == turn`.
  - Basic-energy pseudo-types 'Wild'/'Colorless' are special-energy pips, NOT basic-energy cards,
    so they are never re-created as ('E', type) tokens when a Pokémon is shuffled into the deck.
  - Probabilistic "the Defending Pokémon must flip to attack next turn" effects are recorded as a
    marker on the defender (mirrors the CantRetreat marker convention); the flip lands on the
    OPPONENT's turn, so it is registered as intent rather than resolved now (see notes on each).
"""
from attack_effects import effect, EffectCtx, STATUSES

# Reduction large enough to zero out ANY realistic incoming attack damage — models "prevent all
# damage done to this Pokémon" for one turn. Matches batch_coinflip_gate_0's _WALL.
_WALL = 100000
_PSEUDO = ('Wild', 'Colorless')          # special-energy pips, not basic-energy cards


# ---------------------------------------------------------------- module-level helpers
def _wall_next_turn(ctx: EffectCtx):
    """Schedule 'prevent all attack damage to this Pokémon during your opponent's next turn'.
    incoming_damage() applies dr_amount when `dr_turn + 1 == game.turn` (the opponent's very next
    turn) and it lapses on its own afterward. A huge amount prevents ALL the damage."""
    ctx.attacker.dr_amount = _WALL
    ctx.attacker.dr_turn = ctx.game.turn


def _defender_cant_attack_next(ctx: EffectCtx):
    """Disable ALL of the Defending Pokémon's attacks during the opponent's next turn, via the
    engine cooldown gate. best_attack() skips an attack when `cd_turn + 2 == game.turn` and
    cd_name in ('ALL', name). This attack lands on turn T; the opponent's next turn is T+1, so
    the gate must read cd_turn = T-1 (=> cd_turn + 2 == T+1)."""
    ctx.defender.cd_name = 'ALL'
    ctx.defender.cd_turn = ctx.game.turn - 1


def _mon_to_deck(player, mon):
    """Shuffle a Pokémon and its attached basic energy back into its owner's deck."""
    player.deck.append(('P', mon.card))
    for t, n in list(mon.energy.items()):
        if t not in _PSEUDO:                             # only real basic energy returns as a card
            for _ in range(int(n)):
                player.deck.append(('E', t))
    player.rng.shuffle(player.deck)


def _remove_opp_mon(opp, mon):
    """Remove `mon` from the opponent's board (promoting a new Active if it was the Active)."""
    if mon is opp.active:
        opp.active = None
        opp.promote()
    elif mon in opp.bench:
        opp.bench.remove(mon)


def _best_opp_target(mons):
    """Which of the opponent's Pokémon to disrupt: the most-invested (energy), then ex, then HP."""
    return max(mons, key=lambda m: (m.total_energy(), m.card.is_ex, m.card.hp))


def _attach_basic_from_deck(player, mon, n):
    """Attach up to n basic-energy tokens searched from the deck onto `mon`; shuffle. Returns count."""
    got = 0
    i = len(player.deck) - 1
    while i >= 0 and got < n:
        if player.deck[i][0] == 'E':                     # every ('E', type) deck token is basic energy
            mon.energy[player.deck[i][1]] += 1
            player.deck.pop(i)
            got += 1
        i -= 1
    player.rng.shuffle(player.deck)
    return got


def _attach_basic_from_discard(player, mon, n):
    """Attach up to n basic-energy pips from the discard pile onto `mon`. Returns count."""
    got = 0
    for t in list(player.disc_energy):
        while player.disc_energy[t] > 0 and got < n:
            player.disc_energy[t] -= 1
            mon.energy[t] += 1
            got += 1
        if player.disc_energy[t] <= 0:
            del player.disc_energy[t]
        if got >= n:
            break
    return got


def _discard_to_hand(player, n):
    """Move up to n cards from the discard pile into hand (non-energy pile first, then basic energy)."""
    got = 0
    while got < n and player.discard:
        player.hand.append(player.discard.pop())
        got += 1
    for t in list(player.disc_energy):
        while player.disc_energy[t] > 0 and got < n:
            player.disc_energy[t] -= 1
            player.hand.append(('E', t))
            got += 1
        if player.disc_energy[t] <= 0:
            del player.disc_energy[t]
        if got >= n:
            break
    return got


def _deck_to_hand(player, n):
    """Search the deck for up to n cards (prefer Pokémon, then energy) into hand; shuffle. Returns count."""
    got = 0
    for kind in ('P', 'E', 'S', 'T'):
        i = len(player.deck) - 1
        while i >= 0 and got < n:
            if player.deck[i][0] == kind:
                player.hand.append(player.deck.pop(i))
                got += 1
            i -= 1
        if got >= n:
            break
    player.rng.shuffle(player.deck)
    return got


# ================================================================ EFFECTS

@effect("Flip a coin. If heads, during your opponent's next turn, prevent all damage from and effects of attacks done to this Pokémon.")
def _heads_wall_dmg_and_effects(ctx):
    # Marill / Dunsparce (base 0-30). Heads: deal base AND wall off ALL incoming damage next turn.
    # (The "and effects" clause has no separate engine hook; the damage wall is the modelled part.)
    if ctx.flip():
        _wall_next_turn(ctx)
    return ctx.base


@effect("Flip a coin. If heads, during your opponent's next turn, prevent all damage done to this Pokémon by attacks.")
def _heads_wall_dmg(ctx):
    # Altaria / Bronzor / Shelmet (base 0-100). Heads: deal base AND prevent all attack damage next turn.
    if ctx.flip():
        _wall_next_turn(ctx)
    return ctx.base


@effect("During your opponent's next turn, if the Defending Pokémon tries to use an attack, your opponent flips a coin. If tails, that attack doesn't happen.")
def _def_flip1_to_attack(ctx):
    # Sandslash / Hippopotas / Sandygast: record that the Defending Pokémon must flip (1 coin) to
    # attack next turn (50% fizzle). The flip is the opponent's, on THEIR turn, so we record intent.
    ctx.defender.status['CoinToAttack1'] = ctx.game.turn
    return ctx.base


@effect("Flip 2 coins. If both of them are tails, this Pokémon also does 90 damage to itself.")
def _both_tails_self_90(ctx):
    # Team Rocket's Raticate (base 90). Recoil ONLY when both coins are tails (0 heads).
    if ctx.flips(2) == 0:
        ctx.self_damage(90)
    return ctx.base


@effect("Flip a coin. If heads, your opponent's Active Pokémon is now Confused and Poisoned.")
def _heads_confuse_poison(ctx):
    # Ekans (base 0). Heads: both conditions (Confused + Poisoned coexist).
    if ctx.flip():
        ctx.status('Confused')
        ctx.status('Poisoned')
    return ctx.base


@effect("Your opponent flips a coin for each of their Benched Pokémon. This attack does 80 damage to your opponent's Active Pokémon for each tails. This attack's damage isn't affected by Weakness or Resistance.")
def _80_per_opp_bench_tails(ctx):
    # Team Rocket's Hypno (80×): 80 damage per TAILS among one coin per opponent's benched Pokémon.
    # (The "not affected by Weakness/Resistance" clause cannot be signalled through the int return;
    # the engine applies weakness after — noted as an unavoidable single-card gap.)
    n = len(ctx.opp.bench)
    tails = n - ctx.flips(n)
    return ctx.base * tails


@effect("Flip a coin. If heads, your opponent's Active Pokémon is now Burned.")
def _heads_burn(ctx):
    # Magmar (base 30).
    if ctx.flip():
        ctx.status('Burned')
    return ctx.base


@effect("Flip a coin. If heads, choose 1 of your opponent's Benched Pokémon. Shuffle that Pokémon and all attached cards into their deck.")
def _heads_shuffle_opp_bench(ctx):
    # Sylveon (base 0). Heads: shuffle the most-invested benched Pokémon (+ its basic energy) away.
    if ctx.flip() and ctx.opp.bench:
        tgt = _best_opp_target(ctx.opp.bench)
        _mon_to_deck(ctx.opp, tgt)
        ctx.opp.bench.remove(tgt)
    return ctx.base


@effect("Flip a coin until you get tails. Search your deck for an amount of Basic Energy up to the number of heads and attach it to this Pokémon. Then, shuffle your deck.")
def _flip_attach_basic_self(ctx):
    # Snorlax (base 0): #heads basic energy from deck onto this Pokémon.
    n = ctx.flips_until_tails()
    if n:
        _attach_basic_from_deck(ctx.me, ctx.attacker, n)
    return ctx.base


@effect("Flip a coin. If heads, choose 1 of your opponent's Active Pokémon's attacks and use it as this attack.")
def _heads_copy_attack(ctx):
    # Ethan's Sudowoodo (base 0): metronome — heads copies the defender's best-damage attack.
    # (Copied side-effects/scaling are not resolved; the copied printed damage is returned.)
    if not ctx.flip():
        return ctx.base
    return max((a['dmg'] for a in ctx.defender.card.attacks), default=0)


@effect("During your opponent's next turn, if the Defending Pokémon tries to use an attack, your opponent flips 2 coins. If either of them is tails, that attack doesn't happen.")
def _def_flip2_to_attack(ctx):
    # Octillery (base 30): record that the Defending Pokémon must flip 2 coins to attack next turn
    # (fizzles unless BOTH heads = 75% fizzle). Flip is the opponent's on their turn — intent recorded.
    ctx.defender.status['CoinToAttack2'] = ctx.game.turn
    return ctx.base


@effect("Flip 3 coins. Attach an amount of Basic Energy up to the number of heads from your discard pile to your Benched Pokémon in any way you like.")
def _flip3_attach_discard_bench(ctx):
    # Smeargle (base 0): up to #heads basic energy from discard onto a benched Pokémon.
    h = ctx.flips(3)
    if h and ctx.me.bench:
        tgt = max(ctx.me.bench, key=lambda m: m.total_energy())   # concentrate on the one being built
        _attach_basic_from_discard(ctx.me, tgt, h)
    return ctx.base


@effect("Flip 2 coins. If both of them are heads, heal all damage from 1 of your Pokémon.")
def _both_heads_full_heal(ctx):
    # Miltank (base 0): only on 2 heads, fully heal your most-damaged Pokémon.
    if ctx.flips(2) == 2:
        tgt = max(ctx.me.all_mons(), key=lambda m: m.damage, default=None)
        if tgt is not None:
            tgt.damage = 0
    return ctx.base


@effect("Flip a coin. If heads, choose 1 of your opponent's Pokémon. Shuffle that Pokémon and all attached cards into their deck.")
def _heads_shuffle_opp_any(ctx):
    # Shiftry (base 0). Heads: shuffle the opponent's most-invested Pokémon (Active OR Bench) away.
    if ctx.flip():
        mons = ctx.opp.all_mons()
        if mons:
            tgt = _best_opp_target(mons)
            _mon_to_deck(ctx.opp, tgt)
            _remove_opp_mon(ctx.opp, tgt)
    return ctx.base


@effect("Flip a coin. If tails, during your next turn, this Pokémon can't attack.")
def _tails_self_cant_attack(ctx):
    # Nosepass (base 60). Tails: this Pokémon can't attack next turn.
    if not ctx.flip():
        ctx.cant_attack_next()
    return ctx.base


@effect("Flip 3 coins. Put a number of cards up to the number of heads from your discard pile into your hand.")
def _flip3_recover_discard(ctx):
    # Stoutland (base 0): up to #heads cards recovered from discard to hand.
    h = ctx.flips(3)
    if h:
        _discard_to_hand(ctx.me, h)
    return ctx.base


@effect("Flip a coin. If heads, your opponent's Active Pokémon is now Paralyzed and Poisoned. If tails, your opponent's Active Pokémon is now Confused.")
def _heads_para_poison_else_confuse(ctx):
    # Lilligant (base 30): heads -> Paralyzed + Poisoned; tails -> Confused.
    if ctx.flip():
        ctx.status('Paralyzed')
        ctx.status('Poisoned')
    else:
        ctx.status('Confused')
    return ctx.base


@effect("Flip a coin. If heads, your opponent's Active Pokémon is now Paralyzed, and discard an Energy from that Pokémon.")
def _heads_para_discard(ctx):
    # Stunfisk (base 50): heads -> Paralyzed + discard 1 energy from the defender.
    if ctx.flip():
        ctx.status('Paralyzed')
        ctx.discard_energy_defender(1)
    return ctx.base


@effect("Flip 3 coins. For each tails, discard an Energy from this Pokémon.")
def _flip3_self_discard_per_tails(ctx):
    # Heatmor (base 130): discard 1 self energy per TAILS (0-3).
    tails = 3 - ctx.flips(3)
    if tails:
        ctx.discard_energy_self(tails)
    return ctx.base


@effect("Flip a coin. If tails, during your next turn, this Pokémon can't use attacks.")
def _tails_self_cant_use_attacks(ctx):
    # Eternatus (base 130). Tails: this Pokémon can't use attacks next turn (== can't attack).
    if not ctx.flip():
        ctx.cant_attack_next()
    return ctx.base


@effect("Flip a coin. If heads, during your opponent's next turn, the Defending Pokémon can't attack.")
def _heads_def_cant_attack(ctx):
    # Oinkologne (base 50). Heads: the Defending Pokémon can't attack next turn (engine cooldown gate).
    if ctx.flip():
        _defender_cant_attack_next(ctx)
    return ctx.base


@effect("Flip a coin. If heads, choose a Special Condition. Your opponent's Active Pokémon is now affected by that Special Condition.")
def _heads_choose_condition(ctx):
    # Grafaiai (base 90). Heads: choose a condition — pick Paralyzed (reliably skips their next turn).
    if ctx.flip():
        ctx.status('Paralyzed')
    return ctx.base


@effect("Flip a coin. If heads, your opponent's Active Pokémon is now Paralyzed and Poisoned.")
def _heads_para_poison(ctx):
    # Glimmora (base 0): heads -> Paralyzed + Poisoned.
    if ctx.flip():
        ctx.status('Paralyzed')
        ctx.status('Poisoned')
    return ctx.base


@effect("Flip a coin until you get tails. Search your deck for a number of cards up to the number of heads and put them into your hand. Then, shuffle your deck.")
def _flip_search_cards(ctx):
    # Gholdengo (base 0): search #heads cards from deck to hand.
    n = ctx.flips_until_tails()
    if n:
        _deck_to_hand(ctx.me, n)
    return ctx.base
