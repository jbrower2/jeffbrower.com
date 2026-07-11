#!/usr/bin/env python3
"""Batch: ab_activated_0 — once-per-turn / on-play / on-move player-action abilities
(all `activated`, fn(actx)->bool; True == the ability was used this turn).

Per the ab_search_0 / ab_draw_0 convention, the turn-flow gating ("Once during your turn",
"when you play/evolve this Pokémon", "when this Pokémon moves ...") is owned by the CALLER; each
lambda implements only the effect, gated on its own on-card conditions (board position, a named
Pokémon in play, coin flips) and on having the resources it needs.

Deck order: the engine draws from the END of `deck` (deck.pop()), so the TOP of the deck is the
last element and the BOTTOM is index 0. "Discard the bottom card" -> deck.pop(0); "put on top of
your deck" -> deck.append(...).

Engine gaps (implemented as conservative, never-fire-unconditionally no-ops / narrow gates):
  * Festival Lead needs the Festival Grounds Stadium (out of pool) + attacking twice (unmodeled)
    -> permanent no-op (matches the project's "Festival Lead is dead" note).
  * Excited Dash / Excited Heal gate on a "(Grass) Mega Evolution Pokémon ex in play" — a specific
    named-card family that must actually be on the board, so they never fire in a deck lacking one.
  * Lustrous Assist's real trigger is "when Mega Latias ex moves Bench->Active"; the engine DOES
    track that via `Mon.came_from_bench` (set on promote/retreat/switch, reset each of your turns),
    so it fires only when Mega Latias ex is Active AND moved up this turn — not every turn it sits
    Active. Caller-timing dependent (won't fire if the pass runs before the promote step).
  * Beckoning Tail's cost is discarding a "Chill Teaser Toy" (not in the Trainer pool), so the cost
    is unpayable and it no-ops unless such a token is literally in hand.
"""
from ability_effects import ability, ActivatedCtx  # noqa: F401 (ActivatedCtx per batch header convention)
from engine import Mon


# ---------------------------------------------------------------- helpers
def _discard_token(player, tok):
    """Send one deck/hand token to the discard: basic-Energy tokens to the disc_energy pool,
    everything else to the discard pile."""
    if tok[0] == 'E':
        player.disc_energy[tok[1]] += 1
    else:
        player.discard.append(tok)


def _has_mega_ex(player, ptype=None):
    """Is any Mega Evolution Pokémon ex (optionally of a given on-card type) in play?"""
    for m in player.all_mons():
        c = m.card
        if c.name.startswith('Mega ') and c.is_ex and (ptype is None or c.ptype == ptype):
            return True
    return False


def _pick_gust_target(opp):
    """Best Benched target to drag Active: a prize-rich ex first, then the lowest-HP (softest)."""
    return sorted(opp.bench, key=lambda m: (not m.card.is_ex, m.hp_left))[0]


def _switch_in(opp, tgt):
    """Move `tgt` from opp's Bench into the Active Spot, retiring the old Active to the Bench."""
    opp.bench.remove(tgt)
    if opp.active is not None:
        opp.bench.append(opp.active)
    opp.active = tgt
    tgt.came_from_bench = True


# ================================================================ no-op (out-of-pool)
@ability('activated', "- If Festival Grounds is in play, this Pokémon may use an attack it has twice. If the first attack Knocks Out your opponent's Active Pokémon, you may attack again after your opponent chooses a new Active Pokémon.")
def _festival_lead(actx):
    # Goldeen / Seaking (Festival Lead): needs the Festival Grounds Stadium (out of pool) AND the
    # ability to attack twice (unmodeled). Permanent conservative no-op — never fires.
    return False


# ================================================================ on-evolve triggers
@ability('activated', "- When you play this Pokémon from your hand to evolve 1 of your Pokémon during your turn, you may put 2 damage counters on 1 of your opponent's Pokémon.")
def _sneaky_bite(actx):
    # Team Rocket's Golbat (Sneaky Bite): on-evolve, 2 damage counters (20) onto an opponent's
    # Pokémon. Aim at the softest target (may finish a weakened Bench-sitter).
    targets = actx.opp.all_mons()
    if not targets:
        return False
    tgt = min(targets, key=lambda m: m.hp_left)
    actx.put_counters(2, tgt)                       # put_counters(n) = 10*n damage
    return True


