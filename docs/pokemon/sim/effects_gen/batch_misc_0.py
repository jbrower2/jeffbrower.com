#!/usr/bin/env python3
"""Effect batch: misc_0 — disruption / hand-manipulation / self-bounce / attack-lock / copy attacks
and a handful of "ignore effects" and Stadium clauses that the current sim models structurally.

Each effect is registered by its exact (damage-stripped) card text and returns the pre-Weakness
damage dealt to the defender's Active (the engine applies Weakness afterward). Side effects run via
EffectCtx helpers or direct manipulation of ctx.me / ctx.opp / ctx.attacker / ctx.defender.

Conventions (matched to sibling batches + effects.py / engine.py)
----------------------------------------------------------------
* NEXT-TURN ATTACK LOCK. best_attack() skips an attack when `mon.cd_turn + 2 == game.turn` and
  `mon.cd_name in ('ALL', a['name'])`.
    - Locking THIS Pokémon ("during your next turn, this Pokémon can't ..."): my next turn is T+2, so
      cd_turn = game.turn (== ctx.cant_attack_next). cd_name='ALL' for "can't use attacks"; the exact
      attack name for a single-named lock ("can't use Zap Cannon").
    - Locking the DEFENDER ("during your opponent's next turn, the Defending Pokémon can't ..."): the
      opponent's next turn is T+1, so cd_turn = game.turn - 1 (=> cd_turn + 2 == T+1). This matches
      batch_coinflip_effect_0 / batch_conditional_damage_1.
* STADIUM STATE (now modeled). The engine tracks the Stadium in play as game.stadium=(name, owner);
  EffectCtx exposes ctx.stadium() (name or None) and ctx.discard_stadium(). So:
    - "(You may) discard a Stadium in play." -> discard whatever Stadium is in play, else no-op; base.
    - "If there is no Stadium in play, this attack does nothing." -> full damage only while a Stadium
      is in play; otherwise 0 (never over-applies the printed damage).
* NO RESISTANCE. The engine applies Weakness only (never Resistance), so "isn't affected by
  Resistance" is a no-op -> deal base.
* UNMODELED RIDERS (item-lock, delayed end-of-turn discard) have no engine hook. Following the
  batch_damage_reduction_0 / batch_coinflip_effect_0 marker convention, the precise intent is recorded
  turn-stamped for future wiring and the printed base damage is dealt now; nothing over-applies.
"""
from attack_effects import effect, EffectCtx, STATUSES


# ---------------------------------------------------------------- module-level helpers
def _route_to_discard(player, tok):
    """Send one hand token to `player`'s discard, mirroring the engine's hand-dump routing:
    basic energy -> disc_energy counter, Pokémon -> discard pile, Trainer/Special-energy -> dropped
    (the engine tracks neither in a pile)."""
    if tok[0] == 'E':
        player.disc_energy[tok[1]] += 1
    elif tok[0] == 'P':
        player.discard.append(tok)


def _discard_from_hand(player, n):
    """`player` discards n cards from hand (their choice; we take the last), routed to discard."""
    for _ in range(n):
        if not player.hand:
            break
        _route_to_discard(player, player.hand.pop())


def _pick_random_index(ctx, seq):
    """A uniformly-random index into `seq` via the engine RNG (deterministic under the test RNG,
    which returns the low bound -> index 0)."""
    return ctx.rng.randint(0, len(seq) - 1)


def _shuffle_from_hand_to_deck(ctx, player, n):
    """Move up to n cards (taken from the end = player's choice) from hand into deck, then shuffle."""
    moved = 0
    for _ in range(n):
        if not player.hand:
            break
        player.deck.append(player.hand.pop())
        moved += 1
    if moved:
        ctx.rng.shuffle(player.deck)
    return moved


