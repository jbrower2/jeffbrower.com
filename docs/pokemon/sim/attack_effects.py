#!/usr/bin/env python3
"""Exact-attack-text -> effect-lambda registry. The trustworthy replacement for the heuristic
text-matching in effects.py: every attack in the pool resolves through ONE explicit, unit-tested
implementation keyed by its exact (damage-stripped) effect text.

Design
------
- `normalize(text)` strips the leading damage token ([N] / N× / N+ / N-) and whitespace, leaving the
  pure effect description. That description is the registry key. Vanilla attacks (damage only) reduce
  to '' and use the default handler (return base damage, no side effects).
- Each effect is `fn(ctx) -> int`: it performs ALL side effects via `ctx` helpers and returns the raw
  damage to apply to the defender's Active (the engine then applies weakness/resistance/buffs).
- `ctx` (EffectCtx) wraps the real engine objects (me, opp, attacker, defender, game, attack), so the
  same lambdas run in the live sim and in unit tests.
- Coverage is a hard invariant: `coverage_effects.py` asserts every pool attack has a registry entry.
"""
import re

# ---------------------------------------------------------------- key normalization
_LEAD_DMG = re.compile(r'^\s*(?:\[\d+\]|\d+\s*[+×xX×\-−])\s*')   # [30] / 30× / 60+ / 90-
_LEAD_BULLET = re.compile(r'^\s*-\s*')


def normalize(text):
    """Strip the leading damage token + bullet and collapse whitespace -> the effect key."""
    t = (text or '').strip()
    t = _LEAD_DMG.sub('', t)
    t = _LEAD_BULLET.sub('', t)
    return ' '.join(t.split())


# ---------------------------------------------------------------- registry
ATTACK_EFFECTS = {}          # normalized text -> fn(ctx) -> damage


def effect(*texts):
    """Register a lambda under one or more effect texts (normalized on registration)."""
    def deco(fn):
        for t in texts:
            key = normalize(t)
            if key in ATTACK_EFFECTS:
                raise ValueError(f"duplicate effect registration for: {key!r}")
            ATTACK_EFFECTS[key] = fn
        return fn
    return deco


STATUSES = ('Asleep', 'Burned', 'Confused', 'Paralyzed', 'Poisoned')


# ---------------------------------------------------------------- effect context
class EffectCtx:
    """Everything an attack effect can touch, over the real engine Mon/Player/Game objects."""
    def __init__(self, me, opp, attacker, defender, game, attack):
        self.me, self.opp = me, opp
        self.attacker, self.defender = attacker, defender
        self.game, self.attack = game, attack
        self.rng = game.rng
        self.base = attack['dmg']

    # -- coin flips --
    def flip(self):
        return self.rng.random() < 0.5

    def flips(self, n):
        return sum(1 for _ in range(n) if self.flip())

    def flips_until_tails(self):
        n = 0
        while self.flip():
            n += 1
        return n

    # -- damage / heal --
    def self_damage(self, n):
        self.attacker.damage += n

    def heal(self, n, mon=None):
        m = mon or self.attacker
        m.damage = max(0, m.damage - n)

    def bench_damage(self, n, side='opp', which='all', count=None):
        """Apply n to benched Pokémon of a side ('opp'/'me'). which='all' or count=k random. Returns list hit."""
        pl = self.opp if side == 'opp' else self.me
        targets = list(pl.bench)
        if count is not None:
            self.rng.shuffle(targets); targets = targets[:count]
        for m in targets:
            m.damage += n
        return targets

    # -- energy --
    def _pull_energy(self, mon, n):
        removed = 0
        for t in list(mon.energy):
            while mon.energy[t] > 0 and removed < n:
                mon.energy[t] -= 1; removed += 1
                if t not in ('Wild', 'Colorless'):
                    (self.me if mon is self.attacker else self.opp).disc_energy[t] += 1
            if mon.energy[t] <= 0:
                del mon.energy[t]
        return removed

    def discard_energy_self(self, n=1):
        return self._pull_energy(self.attacker, n)

    def discard_energy_defender(self, n=1):
        return self._pull_energy(self.defender, n)

    # -- status conditions (respect effect-shield specials) --
    def status(self, kind, mon=None):
        m = mon or self.defender
        if kind in STATUSES and not m.effect_immune():
            m.status[kind] = True
            return True
        return False

    # -- turn / retreat control --
    def cant_attack_next(self):
        self.attacker.cd_name = 'ALL'; self.attacker.cd_turn = self.game.turn

    def defender_cant_retreat(self):
        self.defender.status['CantRetreat'] = self.game.turn

    def switch_defender(self):
        """Opponent's Active goes to Bench; opponent promotes their readiest OTHER benched Pokémon."""
        if self.opp.bench:
            old = self.opp.active
            self.opp.promote()               # bring up the readiest currently-benched mon
            self.opp.bench.append(old)       # the switched-out Active joins the bench (not re-promoted)

    # -- cards --
    def draw(self, n=1):
        self.me.draw(n)

    # -- queries --
    def opp_prizes(self):
        return len(self.opp.prizes)

    def my_prizes(self):
        return len(self.me.prizes)

    # -- engine-state trackers (Stadium / Tools / last-turn history) --
    def stadium(self):
        """Name of the Stadium in play, or None."""
        return self.game.stadium[0] if getattr(self.game, 'stadium', None) else None

    def discard_stadium(self):
        self.game.stadium = None

    def used_last_turn(self, name):
        """Did the attacker use the named attack on the player's PREVIOUS turn (2 game-turns ago)?"""
        return self.attacker.last_atk == name and self.attacker.last_atk_turn == self.game.turn - 2

    def ko_last_turn(self):
        """Were any of MY Pokémon KO'd during the opponent's last turn (1 game-turn ago)?"""
        return self.me.last_ko_turn == self.game.turn - 1

    def evolved_this_turn(self):
        return self.attacker.evolved_turn == self.game.turn

    def played_this_turn(self, name):
        return name in self.me.played

    def has_tool(self, mon=None):
        return bool((mon or self.defender).tools)

    def count_tools(self, side='all'):
        mons = (self.me.all_mons() if side in ('all', 'me') else []) + \
               (self.opp.all_mons() if side in ('all', 'opp') else [])
        return sum(len(m.tools) for m in mons)

    def discard_tools(self, mon=None):
        (mon or self.defender).tools.clear()


