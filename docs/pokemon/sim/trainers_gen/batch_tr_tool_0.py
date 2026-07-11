# -*- coding: utf-8 -*-
"""Generated trainer-effect batch: tr_tool_0 (Pokémon Tools).

Faithful exact-text implementation for 14 Pokémon Tool cards. Each is registered by its exact
printed text under the Tool hook kind that matches its effect:

  tool_ondamaged   Adversity Policy, Handheld Fan
  tool_retreat     Air Balloon (-{C}{C}); Gravity Gemstone (+{C} while Active)
  tool_hp          Ancient Booster Energy Capsule (+60 to an Ancient holder);
                   Cynthia's Power Weight (+70 to a Cynthia's holder);
                   Core Memory / Counter Gain (no Tool hook fits their real effect -> conservative +0)
  tool_dr          Babiri / Colbur / Haban Berry (-60 vs a {M}/{D}/{N} attacker; one-shot)
  tool_attack_buff Binding Mochi, Brave Bangle, Future Booster Energy Capsule

Energy notation on the cards: {M}=Metal, {D}=Darkness, {N}=Dragon (D already denotes Darkness, so
Dragon is written {N}), {C}=Colorless.

Ancient / Future are card *subtypes* the data model does not carry, so — matching the existing
effects.py convention that spots a Future paradox Pokémon by its 'Iron ' name prefix — we detect
them by the fixed paradox name sets (`_is_ancient` / `_is_future`), covering both the plain and the
' ex' printings. Rule Box is proxied by `card.is_ex` (the only Rule-Box Pokémon in the reg H/I/J
pool are ex), matching effects.py's own rule-box test.

Not modeled (no engine hook exists for these sub-effects; noted, never fired blind):
  * Ancient Booster Energy Capsule's Special-Condition recover/immunity (only the +60 HP is applied).
  * Future Booster Energy Capsule's 'no Retreat Cost' (this card is registered under its damage-buff kind).
  * Gravity Gemstone's +{C} to the *opponent's* Active (a Tool hook only edits its holder's retreat).
  * Core Memory (grants Mega Zygarde ex an attack — there is no attack-granting hook) -> +0 HP no-op.
  * Counter Gain (attacks cost {C} less — there is no attack-cost hook for Tools) -> +0 HP no-op.
"""
from trainer_effects import trainer, TrainerCtx  # noqa: F401 (kept for uniform import across batches)


# --------------------------------------------------------------------------- paradox subtype detection
# No subtype field exists on the card model; identify the paradox Pokémon by their fixed name sets
# (consistent with effects.py detecting Future Pokémon via the 'Iron ' prefix). Each check also matches
# the ' ex' printing (e.g. "Raging Bolt ex", "Iron Crown ex", "Koraidon ex", "Miraidon ex").
_ANCIENT = ('Koraidon', 'Great Tusk', 'Scream Tail', 'Brute Bonnet', 'Flutter Mane', 'Slither Wing',
            'Sandy Shocks', 'Roaring Moon', 'Walking Wake', 'Gouging Fire', 'Raging Bolt')


def _is_ancient(card):
    n = getattr(card, 'name', '') or ''
    return any(n == a or n.startswith(a + ' ') for a in _ANCIENT)


def _is_future(card):
    n = getattr(card, 'name', '') or ''
    return n.startswith('Iron ') or n == 'Miraidon' or n.startswith('Miraidon ')


def _consume_berry(dfn, dfn_owner, name):
    """One-shot Berry bookkeeping: detach the Tool and put it in the discard once it reduces damage."""
    if dfn is not None and name in getattr(dfn, 'tools', []):
        dfn.tools.remove(name)
        if dfn_owner is not None:
            dfn_owner.discard.append(('T', {'name': name, 'trainerType': 'Tool'}))


