#!/usr/bin/env python3
"""Attack-effect implementations for batch 'misc_2'.

18 distinct effect texts: energy/card recovery, self-referential attack cooldowns,
a forced least-HP KO, single-target devolve, damage-counter placement, self-shuffle
(mandatory + optional), self-mill, and two engine-unmodeled defender debuffs
(temporary Weakness change, attack/retreat cost increase) recorded as best-effort markers.
"""
from attack_effects import effect, EffectCtx, STATUSES
from engine import BY_NAME


# ---------------------------------------------------------------- shared helpers
def _opp_mons(ctx):
    return ctx.opp.all_mons()


def _ko_mon(ctx, mon):
    """Fully remove `mon` from play: discard its card + energy, give the other player its
    prize(s), and promote/remove as appropriate. Mirrors the engine's inline KO handling."""
    for owner, foe in ((ctx.me, ctx.opp), (ctx.opp, ctx.me)):
        if mon is owner.active:
            for t, n in mon.energy.items():
                owner.disc_energy[t] += n
            owner.discard.append(('P', mon.card))
            foe.take_prize(2 if mon.card.is_ex else 1)
            owner.promote()
            return True
        if mon in owner.bench:
            for t, n in mon.energy.items():
                owner.disc_energy[t] += n
            owner.discard.append(('P', mon.card))
            foe.take_prize(2 if mon.card.is_ex else 1)
            owner.bench.remove(mon)
            return True
    return False


def _energy_to_hand(ctx, etype, n):
    """Return up to n basic energy of `etype` from the attacker to its owner's hand (NOT discard)."""
    moved = 0
    while moved < n and ctx.attacker.energy.get(etype, 0) > 0:
        ctx.attacker.energy[etype] -= 1
        if ctx.attacker.energy[etype] <= 0:
            del ctx.attacker.energy[etype]
        ctx.me.hand.append(('E', etype))
        moved += 1
    return moved


def _shuffle_self(ctx):
    """Shuffle the attacker + all attached basic energy back into the owner's deck, then promote."""
    mon = ctx.attacker
    for t, n in list(mon.energy.items()):
        if t in ('Wild', 'Colorless'):          # special-energy pseudo-pips, not basic energy cards
            continue
        for _ in range(n):
            ctx.me.deck.append(('E', t))
    ctx.me.deck.append(('P', mon.card))
    if mon is ctx.me.active:
        ctx.me.active = None
        ctx.game.rng.shuffle(ctx.me.deck)
        ctx.me.promote()
    elif mon in ctx.me.bench:
        ctx.me.bench.remove(mon)
        ctx.game.rng.shuffle(ctx.me.deck)


def _place_counters_opp(ctx, n_counters):
    """Place n damage counters (10 each) on the opponent's Pokémon closest to being KO'd."""
    mons = _opp_mons(ctx)
    if not mons:
        return
    target = min(mons, key=lambda m: m.hp_left)
    target.damage += 10 * n_counters
    if target is not ctx.opp.active and target.damage >= target.max_hp:
        _ko_mon(ctx, target)                     # engine handles an Active KO after the attack; bench is ours


# ---------------------------------------------------------------- card recovery
@effect("Put a Trainer card from your discard pile into your hand.")
def _recover_trainer(ctx):
    trainers = [x for x in ctx.me.discard if x[0] == 'T']
    if trainers:
        pick = next((t for t in trainers if t[1].get('trainerType') == 'Supporter'), trainers[0])
        ctx.me.discard.remove(pick)
        ctx.me.hand.append(pick)
    return ctx.base


@effect("Put up to 2 Pokémon from your discard pile into your hand.")
def _recover_2_pokemon(ctx):
    ps = [x for x in ctx.me.discard if x[0] == 'P']
    ps.sort(key=lambda x: max((a['dmg'] for a in x[1].attacks), default=0), reverse=True)
    for tok in ps[:2]:
        ctx.me.discard.remove(tok)
        ctx.me.hand.append(tok)
    return ctx.base


# ---------------------------------------------------------------- energy retrieval
@effect("Put 2 {R} Energy attached to this Pokémon into your hand.")
def _return_2_fire_to_hand(ctx):
    _energy_to_hand(ctx, 'Fire', 2)
    return ctx.base


