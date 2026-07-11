#!/usr/bin/env python3
"""Effect batch: discard_energy_0.

Energy-manipulation attacks: discard energy from the attacker (all / typed / a fixed count),
strip energy from the opponent's Active (any / typed / Special Energy / only-if-ex), attach basic
Energy from the discard pile onto benched (or typed) Pokémon, and ×-scaling attacks that count
discarded / discard-pile energy. A few combine an energy discard with a snipe or a next-turn
damage-reduction buff.

Return-value contract (matches attack_effects.resolve + the sibling batches):
  * The int returned is damage to the opponent's ACTIVE only; the engine applies Weakness after.
  * Damage dealt to BENCHED Pokémon bypasses Weakness/Resistance, so it is written straight onto the
    target's `.damage` and is NOT part of the return value.
  * "does N to 1/3 of your opponent's Pokémon" (no printed base) returns only the Active's share
    (0 if a Benched target was chosen); Bench shares go to `.damage`.

Energy bookkeeping mirrors the engine: basic energy discarded from a Pokémon is routed to its
owner's `disc_energy` Counter (so it can be re-accelerated); the pseudo-types 'Wild'/'Colorless'
(from Special Energy) are NOT basic energy and are dropped without crediting `disc_energy`. When a
Special Energy is discarded, its provided pips are subtracted and its name removed from `.special`
(so riders like Growing-Grass HP / Magnetic-Metal no-retreat go away).
"""
from attack_effects import effect, EffectCtx, STATUSES
import special_energy as SE

# energy letter -> type name (local copy so this batch is import-light / self-contained)
_L2T = {'G': 'Grass', 'R': 'Fire', 'W': 'Water', 'L': 'Lightning', 'P': 'Psychic',
        'F': 'Fighting', 'D': 'Darkness', 'M': 'Metal', 'C': 'Colorless'}


# ---------------------------------------------------------------- helpers: attacker-side discard
def _discard_all_self(ctx):
    """Discard ALL energy (basic + Special) from the attacker. Basic energy -> owner's disc_energy;
    Special Energy leaves play (pips subtracted, names cleared so riders end)."""
    at = ctx.attacker
    me = ctx.me
    for name in list(at.special):                 # peel Special Energy off first (not basic energy)
        for typ, c in SE.provides(name, at.card).items():
            at.energy[typ] -= c
            if at.energy.get(typ, 0) <= 0:
                at.energy.pop(typ, None)
    at.special = []
    for t in list(at.energy):                     # remaining pips are true basic energy
        if t not in ('Wild', 'Colorless'):
            me.disc_energy[t] += at.energy[t]
    at.energy.clear()


def _discard_typed_self(ctx, typ, n):
    """Discard up to n basic energy of `typ` from the attacker, routing to disc_energy. Returns count."""
    at = ctx.attacker
    me = ctx.me
    removed = 0
    while at.energy.get(typ, 0) > 0 and removed < n:
        at.energy[typ] -= 1
        if at.energy[typ] <= 0:
            at.energy.pop(typ, None)
        me.disc_energy[typ] += 1
        removed += 1
    return removed


def _discard_typed_defender(ctx, typ, n=1):
    """Discard up to n basic energy of `typ` from the opponent's Active, routing to opp.disc_energy."""
    df = ctx.defender
    opp = ctx.opp
    removed = 0
    while df is not None and df.energy.get(typ, 0) > 0 and removed < n:
        df.energy[typ] -= 1
        if df.energy[typ] <= 0:
            df.energy.pop(typ, None)
        opp.disc_energy[typ] += 1
        removed += 1
    return removed


def _discard_energy_from_hand(ctx, max_n):
    """Discard up to max_n Energy cards from the attacker's owner's hand (basic 'E' first, then
    Special 'S'); basic energy is credited to disc_energy. Returns the number discarded."""
    me = ctx.me
    etoks = [t for t in me.hand if t[0] == 'E']
    stoks = [t for t in me.hand if t[0] == 'S']
    removed = 0
    for tok in etoks + stoks:
        if removed >= max_n:
            break
        me.hand.remove(tok)
        if tok[0] == 'E':
            me.disc_energy[tok[1]] += 1
        removed += 1
    return removed


# ---------------------------------------------------------------- helpers: Special Energy removal
def _remove_special(mon, name):
    """Detach one Special Energy `name` from `mon`: drop the name and subtract the pips it provides.
    Special-energy pips are not basic energy, so they are not routed to any disc_energy pile."""
    mon.special.remove(name)
    for typ, c in SE.provides(name, mon.card).items():
        mon.energy[typ] -= c
        if mon.energy.get(typ, 0) <= 0:
            mon.energy.pop(typ, None)


