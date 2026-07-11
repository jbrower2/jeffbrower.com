#!/usr/bin/env python3
"""Effect batch: misc_1.

A grab-bag of one-off attack effects: damage-counter placement, hand/energy disruption,
energy relocation (own team + opponent), from-hand energy attachment, self/team attack
cooldowns, a delayed win condition, and a no-Weakness snipe. Each effect is registered by
its exact (damage-stripped) text and returns the PRE-Weakness damage to the opponent's
Active (0 when the attack only places counters / relocates state).

Convention (matches the sibling batches + attack_effects.resolve):
  * The int returned is damage to the opponent's ACTIVE; the engine applies Weakness after.
  * "Place/Put N damage counters" and "damage isn't affected by Weakness or Resistance"
    bypass Weakness, so they are written straight onto the target's `.damage` and the
    function returns 0 (nothing for the engine to double).
  * Bench damage / relocated counters are written straight to `.damage` (no Weakness).

Not modeled (no engine hook for the opponent's *future* turn / delayed timing) — these
return their printed base and are flagged uncertain: the two "punish an energy attach"
riders (Hypno/Pachirisu), the Glaceon delayed counters, Walrein's low-energy attack lock,
Bronzong's evolve lock, and Mr. Mime's steal-a-Supporter.
"""
from attack_effects import effect, EffectCtx, STATUSES


# ---------------------------------------------------------------- helpers
def _target_ally(ctx, player=None):
    """The ally Pokémon to receive energy / a benefit: the ace (highest-ceiling attacker),
    falling back to the Active, then the first benched Pokémon. None if the player has none."""
    player = player or ctx.me
    t = ctx.game.primary(player)
    return t or player.active or (player.bench[0] if player.bench else None)


def _attach_basics_from_hand(player, target, n, ptype=None):
    """Attach up to `n` Basic Energy cards (tokens ('E', type), optionally only `ptype`) from
    `player`'s hand onto `target`. Returns how many were attached. Special Energy ('S') is not
    a Basic Energy card, so it's never taken here."""
    if target is None:
        return 0
    done = 0
    for tok in list(player.hand):
        if done >= n:
            break
        if tok[0] == 'E' and (ptype is None or tok[1] == ptype):
            player.hand.remove(tok)
            target.energy[tok[1]] += 1
            done += 1
    return done


def _energy_to_hand(mon, owner, n):
    """Remove up to `n` Energy from `mon` and return the Basic ones to `owner`'s hand as
    ('E', type) tokens. Special-energy pseudo-pips ('Wild'/'Colorless') are removed but not
    reconstructed as a hand card (we can't recover which Special Energy card it was).
    Returns the number of pips removed."""
    moved = 0
    for t in list(mon.energy):
        while mon.energy[t] > 0 and moved < n:
            mon.energy[t] -= 1
            moved += 1
            if t not in ('Wild', 'Colorless'):
                owner.hand.append(('E', t))
        if mon.energy.get(t, 0) <= 0:
            mon.energy.pop(t, None)
        if moved >= n:
            break
    return moved


def _discard_one(player):
    """`player` discards one card from hand (their choice — we take the last), routing Basic
    Energy to disc_energy and Pokémon to the discard pile. Returns True iff a card was discarded
    (so an "If you do" gate can fail on an empty hand)."""
    if not player.hand:
        return False
    tok = player.hand.pop()
    if tok[0] == 'E':
        player.disc_energy[tok[1]] += 1
    elif tok[0] == 'P':
        player.discard.append(tok)
    return True


def _consolidate_own_energy(ctx, ptype=None):
    """Move Energy (all types, or only `ptype`) off every OTHER of your Pokémon onto the ace.
    Models "move any amount of Energy to your other Pokémon in any way you like" as gathering
    the energy onto the biggest threat so it can attack."""
    dest = _target_ally(ctx)
    if dest is None:
        return
    for m in ctx.me.all_mons():
        if m is dest:
            continue
        for t in list(m.energy):
            if ptype is not None and t != ptype:
                continue
            cnt = m.energy.get(t, 0)
            if cnt <= 0:
                continue
            dest.energy[t] += cnt
            m.energy.pop(t, None)


def _pick_opp_target(ctx, dmg):
    """Choose the best target among the opponent's Pokémon for a `dmg`-damage snipe / counter
    placement: a Pokémon this would KO (prefer ex for 2 prizes, then lowest HP left); else the
    most valuable/closest-to-KO Pokémon. Returns a Mon or None."""
    opp = ctx.opp
    cands = ([opp.active] if opp.active is not None else []) + list(opp.bench)
    if not cands:
        return None
    koable = [m for m in cands if dmg >= m.hp_left]
    pool = koable or cands
    return min(pool, key=lambda m: (not m.card.is_ex, m.hp_left))


# ================================================================ damage-counter placement
@effect("Place 3 damage counters on your opponent's Active Pokémon.")
def _place_3_on_active(ctx):
    # 3 counters = 30 damage placed straight on the opponent's Active (bypasses Weakness).
    if ctx.defender is not None:
        ctx.defender.damage += 30
    return 0


