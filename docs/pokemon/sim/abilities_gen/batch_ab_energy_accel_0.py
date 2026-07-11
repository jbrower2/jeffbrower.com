#!/usr/bin/env python3
"""Generated ability batch: ab_energy_accel_0 (energy-acceleration & related engines).

Each ability is registered under its EXACT card text with the engine KIND whose hook matches how
the ability actually works. Most here are `activated` (once-per-turn player actions); a couple are
faithful conservative no-ops where the piece they need is outside the modeled pool.
"""
from ability_effects import ability, ActivatedCtx

_L2T = {'G': 'Grass', 'R': 'Fire', 'W': 'Water', 'L': 'Lightning', 'P': 'Psychic',
        'F': 'Fighting', 'D': 'Darkness', 'M': 'Metal', 'C': 'Colorless'}
_BASIC_TYPES = {'Grass', 'Fire', 'Water', 'Lightning', 'Psychic', 'Fighting', 'Darkness', 'Metal'}


# ---------------- shared target helpers ----------------
def _ceiling(mon):
    return max((a['dmg'] for a in mon.card.attacks), default=0)


def _cost_letters(mon):
    """Typed energy letters of `mon`'s cheapest attack cost (to prefer useful energy)."""
    atks = [a for a in mon.card.attacks if a.get('cost')]
    if not atks:
        return []
    cheapest = min(atks, key=lambda a: len(a['cost']))
    return [c for c in cheapest['cost'] if c in 'GRWLPFDM']


def _primary(actx):
    me = actx.me
    return actx.game.primary(me) or me.active or (me.bench[0] if me.bench else None)


def _pref_target(actx, ptype):
    """A Pokémon to load, preferring on-type, then the highest-ceiling / most-built attacker."""
    mons = actx.me.all_mons()
    if not mons:
        return None
    return max(mons, key=lambda m: (m.card.ptype == ptype, _ceiling(m), m.total_energy()))


def _typed_target(actx, ptype, exclude=None):
    mons = [m for m in actx.me.all_mons() if m.card.ptype == ptype and m is not exclude]
    if not mons:
        return None
    return max(mons, key=lambda m: (_ceiling(m), m.total_energy()))


def _bench_target(actx, prefer=None):
    bench = actx.me.bench
    if not bench:
        return None
    return max(bench, key=lambda m: (prefer is not None and m.card.ptype == prefer,
                                     _ceiling(m), m.total_energy()))


def _look_top4_attach(actx, is_wanted, to_bottom):
    """Look at the top 4 cards; attach every basic-energy token matching `is_wanted` to your
    Pokémon (each to a type-preferred target); return the rest to the bottom (or shuffle back)."""
    me = actx.me
    k = min(4, len(me.deck))
    if k == 0:
        return False
    top = me.deck[-k:]          # deck's TOP is the tail (draw pops from the end)
    del me.deck[-k:]
    rest, attached = [], 0
    for tok in top:
        if is_wanted(tok):
            tgt = _pref_target(actx, tok[1])
            if tgt is not None:
                tgt.energy[tok[1]] += 1
                attached += 1
                continue
        rest.append(tok)
    if to_bottom:
        me.deck[0:0] = rest     # bottom of deck = front of the list (drawn last)
    else:
        me.deck.extend(rest)
        actx.rng.shuffle(me.deck)
    return attached > 0


# ================================================================ abilities

@ability('activated', "- Once during your turn, you may attach a Basic {L} Energy card from your discard pile to 1 of your Benched Pokémon.")
def _dynamotor(actx):                                   # Eelektrik
    if actx.me.disc_energy.get('Lightning', 0) <= 0:
        return False
    tgt = _bench_target(actx, prefer='Lightning')
    if tgt is None:
        return False
    actx.attach_energy('Lightning', tgt, source='discard')
    return True