# ---------------------------------------------------------------- helpers: attach basic from discard
def _ceiling(mon):
    return max((a['dmg'] for a in mon.card.attacks), default=0)


def _best_bench_target(bench):
    """The benched Pokémon best worth funding: highest attack ceiling, then most energy, then HP."""
    if not bench:
        return None
    return max(bench, key=lambda m: (_ceiling(m), m.total_energy(), m.card.hp))


def _cheapest_cost_letters(mon):
    """Energy letters of `mon`'s cheapest damaging attack cost (for type-matched acceleration)."""
    atks = [a for a in mon.card.attacks if a['dmg'] > 0 or a['scaling']] or mon.card.attacks
    if not atks:
        return []
    a = min(atks, key=lambda a: len(a['cost']))
    return [c for c in a['cost'] if c in 'GRWLPFDM']


def _available_basic_type(me, target=None):
    """A basic-energy type present in the discard pile, preferring one that advances `target`'s
    cheapest attack cost; else the most-abundant discarded real type. None if the pile has none."""
    real = {t: c for t, c in me.disc_energy.items() if t not in ('Wild', 'Colorless') and c > 0}
    if not real:
        return None
    if target is not None:
        for letter in _cheapest_cost_letters(target):
            t = _L2T.get(letter)
            if t and real.get(t, 0) > 0:
                return t
    return max(real, key=lambda t: real[t])


def _take_basic_from_discard(me, typ):
    """Remove one basic energy of `typ` from disc_energy. Returns True if one was taken."""
    if me.disc_energy.get(typ, 0) > 0:
        me.disc_energy[typ] -= 1
        if me.disc_energy[typ] <= 0:
            me.disc_energy.pop(typ, None)
        return True
    return False


# ---------------------------------------------------------------- helpers: opponent snipe
def _damage_opp_bench_one(ctx, amount):
    """Apply `amount` to the single most valuable KO target on the opponent's Bench (no W&R)."""
    bench = ctx.opp.bench
    if not bench:
        return
    tgt = min(bench, key=lambda b: (b.hp_left > amount, not b.card.is_ex, b.hp_left))
    tgt.damage += amount


def _snipe_opp_any(ctx, amount, n):
    """'does <amount> to <n> of your opponent's Pokémon' — pick n distinct targets among the Active
    and Bench (KO-able first, then ex, then lowest HP remaining). Weakness applies only to an Active
    hit, which is returned so the engine can double it; Bench hits go straight to `.damage`."""
    opp = ctx.opp
    ap = ctx.attacker.card.ptype

    def eff(tag, m):
        if tag == 'active' and m.card.weakness and m.card.weakness == ap:
            return amount * 2
        return amount

    cands = ([('active', opp.active)] if opp.active is not None else [])
    cands += [('bench', b) for b in opp.bench]
    cands.sort(key=lambda tm: (eff(*tm) < tm[1].hp_left, not tm[1].card.is_ex, tm[1].hp_left))
    ret = 0
    for tag, m in cands[:n]:
        if tag == 'active':
            ret += amount                         # engine applies Weakness to the returned Active damage
        else:
            m.damage += amount
    return ret


# ================================================================ discard from opponent's Active
@effect("Discard an Energy from your opponent's Active Pokémon.")
def _discard_opp_energy(ctx):
    ctx.discard_energy_defender(1)
    return ctx.base


@effect("Discard a Special Energy from your opponent's Active Pokémon.")
def _discard_opp_special(ctx):
    df = ctx.defender
    if df is not None and df.special:
        _remove_special(df, df.special[0])
    return ctx.base


@effect("Discard a {R} Energy from your opponent's Active Pokémon.")
def _discard_opp_fire(ctx):
    _discard_typed_defender(ctx, 'Fire', 1)
    return ctx.base


@effect("Discard an Energy from your opponent's Active Pokémon ex.")
def _discard_opp_ex_energy(ctx):
    # Only lands on an ex Active; against a non-ex there is nothing to discard.
    if ctx.defender is not None and ctx.defender.card.is_ex:
        ctx.discard_energy_defender(1)
    return ctx.base


@effect("Before doing damage, discard all Pokémon Tools and Special Energy from your opponent's Active Pokémon.")
def _discard_opp_tools_and_special(ctx):
    # Strip all Pokémon Tools (engine now models mon.tools) and all Special Energy from the Active
    # before dealing the printed damage.
    df = ctx.defender
    if df is not None:
        ctx.discard_tools(df)
        for name in list(df.special):
            _remove_special(df, name)
    return ctx.base


# ================================================================ discard from this Pokémon
@effect("Discard all Energy from this Pokémon.")
def _discard_all_energy_self(ctx):
    _discard_all_self(ctx)
    return ctx.base


