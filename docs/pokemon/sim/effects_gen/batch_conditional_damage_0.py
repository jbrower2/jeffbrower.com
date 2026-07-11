#!/usr/bin/env python3
"""Effect batch: conditional_damage_0.

Scaling / conditional damage attacks: "does N (more) damage for each X", "if <condition>,
this attack does N more damage", plus a few with structural side effects (opponent hand
discard, shuffle-self-into-deck, a next-turn damage buff). Each effect is registered by its
exact (damage-stripped) text and returns the PRE-weakness damage to the defender's Active.

Multiplier convention: for "N× ... does N damage for each Y" attacks the printed base IS the
per-unit multiplier (cards.py parses "20×" -> base 20), so `ctx.base * count`. For "N+ ... does
M more damage for each Y" attacks the per-unit M is written into the text and is NOT the base, so
those hard-code M.
"""
from attack_effects import effect, EffectCtx, STATUSES


# ---------------------------------------------------------------- shared helpers
def _dmg_counters(mon):
    """Damage counters on a Pokémon (each counter = 10 HP of damage)."""
    return mon.damage // 10


def _mon_has_attack(mon, atk_name):
    return any(a.get('name') == atk_name for a in mon.card.attacks)


def _count_named(mons, needles):
    """Count Mons whose card name contains ANY substring in `needles`."""
    return sum(1 for m in mons if any(nd in m.card.name for nd in needles))


def _special_condition_count(mon):
    """Number of Special Conditions on a Pokémon (Asleep/Burned/Confused/Paralyzed/Poisoned).
    Ignores non-condition status keys such as 'CantRetreat'."""
    return sum(1 for s in STATUSES if mon.status.get(s))


def _evolved_this_turn(mon):
    """Heuristic for 'this Pokémon evolved during this turn'.

    A stage>=1 Pokémon only ever enters play by evolving, inheriting its pre-evolution's `turns`
    counter (which is >=1 to be eligible). `turns` is incremented only at end of turn, AFTER the
    attack. Therefore at attack time `turns == 1` is reachable ONLY by a Pokémon that evolved this
    turn from a 1-turn-old pre-evolution — a sufficient, no-false-positive test that fires in the
    common evolve-as-soon-as-possible line the AI plays. (It under-reports the rare case where the
    pre-evolution sat several turns before evolving; that's the safe direction — never over-applies.)
    """
    return mon.turns == 1


def _discard_from_hand(player, n):
    """`player` discards n cards from hand (their choice; we take the last), routing basic energy
    to disc_energy and Pokémon to the discard pile, mirroring the engine's own hand-dump. Trainer /
    special-energy tokens simply leave hand untracked, as the engine does elsewhere."""
    for _ in range(n):
        if not player.hand:
            break
        tok = player.hand.pop()
        if tok[0] == 'E':
            player.disc_energy[tok[1]] += 1
        elif tok[0] == 'P':
            player.discard.append(tok)


def _shuffle_self_into_deck(ctx):
    """Shuffle the attacker and all attached cards into its owner's deck, then promote a benched
    Pokémon into the vacated Active spot."""
    me = ctx.me
    atk = ctx.attacker
    for t, cnt in list(atk.energy.items()):
        if t not in ('Wild', 'Colorless'):          # only real basic-energy cards return as tokens
            me.deck.extend([('E', t)] * cnt)
    atk.energy.clear()
    atk.special = []
    me.deck.append(('P', atk.card))
    if me.active is atk:
        me.active = None
        me.promote()
    elif atk in me.bench:
        me.bench.remove(atk)
    me.rng.shuffle(me.deck)


# ================================================================ per-each scaling (× / +)

@effect("This attack does 30 more damage for each Energy attached to your opponent's Active Pokémon.")
def _plus30_per_opp_active_energy(ctx):
    return ctx.base + 30 * ctx.defender.total_energy()


@effect("This attack does 10 damage for each damage counter on this Pokémon.")
def _times_per_self_counter(ctx):
    return ctx.base * _dmg_counters(ctx.attacker)


