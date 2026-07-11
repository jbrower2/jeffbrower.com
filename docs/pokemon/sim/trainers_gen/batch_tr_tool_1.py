# -*- coding: utf-8 -*-
"""Generated trainer-effect batch: tr_tool_1 (Pokémon Tools).

Faithful exact-text implementations for 14 Tool cards. Each Tool is registered with the tool
KIND whose hook signature matches how the engine queries it:

  tool_hp          fn(mon, owner, game) -> int                       extra max HP
  tool_dr          fn(dmg, atk, dfn, dfn_owner, game) -> int         reduce incoming damage (return dmg-N)
  tool_ondamaged   fn(atk_mon, dfn_mon, dfn_owner, game)             reaction when the holder is damaged
  tool_attack_buff fn(atk_mon, dfn_mon, attack, game) -> int         bonus damage the holder's attacks deal
  tool_retreat     fn(mon, owner, game) -> int                       retreat-cost delta for the holder

Hook-arg convention (mirrors ability_effects): the HOLDER is `dfn_mon` for on_damaged/dr,
`atk_mon` for attack_buff, and `mon` for hp/retreat; `dfn_owner`/`owner` is the holder's Player.

Two cards have no matching tool-hook kind in this framework and are registered as conservative
no-ops (see notes on Powerglass and Technical Machine: Fluorite).
"""
from collections import Counter
from trainer_effects import trainer, TrainerCtx
import special_energy as SE

_BASIC_TYPES = ('Grass', 'Fire', 'Water', 'Lightning', 'Psychic', 'Fighting', 'Darkness', 'Metal')


# ---------------- shared helpers ----------------
def _basic_pips(mon):
    """The real basic-energy pips on `mon` (its energy Counter minus what its attached Special
    Energy provides, and excluding the Colorless/Wild special pseudo-types). 'Basic Energy cards'
    clauses act on these only."""
    special = Counter()
    for name in mon.special:
        for tp, c in SE.provides(name, mon.card).items():
            special[tp] += c
    out = Counter()
    for tp in _BASIC_TYPES:
        real = mon.energy.get(tp, 0) - special.get(tp, 0)
        if real > 0:
            out[tp] = real
    return out


def _is_ko(mon, owner, game):
    """Engine's own KO test if available (damage >= effective HP), else a card-HP fallback."""
    try:
        return game.is_ko(mon, owner)
    except Exception:
        return mon.damage >= mon.card.hp


# ================================================================ TOOLS

# --- Heavy Baton: on a 4-retreat Active holder that is KO'd, salvage its Basic Energy onto the bench.
# Fires only when the holder is actually Knocked Out (requires the engine to invoke the on_damaged
# hook with damage already applied; conservative no-op otherwise). Distributes up to 3 basic pips
# "in any way you like" — piled onto the benched Pokémon with the most energy (finish an attacker).
@trainer('tool_ondamaged', "If the Pokémon this card is attached to has a Retreat Cost of exactly 4, is in the Active Spot, and is Knocked Out by damage from an attack from your opponent's Pokémon, move up to 3 Basic Energy cards from that Pokémon to your Benched Pokémon in any way you like.")
def _heavy_baton(atk_mon, dfn_mon, dfn_owner, game):
    if dfn_mon.card.retreat != 4:
        return
    if dfn_mon is not dfn_owner.active:
        return
    if not _is_ko(dfn_mon, dfn_owner, game):
        return
    if not dfn_owner.bench:
        return
    dest = max(dfn_owner.bench, key=lambda m: m.total_energy())
    bp = _basic_pips(dfn_mon)
    moved = 0
    for tp in list(bp):
        while bp[tp] > 0 and moved < 3:
            dfn_mon.energy[tp] -= 1
            if dfn_mon.energy[tp] <= 0:
                del dfn_mon.energy[tp]
            dest.energy[tp] += 1
            bp[tp] -= 1
            moved += 1


# --- Hop's Choice Band: Hop's holder's attacks do +30 to the Active. The "{C} less" cost reduction
# is a cost effect that the attack_buff hook can't express (noted); only the +30 damage is modeled.
@trainer('tool_attack_buff', "Attacks used by the Hop's Pokémon this card is attached to cost {C} less and do 30 more damage to your opponent's Active Pokémon (before applying Weakness and Resistance).")
def _hops_choice_band(atk_mon, dfn_mon, attack, game):
    return 30 if atk_mon.card.name.startswith("Hop's ") else 0


# --- Light Ball: Pikachu ex holder's attacks do +50 to an opposing Pokémon ex.
@trainer('tool_attack_buff', "Attacks used by the Pikachu ex this card is attached to do 50 more damage to your opponent's Active Pokémon ex (before applying Weakness and Resistance).")
def _light_ball(atk_mon, dfn_mon, attack, game):
    if atk_mon.card.name == 'Pikachu ex' and dfn_mon is not None and dfn_mon.card.is_ex:
        return 50
    return 0


# --- Lillie's Pearl: when a KO'd Lillie's holder, the attacker's player takes 1 fewer Prize.
# There is no prize-count hook in the engine, so this sets a `prize_penalty` marker on the holder
# that a future _resolve_kos integration must honor (conservative; noted). Fires only on real KO.
@trainer('tool_ondamaged', "If the Lillie's Pokémon this card is attached to is Knocked Out by damage from an attack from your opponent's Pokémon, that player takes 1 fewer Prize card.")
def _lillies_pearl(atk_mon, dfn_mon, dfn_owner, game):
    if not dfn_mon.card.name.startswith("Lillie's "):
        return
    if not _is_ko(dfn_mon, dfn_owner, game):
        return
    dfn_mon.prize_penalty = getattr(dfn_mon, 'prize_penalty', 0) + 1