@effect("Discard 3 Energy from this Pokémon.")
def _discard_self_3(ctx):
    ctx.discard_energy_self(3)
    return ctx.base


@effect("Discard a {L} Energy from this Pokémon.")
def _discard_self_lightning(ctx):
    _discard_typed_self(ctx, 'Lightning', 1)
    return ctx.base


@effect("Discard a {G} Energy from this Pokémon.")
def _discard_self_grass(ctx):
    _discard_typed_self(ctx, 'Grass', 1)
    return ctx.base


@effect("Discard all {L} Energy from this Pokémon. This attack does 50 damage for each card you discarded in this way.")
def _galvantula_discharge(ctx):
    n = _discard_typed_self(ctx, 'Lightning', ctx.attacker.energy.get('Lightning', 0))
    return ctx.base * n


@effect("Discard 2 Energy from this Pokémon. During your opponent's next turn, this Pokémon takes 100 less damage from attacks (after applying Weakness and Resistance).")
def _donphan_heavy_impact(ctx):
    ctx.discard_energy_self(2)
    ctx.attacker.dr_amount = 100                   # engine's incoming_damage applies -N on turn dr_turn+1
    ctx.attacker.dr_turn = ctx.game.turn
    return ctx.base


@effect("You may discard 3 {M} Energy from this Pokémon and have this attack do 150 more damage.")
def _metagross_metallic_hammer(ctx):
    # "You may": pay the 3-{M} discard for +150 only when it converts a non-KO into a KO (mirrors the
    # established Poliwrath heuristic) — never waste energy when base already KOs or +150 still can't.
    at = ctx.attacker
    dfn = ctx.defender
    base = ctx.base
    if at.energy.get('Metal', 0) >= 3 and dfn is not None:
        mult = 2 if (dfn.card.weakness and dfn.card.weakness == at.card.ptype) else 1
        if base * mult < dfn.hp_left <= (base + 150) * mult:
            _discard_typed_self(ctx, 'Metal', 3)
            return base + 150
    return base


# ================================================================ discard from hand (gated / scaling)
@effect("Discard up to 2 Energy cards from your hand, and this attack does 60 damage for each card you discarded in this way.")
def _mawile_double_eater(ctx):
    n = _discard_energy_from_hand(ctx, 2)          # maximize damage: discard as many as available (<=2)
    return ctx.base * n


@effect("Discard a Basic {G} Energy card from your hand. If you can't, this attack does nothing.")
def _decidueye_razor_leaf(ctx):
    tok = next((t for t in ctx.me.hand if t[0] == 'E' and t[1] == 'Grass'), None)
    if tok is None:
        return 0                                   # can't pay the discard -> attack does nothing
    ctx.me.hand.remove(tok)
    ctx.me.disc_energy['Grass'] += 1
    return ctx.base


@effect("Discard 2 Basic {G} Energy cards from your hand. If you can't discard 2 cards in this way, this attack does nothing.")
def _lurantis_solar_blade(ctx):
    gtoks = [t for t in ctx.me.hand if t[0] == 'E' and t[1] == 'Grass']
    if len(gtoks) < 2:
        return 0                                   # can't discard 2 -> nothing (and discard none)
    for t in gtoks[:2]:
        ctx.me.hand.remove(t)
        ctx.me.disc_energy['Grass'] += 1
    return ctx.base