# =============================================================================== tool_ondamaged
@trainer(
    'tool_ondamaged',
    "If the Pokémon this card is attached to has Weakness to your opponent's Active Pokémon's type, is in the Active Spot, and is damaged by an attack from your opponent's Pokémon (even if this Pokémon is Knocked Out), draw 3 cards.",
)
def _adversity_policy(atk_mon, dfn_mon, dfn_owner, game):
    """Adversity Policy — if the holder is Active, has Weakness to the attacker's (i.e. the opponent's
    Active Pokémon's) type, and just took damage, its controller draws 3. Fires even while the holder is
    being Knocked Out (this reaction runs before KO resolution)."""
    if dfn_owner is None or dfn_mon is not dfn_owner.active:
        return
    weak = getattr(dfn_mon.card, 'weakness', None)
    atk_type = getattr(atk_mon.card, 'ptype', None) if atk_mon is not None else None
    if weak and atk_type and weak == atk_type:
        dfn_owner.draw(3)


@trainer(
    'tool_ondamaged',
    "If the Pokémon this card is attached to is in the Active Spot and is damaged by an attack from your opponent's Pokémon (even if this Pokémon is Knocked Out), move an Energy from the Attacking Pokémon to 1 of your opponent's Benched Pokémon.",
)
def _handheld_fan(atk_mon, dfn_mon, dfn_owner, game):
    """Handheld Fan — when the Active holder is damaged, move 1 Energy off the Attacking Pokémon onto one
    of the attacker's own Benched Pokémon (that side is the holder's 'opponent'). No-op if the attacker
    has no Energy or an empty bench. Fires even while the holder is being Knocked Out."""
    if dfn_owner is None or dfn_mon is not dfn_owner.active or atk_mon is None:
        return
    players = getattr(game, 'players', None)
    if not players:                                      # real Game always has .players; stand-ins may not
        return
    attacker_owner = next((p for p in players if p is not dfn_owner), None)
    if attacker_owner is None or not attacker_owner.bench or atk_mon.total_energy() <= 0:
        return
    etype = max((k for k in atk_mon.energy if atk_mon.energy[k] > 0), key=lambda k: atk_mon.energy[k])
    atk_mon.energy[etype] -= 1
    if atk_mon.energy[etype] <= 0:
        del atk_mon.energy[etype]
    attacker_owner.bench[0].energy[etype] += 1


# =============================================================================== tool_retreat
@trainer('tool_retreat', "The Retreat Cost of the Pokémon this card is attached to is {C}{C} less.")
def _air_balloon(mon, owner, game):
    """Air Balloon — retreat cost is {C}{C} less (a flat -2 delta while attached)."""
    return -2


@trainer(
    'tool_retreat',
    "As long as the Pokémon this card is attached to is in the Active Spot, the Retreat Cost of both Active Pokémon is {C} more.",
)
def _gravity_gemstone(mon, owner, game):
    """Gravity Gemstone — only while the holder is Active. A Tool retreat hook can only raise the holder's
    own retreat (+{C} = +1); the symmetric +{C} on the OPPONENT's Active is not expressible here."""
    return 1 if (owner is not None and mon is owner.active) else 0


# =============================================================================== tool_hp
@trainer(
    'tool_hp',
    "The Ancient Pokémon this card is attached to gets +60 HP, recovers from all Special Conditions, and can't be affected by any Special Conditions.",
)
def _ancient_booster_energy_capsule(mon, owner, game):
    """Ancient Booster Energy Capsule — +60 HP to an Ancient holder only. The Special-Condition
    recover/immunity clause has no Tool hook, so only the +60 HP is modeled (see header)."""
    return 60 if _is_ancient(mon.card) else 0


@trainer('tool_hp', "The Cynthia's Pokémon this card is attached to gets +70 HP.")
def _cynthias_power_weight(mon, owner, game):
    """Cynthia's Power Weight — +70 HP, but only to a 'Cynthia's' Pokémon (named-family Tool)."""
    name = getattr(mon.card, 'name', '') or ''
    return 70 if name.startswith("Cynthia's ") else 0


@trainer(
    'tool_hp',
    "The Mega Zygarde ex this card is attached to can use the attack on this card. (You still need the necessary Energy to use this attack.)",
)
def _core_memory(mon, owner, game):
    """Core Memory — grants a specific card (Mega Zygarde ex) an extra attack. There is no attack-granting
    Tool hook, so this is a conservative no-op (adds no HP) rather than firing something wrong."""
    return 0