def resolve(me, opp, attacker, defender, game, attack, legacy=None):
    """Resolve an attack's damage+effects through the registry. Falls back to `legacy(ctx)` (the old
    heuristic path) for not-yet-implemented effects, so the sim keeps running while coverage grows."""
    key = normalize(attack.get('text'))
    ctx = EffectCtx(me, opp, attacker, defender, game, attack)
    if not key:
        return ctx.base                       # vanilla: damage only
    fn = ATTACK_EFFECTS.get(key)
    if fn is not None:
        return fn(ctx)
    return legacy(ctx) if legacy else ctx.base


# ================================================================ PROOF BATCH
# The ~20 most common effects across the pool, covering every major mechanic class. Each is unit-tested
# in test_effects.py. The remaining ~560 distinct effects follow these same patterns.

@effect("This Pokémon also does 10 damage to itself.")
def _self_10(ctx):
    ctx.self_damage(10); return ctx.base


@effect("This Pokémon also does 20 damage to itself.")
def _self_20(ctx):
    ctx.self_damage(20); return ctx.base


@effect("This Pokémon also does 30 damage to itself.")
def _self_30(ctx):
    ctx.self_damage(30); return ctx.base


@effect("Flip a coin. If tails, this attack does nothing.")
def _tails_nothing(ctx):
    return ctx.base if ctx.flip() else 0


@effect("Flip a coin. If heads, this attack does 20 more damage.")
def _heads_plus_20(ctx):
    return ctx.base + (20 if ctx.flip() else 0)


@effect("Flip a coin. If heads, this attack does 30 more damage.")
def _heads_plus_30(ctx):
    return ctx.base + (30 if ctx.flip() else 0)


@effect("Flip 2 coins. This attack does 20 damage for each heads.")
def _2coins_20(ctx):
    return 20 * ctx.flips(2)


@effect("Flip 2 coins. This attack does 30 more damage for each heads.")
def _2coins_plus_30(ctx):
    return ctx.base + 30 * ctx.flips(2)


@effect("Flip a coin until you get tails. This attack does 20 damage for each heads.")
def _until_tails_20(ctx):
    return 20 * ctx.flips_until_tails()


@effect("Flip a coin. If heads, your opponent's Active Pokémon is now Paralyzed.")
def _heads_paralyze(ctx):
    if ctx.flip():
        ctx.status('Paralyzed')
    return ctx.base


@effect("Flip a coin. If heads, discard an Energy from your opponent's Active Pokémon.")
def _heads_discard_opp_energy(ctx):
    if ctx.flip():
        ctx.discard_energy_defender(1)
    return ctx.base


@effect("Your opponent's Active Pokémon is now Paralyzed.")
def _paralyze(ctx):
    ctx.status('Paralyzed'); return ctx.base


@effect("Your opponent's Active Pokémon is now Confused.")
def _confuse(ctx):
    ctx.status('Confused'); return ctx.base


@effect("Your opponent's Active Pokémon is now Poisoned.")
def _poison(ctx):
    ctx.status('Poisoned'); return ctx.base


@effect("Your opponent's Active Pokémon is now Asleep.")
def _sleep(ctx):
    ctx.status('Asleep'); return ctx.base


@effect("Heal 20 damage from this Pokémon.")
def _heal_20(ctx):
    ctx.heal(20); return ctx.base


@effect("Heal 30 damage from this Pokémon.")
def _heal_30(ctx):
    ctx.heal(30); return ctx.base


@effect("Discard an Energy from this Pokémon.")
def _discard_self_1(ctx):
    ctx.discard_energy_self(1); return ctx.base


@effect("Discard 2 Energy from this Pokémon.")
def _discard_self_2(ctx):
    ctx.discard_energy_self(2); return ctx.base


@effect("During your next turn, this Pokémon can't attack.")
def _cant_attack_next(ctx):
    ctx.cant_attack_next(); return ctx.base


@effect("During your opponent's next turn, the Defending Pokémon can't retreat.")
def _defender_no_retreat(ctx):
    ctx.defender_cant_retreat(); return ctx.base


@effect("Switch out your opponent's Active Pokémon to the Bench. (Your opponent chooses the new Active Pokémon.)")
def _switch_opp(ctx):
    ctx.switch_defender(); return ctx.base


@effect("Draw a card.")
def _draw_1(ctx):
    ctx.draw(1); return ctx.base


@effect("If your opponent doesn't have exactly 3 or 4 Prize cards remaining, this attack does nothing.")
def _fickle_spitting(ctx):
    return ctx.base if ctx.opp_prizes() in (3, 4) else 0     # <- the bug we found: was always-on 120


if __name__ == '__main__':
    print(f"{len(ATTACK_EFFECTS)} effects registered in the proof batch")
