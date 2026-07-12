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
import json, os, random, re
from collections import Counter
from cards import load_cards
import effects
import attack_effects
import ability_effects
import trainer_effects
import special_energy as SE
# NOTE: the generated effect batches are loaded at the BOTTOM of this module (see _load_registries),
# after Mon/Player/Game are defined — some batches do `from engine import Mon`, so loading them up
# here would hit a partially-initialized module and silently drop the whole registry.

BY_KEY, BY_NAME = load_cards()
TYPE_OF_ENERGY = {'Grass': 'Grass', 'Fire': 'Fire', 'Water': 'Water', 'Lightning': 'Lightning',
                  'Psychic': 'Psychic', 'Fighting': 'Fighting', 'Darkness': 'Darkness', 'Metal': 'Metal'}
# energy letter <-> type
L2T = {'G': 'Grass', 'R': 'Fire', 'W': 'Water', 'L': 'Lightning', 'P': 'Psychic',
       'F': 'Fighting', 'D': 'Darkness', 'M': 'Metal', 'C': 'Colorless'}
T2L = {v: k for k, v in L2T.items()}
TRAINER_THRESH = 1.0     # min estimated board-position gain to play a Trainer (competitive-ish selection)


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
        self.special = []            # names of attached Special Energy (for riders/provision)
        self.ramp = {}               # attack name -> "during your next turn, this attack does N more" bonus
        self.ramp_turn = {}          # attack name -> turn that bonus was set (Game.ramp_bonus expires it after 1 turn)
        self.last_atk = None         # last attack name this Pokémon used (+ the game turn it used it)
        self.last_atk_turn = -9
        self.evolved_turn = -9       # game turn this Pokémon evolved (for "if it evolved this turn")
        self.tools = []              # names of Pokémon Tools attached
    @property
    def bonus_hp(self):
        return 20 * self.special.count('Growing Grass Energy')   # Growing Grass: +20 HP
    @property
    def max_hp(self):
        return self.card.hp + self.bonus_hp
    @property
    def hp_left(self):
        return self.max_hp - self.damage
    def eff_retreat(self):
        return 0 if 'Magnetic Metal Energy' in self.special else self.card.retreat
    def effect_immune(self):
        """Mist/Rocky Fighting shield opponent attack *effects*; Bubbly Water blocks conditions."""
        return any(s in ('Mist Energy', 'Rocky Fighting Energy', 'Bubbly Water Energy') for s in self.special)
    def total_energy(self):
        return sum(self.energy.values())


class Player:
    def __init__(self, name, deck, rng):
        self.name = name
        self.rng = rng
        spec, self.ace_key = deck            # deck = (spec, ace_key)
        # expand spec into tokens: ('P', Card) | ('E', type str) | ('T', trainer dict)
        self.deck = []
        for count, item in spec:
            for _ in range(count):
                if isinstance(item, str):
                    self.deck.append(('E', item))
                elif isinstance(item, dict):
                    self.deck.append(('S', item) if 'special_energy' in item else ('T', item))
                else:
                    self.deck.append(('P', item))
        rng.shuffle(self.deck)
        self.hand = []
        self.active = None
        self.bench = []
        self.discard = []
        self.disc_energy = Counter()   # basic energy in the discard pile, by type
        self.prizes = []
        self.prizes_taken = 0
        self.lost = False
        self.last_ko_turn = -9       # game turn this player last had a Pokémon KO'd by damage
        self.played = []             # names of Trainer cards this player played THIS turn (reset each turn)

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


def _clone_mon(m):
    if m is None:
        return None
    n = Mon.__new__(Mon)
    n.__dict__.update(m.__dict__)
    n.energy = Counter(m.energy); n.status = dict(m.status); n.special = list(m.special)
    n.ramp = dict(m.ramp); n.ramp_turn = dict(m.ramp_turn); n.tools = list(m.tools)
    return n


def _clone_player(p):
    n = Player.__new__(Player)
    n.__dict__.update(p.__dict__)
    n.hand = list(p.hand); n.deck = list(p.deck); n.discard = list(p.discard)
    n.disc_energy = Counter(p.disc_energy); n.prizes = list(p.prizes); n.played = list(p.played)
    n.active = _clone_mon(p.active); n.bench = [_clone_mon(b) for b in p.bench]
    return n


class _EstGame:
    """Throwaway Game stand-in for a non-mutating attack-damage estimate (best_attack). Carries only
    an rng + turn; effects that reach for real Game helper methods raise and fall back to the heuristic."""
    __slots__ = ('rng', 'turn', 'verbose', 'stats', 'stadium')

    def __init__(self, turn, stadium=None):
        self.rng = random.Random(turn * 2654435761 & 0xFFFFFFFF)
        self.turn = turn; self.verbose = False; self.stats = None; self.stadium = stadium