@trainer(
    'tool_hp',
    "If you have more Prize cards remaining than your opponent, attacks used by the Pokémon this card is attached to cost {C} less.",
)
def _counter_gain(mon, owner, game):
    """Counter Gain — reduces the holder's attack cost by {C} when behind on Prizes. Attack-cost reduction
    has no Tool hook, so this is a conservative no-op (adds no HP)."""
    return 0


# =============================================================================== tool_dr (one-shot Berries)
@trainer(
    'tool_dr',
    "If the Pokémon this card is attached to is damaged by an attack from your opponent's {M} Pokémon, it takes 60 less damage (after applying Weakness and Resistance), and discard this card.",
)
def _babiri_berry(dmg, atk, dfn, dfn_owner, game):
    """Babiri Berry — -60 from a {M} (Metal) attacker (post Weakness/Resistance), then discard the Berry."""
    if atk is not None and getattr(atk.card, 'ptype', None) == 'Metal':
        _consume_berry(dfn, dfn_owner, 'Babiri Berry')
        return max(0, dmg - 60)
    return dmg


@trainer(
    'tool_dr',
    "If the Pokémon this card is attached to is damaged by an attack from your opponent's {D} Pokémon, it takes 60 less damage (after applying Weakness and Resistance), and discard this card.",
)
def _colbur_berry(dmg, atk, dfn, dfn_owner, game):
    """Colbur Berry — -60 from a {D} (Darkness) attacker (post Weakness/Resistance), then discard the Berry."""
    if atk is not None and getattr(atk.card, 'ptype', None) == 'Darkness':
        _consume_berry(dfn, dfn_owner, 'Colbur Berry')
        return max(0, dmg - 60)
    return dmg


@trainer(
    'tool_dr',
    "If the Pokémon this card is attached to is damaged by an attack from your opponent's {N} Pokémon, it takes 60 less damage (after applying Weakness and Resistance), and discard this card.",
)
def _haban_berry(dmg, atk, dfn, dfn_owner, game):
    """Haban Berry — -60 from a {N} (Dragon) attacker (post Weakness/Resistance), then discard the Berry."""
    if atk is not None and getattr(atk.card, 'ptype', None) == 'Dragon':
        _consume_berry(dfn, dfn_owner, 'Haban Berry')
        return max(0, dmg - 60)
    return dmg


# =============================================================================== tool_attack_buff
@trainer(
    'tool_attack_buff',
    "Attacks used by the Poisoned Pokémon this card is attached to do 40 more damage to your opponent's Active Pokémon (before applying Weakness and Resistance).",
)
def _binding_mochi(atk_mon, dfn_mon, attack, game):
    """Binding Mochi — +40 damage while the holder itself is Poisoned (pre Weakness/Resistance)."""
    return 40 if 'Poisoned' in getattr(atk_mon, 'status', {}) else 0


@trainer(
    'tool_attack_buff',
    "If the Pokémon this card is attached to doesn't have a Rule Box, the attacks it uses do 30 more damage to your opponent's Active Pokémon ex (before applying Weakness and Resistance). (Pokémon ex, Pokémon V, etc. have Rule Boxes.)",
)
def _brave_bangle(atk_mon, dfn_mon, attack, game):
    """Brave Bangle — +30 damage, but only when the holder has no Rule Box (proxied by is_ex) AND the
    defending Active is a Pokémon ex (pre Weakness/Resistance)."""
    holder_no_rulebox = not getattr(atk_mon.card, 'is_ex', False)
    defender_is_ex = dfn_mon is not None and getattr(dfn_mon.card, 'is_ex', False)
    return 30 if (holder_no_rulebox and defender_is_ex) else 0


@trainer(
    'tool_attack_buff',
    "The Future Pokémon this card is attached to has no Retreat Cost, and the attacks it uses do 20 more damage to your opponent's Active Pokémon (before applying Weakness and Resistance).",
)
def _future_booster_energy_capsule(atk_mon, dfn_mon, attack, game):
    """Future Booster Energy Capsule — +20 damage to a Future holder's attacks (pre Weakness/Resistance).
    The 'no Retreat Cost' clause is a retreat effect that can't be expressed through this attack-buff hook
    (this card's kind), so only the +20 damage is modeled (see header)."""
    return 20 if _is_future(atk_mon.card) else 0