def _energy_to_hand(mon, owner, n):
    """Move up to n Energy off `mon` into `owner`'s hand. Basic-energy pips return as ('E', type)
    tokens; special-energy pips (the 'Wild'/'Colorless' pseudo-types) are removed and a matching
    Special-Energy name popped from mon.special (no hand token — the engine tracks special energy
    off-hand, matching EffectCtx._pull_energy which likewise skips those pseudo-types). Returns the
    number of pips moved."""
    moved = 0
    for t in list(mon.energy):
        while mon.energy[t] > 0 and moved < n:
            mon.energy[t] -= 1
            moved += 1
            if t not in ('Wild', 'Colorless'):
                owner.hand.append(('E', t))
            elif mon.special:
                mon.special.pop()
        if mon.energy[t] <= 0:
            del mon.energy[t]
    return moved


def _bounce_self_to_hand(ctx):
    """Return the attacker and all attached cards to its owner's hand, then vacate its play slot
    (promote a benched Pokémon if it was Active). Basic-energy pips return as ('E', type) tokens;
    special-energy pips are dropped (off-hand). Mirrors batch_conditional_damage_0._shuffle_self_into_deck
    but to HAND instead of deck."""
    me = ctx.me
    atk = ctx.attacker
    for t, cnt in list(atk.energy.items()):
        if t not in ('Wild', 'Colorless'):
            me.hand.extend([('E', t)] * cnt)
    atk.energy.clear()
    atk.special = []
    me.hand.append(('P', atk.card))
    if me.active is atk:
        me.active = None
        me.promote()
    elif atk in me.bench:
        me.bench.remove(atk)


def _best_dmg_attack_name(mon):
    """Name of the mon's highest printed-damage attack (the meaningful pick to disable), or None."""
    atks = mon.card.attacks
    if not atks:
        return None
    return max(atks, key=lambda a: a['dmg'])['name']


def _copy_best_attack_dmg(mon):
    """Damage of copying the mon's best attack: its highest printed base (a floor for scalers). The
    copied attack's energy cost is ignored (that is the point of Metronome-style copy), and nested
    effect text is NOT re-resolved (bounded, never over-applies)."""
    return max((a['dmg'] for a in mon.card.attacks), default=0)


def _disable_defender(ctx, name):
    """Lock the Defending Pokémon out of an attack during the opponent's next turn (T+1) via the
    cooldown gate: cd_turn = game.turn - 1 so `cd_turn + 2 == T+1`. name='ALL' disables every attack."""
    ctx.defender.cd_name = name
    ctx.defender.cd_turn = ctx.game.turn - 1


def _recover_from_discard(player, want):
    """Move the first discard token matching predicate `want` into hand. Returns True if one moved."""
    for tok in list(player.discard):
        if want(tok):
            player.discard.remove(tok)
            player.hand.append(tok)
            return True
    return False


# ================================================================ "ignore ..." / no-op clauses
@effect("This attack's damage isn't affected by Resistance.")
def _ignore_resistance(ctx):
    # The engine models Weakness only (never Resistance), so this clause is already a no-op.
    return ctx.base


@effect("This attack's damage isn't affected by any effects on your opponent's Active Pokémon.")
def _ignore_defender_effects(ctx):
    # Neutralize the one dynamic "effect on the opponent's Active" the engine applies per hit: the
    # defender's temporary damage-reduction (Mon.dr_amount / dr_turn, read by incoming_damage). Clearing
    # it makes this hit ignore it. (Ability-based prevention on the defender is not bypassable without
    # engine support — a known partial; deal the printed base regardless.)
    ctx.defender.dr_amount = 0
    ctx.defender.dr_turn = -9
    return ctx.base


# ================================================================ Stadium clauses (Stadium tracked)
@effect("Discard a Stadium in play.")
def _discard_stadium(ctx):
    # Discard the Stadium in play (if any). Damage is unaffected.
    if ctx.stadium():
        ctx.discard_stadium()
    return ctx.base


@effect("You may discard a Stadium in play.")
def _may_discard_stadium(ctx):
    # "You may" — remove a Stadium in play (beneficial disruption, always taken). No Stadium -> no-op.
    if ctx.stadium():
        ctx.discard_stadium()
    return ctx.base