@ability('activated', "- When you play this Pokémon from your hand to evolve 1 of your Pokémon during your turn, you may flip 2 coins. For each heads, choose a random card from your opponent's hand. Your opponent reveals those cards and shuffles them into their deck.")
def _wicked_tail(actx):
    # Ambipom (Wicked Tail): on-evolve, flip 2 coins; per heads, shuffle a random card from the
    # opponent's hand back into their deck (hand disruption). No point if their hand is empty.
    opp = actx.opp
    if not opp.hand:
        return False
    heads = sum(1 for _ in range(2) if actx.flip())
    moved = 0
    for _ in range(heads):
        if not opp.hand:
            break
        idx = actx.rng.randint(0, len(opp.hand) - 1)
        opp.deck.append(opp.hand.pop(idx))
        moved += 1
    if moved:                                       # only reveal+shuffle cards that were actually chosen
        actx.rng.shuffle(opp.deck)
    return True


# ================================================================ heal
@ability('activated', "- Once during your turn, you may heal 20 damage from your Active Pokémon.")
def _healing_leaves(actx):
    # Swadloon (Healing Leaves): heal 20 from the Active. No-op if the Active is undamaged.
    me = actx.me
    if not me.active or me.active.damage <= 0:
        return False
    actx.heal(20, me.active)
    return True


@ability('activated', "- Once during your turn, if you have any {G} Mega Evolution Pokémon ex in play, you may use this Ability. Heal 60 damage from 1 of your Pokémon.")
def _excited_heal(actx):
    # Ludicolo (Excited Heal): only with a Grass Mega Evolution ex in play; heal 60 from your
    # most-damaged Pokémon.
    me = actx.me
    if not _has_mega_ex(me, 'Grass'):
        return False
    hurt = [m for m in me.all_mons() if m.damage > 0]
    if not hurt:
        return False
    actx.heal(60, max(hurt, key=lambda m: m.damage))
    return True


# ================================================================ recur / bench a Pokémon
@ability('activated', "- Once during your turn, if this Pokémon is in the Active Spot, you may put a Basic Pokémon with 70 HP or less from your discard pile onto your Bench.")
def _gentle_fin(actx):
    # Alomomola (Gentle Fin): from the Active Spot, recur a small Basic (<=70 HP) from the discard
    # onto your Bench.
    me = actx.me
    if actx.mon is not me.active or len(me.bench) >= 5:
        return False
    for tok in me.discard:
        if tok[0] == 'P' and tok[1].stage == 0 and tok[1].hp <= 70:
            me.discard.remove(tok)
            me.bench.append(Mon(tok[1]))
            return True
    return False


@ability('activated', "- Once during your turn, you may use this Ability. Your opponent reveals their hand, and you put a Basic Pokémon with 70 HP or less that you find there onto your opponent's Bench.")
def _look_for_prey(actx):
    # Mandibuzz (Look for Prey): force a small Basic (<=70 HP) out of the opponent's hand onto their
    # Bench (fills their Bench with a soft future prize / gust target).
    opp = actx.opp
    if len(opp.bench) >= 5:
        return False
    for tok in opp.hand:
        if tok[0] == 'P' and tok[1].stage == 0 and tok[1].hp <= 70:
            opp.hand.remove(tok)
            opp.bench.append(Mon(tok[1]))
            return True
    return False


# ================================================================ hand disruption (coin)
@ability('activated', "- Once during your turn, you may use this Ability. Flip a coin. If heads, discard a random card from your opponent's hand.")
def _sky_hunt(actx):
    # Talonflame (Sky Hunt): flip a coin; heads discards a random card from the opponent's hand.
    opp = actx.opp
    if not opp.hand:
        return False
    if actx.flip():
        idx = actx.rng.randint(0, len(opp.hand) - 1)
        _discard_token(opp, opp.hand.pop(idx))
    return True                                     # the Ability was used regardless of the flip


# ================================================================ opponent gust
@ability('activated', "- Once during your turn, you may flip a coin. If heads, switch in 1 of your opponent's Benched Pokémon to the Active Spot, and the new Active Pokémon is now Confused.")
def _captivating_invitation(actx):
    # Florges (Captivating Invitation): flip a coin; heads gusts up an opponent's Benched Pokémon
    # and Confuses it (exposes a target and disrupts). Confusion respects effect-immunity shields.
    opp = actx.opp
    if not opp.bench:
        return False
    if actx.flip():
        tgt = _pick_gust_target(opp)
        _switch_in(opp, tgt)
        if not tgt.effect_immune():
            tgt.status['Confused'] = True
    return True


