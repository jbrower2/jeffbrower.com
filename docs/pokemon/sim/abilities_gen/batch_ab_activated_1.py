#!/usr/bin/env python3
"""Batch: ab_activated_1 — nine once-per-turn (or once-per-play/evolve) `activated` abilities,
each fn(actx)->bool where True == "the Ability was used this turn".

Following the ab_search_0 / ab_draw_0 convention, the turn-flow gating that the printed text spells
out — "Once during your turn", "when you play this Pokémon to evolve", "when you play onto your Bench",
"you can't use during your first turn", "as often as you like" — is owned by the caller (the engine's
main phase). Each lambda here implements only the *effect*, gated on its own on-card condition
(Active-Spot requirement, a valid evolve target in hand, an opponent to disrupt, resources to spend).

Special Conditions respect the target's effect-shield (Mist / Rocky / Bubbly special energy via
Mon.effect_immune()) — a shielded Active is left untouched and the ability reports not-used, per the
"respect effect_immune() for conditions" rule.

Heuristic notes (see `uncertain`):
  * Snack Seek's optional "you may discard" only discards a Basic Energy (feeds discard-recursion
    accel at low cost); a Pokémon/Trainer on top is peeked and kept.
  * Evidence Gathering gives up a spare Basic Energy (redrawn next turn) to pull the deck's top card
    into hand now — the genuinely useful, non-committal swap.
  * Rocket Brain levels damage off the most-hurt Team Rocket's Pokémon onto the healthiest teammate
    without KOing it (pure single-KO-risk reduction); the theoretically-optimal move target depends
    on the opponent's next attack, which the ability can't see.
"""
from ability_effects import ability, ActivatedCtx  # noqa: F401 (ActivatedCtx per batch header convention)
from engine import Mon

BASIC_TYPES = ('Grass', 'Fire', 'Water', 'Lightning', 'Psychic', 'Fighting', 'Darkness', 'Metal')
_EXCLUSIVE = ('Asleep', 'Paralyzed', 'Confused')


# ---------------------------------------------------------------- helpers
def _copy_state(mon, ev):
    """Carry on-board state onto an evolution (damage, energy, special energy, turns, conditions)."""
    ev.damage = mon.damage
    ev.energy = mon.energy
    ev.special = mon.special
    ev.turns = mon.turns
    ev.status = mon.status
    ev.poison_amt = mon.poison_amt
    return ev


def _set_condition(mon, cond):
    """Apply a Special Condition, honoring the Asleep/Paralyzed/Confused mutual exclusion (mirrors
    effects.set_status). No-op returning False if the target shields incoming effects/conditions."""
    if mon.effect_immune():
        return False
    if cond in _EXCLUSIVE:
        for x in _EXCLUSIVE:
            mon.status.pop(x, None)
    mon.status[cond] = True
    return True


def _discard_one_energy(player, mon):
    """Discard 1 energy from `mon`. Prefers a Basic energy pip (it lands in the owner's disc_energy
    pool); falls back to a Special-energy pip ('Wild'/'Colorless' pseudo-type + its name). False if
    the Pokémon has no energy attached."""
    basics = [t for t in BASIC_TYPES if mon.energy.get(t, 0) > 0]
    if basics:
        t = max(basics, key=lambda t: mon.energy[t])
        mon.energy[t] -= 1
        if mon.energy[t] <= 0:
            del mon.energy[t]
        player.disc_energy[t] += 1
        return True
    for t in ('Wild', 'Colorless'):
        if mon.energy.get(t, 0) > 0:
            mon.energy[t] -= 1
            if mon.energy[t] <= 0:
                del mon.energy[t]
            if mon.special:
                mon.special.pop()
            return True
    return False


# ---------------------------------------------------------------- evolve-from-hand
@ability('activated', "- Once during your turn, you may use this Ability. Choose a card in your hand that evolves from this Pokémon and put it onto this Pokémon to evolve it. If you do, place 2 damage counters on the Pokémon you evolved in this way. You can't use this Ability during your first turn.")
def _spiteful_evolution(actx):
    # Phantump (Spiteful Evolution): an alternate evolve path — evolve THIS Pokémon from a matching
    # card in hand, then put 2 damage counters (=20) on the evolution. ("first turn" gate = caller.)
    me, mon = actx.me, actx.mon
    for t in list(me.hand):
        if t[0] == 'P' and t[1].evolves_from == mon.card.name and t[1].stage == mon.card.stage + 1:
            ev = _copy_state(mon, Mon(t[1]))
            ev.damage += 20                      # place 2 damage counters on the evolved Pokémon
            if mon is me.active:
                me.active = ev
            elif mon in me.bench:
                me.bench[me.bench.index(mon)] = ev
            else:
                return False
            me.hand.remove(t)
            return True
    return False


# ---------------------------------------------------------------- deck manipulation
@ability('activated', "- Once during your turn, you may use this Ability. Switch a card from your hand with the top card of your deck.")
def _evidence_gathering(actx):
    # Gumshoos (Evidence Gathering): trade a hand card for the current top of deck (deck[-1] is the
    # top — draw pops the end). Give up a spare Basic Energy (redrawn next turn) if we have one, else
    # the last hand card; the given card becomes the new top.
    me = actx.me
    if not me.hand or not me.deck:
        return False
    give_idx = next((i for i, t in enumerate(me.hand) if t[0] == 'E'), len(me.hand) - 1)
    give = me.hand.pop(give_idx)
    me.hand.append(me.deck.pop())                # take the old top into hand
    me.deck.append(give)                         # given card is the new top
    return True