@effect("If there is no Stadium in play, this attack does nothing.")
def _nothing_without_stadium(ctx):
    # Full damage only while a Stadium is in play; otherwise the attack does nothing.
    return ctx.base if ctx.stadium() else 0


# ================================================================ self attack-locks (this Pokémon)
@effect("During your next turn, this Pokémon can't use attacks.")
def _self_lock_all(ctx):
    ctx.cant_attack_next()          # cd_name='ALL', cd_turn=game.turn -> disabled on my next turn (T+2)
    return ctx.base


@effect("During your next turn, this Pokémon can't use Accelerating Stab.")
def _self_lock_accel_stab(ctx):
    ctx.attacker.cd_name = 'Accelerating Stab'
    ctx.attacker.cd_turn = ctx.game.turn
    return ctx.base


@effect("During your next turn, this Pokémon can't use Flashing Bolt.")
def _self_lock_flashing_bolt(ctx):
    ctx.attacker.cd_name = 'Flashing Bolt'
    ctx.attacker.cd_turn = ctx.game.turn
    return ctx.base


@effect("During your next turn, this Pokémon can't use Zap Cannon.")
def _self_lock_zap_cannon(ctx):
    ctx.attacker.cd_name = 'Zap Cannon'
    ctx.attacker.cd_turn = ctx.game.turn
    return ctx.base


# ================================================================ defender attack-locks (next turn)
@effect("During your opponent's next turn, the Defending Pokémon can't use attacks.")
def _defender_lock_use_attacks(ctx):
    _disable_defender(ctx, 'ALL')
    return ctx.base


@effect("During your opponent's next turn, the Defending Pokémon can't attack.")
def _defender_lock_attack(ctx):
    _disable_defender(ctx, 'ALL')
    return ctx.base


@effect("Choose 1 of your opponent's Active Pokémon's attacks. During your opponent's next turn, that Pokémon can't use that attack.")
def _defender_lock_one_attack(ctx):
    # Choose the defender's highest-damage attack (the meaningful disruption) and lock only that one.
    name = _best_dmg_attack_name(ctx.defender)
    if name is not None:
        _disable_defender(ctx, name)
    return ctx.base


# ================================================================ copy attacks
@effect("Choose 1 of your opponent's Active Pokémon's attacks and use it as this attack.")
def _copy_opponent_attack(ctx):
    # Metronome (Clefable): copy the opponent's Active's best attack, ignoring energy cost. Model the
    # copied damage as that attack's printed base (a floor for scalers); the engine applies Weakness.
    return _copy_best_attack_dmg(ctx.defender)


@effect("Choose 1 of your opponent's Active Tera Pokémon's attacks and use it as this attack.")
def _copy_opponent_tera_attack(ctx):
    # Requires the opponent's Active to be a Tera Pokémon. The card model exposes no Tera flag (Tera-ness
    # lives in un-parsed subtype data), so no Tera target can be confirmed -> the attack does nothing.
    # Conservative (never copies into a non-Tera target). Deals 0.
    return 0


# ================================================================ hand disruption (opponent)
@effect("Your opponent reveals their hand.")
def _opp_reveal_hand(ctx):
    # Information only; the AI already has full information, so no mechanical change. Deal base.
    return ctx.base


@effect("Choose a random card from your opponent's hand. Your opponent reveals that card and shuffles it into their deck.")
def _opp_random_to_deck(ctx):
    opp = ctx.opp
    if opp.hand:
        tok = opp.hand.pop(_pick_random_index(ctx, opp.hand))
        opp.deck.append(tok)
        ctx.rng.shuffle(opp.deck)
    return ctx.base


@effect("Discard a random card from your opponent's hand.")
def _opp_discard_random(ctx):
    opp = ctx.opp
    if opp.hand:
        _route_to_discard(opp, opp.hand.pop(_pick_random_index(ctx, opp.hand)))
    return ctx.base


@effect("Your opponent discards 2 cards from their hand.")
def _opp_discard_2(ctx):
    _discard_from_hand(ctx.opp, 2)
    return ctx.base


