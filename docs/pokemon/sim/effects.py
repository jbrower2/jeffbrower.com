#!/usr/bin/env python3
"""Effect registry for the simulator: turns attack/ability TEXT into game effects.

Two layers implemented here:
  * scaling_damage() — evaluates "×", "+", "-" attacks (per-energy / per-bench /
    per-prize / per-damage-counter / per-type-in-play / coin-flip / conditional).
  * attack_side_effects() — recoil, self-energy discard, and attack cooldowns.
  * ABILITY_ACCEL — energy-acceleration abilities run during the main phase, plus
    on-evolve accel; generic + named handlers.

Anything not recognized falls back to the printed base damage / no-op, so adding
coverage only ever raises fidelity. L2T maps energy letters to type names.
"""
import re

L2T = {'G': 'Grass', 'R': 'Fire', 'W': 'Water', 'L': 'Lightning', 'P': 'Psychic',
       'F': 'Fighting', 'D': 'Darkness', 'M': 'Metal', 'C': 'Colorless'}
TYPES = set(L2T.values())


# ---------------------------------------------------------------- counts
def _energy_in_play(player, t=None):
    return sum((m.energy.get(t, 0) if t else m.total_energy()) for m in player.all_mons())

def eval_count(frag, ctx):
    """Evaluate a 'for each X' fragment into an integer count."""
    me, opp, mon, dfn, g = ctx
    f = frag.lower()
    m = re.search(r'\{(\w)\} energy attached to this pok', f)
    if m: return mon.energy.get(L2T[m.group(1).upper()], 0)
    if 'energy attached to this pok' in f: return mon.total_energy()
    m = re.search(r'\{(\w)\} energy attached to all of your pok', f)
    if m: return _energy_in_play(me, L2T[m.group(1).upper()])
    if 'energy attached to all of your pok' in f: return _energy_in_play(me)
    if "energy attached to your opponent" in f: return dfn.total_energy() if dfn else 0
    if 'damage counter on this pok' in f: return mon.damage // 10
    if "damage counter on your opponent" in f or 'damage counters on your opp' in f:
        return dfn.damage // 10 if dfn else 0
    if "of your opponent's benched" in f or "opponent's pok" in f and 'bench' in f:
        return len(opp.bench)
    if 'benched pok' in f and 'your' in f: return len(me.bench)
    if 'benched pok' in f: return len(me.bench)
    m = re.search(r'of your \{(\w)\} pok', f)
    if m:
        t = L2T[m.group(1).upper()]; return sum(1 for x in me.all_mons() if x.card.ptype == t)
    if 'prize card you have taken' in f or 'prize cards you have taken' in f: return me.prizes_taken
    if "prize card your opponent" in f or "prize cards your opponent" in f: return opp.prizes_taken
    if 'of your pok' in f and 'in play' in f: return len(me.all_mons())
    # named ("for each of your Beedrill and Beedrill ex in play")
    m = re.search(r'of your ([a-z][a-z\' ]+?) (?:and [a-z\' ]+ )?in play', f)
    if m:
        w = m.group(1).strip().split()[0]
        return sum(1 for x in me.all_mons() if w in x.card.name.lower())
    return 0

def _flip_heads(text, rng):
    m = re.search(r'flip (\d+) coins', text.lower())
    if m: return sum(1 for _ in range(int(m.group(1))) if rng.random() < 0.5)
    if 'until you get tails' in text.lower():
        n = 0
        while rng.random() < 0.5: n += 1
        return n
    return 0


