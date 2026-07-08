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
import effects

BY_KEY, BY_NAME = load_cards()
TYPE_OF_ENERGY = {'Grass': 'Grass', 'Fire': 'Fire', 'Water': 'Water', 'Lightning': 'Lightning',
                  'Psychic': 'Psychic', 'Fighting': 'Fighting', 'Darkness': 'Darkness', 'Metal': 'Metal'}
# energy letter <-> type
L2T = {'G': 'Grass', 'R': 'Fire', 'W': 'Water', 'L': 'Lightning', 'P': 'Psychic',
       'F': 'Fighting', 'D': 'Darkness', 'M': 'Metal', 'C': 'Colorless'}
T2L = {v: k for k, v in L2T.items()}


class Mon:
    """A Pokémon in play."""
    def __init__(self, card):
        self.card = card
        self.damage = 0
        self.energy = Counter()      # type -> count of attached basic energy
        self.turns = 0               # turns in play (for evolution eligibility)
        self.came_from_bench = False # moved bench->active this turn (for Gale-Thrust-style bonuses)
        self.cd_name = None          # attack name (or 'ALL') on cooldown
        self.cd_turn = -1            # game turn the cooldown was set
        self.status = {}             # special conditions: Burned/Poisoned/Asleep/Paralyzed/Confused
        self.poison_amt = 10         # poison damage per checkup (raised by heavy-poison attacks)
        self.dr_amount = 0           # temporary damage reduction amount
        self.dr_turn = -9            # game turn the temp reduction was set (applies the turn after)
    @property
    def hp_left(self):
        return self.card.hp - self.damage
    def total_energy(self):
        return sum(self.energy.values())