@effect("Put 2 damage counters on 1 of your opponent's Pokémon.")
def _put_2_on_one(ctx):
    tgt = _pick_opp_target(ctx, 20)          # 2 counters = 20 damage, counter placement (no Weakness)
    if tgt is not None:
        tgt.damage += 20
    return 0


@effect("Put damage counters on your opponent's Active Pokémon until its remaining HP is 10.")
def _counters_until_hp_10(ctx):
    # Add counters until HP left is 10; never removes counters (can't heal an already-lower mon).
    d = ctx.defender
    if d is not None:
        d.damage = max(d.damage, d.max_hp - 10)
    return 0


@effect("This attack does 70 damage to 1 of your opponent's Pokémon. This attack's damage isn't affected by Weakness or Resistance.")
def _snipe_70_no_wr(ctx):
    # No Weakness/Resistance on ANY target -> write 70 straight to the chosen mon's .damage and
    # return 0 (returning it would let the engine double it on Weakness). Active or Bench.
    tgt = _pick_opp_target(ctx, 70)
    if tgt is not None:
        tgt.damage += 70
    return 0


# ================================================================ delayed / future-turn (NOT modeled)
@effect("At the end of your opponent's next turn, put 9 damage counters on the Defending Pokémon.")
def _glaceon_delayed_9(ctx):
    # Delayed 90 damage at the end of the opponent's next turn. The engine has no delayed-damage
    # hook, and placing it now would be a wrong-timing (and possibly wrong-target) over-application,
    # so we deal only the printed base and skip the delayed counters (safe under-application).
    return ctx.base


@effect("During your opponent's next turn, if they attach an Energy card from their hand to the Defending Pokémon, their turn ends.")
def _hypno_end_turn_on_attach(ctx):
    # "If they attach Energy to the Defender, their turn ends" — a reactive lock on the opponent's
    # future turn with no engine hook. Deal the base only.
    return ctx.base


@effect("During your opponent's next turn, whenever they attach an Energy card from their hand to the Defending Pokémon, place 8 damage counters on that Pokémon.")
def _pachirisu_punish_attach(ctx):
    # Punish-on-attach rider on the opponent's future turn — no engine hook. Base only.
    return ctx.base


@effect("During your opponent's next turn, Pokémon that have 2 or less Energy attached can't attack. (This includes new Pokémon that come into play.)")
def _walrein_low_energy_lock(ctx):
    # Opponent-side conditional attack lock (<=2 energy) for their next turn — no engine hook,
    # and the opponent could attach a 3rd energy before attacking, so locking now would over-apply.
    return ctx.base


@effect("During your opponent's next turn, they can't play any Pokémon from their hand to evolve their Pokémon.")
def _bronzong_evolve_lock(ctx):
    # Opponent can't evolve next turn — the engine's evolve step reads no such flag. Base only.
    return ctx.base


@effect("Your opponent reveals their hand. You may use the effect of a Supporter card you find there as the effect of this attack.")
def _mr_mime_borrow_supporter(ctx):
    # "Use a Supporter from the opponent's hand as this attack's effect" needs a full arbitrary-
    # Supporter resolver keyed on whatever they hold — out of scope. No-op (base is 0).
    return ctx.base


# ================================================================ attach energy from hand (own team)
@effect("Attach a Basic Energy card from your hand to 1 of your Pokémon.")
def _attach_1_basic(ctx):
    _attach_basics_from_hand(ctx.me, _target_ally(ctx), 1)
    return ctx.base


@effect("Attach up to 2 Basic {P} Energy cards from your hand to your Pokémon in any way you like.")
def _attach_2_psychic(ctx):
    _attach_basics_from_hand(ctx.me, _target_ally(ctx), 2, ptype='Psychic')
    return ctx.base


@effect("Each player may attach up to 3 Basic Energy cards from their hand to their Pokémon in any way they like. Your opponent does this first.")
def _each_attach_3(ctx):
    # Symmetric acceleration; the opponent goes first (order is independent here). Each dumps up
    # to 3 Basic Energy from their hand onto their own ace.
    _attach_basics_from_hand(ctx.opp, _target_ally(ctx, ctx.opp), 3)
    _attach_basics_from_hand(ctx.me, _target_ally(ctx, ctx.me), 3)
    return ctx.base


# ================================================================ move energy (own team)
@effect("You may move any amount of {M} Energy from your Pokémon to your other Pokémon in any way you like.")
def _move_metal_own(ctx):
    _consolidate_own_energy(ctx, ptype='Metal')
    return ctx.base


@effect("You may move any amount of Energy from your Pokémon to your other Pokémon in any way you like.")
def _move_any_own(ctx):
    _consolidate_own_energy(ctx, ptype=None)
    return ctx.base


