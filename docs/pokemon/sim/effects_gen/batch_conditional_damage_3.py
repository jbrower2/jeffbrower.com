#!/usr/bin/env python3
"""Batch: conditional_damage_3 — conditional / variable (×, +) damage attacks.

Damage-token conventions (matching the proof batch in attack_effects.py):
  - "N× ... does N damage for each X"       -> pure variable: N * count(X)  (base is the per-unit amount)
  - "N+ ... does M more damage for each X"   -> base + M * count(X)
  - "N+ If <cond>, ... does M more damage"   -> base + (M if cond else 0)
  - "[N] ..."                                -> fixed base N, plus a (sometimes unmodeled) rider

Every effect returns the int damage to the opponent's ACTIVE; the engine applies Weakness after.

Engine-gap notes — some conditions the engine now tracks, others it still cannot; for the untracked
ones the conservative, faithful choice is to return the printed base and NOT apply an unverifiable
bonus (the exact OPPOSITE of the prior bug that applied a conditional bonus unconditionally):
  * Stadiums ARE now tracked (game.stadium / ctx.stadium()): "+ if Stadium" bonuses fire, and
    Stadium-discard riders remove the Stadium via ctx.discard_stadium().
  * An attacker's OWN "used <Attack> during your last turn" (ctx.used_last_turn) and "evolved during
    this turn" (ctx.evolved_this_turn) ARE now tracked and applied.
  * Still untracked: whether a DIFFERENT (e.g. Ancient) Pokémon of yours attacked last turn — only the
    attacker's own last attack is exposed — so that compound bonus stays at base.
  * The extra-prize-on-future-KO rider has no engine hook (take_prize is fixed 2-for-ex / 1 otherwise).
  * "isn't affected by Weakness" can't be signalled through the int return (the engine applies
    Weakness after) — an unavoidable single-card gap, per the batch_coinflip_effect_0 precedent.
"""
from attack_effects import effect, EffectCtx, STATUSES


# ---------------------------------------------------------------- helpers
_SWORD_LINE = ('Honedge', 'Doublade', 'Aegislash')


def _is_ex_or_v(card):
    """Pokémon ex OR Pokémon V (incl. VMAX/VSTAR). No V-series exist in the reg H/I/J pool, so this
    reduces to `is_ex`; the name check keeps it correct if any V were ever added."""
    n = card.name
    return card.is_ex or n.endswith(' V') or n.endswith(' VMAX') or n.endswith(' VSTAR')


def _is_future(card):
    """Future-subtype (paradox-future) Pokémon. The card model doesn't carry the subtype, but every
    Future Pokémon in the pool is an 'Iron ___' — the 'Iron ' prefix is exclusive to the Future
    paradox family in the TCG (zero false positives). Conservatively excludes the box legendaries
    (Miraidon) whose Future tagging is version-dependent, mirroring bench_spread_2's ANCIENT list."""
    return card.name.startswith('Iron ')


def _count_opp_special_energy(ctx):
    """Total Special Energy CARDS attached across all of the opponent's Pokémon. Mon.special holds one
    name per attached Special Energy card, so its length is the card count (not the pip count)."""
    return sum(len(m.special) for m in ctx.opp.all_mons())


# ================================================================ variable "×": N per count
@effect("Reveal any number of Honedge, Doublade, and Aegislash from your hand, and this attack does 60 damage for each card you revealed in this way.")
def _reveal_sword_line(ctx):
    # 60 per Honedge/Doublade/Aegislash in hand (reveal "any number" -> reveal all for max damage).
    n = sum(1 for t in ctx.me.hand if t[0] == 'P' and t[1].name in _SWORD_LINE)
    return ctx.base * n


