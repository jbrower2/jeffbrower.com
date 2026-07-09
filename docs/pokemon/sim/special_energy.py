#!/usr/bin/env python3
"""Curated registry of Standard-legal (reg H/I/J) Special Energy for the simulator.

The raw carddata still contains rotated-out G cards (Jet, Luminous) and the F-mark
accelerators (Double Turbo/Twin/Reversal) are long gone, so this list is hand-verified
to the current format. Legality follows the same money-slot rule as every other card:
Common/Uncommon → free & unlimited (cat 'green'); Rare & ≤$0.50 → a support-slot card
(cat 'yellow'); >$1 → illegal (Legacy Energy at $3.22 is excluded on that basis).

The engine models an attached special energy by what it *provides* toward attack costs:
  colorless(n) -> n 'Colorless' pips (pay {C} only)
  wild(n)      -> n 'Wild' pips (pay any requirement, typed or {C})
  typed(T)     -> 1 real {T} pip (also counts as a T energy for scaling effects)
plus a positional 'rider' handled in engine.py.
"""

# name -> registry entry. `prov` is a rule the engine resolves against the target Pokémon.
SPECIAL_ENERGY = {
    # ---- free (Common/Uncommon) ----
    'Prism Energy':          {'reg': 'I', 'cat': 'green', 'price': 0.0,
                              'prov': 'rainbow_basic', 'rider': None},          # Wild(1) on a Basic, else Colorless(1)
    "Team Rocket's Energy":  {'reg': 'I', 'cat': 'green', 'price': 0.0,
                              'prov': ('wild', 2), 'rider': None, 'constraint': 'team_rocket'},  # 2 in any {P}/{D}
    'Spiky Energy':          {'reg': 'I', 'cat': 'green', 'price': 0.0,
                              'prov': ('colorless', 1), 'rider': 'spiky'},      # +20 to attacker when Active & hit
    'Mist Energy':           {'reg': 'H', 'cat': 'green', 'price': 0.0,
                              'prov': ('colorless', 1), 'rider': 'effect_shield'},
    'Boomerang Energy':      {'reg': 'H', 'cat': 'green', 'price': 0.0,
                              'prov': ('colorless', 1), 'rider': None},
    'Ignition Energy':       {'reg': 'I', 'cat': 'green', 'price': 0.0,
                              'prov': 'ignition', 'rider': 'temp'},             # C, or CCC on an Evolution; discarded end of turn
    # ---- Rare, ≤$0.50: a typed pip + a rider, but costs a support money-slot ----
    'Growing Grass Energy':      {'reg': 'J', 'cat': 'yellow', 'price': 0.30,
                                  'prov': ('typed', 'Grass'), 'rider': 'hp20'},
    'Nitro Fire Energy':         {'reg': 'J', 'cat': 'yellow', 'price': 0.30,
                                  'prov': ('typed', 'Fire'), 'rider': None},
    'Bubbly Water Energy':       {'reg': 'J', 'cat': 'yellow', 'price': 0.30,
                                  'prov': ('typed', 'Water'), 'rider': 'cond_immune'},
    'Rocky Fighting Energy':     {'reg': 'J', 'cat': 'yellow', 'price': 0.30,
                                  'prov': ('typed', 'Fighting'), 'rider': 'effect_shield'},
    'Magnetic Metal Energy':     {'reg': 'J', 'cat': 'yellow', 'price': 0.30,
                                  'prov': ('typed', 'Metal'), 'rider': 'noretreat'},
    'Telepathic Psychic Energy': {'reg': 'J', 'cat': 'yellow', 'price': 0.30,
                                  'prov': ('typed', 'Psychic'), 'rider': 'search2p'},
}

FREE_SPECIAL = [n for n, e in SPECIAL_ENERGY.items() if e['cat'] == 'green']
MONEY_SPECIAL = [n for n, e in SPECIAL_ENERGY.items() if e['cat'] == 'yellow']
# type a Rare typed energy pays for (for candidate matching) -> its name
TYPED_SPECIAL = {e['prov'][1]: n for n, e in SPECIAL_ENERGY.items()
                 if isinstance(e['prov'], tuple) and e['prov'][0] == 'typed'}


def is_special(name):
    return name in SPECIAL_ENERGY


def provides(name, target):
    """Energy pips this special energy contributes to `target` (a Card). Returns a dict
    {pseudo/real-type: count}: 'Colorless' (colorless-only), 'Wild' (any), or a real type."""
    e = SPECIAL_ENERGY[name]; p = e['prov']
    if p == 'rainbow_basic':
        return {'Wild': 1} if getattr(target, 'stage', 0) == 0 else {'Colorless': 1}
    if p == 'ignition':
        return {'Colorless': 3 if getattr(target, 'stage', 0) >= 1 else 1}
    kind, val = p
    if kind == 'colorless':
        return {'Colorless': val}
    if kind == 'wild':
        return {'Wild': val}
    return {val: 1}                       # typed


if __name__ == '__main__':
    print(f"{len(SPECIAL_ENERGY)} legal special energy: {len(FREE_SPECIAL)} free, {len(MONEY_SPECIAL)} money-slot")
    print("free:", FREE_SPECIAL)
    print("money (<=$0.50):", MONEY_SPECIAL)
    print("typed->name:", TYPED_SPECIAL)