# ---------------------------------------------------------------- self-referential cooldowns
# "During your next turn, this Pokémon can't use <this attack>." The named attack is always the
# attack carrying the text (see effects.attack_cooldown), so block the attack's own name next turn.
@effect(
    "During your next turn, this Pokémon can't use Flare Strike.",
    "During your next turn, this Pokémon can't use Haymaker.",
    "During your next turn, this Pokémon can't use Dragon Strike.",
    "During your next turn, this Pokémon can't use Frosty Typhoon.",
    "During your next turn, this Pokémon can't use Zen Blade.",
    "During your next turn, this Pokémon can't use Ogre's Hammer.",
)
def _cant_use_this_next_turn(ctx):
    ctx.attacker.cd_name = ctx.attack['name']
    ctx.attacker.cd_turn = ctx.game.turn
    return ctx.base


# ---------------------------------------------------------------- self-shuffle to deck
@effect("Shuffle this Pokémon and all attached cards into your deck.")
def _shuffle_self_mandatory(ctx):
    dmg = ctx.base                               # damage is dealt first, then this Pokémon leaves play
    _shuffle_self(ctx)
    return dmg


@effect("You may shuffle this Pokémon and all attached cards into your deck.")
def _shuffle_self_optional(ctx):
    dmg = ctx.base
    # Prize-denial / hit-and-run: only shuffle back when this Pokémon is about to be KO'd anyway and a
    # benched Pokémon can take over; otherwise keep the set-up attacker in play.
    if ctx.me.bench and ctx.attacker.hp_left <= 60:
        _shuffle_self(ctx)
    return dmg


# ---------------------------------------------------------------- self-mill
@effect("Discard the top 3 cards of your deck.")
def _discard_top_3(ctx):
    for _ in range(3):
        if not ctx.me.deck:
            break
        tok = ctx.me.deck.pop()                  # top of deck = end of list (draw pops the end)
        if tok[0] == 'E':
            ctx.me.disc_energy[tok[1]] += 1
        else:
            ctx.me.discard.append(tok)
    return ctx.base


# ---------------------------------------------------------------- forced least-HP KO
@effect("Choose a Pokémon in play (yours or your opponent's) that has the least HP remaining, "
        "except for this Pokémon, and it is Knocked Out.")
def _least_hp_ko(ctx):
    opp_mons = _opp_mons(ctx)
    cands = [m for m in (ctx.me.all_mons() + opp_mons) if m is not ctx.attacker]
    if not cands:
        return ctx.base
    least = min(m.hp_left for m in cands)
    tied = [m for m in cands if m.hp_left == least]
    target = next((m for m in tied if m in opp_mons), tied[0])   # break ties toward the opponent's
    _ko_mon(ctx, target)
    return ctx.base


# ---------------------------------------------------------------- damage counter
@effect("Place 1 damage counter on 1 of your opponent's Pokémon.")
def _place_1_counter(ctx):
    _place_counters_opp(ctx, 1)
    return ctx.base


# ---------------------------------------------------------------- devolve
@effect("Devolve 1 of your opponent's evolved Pokémon by putting the highest Stage Evolution card "
        "on it into your opponent's hand.")
def _devolve_opp(ctx):
    cands = [m for m in _opp_mons(ctx) if m.card.stage >= 1 and m.card.evolves_from]
    if not cands:
        return ctx.base
    active = ctx.opp.active
    target = active if active in cands else max(cands, key=lambda m: m.card.stage)  # active > highest stage
    prevs = BY_NAME.get(target.card.evolves_from)
    if not prevs:
        return ctx.base
    ctx.opp.hand.append(('P', target.card))      # top evolution card back to hand
    target.card = prevs[0]                        # revert one stage (damage + energy stay)
    return ctx.base


# ---------------------------------------------------------------- information only (unmodeled)
@effect("Look at 1 of your opponent's face-down Prize cards.")
def _look_at_prize(ctx):
    return ctx.base                              # hidden information not modeled — pure no-op


# ---------------------------------------------------------------- defender debuffs (engine-unmodeled markers)
@effect("Until the end of your next turn, the Defending Pokémon's Weakness is now {C}. "
        "(The amount of Weakness doesn't change.)")
def _set_weakness_colorless(ctx):
    # The engine reads weakness off the shared Card and has no per-Mon override hook, so this is a
    # best-effort marker on the defender (won't currently change damage math).
    ctx.defender.weakness_override = 'Colorless'
    ctx.defender.weakness_override_turn = ctx.game.turn
    return ctx.base


@effect("During your opponent's next turn, attacks used by the Defending Pokémon cost {C} more, "
        "and its Retreat Cost is {C} more.")
def _cost_more_next_turn(ctx):
    # No engine hook for temporary attack/retreat-cost inflation; record as best-effort markers.
    ctx.defender.attack_cost_bonus = 1
    ctx.defender.retreat_bonus = 1
    ctx.defender.cost_debuff_turn = ctx.game.turn
    return ctx.base
