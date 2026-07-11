#!/usr/bin/env python3
"""Exact-ability-text -> effect registry, the ability counterpart of attack_effects.py. Abilities are
not one-shot like attacks: they hook the engine at different points depending on KIND. Each ability is
registered with its kind + a lambda whose signature matches that kind's hook, and the engine queries the
registry at the matching moment. Coverage is a hard invariant (coverage_abilities.py).

Kinds & hook signatures
-----------------------
  passive_hp   fn(mon, owner, game) -> int          extra max HP for `mon` (queried in Mon.max_hp)
  passive_dr   fn(dmg, atk, dfn, dfn_owner, game)->int   reduce incoming damage (queried in incoming_damage)
  immunity     fn(atk, dfn, dfn_owner, game) -> bool  True => this attack does 0 to dfn (queried pre-damage)
  attack_buff  fn(atk_mon, dfn_mon, attack, game)->int   bonus damage YOUR attacks deal (queried in resolve)
  retreat_mod  fn(mon, owner, game) -> int            delta to retreat cost (queried in eff_retreat)
  activated    fn(actx) -> bool                       once-per-turn player action (run in the turn); True if used
  on_damaged   fn(atk_mon, dfn_mon, dfn_owner, game)  reaction when dfn is damaged by an attack (Poison Point)
  between_turns fn(mon, owner, game)                  runs during Pokemon Checkup
  lock         fn(mon, owner, opp, game) -> bool      True => opponents' matching abilities stop working
"""
import re

_LEAD = re.compile(r'^\s*-\s*')


def normalize(text):
    """Collapse whitespace + strip a leading bullet. Ability text keeps its 'Name: -' prefix (unique key)."""
    t = _LEAD.sub('', (text or '').strip())
    return ' '.join(t.split())


ABILITY_EFFECTS = {}          # normalized text -> {'kind': str, 'fn': callable}
KINDS = ('passive_hp', 'passive_dr', 'immunity', 'attack_buff', 'retreat_mod',
         'activated', 'on_damaged', 'between_turns', 'lock')


def ability(kind, *texts):
    """Register a lambda of the given KIND under one or more exact ability texts."""
    assert kind in KINDS, kind
    def deco(fn):
        for t in texts:
            key = normalize(t)
            if key in ABILITY_EFFECTS:
                raise ValueError(f"duplicate ability registration: {key!r}")
            entry = {'kind': kind, 'fn': fn}
            if kind == 'passive_dr':
                # 'team' auras ("all of your Pokémon take N less") reduce damage to ANY teammate;
                # 'self' DR only to the holder. The query gates self-DR to dfn-is-holder.
                entry['scope'] = 'team' if 'all of your' in key.lower() else 'self'
            ABILITY_EFFECTS[key] = entry
        return fn
    return deco


class ActivatedCtx:
    """Context for an activated/triggered ability, centered on the holder Mon."""
    def __init__(self, me, opp, mon, game):
        self.me, self.opp, self.mon, self.game = me, opp, mon, game
        self.rng = game.rng

    def flip(self):
        return self.rng.random() < 0.5

    def draw(self, n=1):
        self.me.draw(n)

    def put_counters(self, n, mon):
        mon.damage += 10 * n

    def heal(self, n, mon=None):
        m = mon or self.mon
        m.damage = max(0, m.damage - n)

    def attach_energy(self, etype, mon, source='discard'):
        """Attach one basic `etype` energy to `mon` from the discard (or 'hand'/'deck' pool)."""
        if source == 'discard' and self.me.disc_energy.get(etype, 0) > 0:
            self.me.disc_energy[etype] -= 1
        mon.energy[etype] += 1


# ---------------- engine query API ----------------
def _entries(mon, kind):
    for ab in mon.card.abilities:
        e = ABILITY_EFFECTS.get(normalize(ab['text']))
        if e and e['kind'] == kind:
            yield e['fn']


def hp_bonus(mon, owner, game):
    return sum(fn(mon, owner, game) for m in owner.all_mons() for fn in _entries(m, 'passive_hp'))


def _dr_entries(mon):
    for ab in mon.card.abilities:
        e = ABILITY_EFFECTS.get(normalize(ab['text']))
        if e and e['kind'] == 'passive_dr':
            yield e['fn'], e.get('scope', 'self')


def reduce_damage(dmg, atk, dfn, dfn_owner, game):
    """Apply DR auras across the defending team: 'team' auras reduce any teammate's incoming damage;
    'self' DR applies only when the holder itself is the one being hit."""
    for holder in dfn_owner.all_mons():
        for fn, scope in _dr_entries(holder):
            if scope == 'self' and dfn is not holder:
                continue
            dmg = fn(dmg, atk, dfn, dfn_owner, game)
    return max(0, dmg)


def is_immune(atk, dfn, dfn_owner, game):
    return any(fn(atk, dfn, dfn_owner, game) for m in dfn_owner.all_mons() for fn in _entries(m, 'immunity'))


def attack_bonus(atk_mon, dfn_mon, attack, game):
    return sum(fn(atk_mon, dfn_mon, attack, game) for fn in _entries(atk_mon, 'attack_buff'))


def retreat_delta(mon, owner, game):
    return sum(fn(mon, owner, game) for fn in _entries(mon, 'retreat_mod'))


def run_between_turns(mon, owner, game):
    for fn in _entries(mon, 'between_turns'):
        fn(mon, owner, game)


def on_damaged(atk_mon, dfn_mon, dfn_owner, game):
    for fn in _entries(dfn_mon, 'on_damaged'):
        fn(atk_mon, dfn_mon, dfn_owner, game)


# ================================================================ PROOF BATCH
@ability('passive_dr', "- This Pokémon takes 30 less damage from attacks (after applying Weakness and Resistance).")
def _thicket(dmg, atk, dfn, owner, game):
    return dmg - 30


@ability('passive_dr', "- This Pokémon takes 20 less damage from attacks (after applying Weakness and Resistance).")
def _exoskeleton(dmg, atk, dfn, owner, game):
    return dmg - 20


@ability('on_damaged', "- If this Pokémon is in the Active Spot and is damaged by an attack from your opponent's Pokémon (even if this Pokémon is Knocked Out), the Attacking Pokémon is now Poisoned.")
def _poison_point(atk_mon, dfn_mon, owner, game):
    if dfn_mon is owner.active and not atk_mon.effect_immune():
        atk_mon.status['Poisoned'] = True


@ability('activated', "- Once during your turn, you may look at the top 2 cards of your deck and put 1 of them into your hand. Put the other card on the bottom of your deck.")
def _recon(actx):
    if len(actx.me.deck) >= 1:
        actx.me.hand.append(actx.me.deck.pop())
        if actx.me.deck:
            actx.me.deck.insert(0, actx.me.deck.pop())
        return True
    return False


@ability('activated', "- Once during your turn, you may put 5 damage counters on 1 of your opponent's Pokémon. If you use this Ability, this Pokémon is Knocked Out.")
def _cursed_blast(actx):
    targets = actx.opp.all_mons()
    if not targets:
        return False
    tgt = max(targets, key=lambda m: m.hp_left)      # counters onto the healthiest (softening a wall)
    actx.put_counters(5, tgt)
    actx.mon.damage = actx.mon.max_hp                # self-KO
    return True


if __name__ == '__main__':
    print(f"{len(ABILITY_EFFECTS)} abilities registered in the proof batch")