@effect("Your opponent chooses 3 cards from their hand and shuffles those cards into their deck.")
def _opp_shuffle_3(ctx):
    _shuffle_from_hand_to_deck(ctx, ctx.opp, 3)
    return ctx.base


@effect("During your opponent's next turn, they can't play any Item cards from their hand.")
def _opp_item_lock(ctx):
    # Item lock has no engine hook (play_trainers plays Items unconditionally). Record the intent
    # turn-stamped for the opponent's next turn (T+1) so a future play_trainers pass could honor it;
    # deal the printed base now. Never affects anything else.
    ctx.opp.no_item_until = ctx.game.turn + 1
    return ctx.base


# ================================================================ energy bounce (to hand)
@effect("You may put 2 Energy attached to your opponent's Active Pokémon into their hand.")
def _bounce_2_opp_energy(ctx):
    # "You may" — beneficial disruption, always taken. Up to 2 Energy off the defender -> opponent's hand.
    _energy_to_hand(ctx.defender, ctx.opp, 2)
    return ctx.base


@effect("Put an Energy attached to this Pokémon into your hand.")
def _bounce_1_self_energy(ctx):
    # 1 Energy off the attacker -> my hand.
    _energy_to_hand(ctx.attacker, ctx.me, 1)
    return ctx.base


# ================================================================ self / card recursion
@effect("Put this Pokémon and all attached cards into your hand.")
def _bounce_self(ctx):
    # Deal the printed damage (returned), then return the attacker + attached cards to my hand and
    # promote a benched Pokémon into the vacated Active spot.
    dmg = ctx.base
    _bounce_self_to_hand(ctx)
    return dmg


@effect("Put a Supporter card from your discard pile into your hand.")
def _recover_supporter(ctx):
    # Recover a Supporter from the discard pile (typically a no-op in this sim, which does not route
    # played Trainers to a discard pile; wired for correctness if that changes).
    _recover_from_discard(ctx.me, lambda t: t[0] == 'T' and t[1].get('trainerType') == 'Supporter')
    return ctx.base


@effect("Put a Pokémon from your discard pile into your hand.")
def _recover_pokemon(ctx):
    # Recover the best attacker (highest-damage attack) among Pokémon in the discard, mirroring
    # engine._do_recover; deal the printed base (0 for Slowpoke).
    ps = [t for t in ctx.me.discard if t[0] == 'P']
    if ps:
        rec = max(ps, key=lambda t: max((a['dmg'] for a in t[1].attacks), default=0))
        ctx.me.discard.remove(rec)
        ctx.me.hand.append(rec)
    return ctx.base


# ================================================================ hand-size gate
@effect("If you don't have exactly 3 cards in your hand, this attack does nothing.")
def _needs_exactly_3_in_hand(ctx):
    # Alolan Dugtrio: full [120] only when the hand holds exactly 3 cards at attack time; else nothing.
    return ctx.base if len(ctx.me.hand) == 3 else 0


# ================================================================ double KO
@effect("Both Active Pokémon are Knocked Out.")
def _both_active_ko(ctx):
    # Mark both Active Pokémon lethal so the engine's defender-KO and attacker-self-KO checks both fire
    # (each side loses its Active, promotes, and takes a Prize). The attack itself deals 0 printed damage.
    ctx.defender.damage = ctx.defender.card.hp + 9999
    ctx.attacker.damage = ctx.attacker.card.hp + 9999
    return 0


# ================================================================ delayed discard (no engine hook)
@effect("At the end of your opponent's next turn, discard the Defending Pokémon and all attached cards.")
def _delayed_discard_defender(ctx):
    # Team Rocket's Grimer: a delayed "discard the Defending Pokémon at the end of the opponent's next
    # turn" has no engine hook (no cross-turn delayed-effect queue, and the opponent could retreat the
    # mon out of it). Record intent turn-stamped for future wiring; do NOT KO now (that would over-apply).
    ctx.defender.status['DiscardEndOfOppNextTurn'] = ctx.game.turn
    return ctx.base