@effect("This attack does 20 damage for each damage counter on your opponent's Active Pokémon.")
def _times_per_opp_counter(ctx):
    return ctx.base * _dmg_counters(ctx.defender)


@effect("This attack does 10 more damage for each damage counter on this Pokémon.")
def _plus10_per_self_counter(ctx):
    return ctx.base + 10 * _dmg_counters(ctx.attacker)


@effect("This attack does 40 damage for each of your Pokémon in play that has the Round attack.")
def _times_per_round_mon(ctx):
    return ctx.base * sum(1 for m in ctx.me.all_mons() if _mon_has_attack(m, 'Round'))


@effect('This attack does 20 damage for each Supporter card that has "Team Rocket" in its name in your discard pile.')
def _times_per_tr_supporter(ctx):
    n = sum(1 for t in ctx.me.discard
            if t[0] == 'T' and t[1].get('trainerType') == 'Supporter'
            and 'Team Rocket' in t[1].get('name', ''))
    return ctx.base * n


@effect("This attack does 40 damage for each Energy attached to all of your opponent's Pokémon.")
def _times_per_all_opp_energy(ctx):
    return ctx.base * sum(m.total_energy() for m in ctx.opp.all_mons())


@effect("This attack does 20 damage for each Energy attached to your opponent's Active Pokémon.")
def _times_per_opp_active_energy(ctx):
    return ctx.base * ctx.defender.total_energy()


@effect("This attack does 20 damage for each of your Pokémon in play.")
def _times_per_my_mons(ctx):
    return ctx.base * len(ctx.me.all_mons())


@effect("This attack does 20 more damage for each {W} Energy attached to this Pokémon.")
def _plus20_per_self_water(ctx):
    return ctx.base + 20 * ctx.attacker.energy.get('Water', 0)


@effect("This attack does 100 damage for each Special Condition affecting your opponent's Active Pokémon.")
def _times_per_special_condition(ctx):
    return ctx.base * _special_condition_count(ctx.defender)


@effect("This attack does 20 more damage for each {L} Energy attached to all of your Iono's Pokémon.")
def _plus20_per_ionos_lightning(ctx):
    n = sum(m.energy.get('Lightning', 0) for m in ctx.me.all_mons() if "Iono's" in m.card.name)
    return ctx.base + 20 * n


@effect("This attack does 30 more damage for each {G} Energy attached to this Pokémon.")
def _plus30_per_self_grass(ctx):
    return ctx.base + 30 * ctx.attacker.energy.get('Grass', 0)


@effect('This attack does 40 damage for each Pokémon in play that has "Koffing" or "Weezing" in its name (both yours and your opponent\'s).')
def _times_per_koffing_weezing(ctx):
    mons = ctx.me.all_mons() + ctx.opp.all_mons()
    return ctx.base * _count_named(mons, ('Koffing', 'Weezing'))


# ================================================================ if-condition bonus (+)

@effect("If your opponent's Active Pokémon already has any damage counters on it, this attack does 60 more damage.")
def _plus60_if_opp_damaged(ctx):
    return ctx.base + (60 if ctx.defender.damage > 0 else 0)


@effect("If your opponent's Active Pokémon is a Pokémon ex, this attack does 70 more damage.")
def _plus70_if_opp_ex(ctx):
    return ctx.base + (70 if ctx.defender.card.is_ex else 0)


@effect("If your opponent's Active Pokémon is a {D} Pokémon, this attack does 100 more damage.")
def _plus100_if_opp_dark(ctx):
    return ctx.base + (100 if ctx.defender.card.ptype == 'Darkness' else 0)


@effect("If your opponent has any {W} Pokémon in play, this attack does 120 more damage.")
def _plus120_if_opp_has_water(ctx):
    return ctx.base + (120 if any(m.card.ptype == 'Water' for m in ctx.opp.all_mons()) else 0)


@effect("If your opponent's Active Pokémon is a Stage 1 Pokémon, this attack does 90 more damage.")
def _plus90_if_opp_stage1(ctx):
    return ctx.base + (90 if ctx.defender.card.stage == 1 else 0)