# ------------------------------------------------------------- conditions
def eval_cond(text, ctx):
    me, opp, mon, dfn, g = ctx
    t = text.lower()
    if dfn is None: dfn_ex = dfn_evo = dfn_s2 = dfn_dmg = False
    else:
        dfn_ex = dfn.card.is_ex; dfn_evo = dfn.card.stage > 0; dfn_s2 = dfn.card.stage == 2; dfn_dmg = dfn.damage > 0
    if 'active pokémon is a pokémon ex' in t or 'active pokemon is a pokémon ex' in t or 'active pokémon is a pokemon ex' in t:
        return dfn_ex
    if 'is an evolution pok' in t: return dfn_evo
    if 'is a stage 2' in t: return dfn_s2
    if "opponent's active pokémon already has any damage" in t or "opponent's active pokemon already has any damage" in t:
        return dfn_dmg
    if 'this pokémon has any damage counter' in t or 'this pokemon has any damage counter' in t: return mon.damage > 0
    if 'this pokémon has no damage counter' in t or 'this pokemon has no damage counter' in t: return mon.damage == 0
    if 'moved from your bench to the active spot this turn' in t: return getattr(mon, 'came_from_bench', False)
    if 'your benched pokémon have any damage' in t or 'your benched pokemon have any damage' in t:
        return any(x.damage > 0 for x in me.bench)
    if 'a stadium is in play' in t: return False
    for s in ('Burned', 'Poisoned', 'Asleep', 'Paralyzed', 'Confused'):
        if s.lower() in t:
            if 'this pok' in t:
                return s in mon.status
            return dfn is not None and s in dfn.status
    m = re.search(r'at least (\d+) \{(\w)\} energy in play', t)
    if m: return _energy_in_play(me, L2T[m.group(2).upper()]) >= int(m.group(1))
    if 'at least 2 extra energy attached' in t:
        return mon.total_energy() >= 2  # rough: 2 beyond a typical cost
    return False


# --------------------------------------------------------- scaling damage
def scaling_damage(ctx, attack):
    """Return pre-weakness damage for an attack, honoring ×/+/- scaling & conditionals."""
    me, opp, mon, dfn, g = ctx
    base = attack['dmg']; sc = attack['scaling']; text = attack['text']
    if sc == '×':
        if 'for each heads' in text.lower() or 'flip' in text.lower():
            return base * _flip_heads(text, g.rng)
        m = re.search(r'for each (.+?)(?:\.|$)', text, re.I)
        return base * (eval_count(m.group(1), ctx) if m else 0)
    if sc == '+':
        dmg = base
        for m in re.finditer(r'does (\d+) more damage for each (.+?)(?:\.|$)', text, re.I):
            dmg += int(m.group(1)) * eval_count(m.group(2), ctx)
        # conditional bonus: only "if <cond>, ... does N more damage" (not the per-each clauses above)
        for m in re.finditer(r'if ([^,]+?), (?:[^.]*?)this attack does (\d+) more damage', text, re.I):
            if 'for each' in m.group(0).lower():
                continue
            if eval_cond(m.group(1), ctx):
                dmg += int(m.group(2))
        return dmg
    if sc == '-':
        m = re.search(r'(\d+) less damage for each (.+?)(?:\.|$)', text, re.I)
        if m:
            return max(0, base - int(m.group(1)) * eval_count(m.group(2), ctx))
        return base
    return base


# --------------------------------------------------------- attack side FX
def attack_side_effects(ctx, attack):
    """Apply recoil, self-energy discard, and cooldowns after an attack resolves."""
    me, opp, mon, dfn, g = ctx
    text = attack['text']
    m = re.search(r'also does (\d+) damage to itself', text, re.I)
    if m: mon.damage += int(m.group(1))
    m = re.search(r'discard (all|an|a|\d+) .*?energy from this pok', text, re.I)
    if m:
        qty = mon.total_energy() if m.group(1) == 'all' else (1 if m.group(1) in ('a', 'an') else int(m.group(1)))
        for _ in range(qty):
            if mon.total_energy() <= 0: break
            t = max(mon.energy, key=lambda k: mon.energy[k]); mon.energy[t] -= 1
            if mon.energy[t] <= 0: del mon.energy[t]
            me.disc_energy[t] += 1
    # healing
    tl = text.lower()
    if re.search(r'heal (\d+) damage from each pok', tl):                       # both players' Pokémon
        n = int(re.search(r'heal (\d+) damage from each pok', tl).group(1))
        for pl in (me, opp):
            for x in pl.all_mons(): x.damage = max(0, x.damage - n)
    elif re.search(r'heal (\d+) damage from each of your pok', tl):             # your team
        n = int(re.search(r'heal (\d+) damage from each of your pok', tl).group(1))
        for x in me.all_mons(): x.damage = max(0, x.damage - n)
    elif re.search(r'heal (\d+) damage from this pok', tl):                     # self
        mon.damage = max(0, mon.damage - int(re.search(r'heal (\d+) damage from this pok', tl).group(1)))
    # temporary self damage-reduction "during your opponent's next turn ... takes N less"
    m = re.search(r'this pok\w*mon takes (\d+) less damage from attacks', tl)
    if m:
        mon.dr_amount = int(m.group(1)); mon.dr_turn = g.turn