@ability('activated', "- Once during your turn, you may look at the top card of your deck. You may discard that card.")
def _snack_seek(actx):
    # Morpeko (Snack Seek): peek the top card; the optional discard is taken ONLY for a Basic Energy
    # (fuels discard-recursion accel at minimal cost). A Pokémon/Trainer on top is kept (no-op).
    me = actx.me
    if not me.deck:
        return False
    top = me.deck[-1]
    if top[0] == 'E':
        me.deck.pop()
        me.disc_energy[top[1]] += 1
        return True
    return False


@ability('activated', "- Once during your turn, if this Pokémon is in the Active Spot, you may look at the top 6 cards of your deck, reveal a Supporter card you find there, and put it into your hand. Shuffle the other cards back into your deck.")
def _attract_customers(actx):
    # Tatsugiri (Attract Customers): from the Active Spot only, dig the top 6 (deck[-6:], deck[-1] the
    # very top) for a Supporter and put it into hand. Shuffle-back of the rest is a mechanical no-op.
    me = actx.me
    if actx.mon is not me.active:
        return False
    lo = max(0, len(me.deck) - 6)
    for i in range(len(me.deck) - 1, lo - 1, -1):
        t = me.deck[i]
        if t[0] == 'T' and t[1].get('trainerType') == 'Supporter':
            me.hand.append(me.deck.pop(i))
            return True
    return False


# ---------------------------------------------------------------- heal / cure
@ability('activated', "- When you play this Pokémon from your hand onto your Bench during your turn, you may heal 30 damage from your Active Pokémon and have it recover from a Special Condition.")
def _obliging_heal(actx):
    # Indeedee (Obliging Heal): on being benched, heal 30 from your ACTIVE and clear one of its
    # Special Conditions. No benefit (and so not used) if the Active is undamaged and status-free.
    act = actx.me.active
    if act is None or (act.damage <= 0 and not act.status):
        return False
    actx.heal(30, act)
    if act.status:                               # recover from one Special Condition ("a" = singular)
        # Cure the most crippling one first: Asleep/Paralyzed fully block this Active from attacking
        # THIS turn, Confused is a 50% block, Poisoned/Burned only tick damage. Wasting the single
        # cure on Poison while the Active stays Asleep would defeat the ability's purpose.
        order = ('Asleep', 'Paralyzed', 'Confused', 'Poisoned', 'Burned')
        cond = next((c for c in order if c in act.status), next(iter(act.status)))
        act.status.pop(cond, None)
    return True


@ability('activated', "- As often as you like during your turn, you may move 1 damage counter from 1 of your Team Rocket's Pokémon to another of your Pokémon.")
def _rocket_brain(actx):
    # Team Rocket's Orbeetle (Rocket Brain): relocate damage off the most-hurt Team Rocket's Pokémon
    # onto the healthiest teammate, never KOing it and never loading it past the source (pure damage
    # leveling -> lowers single-KO risk). "As often as you like" = drain the loop.
    mons = actx.me.all_mons()
    moved = False
    while True:
        srcs = [m for m in mons if m.card.name.startswith("Team Rocket's") and m.damage > 0]
        if not srcs:
            break
        src = max(srcs, key=lambda m: m.damage)
        recips = [m for m in mons if m is not src and m.damage + 10 < m.max_hp
                  and src.damage >= m.damage + 20]
        if not recips:
            break
        dst = max(recips, key=lambda m: m.max_hp - m.damage)
        src.damage -= 10
        dst.damage += 10
        moved = True
    return moved


# ---------------------------------------------------------------- opponent disruption (conditions)
@ability('activated', "- Once during your turn, if this Pokémon is in the Active Spot, you may make your opponent's Active Pokémon Asleep.")
def _calming_light(actx):
    # Shiinotic (Calming Light): from the Active Spot only, put the opponent's Active to Sleep.
    if actx.mon is not actx.me.active or actx.opp.active is None:
        return False
    return _set_condition(actx.opp.active, 'Asleep')


@ability('activated', "- Once during your turn, when you play this Pokémon from your hand to evolve 1 of your Pokémon, you may use this Ability. Make your opponent's Active Pokémon Confused.")
def _prison_panic(actx):
    # Brambleghast (Prison Panic): on-evolve, Confuse the opponent's Active.
    if actx.opp.active is None:
        return False
    return _set_condition(actx.opp.active, 'Confused')


@ability('activated', "- Once during your turn, when you play this Pokémon from your hand to evolve 1 of your Pokémon, you may use this Ability. Flip a coin. If heads, discard an Energy from your opponent's Active Pokémon.")
def _haphazard_hammer(actx):
    # Tinkatuff (Haphazard Hammer): on-evolve, flip a coin; heads discards 1 Energy from the
    # opponent's Active. The ability is "used" (flip resolved) whenever there's an Active to target.
    opp_active = actx.opp.active
    if opp_active is None:
        return False
    if actx.flip():                              # heads
        _discard_one_energy(actx.opp, opp_active)
    return True