# ================================================================ discard-self + snipe / doom
@effect("Discard all Energy from this Pokémon, and this attack also does 90 damage to 1 of your opponent's Benched Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _ns_darmanitan_flare_blitz(ctx):
    _discard_all_self(ctx)
    _damage_opp_bench_one(ctx, 90)                 # a Benched Pokémon takes 90 (no W&R)
    return ctx.base                                # printed 90 to the Active


@effect("Discard 2 Energy from this Pokémon, and this attack does 120 damage to 1 of your opponent's Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _honchkrow_night_slash(ctx):
    ctx.discard_energy_self(2)
    return _snipe_opp_any(ctx, 120, 1)             # 1 target: Active OR Bench (no printed base)


@effect("Discard all Energy from this Pokémon. This attack does 110 damage to 3 of your opponent's Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _kyurem_trifrost(ctx):
    _discard_all_self(ctx)
    return _snipe_opp_any(ctx, 110, 3)


@effect("Discard all Energy from this Pokémon, and this attack does 90 damage to 1 of your opponent's Pokémon. (Don't apply Weakness and Resistance for Benched Pokémon.)")
def _dartrix_razor_leaf(ctx):
    _discard_all_self(ctx)
    return _snipe_opp_any(ctx, 90, 1)


@effect("Discard all Energy from this Pokémon. At the end of your opponent's next turn, the Defending Pokémon will be Knocked Out.")
def _pinsir_doom(ctx):
    # The discard-all-energy cost is modeled. The delayed KO ("at the end of your opponent's next
    # turn") has no engine timer to hang on and the opponent could dodge it by switching, so it is
    # left unmodeled rather than approximated as immediate damage (which would over-apply). 0 damage now.
    _discard_all_self(ctx)
    return 0


# ================================================================ ×-scaling off discard-pile / deck energy
@effect("This attack does 30 damage for each Basic Energy card in your opponent's discard pile.")
def _30x_opp_discard_basic_energy(ctx):
    n = sum(c for t, c in ctx.opp.disc_energy.items() if t not in ('Wild', 'Colorless'))
    return ctx.base * n


@effect("Discard the top 6 cards of your deck, and this attack does 60 damage for each Basic {W} Energy card you discarded in this way.")
def _avalugg_iceberg_breaker(ctx):
    me = ctx.me
    water = 0
    for _ in range(6):
        if not me.deck:
            break
        tok = me.deck.pop()                        # top of deck = end of the list (engine convention)
        if tok[0] == 'E':
            me.disc_energy[tok[1]] += 1
            if tok[1] == 'Water':
                water += 1
        else:                                      # 'P' / 'T' / 'S' -> discard pile
            me.discard.append(tok)
    return ctx.base * water


# ================================================================ attach basic Energy from discard
@effect("Attach a Basic Energy card from your discard pile to 1 of your Benched Pokémon.")
def _attach_basic_discard_1_bench(ctx):
    me = ctx.me
    tgt = _best_bench_target(me.bench)
    if tgt is not None:
        typ = _available_basic_type(me, tgt)
        if typ and _take_basic_from_discard(me, typ):
            tgt.energy[typ] += 1
    return ctx.base


@effect("Attach up to 2 Basic Energy cards from your discard pile to 1 of your Benched Pokémon.")
def _attach_basic_discard_2_bench(ctx):
    me = ctx.me
    tgt = _best_bench_target(me.bench)
    if tgt is not None:
        for _ in range(2):
            typ = _available_basic_type(me, tgt)
            if not (typ and _take_basic_from_discard(me, typ)):
                break
            tgt.energy[typ] += 1
    return ctx.base


@effect("Attach a Basic {R} Energy card from your discard pile to 1 of your {N} Pokémon.")
def _druddigon_attach_fire_to_dragon(ctx):
    # {N} = Dragon in this notation; fund the readiest Dragon-type Pokémon (Active or Bench).
    me = ctx.me
    dragons = [m for m in me.all_mons() if m.card.ptype == 'Dragon']
    if dragons and me.disc_energy.get('Fire', 0) > 0:
        tgt = max(dragons, key=lambda m: (_ceiling(m), m.total_energy()))
        _take_basic_from_discard(me, 'Fire')
        tgt.energy['Fire'] += 1
    return ctx.base


@effect("Attach up to 2 Basic {F} Energy cards from your discard pile to your Benched Pokémon in any way you like.")
def _lycanroc_attach_2f_bench(ctx):
    me = ctx.me
    if not me.bench:
        return ctx.base
    for _ in range(2):
        if me.disc_energy.get('Fighting', 0) <= 0:
            break
        tgt = _best_bench_target(me.bench)         # concentrate on the readiest bench attacker
        _take_basic_from_discard(me, 'Fighting')
        tgt.energy['Fighting'] += 1
    return ctx.base


@effect("Attach a Basic {F} Energy card from your discard pile to each of your Benched Pokémon.")
def _mudsdale_attach_f_each_bench(ctx):
    me = ctx.me
    for m in me.bench:                             # one {F} per Benched Pokémon, until the pile runs out
        if me.disc_energy.get('Fighting', 0) <= 0:
            break
        _take_basic_from_discard(me, 'Fighting')
        m.energy['Fighting'] += 1
    return ctx.base


@effect("Choose Basic {L} Energy cards from your discard pile up to the amount of Energy attached to all of your opponent's Pokémon and attach them to your {L} Pokémon in any way you like.")
def _dedenne_energy_assist(ctx):
    me = ctx.me
    cap = sum(m.total_energy() for m in ctx.opp.all_mons())
    lightning = [m for m in me.all_mons() if m.card.ptype == 'Lightning']
    if not lightning or cap <= 0:
        return ctx.base
    tgt = max(lightning, key=lambda m: (_ceiling(m), m.total_energy()))
    attached = 0
    while attached < cap and me.disc_energy.get('Lightning', 0) > 0:
        _take_basic_from_discard(me, 'Lightning')
        tgt.energy['Lightning'] += 1
        attached += 1
    return ctx.base