def apply_spread(ctx, attack):
    """Damage to the opponent's BENCH. Returns benched Mons that were KO'd (for prizes)."""
    me, opp, mon, dfn, g = ctx
    text = attack['text']
    m = re.search(r'does (\d+) damage to (each|1|2|3) of your opponent', text, re.I) \
        or re.search(r'also does (\d+) damage to (each|1|2|3) of your opponent', text, re.I)
    if not m or not opp.bench:
        return []
    amt = int(m.group(1)); how = m.group(2)
    targets = list(opp.bench) if how == 'each' else sorted(opp.bench, key=lambda b: b.hp_left)[:int(how) if how.isdigit() else 1]
    ko = []
    for b in targets:
        b.damage += amt          # bench damage ignores weakness/resistance
        if b.damage >= b.card.hp:
            ko.append(b)
    return ko

def _search(me, n, kind):
    """Move up to n tokens of a kind ('P' Pokémon / 'E' energy) from deck to hand."""
    got = 0
    for i in range(len(me.deck) - 1, -1, -1):
        if got >= n:
            break
        if me.deck[i][0] == kind:
            me.hand.append(me.deck.pop(i)); got += 1

def is_utility(attack):
    t = attack['text'].lower()
    return 'draw' in t or 'search your deck' in t

def apply_attack_utility(ctx, attack):
    """Draw / search-to-hand attack effects (consistency engines like Call Sign, Nasty Plot)."""
    me = ctx[0]; t = attack['text'].lower()
    m = re.search(r'draw (\d+) card', t)
    if m: me.draw(int(m.group(1)))
    m = re.search(r'until you have (\d+) card', t)
    if m:
        while len(me.hand) < int(m.group(1)) and me.draw(1):
            pass
    m = re.search(r'search your deck for up to (\d+) basic energy', t)
    if m:
        _search(me, int(m.group(1)), 'E'); return
    m = re.search(r'search your deck for (?:up to (\d+) )?(?:basic )?pok', t)
    if m:
        _search(me, int(m.group(1)) if m.group(1) else 1, 'P')

def attack_cooldown(attack):
    """Return the attack name it disables next turn, 'ALL', or None."""
    tl = attack['text'].lower(); nm = attack['name'].lower()
    if "can't attack" in tl:
        return 'ALL'
    if "can't use " + nm in tl or 'until it leaves the active spot' in tl:
        return attack['name']
    return None


# --------------------------------------------------- energy acceleration
def _pull_energy_from(src_counter, t, mon, n=1):
    got = 0
    for _ in range(n):
        if src_counter.get(t, 0) <= 0: break
        src_counter[t] -= 1; mon.energy[t] += 1; got += 1
    return got

def accel_from_discard(me, letter, mon, n=1):
    return _pull_energy_from(me.disc_energy, L2T[letter], mon, n)

def accel_from_deck(me, letter, mon, n=1):
    """Search deck for basic energy of a type and attach (removes energy tokens)."""
    t = L2T[letter]; got = 0
    for _ in range(n):
        for i, tok in enumerate(me.deck):
            if tok[0] == 'E' and tok[1] == t:
                me.deck.pop(i); mon.energy[t] += 1; got += 1
                break
        else:
            break
    return got

def accel_from_hand(me, letter, mon, n=1):
    t = L2T[letter]; got = 0
    for _ in range(n):
        for i, tok in enumerate(me.hand):
            if tok[0] == 'E' and tok[1] == t:
                me.hand.pop(i); mon.energy[t] += 1; got += 1
                break
        else:
            break
    return got