@effect("This attack does 20 damage for each damage counter on this Pokémon.")
def _20_per_self_counter(ctx):
    # 20 per damage counter on the attacker (1 counter = 10 damage).
    return ctx.base * (ctx.attacker.damage // 10)


@effect("This attack does 40 damage for each Special Energy attached to all of your opponent's Pokémon.")
def _40_per_opp_special(ctx):
    return ctx.base * _count_opp_special_energy(ctx)


@effect("This attack does 20 damage for each Pokémon in your discard pile that has the United Wings attack.")
def _20_per_united_wings_in_discard(ctx):
    n = sum(1 for t in ctx.me.discard
            if t[0] == 'P' and any(a['name'] == 'United Wings' for a in t[1].attacks))
    return ctx.base * n


@effect("This attack does 20 damage for each of your Basic Pokémon in play.")
def _20_per_my_basic(ctx):
    # "in play" = your Active + Bench; the attacker itself counts if it is a Basic.
    n = sum(1 for m in ctx.me.all_mons() if m.card.stage == 0)
    return ctx.base * n


@effect("This attack does 50 damage for each {C} in your opponent's Active Pokémon's Retreat Cost.")
def _50_per_opp_retreat_c(ctx):
    # {C} count in the defender's CURRENT Retreat Cost; eff_retreat() honors the modeled Magnetic
    # Metal Energy "no Retreat Cost" rider.
    return ctx.base * ctx.defender.eff_retreat()


# ================================================================ bonus "+": base + M per count
@effect("This attack does 40 more damage for each Energy attached to your opponent's Active Pokémon.")
def _plus_40_per_opp_active_energy(ctx):
    return ctx.base + 40 * ctx.defender.total_energy()


@effect("This attack does 80 more damage for each {R} Energy attached to this Pokémon.")
def _plus_80_per_self_fire(ctx):
    # {R} = Fire. Counts basic Fire pips attached to the attacker (consistent with effects.eval_count).
    return ctx.base + 80 * ctx.attacker.energy.get('Fire', 0)


@effect("This attack does 40 more damage for each {D} Energy attached to this Pokémon.")
def _plus_40_per_self_dark(ctx):
    # {D} = Darkness.
    return ctx.base + 40 * ctx.attacker.energy.get('Darkness', 0)


@effect("This attack does 50 more damage for each damage counter on your opponent's Active Pokémon.")
def _plus_50_per_opp_counter(ctx):
    return ctx.base + 50 * (ctx.defender.damage // 10)


# ================================================================ bonus "+": base + M if <condition>
@effect("If your opponent's Active Pokémon is a Pokémon ex, this attack does 50 more damage.")
def _plus_50_if_opp_ex(ctx):
    return ctx.base + (50 if ctx.defender.card.is_ex else 0)


@effect("If your opponent's Active Pokémon is a Pokémon ex or Pokémon V, this attack does 80 more damage.")
def _plus_80_if_opp_ex_or_v(ctx):
    return ctx.base + (80 if _is_ex_or_v(ctx.defender.card) else 0)


@effect("If you have more Prize cards remaining than your opponent, this attack does 90 more damage.")
def _plus_90_if_more_prizes(ctx):
    return ctx.base + (90 if ctx.my_prizes() > ctx.opp_prizes() else 0)


@effect("If your opponent has 2 or fewer Prize cards remaining, this attack does 100 more damage.")
def _plus_100_if_opp_le2_prizes(ctx):
    return ctx.base + (100 if ctx.opp_prizes() <= 2 else 0)


@effect("If your opponent has any Future Pokémon in play, this attack does 120 more damage.")
def _plus_120_if_opp_future(ctx):
    return ctx.base + (120 if any(_is_future(m.card) for m in ctx.opp.all_mons()) else 0)


@effect("If you have 3 or more Energy in play, this attack does 70 more damage. This attack's damage isn't affected by Weakness.")
def _plus_70_if_3_energy(ctx):
    # +70 if you have >=3 Energy (pips) across all your Pokémon in play. The "isn't affected by
    # Weakness" clause can't be signalled through the int return (engine applies Weakness after).
    total = sum(m.total_energy() for m in ctx.me.all_mons())
    return ctx.base + (70 if total >= 3 else 0)


# ================================================================ fixed [N] + (unmodeled) rider
@effect("During your next turn, if the Defending Pokémon is Knocked Out, take 2 more Prize cards.")
def _fixed_take_2_more_prizes(ctx):
    # Flat [30]. The "+2 Prizes if this Defending Pokémon is KO'd next turn" rider has no engine hook,
    # so only the damage is applied.
    return ctx.base


@effect("If this Pokémon has any damage counters on it, this attack can be used for {F}.")
def _fixed_cost_reduction_if_damaged(ctx):
    # Flat [130]. The "can be used for {F} if damaged" clause is a COST reduction the engine checks
    # before resolution (via the attack's printed cost), not a damage effect — damage is unconditional.
    return ctx.base


# ================================================================ Stadium-gated (Stadiums unmodeled)
@effect("If you have a Stadium in play, this attack does 50 more damage.")
def _plus_50_if_my_stadium(ctx):
    # +50 if a Stadium is in play. ctx.stadium() exposes presence, not owner (the estimation game
    # carries no player list), so this reads the card's "you have a Stadium" as "a Stadium is in play".
    return ctx.base + (50 if ctx.stadium() else 0)


@effect("If a Stadium is in play, this attack does 60 more damage. Then, discard that Stadium.")
def _plus_60_if_any_stadium_discard(ctx):
    if ctx.stadium():
        ctx.discard_stadium()            # +60, then discard the Stadium in play
        return ctx.base + 60
    return ctx.base


@effect("If your opponent has a Stadium in play, discard it. If you do, your opponent can't play any Stadium cards from their hand during their next turn.")
def _fixed_discard_opp_stadium(ctx):
    # Flat [40]; discard the Stadium in play. ctx.stadium() exposes presence, not owner, so it discards
    # whatever Stadium is in play; the next-turn Stadium-play lock has no engine hook (stays unmodeled).
    if ctx.stadium():
        ctx.discard_stadium()
    return ctx.base


# ================================================================ setup-gated (timing untracked -> base)
@effect("If this Pokémon used Form Ranks during your last turn, this attack does 90 more damage.")
def _plus_90_if_form_ranks_last_turn(ctx):
    # +90 if THIS Pokémon used Form Ranks on your previous turn (engine now records last_atk /
    # last_atk_turn per Pokémon, surfaced by ctx.used_last_turn(name)).
    return ctx.base + (90 if ctx.used_last_turn('Form Ranks') else 0)


@effect("If this Pokémon evolved from Gimmighoul during this turn, this attack does 90 more damage.")
def _plus_90_if_evolved_this_turn(ctx):
    # +90 if this Pokémon (Gholdengo — which only evolves from Gimmighoul) evolved this turn (engine
    # now records evolved_turn per Pokémon, surfaced by ctx.evolved_this_turn()).
    return ctx.base + (90 if ctx.evolved_this_turn() else 0)


@effect("If 1 of your other Ancient Pokémon used an attack during your last turn, this attack does 150 more damage.")
def _plus_150_if_ancient_attacked_last_turn(ctx):
    # ctx.used_last_turn exposes only the ATTACKER's own last attack, not whether a DIFFERENT (Ancient)
    # Pokémon of yours attacked last turn — and Ancient is a subtype the card model doesn't carry — so
    # this compound condition stays conservative (no bonus applied).
    return ctx.base
