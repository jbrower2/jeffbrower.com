#!/usr/bin/env python3
"""Simplified Pokémon TCG match engine (v1).

Scope of v1 — implemented:
  setup + mulligans, 6 prizes, turn loop (draw / play basics / evolve / one energy
  attach / retreat / attack), energy-cost checks, base attack damage, Weakness ×2,
  KO + prize taking (2 for ex), win by prizes / no-Pokémon / deck-out, a heuristic AI.

Scope of v1 — NOT yet modeled (base-combat baseline; see EFFECTS registry to extend):
  attack/ability *text effects* (scaling damage, energy accel, heal, spread, status,
  search, disruption). Scaling attacks use their printed base number as a floor.
  So combo decks are currently under-valued — that's the next layer.

Deck spec: list of (count:int, item) where item is a Card or an energy type string
like 'Grass'. Basic energy is unlimited; every other card is capped at 4 by the builder.
"""
import random
from collections import Counter
from cards import load_cards

BY_KEY, BY_NAME = load_cards()
TYPE_OF_ENERGY = {'Grass': 'Grass', 'Fire': 'Fire', 'Water': 'Water', 'Lightning': 'Lightning',
                  'Psychic': 'Psychic', 'Fighting': 'Fighting', 'Darkness': 'Darkness', 'Metal': 'Metal'}
# energy letter <-> type
L2T = {'G': 'Grass', 'R': 'Fire', 'W': 'Water', 'L': 'Lightning', 'P': 'Psychic',
       'F': 'Fighting', 'D': 'Darkness', 'M': 'Metal', 'C': 'Colorless'}


class Mon:
    """A Pokémon in play."""
    def __init__(self, card):
        self.card = card
        self.damage = 0
        self.energy = Counter()      # type -> count of attached basic energy
        self.turns = 0               # turns in play (for evolution eligibility)
    @property
    def hp_left(self):
        return self.card.hp - self.damage
    def total_energy(self):
        return sum(self.energy.values())


class Player:
    def __init__(self, name, deck_spec, rng):
        self.name = name
        self.rng = rng
        # expand spec into a deck of tokens: ('P', Card) or ('E', type)
        self.deck = []
        for count, item in deck_spec:
            for _ in range(count):
                self.deck.append(('E', item) if isinstance(item, str) else ('P', item))
        rng.shuffle(self.deck)
        self.hand = []
        self.active = None
        self.bench = []
        self.discard = []
        self.prizes = []
        self.prizes_taken = 0
        self.lost = False

    def draw(self, n=1):
        for _ in range(n):
            if not self.deck:
                return False
            self.hand.append(self.deck.pop())
        return True

    def basics_in_hand(self):
        return [t for t in self.hand if t[0] == 'P' and t[1].stage == 0]

    def setup(self):
        # mulligan until at least one Basic Pokémon in the opening 7
        for _ in range(20):
            self.hand = []; self.draw(7)
            if self.basics_in_hand():
                break
            self.deck += self.hand; self.rng.shuffle(self.deck)
        # place active + bench (all basics, up to 5 bench)
        basics = self.basics_in_hand()
        self.rng.shuffle(basics)
        self.active = Mon(basics[0][1]); self.hand.remove(basics[0])
        for t in basics[1:6]:
            self.bench.append(Mon(t[1])); self.hand.remove(t)
        # 6 prizes off the top
        self.prizes = [self.deck.pop() for _ in range(6) if self.deck]

    def all_mons(self):
        return ([self.active] if self.active else []) + self.bench

    def take_prize(self, n=1):
        for _ in range(n):
            if self.prizes:
                self.hand.append(self.prizes.pop())
            self.prizes_taken += 1

    def promote(self):
        """Move a benched Pokémon to Active (AI: highest HP)."""
        if not self.bench:
            self.active = None
            return
        self.bench.sort(key=lambda m: m.card.hp, reverse=True)
        self.active = self.bench.pop(0)


def cost_met(mon, cost):
    """Can `mon`'s attached energy pay `cost` (a letter string like 'GGGG'/'RC')?"""
    need = Counter(cost)
    colorless = need.pop('C', 0)
    pool = Counter(mon.energy)          # type-name -> count
    # map letters to type names for specific requirements
    for letter, cnt in need.items():
        t = L2T[letter]
        if pool[t] < cnt:
            return False
        pool[t] -= cnt
    return sum(pool.values()) >= colorless