@ability('activated', "- Once during your turn, you may attach up to 3 Basic Energy cards from your discard pile to your {L} Pokémon in any way you like. If you use this Ability, this Pokémon is Knocked Out.")
def _overvolt_discharge(actx):                          # Magneton
    me = actx.me
    tgt = _typed_target(actx, 'Lightning', exclude=actx.mon)   # load a DIFFERENT {L} attacker (holder self-KOs)
    if tgt is None or sum(me.disc_energy.values()) <= 0:
        return False
    moved = 0
    order = _cost_letters(tgt) + list('GRWLPFDM')       # target's needs first, then fill from any basic
    for L in order:
        t = _L2T[L]
        while moved < 3 and me.disc_energy.get(t, 0) > 0:
            me.disc_energy[t] -= 1
            tgt.energy[t] += 1
            moved += 1
        if moved >= 3:
            break
    if moved <= 0:
        return False
    actx.mon.damage = actx.mon.max_hp                   # "this Pokémon is Knocked Out"
    return True


@ability('activated', "- Once during your turn, if this Pokémon has any Energy attached, you may use this Ability. Search your deck for an Evolution Pokémon, reveal it, and put it into your hand. Then, shuffle your deck.")
def _evolutionary_guidance(actx):                       # Dragonair
    if actx.mon.total_energy() <= 0:
        return False
    got = actx.game._search_deck_to_hand(
        actx.me, lambda tok: tok[0] == 'P' and tok[1].stage >= 1, 1)
    return got > 0


@ability('activated', "- Once during your turn, if this Pokémon has any {G} Energy attached, you may use this Ability. Heal 30 damage from 1 of your Pokémon.")
def _fermented_juice(actx):                             # Shuckle
    if actx.mon.energy.get('Grass', 0) <= 0:
        return False
    tgt = max(actx.me.all_mons(), key=lambda m: m.damage, default=None)
    if tgt is None or tgt.damage <= 0:
        return False
    actx.heal(30, tgt)
    return True


@ability('activated', "- Once during your turn, you may use this Ability. Flip a coin. If heads, put an Energy attached to your opponent's Active Pokémon into their hand.")
def _boisterous_wind(actx):                             # Dustox
    if not actx.flip():
        return False
    oa = actx.opp.active
    if oa is None or oa.total_energy() <= 0:
        return False
    basics = {t: c for t, c in oa.energy.items() if t in _BASIC_TYPES and c > 0}
    pool = basics or {t: c for t, c in oa.energy.items() if c > 0}
    if not pool:
        return False
    t = max(pool, key=pool.get)                         # bounce the most-plentiful attached energy
    oa.energy[t] -= 1
    if oa.energy[t] <= 0:
        del oa.energy[t]
    if t in _BASIC_TYPES:                               # a real basic returns as a hand token
        actx.opp.hand.append(('E', t))
    return True


@ability('activated', "- Once during your turn, when you play this Pokémon from your hand to evolve 1 of your Pokémon, you may use this Ability. Look at the top 4 cards of your deck and attach any number of Basic Energy cards you find there to your Pokémon in any way you like. Shuffle the other cards back into your deck.")
def _energized_steps(actx):                             # Grumpig
    # On-evolve trigger; the engine tracks no per-turn "evolved this turn" flag, so this is modeled as a
    # once-per-turn top-4 basic-energy attach (matches the sim's treatment of Grumpig as an accel engine).
    return _look_top4_attach(actx, lambda tok: tok[0] == 'E' and tok[1] in _BASIC_TYPES, to_bottom=False)


@ability('activated', "- Once during your turn, you may look at the top 4 cards of your deck and attach any number of Basic {M} Energy cards you find there to your Pokémon in any way you like. Shuffle the other cards and put them on the bottom of your deck.")
def _metal_maker(actx):                                 # Metang
    return _look_top4_attach(actx, lambda tok: tok[0] == 'E' and tok[1] == 'Metal', to_bottom=True)


@ability('activated', "- Once during your turn, you may use this Ability. Attach a Basic {F} Energy card from your hand to 1 of your {F} Pokémon.")
def _stone_arms(actx):                                  # Barbaracle
    me = actx.me
    tok = next((t for t in me.hand if t[0] == 'E' and t[1] == 'Fighting'), None)
    if tok is None:
        return False
    tgt = _typed_target(actx, 'Fighting')
    if tgt is None:
        return False
    me.hand.remove(tok)
    tgt.energy['Fighting'] += 1
    return True