@ability('activated', "- You must discard a Chill Teaser Toy card from your hand in order to use this Ability. Once during your turn, you may switch in 1 of your opponent's Benched Pokémon to the Active Spot.")
def _beckoning_tail(actx):
    # Meowstic (Beckoning Tail): cost = discard a Chill Teaser Toy (not in the Trainer pool, so this
    # is normally unpayable -> no-op). With the toy in hand and an opponent Bench, gust one up.
    me, opp = actx.me, actx.opp
    toy = next((t for t in me.hand if t[0] == 'T' and t[1].get('name') == 'Chill Teaser Toy'), None)
    if toy is None or not opp.bench:
        return False
    me.hand.remove(toy)
    me.discard.append(toy)
    _switch_in(opp, _pick_gust_target(opp))
    return True


# ================================================================ self-switch (own board)
@ability('activated', "- Once during your turn, if this Pokémon is on your Bench, and if you have any Mega Evolution Pokémon ex in play, you may use this Ability. Switch this Pokémon with your Active Pokémon.")
def _excited_dash(actx):
    # Linoone (Excited Dash): from the Bench, with any Mega Evolution ex in play, swap this Pokémon
    # into the Active Spot (free pivot to promote a chosen attacker).
    me = actx.me
    if actx.mon not in me.bench or not _has_mega_ex(me):
        return False
    old = me.active
    me.bench.remove(actx.mon)
    if old is not None:
        me.bench.append(old)
    me.active = actx.mon
    actx.mon.came_from_bench = True
    return True


@ability('activated', "- Once during your turn, if this Pokémon is on your Bench, you may discard the bottom card of your deck. If you do, discard all cards from this Pokémon and put this Pokémon on top of your deck.")
def _flustered_leap(actx):
    # Misty's Psyduck (Flustered Leap): on the Bench, mill the bottom card of your deck, discard
    # everything attached to this Pokémon, then put this Pokémon back on TOP of the deck (recycles
    # a Bench-sitter for a fresh redraw). Needs a card to mill.
    me = actx.me
    if actx.mon not in me.bench or not me.deck:
        return False
    _discard_token(me, me.deck.pop(0))              # discard the bottom card of the deck
    for typ, cnt in list(actx.mon.energy.items()):  # discard all attached (basic) energy
        if typ not in ('Colorless', 'Wild') and cnt > 0:
            me.disc_energy[typ] += cnt
    actx.mon.energy.clear()
    actx.mon.special.clear()
    me.bench.remove(actx.mon)
    me.deck.append(('P', actx.mon.card))            # put this Pokémon on top of the deck
    return True


@ability('activated', "- Once during your turn, if this Pokémon is in the Active Spot, you may shuffle it and all attached cards into your deck.")
def _teleporter(actx):
    # Abra (Teleporter): from the Active Spot, shuffle this Pokémon + its attached basic energy back
    # into the deck, then promote a Benched Pokémon. Guarded on having a Bench (never self-loses).
    me = actx.me
    if actx.mon is not me.active or not me.bench:
        return False
    me.deck.append(('P', actx.mon.card))
    for typ, cnt in list(actx.mon.energy.items()):
        if typ not in ('Colorless', 'Wild'):        # basic energy returns to the deck as tokens
            me.deck.extend([('E', typ)] * cnt)
    actx.rng.shuffle(me.deck)
    me.active = None
    me.promote()                                    # promote the readiest Benched attacker
    return True


# ================================================================ named-ex energy move
@ability('activated', "- Once during your turn, when your Mega Latias ex moves from your Bench to the Active Spot, you may use this Ability. Move any amount of Energy from your Benched Pokémon to your Active Pokémon.")
def _lustrous_assist(actx):
    # Latios (Lustrous Assist): the trigger is "when your Mega Latias ex moves Bench->Active".
    # The engine already tracks that exact event with `Mon.came_from_bench` (reset at the start of
    # each of your turns, set True whenever a mon is promoted/retreated/switched Bench->Active), so
    # gate on Mega Latias ex being Active AND having moved up THIS turn — this fires once on the
    # promotion turn rather than every turn the ex happens to sit Active. Then rush all energy from
    # your Bench onto it. (If the caller runs this pass before the promote/retreat step, the flag is
    # not yet set and it simply doesn't fire — the conservative direction.)
    me = actx.me
    if (me.active is None or me.active.card.name != 'Mega Latias ex'
            or not me.active.came_from_bench):
        return False
    moved = 0
    for b in me.bench:
        for typ, cnt in list(b.energy.items()):
            if cnt > 0:
                me.active.energy[typ] += cnt
                moved += cnt
        b.energy.clear()
        if b.special:                               # carry the special-energy riders too
            me.active.special.extend(b.special)
            b.special.clear()
    return moved > 0