# named ability handlers: fn(me, opp, mon, game) -> bool (did something).
# `mon` is the pokemon that HAS the ability. Called once/turn during main phase.
def _dynamotor(me, opp, mon, g):          # Eelektrik: 1 {L} from discard to a benched mon
    tgt = _best_attacker(me)
    return accel_from_discard(me, 'L', tgt) > 0
def _inferno_fandango(me, opp, mon, g):   # Emboar: attach {R} from hand (model: up to 2/turn)
    return accel_from_hand(me, 'R', _best_attacker(me), 2) > 0
def _electric_streamer(me, opp, mon, g):  # Iono's Bellibolt: attach {L} from hand (up to 2/turn)
    return accel_from_hand(me, 'L', _best_attacker(me), 2) > 0
def _golden_flame(me, opp, mon, g):       # Ethan's Ho-Oh: 2 {R} from hand to a benched attacker
    return accel_from_hand(me, 'R', _best_attacker(me), 2) > 0
def _metal_maker(me, opp, mon, g):        # Metang: {M} from deck (top-of-deck search)
    return accel_from_deck(me, 'M', _best_attacker(me), 1) > 0
def _stone_arms(me, opp, mon, g):         # Barbaracle: 1 {F} from hand
    return accel_from_hand(me, 'F', _best_attacker(me)) > 0
def _wash_out(me, opp, mon, g):           # Dewgong: move {W} bench->active (model as +1 from discard/deck)
    return accel_from_discard(me, 'W', me.active) or accel_from_deck(me, 'W', me.active)
def _regi_charge(letter):
    return lambda me, opp, mon, g: accel_from_discard(me, letter, mon, 2) > 0

def _best_attacker(me):
    """Pick the pokemon the deck wants to power: prefer the ex, else the active."""
    exs = [m for m in me.all_mons() if m.card.is_ex]
    if exs:
        return max(exs, key=lambda m: m.card.hp)
    return me.active or (me.bench[0] if me.bench else None)

ABILITY_ACCEL = {
    'Dynamotor': _dynamotor,
    'Inferno Fandango': _inferno_fandango,
    'Electric Streamer': _electric_streamer,
    'Golden Flame': _golden_flame,
    'Metal Maker': _metal_maker,
    'Stone Arms': _stone_arms,
    'Wash Out': _wash_out,
    'Metal Road': _regi_charge('M'),
}


# --------------------------------------------------------- special conditions
STATUSES = ('Burned', 'Poisoned', 'Asleep', 'Paralyzed', 'Confused')

def set_status(mon, s, text=''):
    if s in ('Asleep', 'Paralyzed', 'Confused'):     # these three are mutually exclusive
        for x in ('Asleep', 'Paralyzed', 'Confused'):
            mon.status.pop(x, None)
    mon.status[s] = True
    if s == 'Poisoned':
        m = re.search(r'(?:put|place) (\d+) damage counters on that pok\w*mon instead of 1', text, re.I)
        mon.poison_amt = int(m.group(1)) * 10 if m else 10

def apply_attack_status(ctx, attack):
    me, opp, mon, dfn, g = ctx
    text = attack['text']
    for s in STATUSES:
        if dfn and (re.search(r"active pok\w*mon is now [\w ]*?" + s, text, re.I) or
                    re.search(r"defending pok\w*mon is now [\w ]*?" + s, text, re.I)):
            set_status(dfn, s, text)
        if re.search(r"this pok\w*mon is now [\w ]*?" + s, text, re.I):
            set_status(mon, s, text)

def checkup(mon, rng):
    """Between-turns Pokémon Checkup: apply poison/burn, coin-off sleep/burn."""
    if 'Poisoned' in mon.status:
        mon.damage += getattr(mon, 'poison_amt', 10)
    if 'Burned' in mon.status:
        mon.damage += 20
        if rng.random() < 0.5:
            mon.status.pop('Burned', None)
    if 'Asleep' in mon.status and rng.random() < 0.5:
        mon.status.pop('Asleep', None)