# --- Lucky Helmet: Active holder damaged by an attack -> its owner draws 2 (even if it's KO'd).
@trainer('tool_ondamaged', "If the Pokémon this card is attached to is in the Active Spot and is damaged by an attack from your opponent's Pokémon (even if this Pokémon is Knocked Out), draw 2 cards.")
def _lucky_helmet(atk_mon, dfn_mon, dfn_owner, game):
    if dfn_mon is dfn_owner.active:
        dfn_owner.draw(2)


# --- Berries: -60 from an attack by a specific-type attacker, then discard the Berry.
def _berry_dr(etype):
    def fn(dmg, atk, dfn, dfn_owner, game, _et=etype):
        if atk is None or atk.card.ptype != _et:
            return dmg
        _discard_tool(dfn, dfn_owner, _et)
        return max(0, dmg - 60)         # damage floors at 0 (matches sibling Babiri/Colbur/Haban berries)
    return fn


_BERRY_NAME = {'Fire': 'Occa Berry', 'Water': 'Passho Berry', 'Psychic': 'Payapa Berry'}


def _discard_tool(dfn, dfn_owner, etype):
    name = _BERRY_NAME[etype]
    if name in dfn.tools:
        dfn.tools.remove(name)
        dfn_owner.discard.append(('T', {'name': name}))


trainer('tool_dr', "If the Pokémon this card is attached to is damaged by an attack from your opponent's {R} Pokémon, it takes 60 less damage (after applying Weakness and Resistance), and discard this card.")(_berry_dr('Fire'))
trainer('tool_dr', "If the Pokémon this card is attached to is damaged by an attack from your opponent's {W} Pokémon, it takes 60 less damage (after applying Weakness and Resistance), and discard this card.")(_berry_dr('Water'))
trainer('tool_dr', "If the Pokémon this card is attached to is damaged by an attack from your opponent's {P} Pokémon, it takes 60 less damage (after applying Weakness and Resistance), and discard this card.")(_berry_dr('Psychic'))


# --- Powerglass: end-of-turn energy acceleration on the Active holder. NO matching tool-hook kind
# exists (there is no end-of-turn tool hook), so this is a conservative tool_hp no-op (grants no HP).
# The recurring {R}/{G}/etc. attach-from-discard is unmodeled — noted.
@trainer('tool_hp', "At the end of your turn (after your attack), if the Pokémon this card is attached to is in the Active Spot, you may attach a Basic Energy card from your discard pile to it.")
def _powerglass(mon, owner, game):
    return 0


# --- Punk Helmet: Active {D} holder damaged by an attack -> place 4 damage counters (40) on the
# Attacking Pokémon (even if the holder is KO'd).
@trainer('tool_ondamaged', "If the {D} Pokémon this card is attached to is in the Active Spot and is damaged by an attack from your opponent's Pokémon (even if this Pokémon is Knocked Out), place 4 damage counters on the Attacking Pokémon.")
def _punk_helmet(atk_mon, dfn_mon, dfn_owner, game):
    if dfn_mon.card.ptype == 'Darkness' and dfn_mon is dfn_owner.active and atk_mon is not None:
        atk_mon.damage += 40


# --- Rescue Board: retreat cost is {C} less; if the holder has 30 or less HP left, no retreat cost.
@trainer('tool_retreat', "The Retreat Cost of the Pokémon this card is attached to is {C} less. If that Pokémon's remaining HP is 30 or less, it has no Retreat Cost.")
def _rescue_board(mon, owner, game):
    if mon.hp_left <= 30:
        return -mon.card.retreat            # zero out the printed cost -> no Retreat Cost
    return -1


# --- Sacred Charm: -30 from attacks by an opposing Pokémon that has an Ability.
@trainer('tool_dr', "The Pokémon this card is attached to takes 30 less damage from attacks from your opponent's Pokémon that have an Ability (after applying Weakness and Resistance).")
def _sacred_charm(dmg, atk, dfn, dfn_owner, game):
    if atk is not None and atk.card.abilities:
        return max(0, dmg - 30)         # damage floors at 0 (tool_reduce doesn't floor centrally)
    return dmg


# --- Team Rocket's Hypnotizer: Active Team Rocket's holder damaged by an attack -> the Attacking
# Pokémon is now Asleep (even if the holder is KO'd). Blocked by the attacker's effect-immunity
# (Bubbly Water Energy &c.), consistent with Poison Point.
@trainer('tool_ondamaged', "If the Team Rocket's Pokémon this card is attached to is in the Active Spot and is damaged by an attack from your opponent's Pokémon (even if this Team Rocket's Pokémon is Knocked Out), the Attacking Pokémon is now Asleep.")
def _tr_hypnotizer(atk_mon, dfn_mon, dfn_owner, game):
    if (dfn_mon.card.name.startswith("Team Rocket's ") and dfn_mon is dfn_owner.active
            and atk_mon is not None and not atk_mon.effect_immune()):
        atk_mon.status['Asleep'] = True


# --- Technical Machine: Fluorite: grants the holder an extra attack (the one printed on the TM) and
# self-discards at end of turn. Neither "grant an attack" nor "discard at end of turn" maps to any
# tool-hook kind, so this is a conservative tool_hp no-op (grants no HP). Unmodeled — noted.
@trainer('tool_hp', "The Pokémon this card is attached to can use the attack on this card. (You still need the necessary Energy to use this attack.) If this card is attached to 1 of your Pokémon, discard it at the end of your turn.")
def _tm_fluorite(mon, owner, game):
    return 0
