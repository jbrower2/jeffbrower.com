#!/usr/bin/env python3
"""Exact-trainer-text -> effect registry, the Trainer counterpart of attack_effects / ability_effects.
Replaces the heuristic _tcat/_do_* resolver in engine.py. Trainers span four play-types, so (like
abilities) each effect is registered with a KIND whose lambda signature matches how the engine uses it:

  item / supporter   fn(tctx) -> bool     immediate action when played (True if it did something).
                                          Supporters are 1/turn; Items unlimited. tctx = TrainerCtx.
  stadium            fn(tctx) -> bool      the "Once during each player's turn, may ..." action a
                                          Stadium grants (played to the board; its presence is game.stadium).
  --- Tools attach to a Pokémon (mon.tools) and behave like abilities on the holder: ---
  tool_hp            fn(mon, owner, game) -> int             extra max HP
  tool_dr            fn(dmg, atk, dfn, dfn_owner, game) -> int   reduce incoming damage to the holder
  tool_ondamaged     fn(atk_mon, dfn_mon, dfn_owner, game)   reaction when the holder is damaged
  tool_attack_buff   fn(atk_mon, dfn_mon, attack, game) -> int   bonus damage the holder's attacks deal
  tool_retreat       fn(mon, owner, game) -> int             retreat-cost delta for the holder
"""
import re

ACTION_KINDS = ('item', 'supporter', 'stadium')
TOOL_KINDS = ('tool_hp', 'tool_dr', 'tool_ondamaged', 'tool_attack_buff', 'tool_retreat')
_LEAD = re.compile(r'^\s*-\s*')


def normalize(text):
    return ' '.join(_LEAD.sub('', (text or '').strip()).split())


TRAINER_EFFECTS = {}          # normalized text -> {'kind': str, 'fn': callable}


def trainer(kind, *texts):
    assert kind in ACTION_KINDS + TOOL_KINDS, kind
    def deco(fn):
        for t in texts:
            key = normalize(t)
            if key in TRAINER_EFFECTS:
                raise ValueError(f"duplicate trainer registration: {key!r}")
            TRAINER_EFFECTS[key] = {'kind': kind, 'fn': fn}
        return fn
    return deco


class TrainerCtx:
    """Context for an Item/Supporter/Stadium action, centered on the player who plays it."""
    def __init__(self, me, opp, game):
        self.me, self.opp, self.game = me, opp, game
        self.rng = game.rng

    # -- cards --
    def draw(self, n=1):
        self.me.draw(n)

    def discard_hand(self):
        n = len(self.me.hand); self.me.discard += self.me.hand; self.me.hand = []; return n

    def shuffle_hand_into_deck(self):
        self.me.deck += self.me.hand; self.me.hand = []; self.rng.shuffle(self.me.deck)

    def search_pokemon(self, pred, n=1, to_bench=False):
        if to_bench:
            return self.game._search_basics_to_bench(self.me, pred, n)
        return self.game._search_deck_to_hand(self.me, lambda t: t[0] == 'P' and pred(t[1]), n)

    def search_energy(self, n=1):
        return self.game._search_deck_to_hand(self.me, lambda t: t[0] == 'E', n)

    def recover_from_discard(self, pred):
        hit = next((x for x in self.me.discard if pred(x)), None)
        if hit:
            self.me.discard.remove(hit); self.me.hand.append(hit); return True
        return False

    # -- board / mons --
    def gust(self):
        return self.game._gust(self.me, self.opp)

    def switch_self(self):
        if self.me.bench:
            self.me.bench.append(self.me.active); self.me.promote(); return True
        return False

    def heal(self, n, each=False):
        tgts = self.me.all_mons() if each else [max(self.me.all_mons(), key=lambda m: m.damage, default=None)]
        did = False
        for m in tgts:
            if m and m.damage > 0:
                m.damage = max(0, m.damage - n); did = True
        return did

    def accel_from_discard(self, etype, mon, n=1):
        did = 0
        while did < n and self.me.disc_energy.get(etype, 0) > 0:
            self.me.disc_energy[etype] -= 1; mon.energy[etype] += 1; did += 1
        return did

    def opp_mill(self, n=1):
        for _ in range(n):
            if self.opp.deck:
                self.opp.discard.append(self.opp.deck.pop())

    def primary(self):
        return self.game.primary(self.me) or self.me.active


# ---------------- engine query API (tools; mirrors ability_effects) ----------------
def _tool_fns(mon, kind):
    for name in mon.tools:
        e = TRAINER_EFFECTS.get(normalize(_TOOL_TEXT.get(name, name)))
        if e and e['kind'] == kind:
            yield e['fn']


_TOOL_TEXT = {}          # tool card name -> its effect text (filled by load, so mon.tools[name] resolves)


def register_tool_texts(name_to_text):
    _TOOL_TEXT.update(name_to_text)


def tool_hp(mon, owner, game):
    return sum(fn(mon, owner, game) for fn in _tool_fns(mon, 'tool_hp'))


def tool_reduce(dmg, atk, dfn, dfn_owner, game):
    for fn in _tool_fns(dfn, 'tool_dr'):
        dmg = fn(dmg, atk, dfn, dfn_owner, game)
    return dmg


def tool_on_damaged(atk_mon, dfn_mon, dfn_owner, game):
    for fn in _tool_fns(dfn_mon, 'tool_ondamaged'):
        fn(atk_mon, dfn_mon, dfn_owner, game)


def tool_attack_bonus(atk_mon, dfn_mon, attack, game):
    return sum(fn(atk_mon, dfn_mon, attack, game) for fn in _tool_fns(atk_mon, 'tool_attack_buff'))


def resolve_action(me, opp, game, text):
    """Run an Item/Supporter/Stadium action by exact text. Returns (did_something, kind) or (None, None)."""
    e = TRAINER_EFFECTS.get(normalize(text))
    if e and e['kind'] in ACTION_KINDS:
        return bool(e['fn'](TrainerCtx(me, opp, game))), e['kind']
    return None, None


# ================================================================ PROOF BATCH
@trainer('supporter', "- Draw 3 cards.")
def _draw3(t):
    t.draw(3); return True


@trainer('supporter', "- Each player shuffles their hand into their deck. Then, you draw 5 cards and your opponent draws 4 cards.")
def _iono(t):
    t.shuffle_hand_into_deck()
    t.opp.deck += t.opp.hand; t.opp.hand = []; t.rng.shuffle(t.opp.deck)
    t.draw(5); [t.opp.hand.append(t.opp.deck.pop()) for _ in range(4) if t.opp.deck]
    return True


@trainer('item', "- Search your deck for a Pokémon, reveal it, and put it into your hand. Then, shuffle your deck.")
def _pokeball(t):
    return t.search_pokemon(lambda c: True, 1) > 0


@trainer('item', "- Heal 30 damage from 1 of your Pokémon.")
def _potion(t):
    return t.heal(30)


@trainer('tool_hp', "- The Pokémon this card is attached to gets +20 HP.")
def _hp20(mon, owner, game):
    return 20


@trainer('tool_dr', "- The Pokémon this Pokémon Tool is attached to takes 30 less damage from attacks from your opponent's Pokémon (after applying Weakness and Resistance).")
def _defender_dr(dmg, atk, dfn, owner, game):
    return dmg - 30


if __name__ == '__main__':
    print(f"{len(TRAINER_EFFECTS)} trainer effects registered in the proof batch")