@ability('activated', "- Once during your turn, if you played Canari from your hand this turn, you may use this Ability. Search your deck for up to 2 Basic {L} Energy cards and attach them to this Pokémon. Then, shuffle your deck.")
def _frilled_generator(actx):                           # Heliolisk
    # Gated on "if you played Canari from your hand this turn". The engine now tracks the Trainers a
    # player played this turn (player.played) and Canari is a legal reg-I Supporter in the pool, so the
    # gate IS satisfiable: when Canari was played, pull up to 2 Basic {L} Energy from the deck onto this
    # Pokémon (Heliolisk), then shuffle. No Canari this turn, or no {L} in the deck -> no-op.
    me = actx.me
    if 'Canari' not in me.played:
        return False
    kept, pulled = [], 0
    for tok in me.deck:
        if pulled < 2 and tok[0] == 'E' and tok[1] == 'Lightning':
            actx.mon.energy['Lightning'] += 1
            pulled += 1
        else:
            kept.append(tok)
    if pulled <= 0:
        return False
    me.deck[:] = kept
    actx.rng.shuffle(me.deck)
    return True


@ability('activated', "- Once during your turn, if this Pokémon is on your Bench, you may use this Ability. Attach an Energy card from your hand to your Active Larry's Pokémon.")
def _lethargic_charge(actx):                            # Larry's Komala
    me = actx.me
    if actx.mon not in me.bench:                        # holder must be Benched
        return False
    act = me.active
    if act is None or not act.card.name.startswith("Larry's"):
        return False
    tok = next((t for t in me.hand if t[0] == 'E'), None)   # a basic Energy card from hand
    if tok is None:
        return False
    me.hand.remove(tok)
    act.energy[tok[1]] += 1
    return True


@ability('attack_buff', "- As long as this Pokémon has a Future Booster Energy Capsule attached, it is {F} and {M} type.")
def _dual_core(atk_mon, dfn_mon, attack, game):         # Iron Treads
    # Dual Core makes the holder {F}(Fighting) and {M}(Metal) type while a Future Booster Energy Capsule
    # Tool is attached. The engine now tracks attached Tools (mon.tools), so gate on the Capsule. The one
    # in-sim consequence of the extra typing is Weakness when the holder ATTACKS: the engine doubles only
    # for the printed ptype, so a defender Weak to an *added* type the printed type doesn't already cover
    # should also take ×2. Simulate that ×2 by adding the attack's base damage (mirrors Double Type /
    # Carbink in ab_other_1). No Capsule, no defender, or no added-type Weakness -> 0 bonus.
    if dfn_mon is None or 'Future Booster Energy Capsule' not in atk_mon.tools:
        return 0
    extra = {'Fighting', 'Metal'} - {atk_mon.card.ptype}
    if dfn_mon.card.weakness in extra:
        return attack.get('dmg', 0)
    return 0


@ability('on_damaged', "- When 1 of your {W} Pokémon is Knocked Out by damage from an attack from your opponent's Pokémon, you may put all Basic {W} Energy attached to that Pokémon into your hand instead of the discard pile.")
def _divers_catch(atk_mon, dfn_mon, dfn_owner, game):   # Huntail
    # Framework limit: the on_damaged hook only sees the KO'd Pokémon's OWN abilities, so a benched
    # Huntail can't react to a teammate's KO — this fires only when Huntail itself (a {W} Pokémon) is
    # the one KO'd, recovering its Basic {W} energy to hand instead of the discard pile.
    if dfn_mon.card.ptype != 'Water':
        return
    if dfn_mon.damage < dfn_mon.max_hp:                 # only on a lethal (KO) hit
        return
    n = dfn_mon.energy.get('Water', 0)
    if n <= 0:
        return
    dfn_mon.energy.pop('Water', None)
    for _ in range(n):
        dfn_owner.hand.append(('E', 'Water'))