def cost_met(mon, cost):
    """Can `mon`'s attached energy pay `cost` (a letter string like 'GGGG'/'RC')?
    Pool keys are types plus two special-energy pseudo-types: 'Colorless' (pays {C} only)
    and 'Wild' (rainbow — pays any requirement)."""
    need = Counter(cost)
    colorless = need.pop('C', 0)
    pool = Counter(mon.energy)          # type-name -> count
    wild = pool.pop('Wild', 0)          # rainbow special energy: fills any requirement
    for letter, cnt in need.items():
        t = L2T[letter]
        use = min(pool.get(t, 0), cnt)
        pool[t] = pool.get(t, 0) - use; cnt -= use
        if cnt:                          # cover the typed shortfall with wild pips
            if wild >= cnt:
                wild -= cnt
            else:
                return False
    return sum(pool.values()) + wild >= colorless   # 'Colorless' pips count only here


class Game:
    def __init__(self, deck_a, deck_b, seed=0, verbose=False, stats=False):
        self.rng = random.Random(seed)
        self.players = [Player('A', deck_a, self.rng), Player('B', deck_b, self.rng)]
        self.verbose = verbose
        self.turn = 0
        self.stadium = None          # (name, owner_idx) of the Stadium in play, or None
        self.stats = [self._newstat(), self._newstat()] if stats else None

    @staticmethod
    def _newstat():
        return {'dmg_dealt': 0, 'dmg_taken': 0, 'attacks': 0}

    def log(self, *a):
        if self.verbose:
            print(*a)

    def setup(self):
        for p in self.players:
            p.setup()

    def is_ko(self, mon, owner):
        extra = (effects.team_hp_bonus(owner) + mon.bonus_hp                 # ability HP auras + Growing Grass
                 + ability_effects.hp_bonus(mon, owner, self)               # registry passive-HP abilities
                 + trainer_effects.tool_hp(mon, owner, self))               # Tool +HP (e.g. Defender)
        return mon.damage >= mon.card.hp + extra

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
    def primary(self, me):
        """The Pokémon to invest energy in this turn — the highest-ceiling attacker in play.
        Generic 'develop the biggest threat' pick; the deck has no designated ace. Prefers a fully
        evolved / high-damage Pokémon, tie-broken by energy already attached (finish what's started)."""
        mons = me.all_mons()
        if not mons:
            return None

        def ceiling(m):
            return max((a['dmg'] for a in m.card.attacks), default=0)
        cand = [m for m in mons if ceiling(m) > 0] or mons
        return max(cand, key=lambda m: (ceiling(m), m.card.stage, m.total_energy()))

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
                        ev.special = mon.special; ev.ramp = mon.ramp; ev.ramp_turn = mon.ramp_turn; ev.tools = mon.tools   # keep attached/accumulated state
                        ev.last_atk = mon.last_atk; ev.last_atk_turn = mon.last_atk_turn
                        ev.evolved_turn = self.turn
                        me.hand.remove(t)
                        if mon is me.active:
                            me.active = ev
                        else:
                            me.bench[me.bench.index(mon)] = ev
                        self.log(f"    evolve {mon.card.name} -> {ev.card.name}")
                        changed = True
                        break
                if changed:
                    break

    def attach_energy(self, me):
        etoks = [t for t in me.hand if t[0] == 'E']
        stoks = [t for t in me.hand if t[0] == 'S']
        if not (etoks or stoks) or not me.all_mons():
            return
        ace = self.primary(me)
        # build the ace first (even benched); once it can attack, top up the active
        target = ace if (ace and not self._fundable(ace)) else me.active
        target = target or me.active or (me.bench[0] if me.bench else None)
        if target is None:
            return
        need = self._cheapest_cost(target)
        # 1) a Special Energy that meaningfully advances this target's cost takes priority
        for t in stoks:
            prov = self._special_provides(t[1], target)
            if prov and self._prov_useful(prov, target, need):
                self._attach_special(me, target, t, prov)
                return
        # 2) otherwise the type-matched basic-energy pick
        pick = None
        if need:
            for t in etoks:
                letter = T2L.get(t[1])
                if letter and letter in need and target.energy.get(t[1], 0) < need.count(letter):
                    pick = t; break
        pick = pick or (etoks[0] if etoks else None)
        if pick is not None:
            target.energy[pick[1]] += 1; me.hand.remove(pick)
            self.log(f"    attach {pick[1]} Energy -> {target.card.name} (now {target.total_energy()} energy)")
            return
        # 3) only special energy left in hand — attach the first legal one
        for t in stoks:
            prov = self._special_provides(t[1], target)
            if prov:
                self._attach_special(me, target, t, prov)
                return

    def _special_provides(self, sdict, target):
        """Provision dict for attaching this special energy to `target`, or None if illegal."""
        name = sdict['special_energy']
        e = SE.SPECIAL_ENERGY[name]
        if e.get('constraint') == 'team_rocket' and not target.card.name.startswith("Team Rocket's"):
            return None
        return SE.provides(name, target.card)

    @staticmethod
    def _prov_useful(prov, target, need):
        """Attach a special energy proactively only if it fills a gap or accelerates."""
        if prov.get('Wild'):                            # rainbow always helps a typed cost
            return True
        if sum(prov.values()) >= 2:                     # 2-pip accel (Team Rocket's / Ignition-on-evo)
            return True
        if need:                                        # a typed pip matching an unmet requirement
            for t, c in prov.items():
                letter = T2L.get(t)
                if letter and letter in need and target.energy.get(t, 0) < need.count(letter):
                    return True
        return False

    def _attach_special(self, me, target, tok, prov):
        name = tok[1]['special_energy']
        for typ, c in prov.items():
            target.energy[typ] += c
        target.special.append(name)
        me.hand.remove(tok)
        if name == 'Telepathic Psychic Energy':         # on-attach: bench up to 2 Basic {P}
            self._search_basics_to_bench(me, lambda c: c.ptype == 'Psychic', 2)

    def maybe_retreat(self, me, opp):
        if not me.active:
            return
        ace = self.primary(me)
        desired = None
        if ace and ace in me.bench and self._fundable(ace):
            desired = ace                                   # promote a ready ace
        elif not self._fundable(me.active):
            ready = [m for m in me.bench if self._fundable(m)]
            if ready:
                desired = max(ready, key=lambda m: (self.best_attack(me, opp, m, opp.active) or (None, 0, 0))[2])
        if desired and desired is not me.active:
            sw = next((t for t in me.hand if t[0] == 'T' and t[1]['name'] == 'Switch'), None)
            if sw:                                          # free pivot via Switch item
                me.hand.remove(sw)
            elif me.active.total_energy() >= me.active.eff_retreat():
                for _ in range(me.active.eff_retreat()):    # pay retreat by discarding energy
                    t = max(me.active.energy, key=lambda k: me.active.energy[k])
                    me.active.energy[t] -= 1
                    if me.active.energy[t] <= 0: del me.active.energy[t]
                    me.disc_energy[t] += 1
            else:
                return
            old = me.active
            me.bench.remove(desired); me.bench.append(old)
            me.active = desired; desired.came_from_bench = True

    def _promote_if_idle(self, me, opp):
        """A cooldown attacker (used a 'can't use next turn' attack last turn) would otherwise sit
        idle this turn — if a benched Pokémon can attack usefully, promote it so the turn isn't wasted.
        Scoped to a mon that is *currently mid-cooldown*, so it never disrupts intentional walls."""
        if not me.active or not me.bench or me.active.cd_name is None:
            return
        if me.active.cd_turn + 2 != self.turn:                  # not disabled this turn
            return
        cur = self.best_attack(me, opp, me.active, opp.active)
        if cur and cur[2] > 0:                                  # active still has a useful non-cooldown attack
            return
        best = None
        for m in me.bench:
            b = self.best_attack(me, opp, m, opp.active)
            if b and b[2] > 0 and (best is None or b[2] > best[1]):
                best = (m, b[2])
        if best is None:
            return
        desired = best[0]
        sw = next((t for t in me.hand if t[0] == 'T' and t[1]['name'] == 'Switch'), None)
        if sw:
            me.hand.remove(sw)
        elif me.active.total_energy() >= me.active.eff_retreat():
            for _ in range(me.active.eff_retreat()):
                tk = max(me.active.energy, key=lambda k: me.active.energy[k])
                me.active.energy[tk] -= 1
                if me.active.energy[tk] <= 0:
                    del me.active.energy[tk]
                me.disc_energy[tk] += 1
        else:
            return
        old = me.active
        me.bench.remove(desired); me.bench.append(old)
        me.active = desired; desired.came_from_bench = True

    # ---------------- Trainers ----------------
    def _find_in_hand(self, me, pred):
        return next((t for t in me.hand if pred(t)), None)

    def _search_deck_to_hand(self, me, pred, n=1):
        got = 0
        for i in range(len(me.deck) - 1, -1, -1):
            if got >= n:
                break
            if pred(me.deck[i]):
                me.hand.append(me.deck.pop(i)); got += 1
        return got

    def _search_basics_to_bench(self, me, pred, n=2):
        got = 0
        for i in range(len(me.deck) - 1, -1, -1):
            if got >= n or len(me.bench) >= 5:
                break
            tok = me.deck[i]
            if tok[0] == 'P' and tok[1].stage == 0 and pred(tok[1]):
                me.bench.append(Mon(tok[1])); me.deck.pop(i); got += 1
        return got

    def _rare_candy(self, me):
        """Evolve a Basic in play straight to a Stage-2 in hand (skipping Stage 1)."""
        for t in list(me.hand):
            if t[0] != 'P' or t[1].stage != 2:
                continue
            s2 = t[1]
            s1 = BY_NAME.get(s2.evolves_from, [None])[0]
            basic = s1.evolves_from if s1 else None
            for mon in me.all_mons():
                if mon.turns >= 1 and mon.card.stage == 0 and mon.card.name in (basic, s2.evolves_from):
                    ev = Mon(s2)
                    ev.damage = mon.damage; ev.energy = mon.energy; ev.turns = mon.turns; ev.status = mon.status
                    me.hand.remove(t)
                    if mon is me.active:
                        me.active = ev
                    else:
                        me.bench[me.bench.index(mon)] = ev
                    return True
        return False

    def _gust(self, me, opp):
        """Boss's Orders: drag up an opponent's benched target we can KO this turn."""
        if not opp.bench or not me.active:
            return False
        cand = sorted(opp.bench, key=lambda m: (not m.card.is_ex, m.hp_left))
        cur = self.best_attack(me, opp, me.active, opp.active)
        cur_ko = cur and opp.active and cur[1] >= opp.active.hp_left
        for tgt in cand:
            ba = self.best_attack(me, opp, me.active, tgt)
            if ba and ba[1] >= tgt.hp_left and not cur_ko:
                opp.bench.remove(tgt); opp.bench.append(opp.active); opp.active = tgt
                return True
        return False

    # --- generic, text-driven Trainer resolvers (so per-deck tech works, not just the core) ---
    def _tcat(self, name, eff):
        e = eff.lower()
        if name == 'Rare Candy': return 'CANDY'
        if 'switch in 1 of your opponent' in e: return 'GUST'
        if 'switch your active' in e and 'bench' in e: return 'SWITCH'
        if 'attach' in e and 'energy' in e and ('from your discard' in e or 'search your deck' in e): return 'ACCEL'
        if 'onto your bench' in e and 'pok' in e: return 'BENCH'
        if 'search your deck' in e and 'pok' in e and 'into your hand' in e: return 'SEARCHPOKE'
        if 'search your deck' in e and 'energy' in e and 'into your hand' in e: return 'SEARCHNRG'
        if 'from your discard pile into your hand' in e: return 'RECOVER'
        if 'heal' in e and 'damage' in e: return 'HEAL'
        if 'draw' in e: return 'DRAW'
        return 'OTHER'

    def _do_accel(self, me, eff):
        tgt = self.primary(me) or me.active
        if not tgt: return False
        letters = [x for x in re.findall(r'\{(\w)\}', eff) if x in 'GRWLPFDM']
        letters = letters or [c for c in (self._cheapest_cost(tgt) or '') if c in 'GRWLPFDM']
        n = 2 if 'up to 2' in eff.lower() else 1
        did = 0
        for L in (letters or list('GRWLPFDM')):
            t = L2T[L]
            while did < n and me.disc_energy.get(t, 0) > 0:
                me.disc_energy[t] -= 1; tgt.energy[t] += 1; did += 1
            while did < n:
                idx = next((i for i in range(len(me.deck)) if me.deck[i] == ('E', t)), None)
                if idx is None: break
                me.deck.pop(idx); tgt.energy[t] += 1; did += 1
            if did >= n: break
        return did > 0

    def _do_heal(self, me, eff):
        m = re.search(r'heal (\d+) damage', eff.lower())
        if not m: return False
        amt = int(m.group(1)); e = eff.lower(); did = False
        if 'each of your' in e or 'from each' in e:
            for x in me.all_mons():
                if x.damage > 0: x.damage = max(0, x.damage - amt); did = True
        else:
            tgt = max(me.all_mons(), key=lambda x: x.damage, default=None)
            if tgt and tgt.damage > 0: tgt.damage = max(0, tgt.damage - amt); did = True
        return did

    def _poke_qual(self, eff):
        e = eff.lower()
        if 'mega evolution pok' in e: return lambda c: c.name.startswith('Mega ') and c.is_ex
        if 'pokémon ex' in e or 'pokemon ex' in e: return lambda c: c.is_ex
        m = re.search(r'\{(\w)\} pok', e)
        if m: return lambda c, t=L2T[m.group(1).upper()]: c.ptype == t
        if 'basic' in e and 'evolution' not in e: return lambda c: c.stage == 0
        return lambda c: True

    def _do_search_poke(self, me, eff, to_bench=False):
        q = self._poke_qual(eff)
        n = 3 if 'up to 3' in eff.lower() else (2 if 'up to 2' in eff.lower() else 1)
        if to_bench:
            return self._search_basics_to_bench(me, q, n) > 0
        return self._search_deck_to_hand(me, lambda x: x[0] == 'P' and q(x[1]), n) > 0

    def _do_draw(self, me, eff):
        e = eff.lower()
        if 'discard your hand and draw 7' in e:
            for t in me.hand:
                if t[0] == 'E': me.disc_energy[t[1]] += 1
                elif t[0] == 'P': me.discard.append(t)
            me.hand = []; me.draw(7); return True
        m = re.search(r'until you have (\d+) card', e)
        if m:
            if 'shuffle your hand' in e:
                me.deck += me.hand; me.hand = []; self.rng.shuffle(me.deck)
            while len(me.hand) < int(m.group(1)) and me.draw(1):
                pass
            return True
        if 'shuffle your hand into your deck' in e:
            m2 = re.search(r'draw (\d+)', e); me.deck += me.hand; me.hand = []
            self.rng.shuffle(me.deck); me.draw(int(m2.group(1)) if m2 else 4); return True
        m = re.search(r'draw (\d+) card', e)
        if m: me.draw(int(m.group(1))); return True
        return False

    def _do_recover(self, me):
        ps = [x for x in me.discard if x[0] == 'P']
        if not ps:
            return False
        rec = max(ps, key=lambda x: max((a['dmg'] for a in x[1].attacks), default=0))  # best attacker back
        me.discard.remove(rec); me.hand.append(rec); return True

    def play_trainers(self, me, opp):
        # ---- ITEMS / TOOLS (unlimited) ----
        changed = True
        while changed:
            changed = False
            for t in [x for x in me.hand if x[0] == 'T' and x[1]['trainerType'] in ('Item', 'Tool')]:
                nm = t[1]['name']; eff = t[1].get('effect', ''); cat = self._tcat(nm, eff)
                if t[1]['trainerType'] == 'Tool':            # attach a Tool to the readiest attacker
                    tgt = self.primary(me) or me.active
                    if tgt and not tgt.tools:
                        tgt.tools.append(nm); me.hand.remove(t); me.played.append(nm); changed = True; break
                    continue
                if cat == 'CANDY':                           # Rare Candy: evolution mechanic, not a text effect
                    if self._rare_candy(me):
                        me.hand.remove(t); me.played.append(nm); changed = True; break
                    continue
                # fast category gate for common kinds; benefit-estimate ONLY the uncategorized/diverse ones
                if cat == 'BENCH': play = len(me.bench) < 5
                elif cat == 'SEARCHPOKE': play = (not self.primary(me) or len(me.bench) < 3)
                elif cat == 'SEARCHNRG': play = sum(1 for x in me.hand if x[0] == 'E') < 2
                elif cat == 'ACCEL': play = (self.primary(me) and not self._fundable(self.primary(me))) or (me.active and not self._fundable(me.active))
                elif cat == 'HEAL': play = me.active and me.active.damage >= 60
                elif cat == 'RECOVER': play = any(x[0] == 'P' for x in me.discard)
                else: play = self._trainer_benefit(me, opp, eff) > TRAINER_THRESH
                if play:
                    me.hand.remove(t); me.played.append(nm)                 # play the card FIRST, then resolve
                    trainer_effects.resolve_action(me, opp, self, eff)
                    changed = True; break
        # ---- STADIUM (one on the board; play the most useful new one) ----
        stads = [x for x in me.hand if x[0] == 'T' and x[1]['trainerType'] == 'Stadium'
                 and (self.stadium is None or self.stadium[0] != x[1]['name'])]
        if stads:
            stad = max(stads, key=lambda x: self._trainer_benefit(me, opp, x[1].get('effect', '')))
            if self._trainer_benefit(me, opp, stad[1].get('effect', '')) > TRAINER_THRESH - 0.5:
                self.stadium = (stad[1]['name'], self.players.index(me))
                me.hand.remove(stad); me.played.append(stad[1]['name'])
                trainer_effects.resolve_action(me, opp, self, stad[1].get('effect', ''))   # once-per-turn action
        # ---- SUPPORTER (one per turn) ----
        sup = [t for t in me.hand if t[0] == 'T' and t[1]['trainerType'] == 'Supporter']
        if not sup:
            return
        # Boss's Orders-style gust: enabling a KO isn't captured by board value -> targeted special-case
        boss = next((t for t in sup if self._tcat(t[1]['name'], t[1].get('effect', '')) == 'GUST'), None)
        if boss and self._gust(me, opp):
            me.hand.remove(boss); me.played.append(boss[1]['name']); return
        hurt = me.active and me.active.damage >= 80
        need_poke = (not self.primary(me)) or len(me.bench) < 3
        short_nrg = sum(1 for x in me.hand if x[0] == 'E') < 2
        underfunded = (self.primary(me) and not self._fundable(self.primary(me))) or (me.active and not self._fundable(me.active))

        def sup_score(t):
            eff = t[1].get('effect', ''); c = self._tcat(t[1]['name'], eff)
            if c == 'DRAW': return 30 if ('discard your hand' in eff.lower() and len(me.hand) <= 3) else (20 if len(me.hand) <= 4 else 6)
            if c == 'ACCEL': return 25 if underfunded else 4
            if c == 'HEAL': return 22 if hurt else 0
            if c == 'SEARCHPOKE': return 16 if need_poke else 3
            if c == 'SEARCHNRG': return 12 if short_nrg else 2
            if c == 'BENCH': return 11 if len(me.bench) < 4 else 0
            b = self._trainer_benefit(me, opp, eff)              # OTHER supporter: benefit-estimate
            return b if b > TRAINER_THRESH else 0
        s_val, best = max(((sup_score(t), t) for t in sup), key=lambda z: z[0])
        if s_val > 0:
            me.hand.remove(best); me.played.append(best[1]['name'])
            trainer_effects.resolve_action(me, opp, self, best[1].get('effect', ''))

    def ai_main(self, me, opp):
        for m in me.all_mons():
            m.came_from_bench = False
        self.play_trainers(me, opp)                         # supporter + items (draw/search/candy/gust)
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

    def _est_game(self):
        """A throwaway clone of the game (both players cloned + a fresh rng) for non-mutating estimates.
        Carries the real Game methods, so effects that search/gust/etc. resolve correctly on the copy."""
        g = Game.__new__(Game)
        g.rng = random.Random((self.turn * 2654435761) & 0xFFFFFFFF)
        g.turn = self.turn; g.verbose = False; g.stats = None; g.stadium = self.stadium
        g.players = [_clone_player(self.players[0]), _clone_player(self.players[1])]
        return g

    def ramp_bonus(self, mon, name):
        """A "during your next turn, this attack does +N" buff is valid ONLY on the player's very next
        turn (set_turn + 2, since turns alternate). Return the bonus if we're within that window, else
        expire it — a buff whose turn was slept/passed through is gone, not banked."""
        if self.turn - mon.ramp_turn.get(name, -99) <= 2:
            return mon.ramp.get(name, 0)
        mon.ramp.pop(name, None); mon.ramp_turn.pop(name, None)      # expired: clear so it can't resurface
        return 0

    def _est_damage(self, me, opp, a):
        """Estimate an attack's raw damage for AI attack-selection. The fast scaling heuristic is used
        for ordinary attacks; only CONDITIONAL-GATE attacks (which the heuristic over-estimates, e.g.
        Fickle Spitting's phantom 120) are resolved on a non-mutating clone to get the honest value."""
        txt = (a.get('text') or '').lower()
        if not ('does nothing' in txt or 'only if' in txt or 'only during' in txt or "can use this attack only" in txt):
            return max(0, effects.scaling_damage((me, opp, me.active, opp.active, self), a))
        try:
            g2 = self._est_game(); mi = self.players.index(me)
            me2, opp2 = g2.players[mi], g2.players[1 - mi]
            return max(0, attack_effects.resolve(me2, opp2, me2.active, opp2.active, g2, a))
        except Exception:
            return max(0, effects.scaling_damage((me, opp, me.active, opp.active, self), a))

    def _position(self, pl, opp):
        """Heuristic value of a player's board (higher = better): attacker energy-readiness (the ACTIVE
        weighted most, since it does the attacking), a bonus for an Active that can attack RIGHT NOW,
        bench development, hand/card advantage, prizes taken, and durability. Used to score trainer plays."""
        if not pl.all_mons():
            return -200.0
        s = len(pl.bench) * 3.0 + len(pl.hand) * 1.5 + pl.prizes_taken * 18.0
        for m in pl.all_mons():
            active = m is pl.active
            cost = self._cheapest_cost(m) or ''
            if cost:
                s += min(m.total_energy(), len(cost)) * (5.0 if active else 3.0)   # energy toward attacking
                if active and cost_met(m, cost):
                    s += 8.0                                                        # Active can attack NOW
            s += max(0, m.max_hp - m.damage) * (0.06 if active else 0.03)          # durability (Active matters more)
        return s

    def _trainer_benefit(self, me, opp, text):
        """Net position gain from playing a trainer, estimated on a clone (my gain minus the opponent's).
        Large-negative if it can't be evaluated or is a no-op, so it won't be played."""
        mi = self.players.index(me)
        before = self._position(me, opp) - self._position(opp, me)
        try:
            g2 = self._est_game(); me2, opp2 = g2.players[mi], g2.players[1 - mi]
            did, _ = trainer_effects.resolve_action(me2, opp2, g2, text)
        except Exception:
            return -999.0
        if not did:
            return -999.0
        return (self._position(me2, opp2) - self._position(opp2, me2)) - before

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
            dmg = self._est_damage(me, opp, a) + self.ramp_bonus(mon, a['name'])   # real, gate-aware estimate (ramp expires)
            if dmg > 0:
                dmg += effects.team_attack_bonus(ctx, a)     # Regal Cheer / Cobalt Command / etc.
            if dmg and defender and defender.card.weakness and defender.card.weakness == mon.card.ptype:
                dmg *= 2
            txt = a['text'].lower()
            value = (dmg + (25 if 'is now' in txt else 0)
                     + effects.spread_value(ctx, a) + effects.wipe_value(ctx, a))
            if dmg < 20 and effects.is_utility(a):          # draw/search setup, as a fallback
                value = max(value, 18)
            if best is None or value > best[2]:
                best = (a, dmg, value)
        return best

    def _resolve_kos(self, me, opp):
        """After an attack: KO every Pokémon at/over its HP on either side (active OR bench — covers
        spread, recoil, self-damage), award prizes to the other player, and promote where the Active fell."""
        for pl, taker in ((opp, me), (me, opp)):                 # defender's KOs score for the attacker first
            for mon in [m for m in pl.all_mons() if m and self.is_ko(m, pl)]:
                pl.last_ko_turn = self.turn                  # for "if any of your Pokémon were KO'd last turn"
                for t, n in mon.energy.items():
                    pl.disc_energy[t] += n
                pl.discard.append(('P', mon.card))
                spot = 'Active' if mon is pl.active else 'Bench'
                if mon is pl.active:
                    pl.active = None
                elif mon in pl.bench:
                    pl.bench.remove(mon)
                taker.take_prize(2 if mon.card.is_ex else 1)
                self.log(f"    KO {mon.card.name} ({spot}) — {taker.name} prizes {taker.prizes_taken}/6")
            if pl.active is None:
                pl.promote()

    def _log_attack(self, me, opp, attacker, a, raw, dmg, weak, immune, b):
        """One structured line auditing an attack: raw → weakness/immunity/DR → final, plus side effects."""
        d = opp.active
        pre = raw * 2 if weak else raw
        mods = []
        if weak:
            mods.append('x2WEAK')
        if immune:
            mods.append('IMMUNE->0')
        elif pre != dmg:
            mods.append(f'DR-{pre - dmg}')
        fx = []
        if d:
            newst = [s for s in d.status if s not in b['dst'] and s != 'CantRetreat']
            if newst:
                fx.append('status+' + ','.join(newst))
            if d.total_energy() < b['den']:
                fx.append(f'-{b["den"] - d.total_energy()}E')
        for (nm, dm), m in zip(b['obench'], opp.bench):
            if m.card.name == nm and m.damage != dm:
                fx.append(f'{nm}(bench)+{m.damage - dm}')
        if len(me.hand) > b['hand']:
            fx.append(f'draw+{len(me.hand) - b["hand"]}')
        if attacker.damage > b['sdmg']:
            fx.append(f'selfDmg+{attacker.damage - b["sdmg"]}')
        hp = f"{max(0, d.hp_left)}/{d.max_hp}HP" if d else '-'
        self.log(f"  T{self.turn} {me.name}: {attacker.card.name} -> {a['name']}  raw={raw}"
                 f"{' ' + ' '.join(mods) if mods else ''} => {dmg}  |  vs {b['dname']} {hp}"
                 f"{'  [' + ', '.join(fx) + ']' if fx else ''}")

    def take_turn(self, idx, first_turn=False):
        me, opp = self.players[idx], self.players[1 - idx]
        me.played = []                                   # reset "played this turn" history
        if not me.draw(1):
            me.lost = True; self.log(f"{me.name} decks out"); return
        self.log(f"-- Turn {self.turn}: {me.name} draws (hand {len(me.hand)}, deck {len(me.deck)}, "
                 f"prizes {me.prizes_taken}/6) active={me.active.card.name if me.active else '-'}"
                 f" {sorted(me.active.status) if me.active and me.active.status else ''}")
        self.ai_main(me, opp)
        # attack (not on the very first turn of the game for the starting player)
        if not first_turn and me.active and opp.active:
            self._promote_if_idle(me, opp)                   # don't waste the turn if the ace is mid-cooldown
        if not first_turn and me.active and opp.active and effects.can_attack(me.active, self.rng):
            atk = self.best_attack(me, opp, me.active, opp.active)
            if atk and atk[2] > 0:
                a = atk[0]
                attacker = me.active
                defender = opp.active                             # capture before any switch effect
                _b = None
                if self.verbose:                                  # snapshot for move-auditing
                    _b = {'dst': dict(defender.status) if defender else {}, 'den': defender.total_energy() if defender else 0,
                          'obench': [(m.card.name, m.damage) for m in opp.bench], 'hand': len(me.hand),
                          'dname': defender.card.name if defender else '-', 'sdmg': attacker.damage}
                ctxb = (me, opp, attacker, defender, self)
                pre_ramp = self.ramp_bonus(attacker, a['name'])   # capture BEFORE resolve(): a "during your next
                #   turn, this attack does N more" buff sets ramp[name] as a side effect. Reading it back AFTER
                #   resolve would apply that buff on the SAME turn (Slumbering Smack/Meteor Mash/Hyper Fang would
                #   hit for the buffed amount immediately). ramp_bonus returns only a PRIOR-turn buff, and expires
                #   any buff whose next turn has already passed (e.g. Komala slept through it).
                raw = attack_effects.resolve(me, opp, attacker, defender, self, a)    # registry: damage + ALL side effects
                attacker.last_atk, attacker.last_atk_turn = a['name'], self.turn      # record AFTER resolving (so gates see prior turn)
                if raw > 0:                                       # attacker-side buffs (ability + tool + team + ramp)
                    raw += (pre_ramp + effects.team_attack_bonus(ctxb, a)
                            + ability_effects.attack_bonus(attacker, defender, a, self)
                            + trainer_effects.tool_attack_bonus(attacker, defender, a, self))
                dmg, immune, weak = 0, False, False
                if raw > 0 and defender is not None:
                    weak = bool(defender.card.weakness and defender.card.weakness == attacker.card.ptype)
                    dmg = raw * 2 if weak else raw
                    if ability_effects.is_immune(attacker, defender, opp, self):
                        dmg = 0; immune = True                        # ability immunity (registry, team-aware)
                    else:
                        dmg = ability_effects.reduce_damage(dmg, attacker, defender, opp, self)    # ability DR
                        dmg = trainer_effects.tool_reduce(dmg, attacker, defender, opp, self)      # Tool DR (Defender &c.)
                        if getattr(defender, 'dr_turn', -9) + 1 == self.turn:                     # attack-set "-N next turn"
                            dmg = max(0, dmg - getattr(defender, 'dr_amount', 0))
                    if dmg > 0:
                        ability_effects.on_damaged(attacker, defender, opp, self)                  # Poison Point &c.
                        trainer_effects.tool_on_damaged(attacker, defender, opp, self)             # Tool reactions (Lucky Helmet &c.)
                    defender.damage += dmg
                    if 'Spiky Energy' in defender.special:
                        attacker.damage += 20                    # Spiky Energy counters the attacker
                if self.stats is not None:
                    self.stats[idx]['attacks'] += 1
                    self.stats[idx]['dmg_dealt'] += dmg
                    self.stats[1 - idx]['dmg_taken'] += dmg
                if self.verbose:
                    self._log_attack(me, opp, attacker, a, raw, dmg, weak, immune, _b)
                self._resolve_kos(me, opp)                        # KO/prizes/promote both sides (spread, recoil, self-KO)
        # end of turn: age, clear my paralysis, run Pokémon Checkup on both actives
        for m in me.all_mons():
            m.turns += 1
            while 'Ignition Energy' in m.special:            # Ignition Energy is discarded end of turn
                m.special.remove('Ignition Energy')
                for typ, c in SE.provides('Ignition Energy', m.card).items():
                    m.energy[typ] -= c
                    if m.energy[typ] <= 0:
                        del m.energy[typ]
        if me.active:
            effects.clear_paralysis(me.active)
        self._checkup()

    def _checkup(self):
        for i, p in enumerate(self.players):
            other = self.players[1 - i]
            if not p.active:
                continue
            for m in p.all_mons():
                ability_effects.run_between_turns(m, p, self)    # e.g. Insomnia clears Asleep each checkup
            _cbefore = p.active.damage
            effects.checkup(p.active, self.rng)
            if p.active.damage > _cbefore:
                self.log(f"    checkup: {p.active.card.name} +{p.active.damage - _cbefore} "
                         f"({','.join(sorted(p.active.status)) or 'none'})")
            if self.is_ko(p.active, p):
                ko = p.active
                p.last_ko_turn = self.turn
                for t, n in ko.energy.items():
                    p.disc_energy[t] += n
                p.discard.append(('P', ko.card))
                other.take_prize(2 if ko.card.is_ex else 1)
                self.log(f"    KO {ko.card.name} (checkup: {','.join(sorted(ko.status)) or 'condition'}) "
                         f"— {other.name} prizes {other.prizes_taken}/6")
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


def _load_registries():
    """Load every generated effect/ability/trainer batch into its registry. Called at import time BELOW,
    after Mon/Player/Game exist — some generated batches do `from engine import Mon`, so this must run
    after the classes are defined, not at the top of the module."""
    try:
        import effects_gen; effects_gen.load_all()
        import abilities_gen; abilities_gen.load_all()
        import trainers_gen; trainers_gen.load_all()
        tj = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'deckgen', 'trainers.json')))
        trainer_effects.register_tool_texts({n: v.get('effect', '') for n, v in tj.items() if v.get('trainerType') == 'Tool'})
    except Exception:
        import traceback; traceback.print_exc()


_load_registries()


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