@effect("If this Pokémon has at least 2 extra Energy attached (in addition to this attack's cost), this attack does 140 more damage.")
def _plus140_if_two_extra_energy(ctx):
    cost_len = len(ctx.attack.get('cost') or '')
    return ctx.base + (140 if ctx.attacker.total_energy() >= cost_len + 2 else 0)


@effect("If this Pokémon evolved from Magneton during this turn, this attack does 120 more damage.")
def _plus120_if_evo_magneton(ctx):
    return ctx.base + (120 if _evolved_this_turn(ctx.attacker) else 0)


@effect("If this Pokémon evolved from Misty's Staryu during this turn, this attack does 80 more damage.")
def _plus80_if_evo_mistys_staryu(ctx):
    return ctx.base + (80 if _evolved_this_turn(ctx.attacker) else 0)


# ---- conditions on cross-turn history. The engine now tracks a player's last-KO turn and each
# ---- Pokémon's last-used attack, so the generic "were any of your Pokémon KO'd last turn" and
# ---- "did this Pokémon use attack X last turn" conditions resolve correctly.

@effect("If any of your Pokémon were Knocked Out by damage from an attack during your opponent's last turn, this attack does 90 more damage.")
def _plus90_if_ko_last_turn(ctx):
    return ctx.base + (90 if ctx.ko_last_turn() else 0)


# The engine records only the TURN a player last had a Pokémon KO'd, not the identity/family of the
# KO'd card, so "an Ethan's Pokémon specifically" is unverifiable. Stay conservative (never fire) so a
# generic KO of a non-Ethan's teammate can't wrongly grant +100.
@effect("If any of your Ethan's Pokémon were Knocked Out by damage from an attack during your opponent's last turn, this attack does 100 more damage.")
def _plus100_if_ethans_ko_last_turn(ctx):
    return ctx.base


@effect("If this Pokémon used Pervasive Gas during your last turn, this attack does 120 more damage.")
def _plus120_if_used_pervasive_gas(ctx):
    return ctx.base + (120 if ctx.used_last_turn('Pervasive Gas') else 0)


# ================================================================ structural side effects

@effect("Your opponent discards a card from their hand. If this Pokémon evolved from Salandit during this turn, your opponent discards 2 more cards.")
def _salazzle_sudden_scorching(ctx):
    n = 3 if _evolved_this_turn(ctx.attacker) else 1
    _discard_from_hand(ctx.opp, n)
    return ctx.base   # printed 0 damage


@effect("During your next turn, attacks used by this Pokémon do 120 more damage to your opponent's Active Pokémon (before applying Weakness and Resistance).")
def _buff_next_turn_120(ctx):
    # Model the one-shot next-turn buff via the engine's mon.ramp "next turn does N more" hook
    # (added to damage BEFORE weakness, matching the parenthetical). Applied to this Pokémon's
    # OTHER attacks — the payoff hit it will use next turn — not the (small) buff attack itself.
    atk = ctx.attacker
    cur = ctx.attack.get('name')
    for a in atk.card.attacks:
        if a.get('name') != cur:
            atk.ramp[a['name']] = atk.ramp.get(a['name'], 0) + 120
    return ctx.base


@effect("You may do 120 more damage. If you do, shuffle this Pokémon and all attached cards into your deck.")
def _poliwrath_jumping_uppercut(ctx):
    # "You may": commit the extra 120 (and the self-shuffle cost) only when it converts a non-KO
    # into a KO and there is a benched Pokémon to promote into the Active spot.
    dfn = ctx.defender
    base = ctx.base
    if dfn is not None and ctx.me.bench:
        mult = 2 if (dfn.card.weakness and dfn.card.weakness == ctx.attacker.card.ptype) else 1
        base_kos = base * mult >= dfn.hp_left
        full_kos = (base + 120) * mult >= dfn.hp_left
        if (not base_kos) and full_kos:
            _shuffle_self_into_deck(ctx)
            return base + 120
    return base