# ================================================================ opponent energy relocation / removal
@effect("Move an Energy from 1 of your opponent's Pokémon to another of their Pokémon.")
def _move_opp_energy(ctx):
    # Disruption: strip an Energy off the opponent's Active (their attacker) and dump it on the
    # least-developed benched Pokémon (wasting it). No-op without a bench or without energy.
    opp = ctx.opp
    if opp.active is None or not opp.bench or opp.active.total_energy() <= 0:
        return ctx.base
    src = opp.active
    t = max(src.energy, key=lambda k: src.energy[k])
    src.energy[t] -= 1
    if src.energy.get(t, 0) <= 0:
        src.energy.pop(t, None)
    sink = min(opp.bench, key=lambda m: m.total_energy())
    sink.energy[t] += 1
    return ctx.base


@effect("You may put an Energy attached to your opponent's Active Pokémon into their hand.")
def _bounce_1_opp_energy(ctx):
    if ctx.opp.active is not None:
        _energy_to_hand(ctx.opp.active, ctx.opp, 1)
    return ctx.base


@effect("You may put 2 Energy attached to your opponent's Active Stage 2 Pokémon into their hand.")
def _bounce_2_opp_stage2_energy(ctx):
    # Gated on the opponent's Active being a Stage 2 Pokémon; then bounce up to 2 of its Energy.
    d = ctx.opp.active
    if d is not None and d.card.stage == 2:
        _energy_to_hand(d, ctx.opp, 2)
    return ctx.base


# ================================================================ hand disruption
@effect("Your opponent discards a card from their hand.")
def _opp_discard_1(ctx):
    _discard_one(ctx.opp)
    return ctx.base


@effect("Discard a card from your hand. If you do, your opponent discards a card from their hand.")
def _discard_both(ctx):
    if _discard_one(ctx.me):                  # only forces the opponent's discard if we discarded
        _discard_one(ctx.opp)
    return ctx.base


@effect("Discard random cards from your opponent's hand until they have 5 cards in their hand.")
def _opp_discard_to_5(ctx):
    while len(ctx.opp.hand) > 5:
        if not _discard_one(ctx.opp):
            break
    return ctx.base


@effect("Choose a random card from your opponent's hand, and your opponent reveals that card and shuffles it into their deck.")
def _shuffle_random_opp_card(ctx):
    opp = ctx.opp
    if opp.hand:
        tok = ctx.rng.choice(opp.hand)        # scripted RNG -> hand[0]; live RNG -> a random card
        opp.hand.remove(tok)
        opp.deck.append(tok)
        ctx.rng.shuffle(opp.deck)
    return ctx.base


@effect("Your opponent reveals their hand, and you choose a card you find there and put it on the bottom of their deck.")
def _bottom_deck_opp_card(ctx):
    # We choose the card, so strip the most useful one: a Trainer/Pokémon/Special over Basic Energy.
    opp = ctx.opp
    if opp.hand:
        tok = next((t for t in opp.hand if t[0] in ('T', 'P', 'S')), opp.hand[-1])
        opp.hand.remove(tok)
        opp.deck.insert(0, tok)               # bottom of deck (draw pops from the end = top)
    return ctx.base


# ================================================================ attack cooldowns (self / team)
@effect("During your next turn, this Pokémon can't use Slashing Strike.")
def _cd_slashing_strike(ctx):
    # Disable only the named attack next turn (best_attack skips cd_name in ('ALL', attack name)).
    ctx.attacker.cd_name = 'Slashing Strike'
    ctx.attacker.cd_turn = ctx.game.turn
    return ctx.base


@effect("During your next turn, your Pokémon can't attack. (This includes new Pokémon that come into play.)")
def _cd_all_own(ctx):
    # Whole-team attack lock next turn: set the 'ALL' cooldown on every Pokémon currently in play
    # (covers a promote/retreat into a benched attacker). Newly-played mons next turn aren't caught
    # — an accepted edge given the per-mon cooldown model.
    for m in ctx.me.all_mons():
        m.cd_name = 'ALL'
        m.cd_turn = ctx.game.turn
    return ctx.base


# ================================================================ next-turn self damage buff
@effect("During your next turn, this Pokémon's Hyper Fang attack's base damage is 240.")
def _buff_hyper_fang_240(ctx):
    # Set Hyper Fang's base to 240 next turn via the ramp channel (best_attack adds mon.ramp[name]
    # to the attack's damage): ramp = 240 - Hyper Fang's printed base.
    hf = next((a for a in ctx.attacker.card.attacks if a.get('name') == 'Hyper Fang'), None)
    cur = hf['dmg'] if hf else 0
    ctx.attacker.ramp['Hyper Fang'] = 240 - cur
    return ctx.base


# ================================================================ hand-size gate / win condition
@effect("If you don't have exactly 7 cards in your hand, this attack does nothing.")
def _gate_hand_7(ctx):
    return ctx.base if len(ctx.me.hand) == 7 else 0


@effect("If you use this attack when you have exactly 1 Prize card remaining, you win this game.")
def _win_at_1_prize(ctx):
    # Win now if exactly 1 Prize left: mark the opponent as lost (Game.winner reads player.lost).
    if ctx.my_prizes() == 1:
        ctx.opp.lost = True
    return ctx.base