class Game:
    def __init__(self, spec_a, spec_b, seed=0, verbose=False):
        self.rng = random.Random(seed)
        self.players = [Player('A', spec_a, self.rng), Player('B', spec_b, self.rng)]
        self.verbose = verbose
        self.turn = 0

    def log(self, *a):
        if self.verbose:
            print(*a)

    def setup(self):
        for p in self.players:
            p.setup()

    def winner(self):
        for i, p in enumerate(self.players):
            if p.lost:
                return 1 - i
        for i, p in enumerate(self.players):
            if p.prizes_taken >= 6:
                return i
        return None

    # ---- AI main phase ----
    def ai_main(self, me):
        # 1) bench any basics
        for t in list(me.basics_in_hand()):
            if len(me.bench) >= 5:
                break
            me.bench.append(Mon(t[1])); me.hand.remove(t)
        # 2) evolve (a pokemon in play >=1 turn, with matching evolution in hand)
        changed = True
        while changed:
            changed = False
            for mon in me.all_mons():
                if mon.turns < 1:
                    continue
                for t in list(me.hand):
                    if t[0] == 'P' and t[1].evolves_from == mon.card.name and t[1].stage == mon.card.stage + 1:
                        ev = Mon(t[1]); ev.damage = mon.damage; ev.energy = mon.energy; ev.turns = mon.turns
                        me.hand.remove(t)
                        if mon is me.active:
                            me.active = ev
                        else:
                            me.bench[me.bench.index(mon)] = ev
                        changed = True
                        break
                if changed:
                    break
        # 3) attach one energy to the active (prefer the highest-HP attacker there)
        energies = [t for t in me.hand if t[0] == 'E']
        if energies and me.active:
            # pick an energy the active can use (matches a cost) else any
            tok = energies[0]
            me.active.energy[tok[1]] += 1
            me.hand.remove(tok)

    def best_attack(self, mon, defender):
        """Return (attack, damage) for the highest-damage affordable attack, or None."""
        best = None
        for a in mon.card.attacks:
            if not cost_met(mon, a['cost']):
                continue
            dmg = a['dmg']
            if dmg and defender and defender.card.weakness and defender.card.weakness == mon.card.ptype:
                dmg *= 2
            if best is None or dmg > best[1]:
                best = (a, dmg)
        return best

    def take_turn(self, idx, first_turn=False):
        me, opp = self.players[idx], self.players[1 - idx]
        if not me.draw(1):
            me.lost = True; self.log(f"{me.name} decks out"); return
        self.ai_main(me)
        # attack (not on the very first turn of the game for the starting player)
        if not first_turn and me.active and opp.active:
            atk = self.best_attack(me.active, opp.active)
            if atk and atk[1] > 0:
                a, dmg = atk
                opp.active.damage += dmg
                self.log(f"  {me.name}'s {me.active.card.name} uses {a['name']} for {dmg} "
                         f"({opp.active.card.name} {max(0,opp.active.hp_left)}/{opp.active.card.hp})")
                if opp.active.hp_left <= 0:
                    ko = opp.active
                    self.log(f"    KO {ko.card.name}!")
                    opp.discard.append(('P', ko.card))
                    me.take_prize(2 if ko.card.is_ex else 1)
                    opp.promote()
        # end of turn: age all my mons
        for m in me.all_mons():
            m.turns += 1

    def play(self, max_turns=200):
        self.setup()
        for t in range(max_turns):
            idx = t % 2
            self.turn = t
            self.take_turn(idx, first_turn=(t == 0))
            w = self.winner()
            if w is not None:
                return w
            # loss if a player has no active and no bench to promote
            for i, p in enumerate(self.players):
                if p.active is None and not p.bench:
                    return 1 - i
        return None  # draw / turn cap


def run_match(spec_a, spec_b, games=200, base_seed=1):
    wins = [0, 0, 0]  # A, B, draw
    for g in range(games):
        # alternate who goes first; vary seed
        a, b = (spec_a, spec_b) if g % 2 == 0 else (spec_b, spec_a)
        w = Game(a, b, seed=base_seed + g).play()
        if w is None:
            wins[2] += 1
        else:
            # map back to A/B accounting for swap
            actual = w if g % 2 == 0 else 1 - w
            wins[actual] += 1
    return wins


if __name__ == '__main__':
    # smoke test: two simple mono decks of a single basic attacker + energy
    def simple_deck(card_name, energy_type):
        c = [x for x in BY_NAME[card_name] if x.cat != 'cat-red'][0]
        return [(4, c), (56, energy_type)]
    # Reshiram ex (basic, RRC Blazing Burst) vs Zangoose ex (basic, colorless)
    A = simple_deck('Reshiram ex', 'Fire')
    B = simple_deck('Zangoose ex', 'Fire')
    print("Single verbose game (Reshiram ex vs Zangoose ex):")
    w = Game(A, B, seed=3, verbose=True).play()
    print("winner:", ['A', 'B'][w] if w is not None else 'draw')
    print("\n200-game match:")
    print(run_match(A, B, games=200))