def can_attack(mon, rng):
    """Sleep/Paralysis block attacking; Confusion is a coin flip (tails = 30 to self)."""
    if 'Asleep' in mon.status or 'Paralyzed' in mon.status:
        return False
    if 'Confused' in mon.status and rng.random() < 0.5:
        mon.damage += 30
        return False
    return True

def clear_paralysis(mon):
    mon.status.pop('Paralyzed', None)


# ----------------------------------------- layer 4: reduction / immunity / HP / heal
def incoming_damage(dmg, atk_mon, dfn_mon, dfn_player, g):
    """Adjust damage to a defender: immunity, coin-prevent, flat reductions, temp buffs."""
    if dmg <= 0:
        return dmg
    for ab in dfn_mon.card.abilities:                       # immunity / coin-prevent on the DEFENDER
        t = ab['text'].lower()
        if 'prevent all damage' in t and 'done to this pok' in t:
            if 'pokémon ex' in t or 'pokemon ex' in t:
                if atk_mon.card.is_ex: return 0
            elif 'that have an ability' in t:
                if atk_mon.card.abilities: return 0
            elif '200 or more' in t:
                if dmg >= 200: return 0
            else:
                return 0
        if 'flip a coin' in t and 'prevent that damage' in t:
            if g.rng.random() < 0.5: return 0
    red = 0
    for src in dfn_player.all_mons():                       # flat reductions from anything in play
        for ab in src.card.abilities:
            t = ab['text'].lower()
            m = re.search(r'takes? (\d+) less damage from attacks', t)   # "takes" (self) or "take" (team)
            if not m:
                continue
            n = int(m.group(1))
            if 'all of your' in t:
                em = re.search(r'\{(\w)\} energy attached', t)
                if em:
                    if dfn_mon.energy.get(L2T[em.group(1).upper()], 0) > 0: red += n
                elif "steven's" in t:
                    if dfn_mon.card.name.startswith("Steven's"): red += n
                else:
                    red += n
            elif 'this pok' in t and src is dfn_mon:
                red += n
    if getattr(dfn_mon, 'dr_turn', -9) + 1 == g.turn:       # temp "-N during opponent's next turn"
        red += getattr(dfn_mon, 'dr_amount', 0)
    return max(0, dmg - red)

def team_hp_bonus(player):
    """+HP auras in play (e.g. Ludicolo's Vibrant Dance). Doesn't stack."""
    b = 0
    for m in player.all_mons():
        for ab in m.card.abilities:
            hm = re.search(r'all of your pok\w*mon in play get \+(\d+) hp', ab['text'].lower())
            if hm: b = max(b, int(hm.group(1)))
    return b

def _confectionary(me, opp, mon, g):        # Alcremie ex: heal 30 from your most-damaged
    tgt = max(me.all_mons(), key=lambda m: m.damage, default=None)
    if tgt and tgt.damage > 0: tgt.damage = max(0, tgt.damage - 30); return True
    return False
def _lovely_fragrance(me, opp, mon, g):     # Erika's Vileplume ex: heal 30 from each of yours
    did = False
    for x in me.all_mons():
        if x.damage > 0: x.damage = max(0, x.damage - 30); did = True
    return did
def _auto_heal(me, opp, mon, g):            # Magearna (approx: 90 off your most-damaged / turn)
    tgt = max(me.all_mons(), key=lambda m: m.damage, default=None)
    if tgt and tgt.damage > 0: tgt.damage = max(0, tgt.damage - 90); return True
    return False
HEAL_ABILITIES = {'Confectionary Gift': _confectionary,
                  'Lovely Fragrance': _lovely_fragrance, 'Auto Heal': _auto_heal}


# --------------------------------------------- layer 5: ability lock
def abilities_disabled(mon, me, opp):
    """Is `mon`'s ability shut off? Flutter Mane (opp active) locks the facing Active;
    Iron Thorns' Initialization (opp active) locks Rule-Box (ex) abilities."""
    oa = opp.active
    if oa and oa is not mon:
        for ab in oa.card.abilities:
            t = ab['text'].lower()
            if 'has no abilities' in t and mon is me.active:            # Flutter Mane
                return True
            if 'have no abilities' in t and 'rule box' in t and mon.card.is_ex:  # Iron Thorns
                return True
    return False
