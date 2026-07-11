#!/usr/bin/env python3
"""Batch ab_other_1 — four abilities the batch generator flagged "other" (no clean hook).

Each text was read against the hook contracts in ability_effects.py and mapped to the closest
faithful kind. Two are genuinely engine-usable; two are cost/card-play rules the engine has no
mechanic for and so are conservative, well-guarded no-ops (never fire spuriously).

  1) Stimulated Evolution (Shelmet)  -> activated  (FAITHFUL)
        "If you have Karrablast in play, this Pokémon can evolve during your first turn or the
        turn you play it." Evolution timing has no dedicated hook, but the effect *is* an action
        taken on your turn: evolve early. The engine's normal evolution path (Game.evolve_all)
        only evolves a Pokémon that has been in play a turn (turns>=1); this ability additionally
        allows evolving on the turn the Pokémon entered play (turns==0) IF Karrablast is in play
        and the evolution card is in hand. Modeled as an `activated` that performs exactly that
        early evolution, heavily guarded so it never fires outside its printed condition.

  2) Plasma Bane (Kyurem)  -> attack_buff returning 0  (NO-OP, cost modifier)
        "If your opponent has ... 'Colress' ... this Pokémon can use the Trifrost attack for {C}."
        A conditional attack-COST reduction. No kind models attack cost, so this is a 0-damage
        no-op in the "your attacks" family; it never grants a damage bonus.

  3) ACE Nullifier (Genesect)  -> lock returning False  (NO-OP, out-of-pool)
        "If this Pokémon has a Pokémon Tool attached, your opponent can't play any ACE SPEC cards
        from their hand." Locks opponent CARD PLAY (ACE SPEC), not abilities, and gates on an
        attached Tool. ACE SPEC cards are out of pool and attached Tools aren't modeled, so there
        is nothing to lock — the lock query returns False (never disables any opponent ability).

  4) Double Type (Carbink)  -> attack_buff  (FAITHFUL, partial)
        "As long as this Pokémon is in play, it is {F} and {P} type." No multi-type hook exists.
        The one mechanically-relevant consequence in-sim is Weakness when the holder ATTACKS: the
        engine only doubles for the card's printed `ptype`, so a defender Weak to the *added* type
        is otherwise missed. Simulated by adding the attack's base damage (the codebase's
        scaling-floor convention for a ×2) when the defender is Weak to a type this ability grants
        that the printed type doesn't already cover.
"""
from ability_effects import ability, ActivatedCtx  # noqa: F401 (ActivatedCtx: prescribed header)


# 1) Stimulated Evolution (Shelmet) — evolve on the turn it comes into play, if Karrablast is in play
@ability('activated',
         "- If you have Karrablast in play, this Pokémon can evolve during your first turn or the turn you play it.")
def _stimulated_evolution(actx):
    mon = actx.mon
    # turns>=1 is already covered by the engine's normal evolution path — this ability only adds the
    # "turn you play it / your first turn" case (the holder just entered play, turns==0).
    if mon.turns >= 1:
        return False
    # Requires a Karrablast anywhere in your play area (Active or Bench).
    if not any(m.card.name == 'Karrablast' for m in actx.me.all_mons()):
        return False
    # ... and the direct evolution of this Pokémon in hand.
    tok = next((t for t in actx.me.hand
                if t[0] == 'P' and t[1].evolves_from == mon.card.name
                and t[1].stage == mon.card.stage + 1), None)
    if tok is None:
        return False
    actx.me.hand.remove(tok)
    mon.card = tok[1]          # evolve in place: same Mon keeps its damage/energy/status/turns
    return True


# 2) Plasma Bane (Kyurem) — conditional attack-COST reduction; no cost hook -> 0-damage no-op
@ability('attack_buff',
         '- If your opponent has any cards in their discard pile that have "Colress" in the name, '
         'this Pokémon can use the Trifrost attack for {C}.')
def _plasma_bane(atk_mon, dfn_mon, attack, game):
    # Lets Trifrost be paid with {C} instead of its printed {W}{W}{M}{M}{C} when the opponent's
    # discard holds a "Colress" card. That is a cost change, which no hook models — and it is never
    # a damage change — so this contributes 0 bonus damage regardless of the discard.
    return 0


# 3) ACE Nullifier (Genesect) — locks opponent ACE SPEC card play (out-of-pool) -> never locks abilities
@ability('lock',
         "- If this Pokémon has a Pokémon Tool attached, your opponent can't play any ACE SPEC cards from their hand.")
def _ace_nullifier(mon, owner, opp, game):
    # Would stop the opponent from playing ACE SPEC cards while this Pokémon holds a Tool. ACE SPEC
    # cards are out of the modeled pool and attached Tools aren't tracked, so there is nothing to
    # disrupt. Critically, this is NOT an ability-lock, so it must never disable opponent abilities.
    return False


# 4) Double Type (Carbink) — counts as {F} AND {P}; model the Weakness-on-attack consequence
@ability('attack_buff', "- As long as this Pokémon is in play, it is {F} and {P} type.")
def _double_type(atk_mon, dfn_mon, attack, game):
    if dfn_mon is None:
        return 0
    # The engine applies Weakness only for the card's printed `ptype`. This ability additionally
    # makes the holder Fighting AND Psychic, so a defender Weak to the *added* type (the one the
    # printed type doesn't already cover) should also take double. Approximate that ×2 by adding the
    # attack's base damage (exact for fixed-damage attacks; a floor for scaling ones). A defender
    # Weak to the printed type is already doubled by the engine, so add nothing there (no double-count).
    extra = {'Fighting', 'Psychic'} - {atk_mon.card.ptype}
    if dfn_mon.card.weakness in extra:
        return attack.get('dmg', 0)
    return 0