class Player:
    def __init__(self, name, deck, rng):
        self.name = name
        self.rng = rng
        spec, self.ace_key = deck            # deck = (spec, ace_key)
        # expand spec into a deck of tokens: ('P', Card) or ('E', type)
        self.deck = []
        for count, item in spec:
            for _ in range(count):
                self.deck.append(('E', item) if isinstance(item, str) else ('P', item))
        rng.shuffle(self.deck)
        self.hand = []
        self.active = None
        self.bench = []
        self.discard = []
        self.disc_energy = Counter()   # basic energy in the discard pile, by type
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
        """Move a benched Pokémon to Active: the readiest attacker (most energy, then HP)."""
        if not self.bench:
            self.active = None
            return
        self.bench.sort(key=lambda m: (m.total_energy(), m.card.hp), reverse=True)
        self.active = self.bench.pop(0)
        self.active.came_from_bench = True


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
    def __init__(self, deck_a, deck_b, seed=0, verbose=False):
        self.rng = random.Random(seed)
        self.players = [Player('A', deck_a, self.rng), Player('B', deck_b, self.rng)]
        self.verbose = verbose
        self.turn = 0

    def log(self, *a):
        if self.verbose:
            print(*a)

    def setup(self):
        for p in self.players:
            p.setup()

    def is_ko(self, mon, owner):
        return mon.damage >= mon.card.hp + effects.team_hp_bonus(owner)

    def winner(self):
        for i, p in enumerate(self.players):
            if p.lost:
                return 1 - i
        for i, p in enumerate(self.players):
            if p.prizes_taken >= 6:
                return i
        return None

    # ---- AI main phase ----
    # ---- AI helpers ----
    def ace_mon(self, me):
        return next((m for m in me.all_mons() if m.card.key == me.ace_key), None)

    def _dmg_attacks(self, mon):
        return [a for a in mon.card.attacks if a['dmg'] > 0 or 'is now' in a['text'].lower()]

    def _cheapest_cost(self, mon):
        atks = self._dmg_attacks(mon)
        return min((a['cost'] for a in atks), key=len) if atks else None

    def _fundable(self, mon):
        return any(cost_met(mon, a['cost']) for a in self._dmg_attacks(mon))

    def evolve_all(self, me):
        changed = True
        while changed:
            changed = False
            for mon in me.all_mons():
                if mon.turns < 1:
                    continue
                for t in list(me.hand):
                    if t[0] == 'P' and t[1].evolves_from == mon.card.name and t[1].stage == mon.card.stage + 1:
                        ev = Mon(t[1])
                        ev.damage = mon.damage; ev.energy = mon.energy; ev.turns = mon.turns
                        ev.status = mon.status; ev.poison_amt = mon.poison_amt
                        me.hand.remove(t)
                        if mon is me.active:
                            me.active = ev
                        else:
                            me.bench[me.bench.index(mon)] = ev
                        changed = True
                        break
                if changed:
                    break

    def attach_energy(self, me):
        toks = [t for t in me.hand if t[0] == 'E']
        if not toks or not me.all_mons():
            return
        ace = self.ace_mon(me)
        # build the ace first (even benched); once it can attack, top up the active
        target = ace if (ace and not self._fundable(ace)) else me.active
        target = target or me.active or (me.bench[0] if me.bench else None)
        if target is None:
            return
        need = self._cheapest_cost(target)
        pick = None
        if need:
            for t in toks:
                letter = T2L.get(t[1])
                if letter and letter in need and target.energy.get(t[1], 0) < need.count(letter):
                    pick = t; break
        pick = pick or toks[0]
        target.energy[pick[1]] += 1; me.hand.remove(pick)

    def maybe_retreat(self, me, opp):
        if not me.active:
            return
        ace = self.ace_mon(me)
        desired = None
        if ace and ace in me.bench and self._fundable(ace):
            desired = ace                                   # promote a ready ace
        elif not self._fundable(me.active):
            ready = [m for m in me.bench if self._fundable(m)]
            if ready:
                desired = max(ready, key=lambda m: (self.best_attack(me, opp, m, opp.active) or (None, 0, 0))[2])
        if desired and desired is not me.active and me.active.total_energy() >= me.active.card.retreat:
            for _ in range(me.active.card.retreat):         # pay retreat by discarding energy
                t = max(me.active.energy, key=lambda k: me.active.energy[k])
                me.active.energy[t] -= 1
                if me.active.energy[t] <= 0: del me.active.energy[t]
                me.disc_energy[t] += 1
            old = me.active
            me.bench.remove(desired); me.bench.append(old)
            me.active = desired; desired.came_from_bench = True

    def ai_main(self, me, opp):
        for m in me.all_mons():
            m.came_from_bench = False
        for t in list(me.basics_in_hand()):                 # bench basics
            if len(me.bench) >= 5:
                break
            me.bench.append(Mon(t[1])); me.hand.remove(t)
        self.evolve_all(me)                                 # evolve (ace line included)
        for mon in me.all_mons():                           # abilities: accel / heal
            if effects.abilities_disabled(mon, me, opp):
                continue
            for ab in mon.card.abilities:
                h = effects.ABILITY_ACCEL.get(ab['name']) or effects.HEAL_ABILITIES.get(ab['name'])
                if h:
                    h(me, opp, mon, self)
        self.attach_energy(me)                              # fund the ace / active
        self.maybe_retreat(me, opp)                         # promote the best attacker

    def best_attack(self, me, opp, mon, defender):
        """Best affordable, non-cooldowned attack -> (attack, actual_damage, value) or None.
        Selection uses `value` (damage + a bonus for status-inflicting attacks) so pure
        status attacks like poison get used; `actual_damage` is what's dealt."""
        best = None
        for a in mon.card.attacks:
            if not cost_met(mon, a['cost']):
                continue
            if mon.cd_turn + 2 == self.turn and mon.cd_name in ('ALL', a['name']):
                continue
            ctx = (me, opp, mon, defender, self)
            dmg = effects.scaling_damage(ctx, a)
            if dmg and defender and defender.card.weakness and defender.card.weakness == mon.card.ptype:
                dmg *= 2
            txt = a['text'].lower()
            value = dmg + (25 if 'is now' in txt else 0)
            if dmg < 20 and effects.is_utility(a):          # draw/search setup, as a fallback
                value = max(value, 18)
            if best is None or value > best[2]:
                best = (a, dmg, value)
        return best

    def take_turn(self, idx, first_turn=False):
        me, opp = self.players[idx], self.players[1 - idx]
        if not me.draw(1):
            me.lost = True; self.log(f"{me.name} decks out"); return
        self.ai_main(me, opp)
        # attack (not on the very first turn of the game for the starting player)
        if not first_turn and me.active and opp.active and effects.can_attack(me.active, self.rng):
            atk = self.best_attack(me, opp, me.active, opp.active)
            if atk and atk[2] > 0:
                a, dmg, _ = atk
                ctx = (me, opp, me.active, opp.active, self)
                dmg = effects.incoming_damage(dmg, me.active, opp.active, opp, self)
                opp.active.damage += dmg
                self.log(f"  {me.name}'s {me.active.card.name} uses {a['name']} for {dmg} "
                         f"({opp.active.card.name} {max(0,opp.active.hp_left)}/{opp.active.card.hp})")
                effects.attack_side_effects(ctx, a)
                effects.apply_attack_status(ctx, a)
                effects.apply_attack_utility(ctx, a)
                for b in effects.apply_spread(ctx, a):           # bench spread KOs
                    if b in opp.bench:
                        for t, n in b.energy.items():
                            opp.disc_energy[t] += n
                        opp.discard.append(('P', b.card)); opp.bench.remove(b)
                        me.take_prize(2 if b.card.is_ex else 1)
                cd = effects.attack_cooldown(a)
                if cd:
                    me.active.cd_name = cd; me.active.cd_turn = self.turn
                if self.is_ko(opp.active, opp):                  # defender KO
                    ko = opp.active
                    self.log(f"    KO {ko.card.name}!")
                    for t, n in ko.energy.items():
                        opp.disc_energy[t] += n
                    opp.discard.append(('P', ko.card))
                    me.take_prize(2 if ko.card.is_ex else 1)
                    opp.promote()
                if me.active and self.is_ko(me.active, me):       # attacker self-KO (recoil)
                    ko = me.active
                    for t, n in ko.energy.items():
                        me.disc_energy[t] += n
                    me.discard.append(('P', ko.card))
                    opp.take_prize(2 if ko.card.is_ex else 1)
                    me.promote()
        # end of turn: age, clear my paralysis, run Pokémon Checkup on both actives
        for m in me.all_mons():
            m.turns += 1
        if me.active:
            effects.clear_paralysis(me.active)
        self._checkup()

    def _checkup(self):
        for i, p in enumerate(self.players):
            other = self.players[1 - i]
            if not p.active:
                continue
            effects.checkup(p.active, self.rng)
            if self.is_ko(p.active, p):
                ko = p.active
                for t, n in ko.energy.items():
                    p.disc_energy[t] += n
                p.discard.append(('P', ko.card))
                other.take_prize(2 if ko.card.is_ex else 1)
                p.promote()

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


def run_match(deck_a, deck_b, games=200, base_seed=1):
    wins = [0, 0, 0]  # A, B, draw
    for g in range(games):
        # alternate who goes first; vary seed
        a, b = (deck_a, deck_b) if g % 2 == 0 else (deck_b, deck_a)
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
        return ([(4, c), (56, energy_type)], c.key)
    # Reshiram ex (basic, RRC Blazing Burst) vs Zangoose ex (basic, colorless)
    A = simple_deck('Reshiram ex', 'Fire')
    B = simple_deck('Zangoose ex', 'Fire')
    print("Single verbose game (Reshiram ex vs Zangoose ex):")
    w = Game(A, B, seed=3, verbose=True).play()
    print("winner:", ['A', 'B'][w] if w is not None else 'draw')
    print("\n200-game match:")
    print(run_match(A, B, games=200))
