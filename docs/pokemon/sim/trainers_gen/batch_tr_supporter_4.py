#!/usr/bin/env python3
"""Generated trainer effects — batch tr_supporter_4 (14 Supporters).

Each effect is fn(tctx) -> bool (True if it changed the game state). Registered under the card's
EXACT rules text via @trainer('supporter', <text>). The exact-text keys are round-trip verified in
test_batch_tr_supporter_4.py against effects_work/trainer_batches.json.

Model reminders (see engine.py):
  - Deck/hand tokens: ('P', Card) | ('E', type_str) | ('T', trainer_dict) | ('S', special_dict).
  - Top of deck == END of the deck list (draw() does deck.pop()).
  - Basic energy in the discard lives in player.disc_energy (a Counter), NOT the discard list;
    other cards (Pokémon / Trainer / Special Energy) live in player.discard as tokens.
"""
from trainer_effects import trainer, TrainerCtx
from engine import Mon, L2T
import special_energy as SE


def _dig_priority(tok):
    """How useful a card we get to order/keep is (higher = want it drawn sooner)."""
    if tok[0] == 'P':
        return 4 if tok[1].stage == 0 else 3      # a Basic can hit the board immediately
    if tok[0] in ('E', 'S'):
        return 2
    return 1                                       # Trainers are situational


# ---------------- Professor's Research ----------------
@trainer('supporter', "Discard your hand and draw 7 cards.")
def _professors_research(t):
    me = t.me
    for tok in me.hand:
        if tok[0] == 'E':
            me.disc_energy[tok[1]] += 1            # basic energy -> disc_energy Counter
        else:
            me.discard.append(tok)                 # Pokémon / Trainer / Special Energy -> discard pile
    me.hand = []
    me.draw(7)
    return True


# ---------------- Raifort ----------------
@trainer('supporter', "Look at the top 5 cards of your deck and discard any number of them. Put the other cards back in any order.")
def _raifort(t):
    # "Discard any number" is modeled as discard 0 (thinning deck resources is rarely correct without
    # deck-specific knowledge) plus the fully-modelable half: order the looked-at cards so the most
    # useful is drawn next.
    me = t.me
    if not me.deck:
        return False
    k = min(5, len(me.deck))
    region = me.deck[-k:]
    del me.deck[-k:]
    region.sort(key=_dig_priority)                 # ascending -> highest priority ends last == top
    me.deck.extend(region)
    return True


# ---------------- Rosa's Encouragement ----------------
@trainer('supporter', "You can use this card only if you have more Prize cards remaining than your opponent.\n\nAttach up to 2 Basic Energy cards from your discard pile to 1 of your Stage 2 Pokémon.")
def _rosas_encouragement(t):
    me, opp = t.me, t.opp
    if len(me.prizes) <= len(opp.prizes):          # need MORE prizes remaining (i.e. behind)
        return False
    s2 = [m for m in me.all_mons() if m and m.card.stage == 2]
    if not s2:
        return False
    prim = t.primary()
    tgt = prim if prim in s2 else min(s2, key=lambda m: m.total_energy())
    need = t.game._cheapest_cost(tgt) or ''
    letters = [c for c in need if c in 'GRWLPFDM']
    attached = 0
    for L in letters:                              # the target's needed basic-energy types first
        if attached >= 2:
            break
        attached += t.accel_from_discard(L2T[L], tgt, 2 - attached)
    if attached < 2:                               # then any remaining basic energy in the discard
        for typ in list(me.disc_energy):
            if attached >= 2:
                break
            attached += t.accel_from_discard(typ, tgt, 2 - attached)
    return attached > 0


# ---------------- Roxie's Performance ----------------
@trainer('supporter', "During your opponent's next turn, their Poisoned Pokémon can't retreat. (This includes newly Poisoned Pokémon.)")
def _roxies_performance(t):
    # LIMITATION: the engine's retreat AI does not consult a can't-retreat flag, so this is effectively
    # inert; and "newly Poisoned" opponent Pokémon can't be pre-marked. We mark the opponent's currently
    # Poisoned Pokémon with the codebase's existing 'CantRetreat' marker as a best-effort / future hook.
    did = False
    for m in t.opp.all_mons():
        if m and 'Poisoned' in m.status:
            m.status['CantRetreat'] = True
            did = True
    return did


# ---------------- Ruffian ----------------
@trainer('supporter', "Discard a Pokémon Tool and a Special Energy from 1 of your opponent's Pokémon.")
def _ruffian(t):
    opp = t.opp
    cands = [m for m in opp.all_mons() if m and (m.tools or m.special)]
    if not cands:
        return False
    # target the Pokémon carrying the most of the two (then the most energy — biggest disruption)
    tgt = max(cands, key=lambda m: (bool(m.tools) + bool(m.special), m.total_energy()))
    did = False
    if tgt.tools:
        name = tgt.tools.pop(0)
        opp.discard.append(('T', {'name': name, 'trainerType': 'Tool'}))
        did = True
    if tgt.special:
        sname = tgt.special.pop(0)
        for typ, c in SE.provides(sname, tgt.card).items():   # remove the pips it was providing
            tgt.energy[typ] -= c
            if tgt.energy[typ] <= 0:
                del tgt.energy[typ]
        opp.discard.append(('S', {'special_energy': sname}))
        did = True
    return did


# ---------------- Salvatore ----------------
@trainer('supporter', "Search your deck for a card that has no Abilities and evolves from 1 of your Pokémon, and put it onto that Pokémon to evolve it. Then, shuffle your deck. You can use this card on a Pokémon you put down when you were setting up to play or on a Pokémon that was put into play this turn.")
def _salvatore(t):
    me = t.me
    for mon in me.all_mons():
        if not mon:
            continue
        for i in range(len(me.deck) - 1, -1, -1):
            tok = me.deck[i]
            if tok[0] != 'P':
                continue
            c = tok[1]
            if c.abilities:                        # "a card that has no Abilities"
                continue
            if c.evolves_from == mon.card.name and c.stage == mon.card.stage + 1:
                ev = Mon(c)                        # carry over state (mirrors engine.evolve_all)
                ev.damage = mon.damage; ev.energy = mon.energy; ev.turns = mon.turns
                ev.status = mon.status; ev.poison_amt = mon.poison_amt
                ev.special = mon.special; ev.ramp = mon.ramp; ev.tools = mon.tools
                ev.last_atk = mon.last_atk; ev.last_atk_turn = mon.last_atk_turn
                ev.evolved_turn = t.game.turn      # note: no turns>=1 gate — evolving a fresh mon is allowed
                me.deck.pop(i)
                if mon is me.active:
                    me.active = ev
                else:
                    me.bench[me.bench.index(mon)] = ev
                t.rng.shuffle(me.deck)
                return True
    return False


# ---------------- Surfer ----------------
@trainer('supporter', "Switch your Active Pokémon with 1 of your Benched Pokémon. If you do, draw cards until you have 5 cards in your hand.")
def _surfer(t):
    me = t.me
    if not me.bench:                               # can't switch -> "if you do" draw doesn't happen
        return False
    t.switch_self()
    while len(me.hand) < 5 and me.draw(1):
        pass
    return True


# ---------------- Tarragon ----------------
@trainer('supporter', "Put up to 4 in any combination of {F} Pokémon and Basic {F} Energy cards from your discard pile into your hand.")
def _tarragon(t):
    me = t.me
    got = 0
    for tok in [x for x in me.discard if x[0] == 'P' and x[1].ptype == 'Fighting']:   # {F} == Fighting
        if got >= 4:
            break
        me.discard.remove(tok)
        me.hand.append(tok)
        got += 1
    while got < 4 and me.disc_energy.get('Fighting', 0) > 0:                          # Basic {F} Energy
        me.disc_energy['Fighting'] -= 1
        me.hand.append(('E', 'Fighting'))
        got += 1
    return got > 0


# ---------------- Team Rocket's Archer ----------------
@trainer('supporter', "You can use this card only if any of your Team Rocket's Pokémon were Knocked Out during your opponent's last turn.\n\nEach player shuffles their hand into their deck. Then, you draw 5 cards, and your opponent draws 3 cards.")
def _team_rockets_archer(t):
    # LIMITATION: the engine records that a Pokémon was KO'd last turn (last_ko_turn) but not whether it
    # was a Team Rocket's Pokémon. These cards only see play in Team-Rocket's decks (where nearly every
    # Pokémon is one), so "a mon KO'd on the opponent's last turn" is a faithful proxy for the gate.
    me, opp = t.me, t.opp
    if me.last_ko_turn != t.game.turn - 1:
        return False
    t.shuffle_hand_into_deck()
    opp.deck += opp.hand; opp.hand = []; t.rng.shuffle(opp.deck)
    t.draw(5)
    opp.draw(3)
    return True


# ---------------- Team Rocket's Ariana ----------------
@trainer('supporter', "Draw cards until you have 5 cards in your hand. If all of your Pokémon in play are Team Rocket's Pokémon, draw cards until you have 8 cards in your hand instead.")
def _team_rockets_ariana(t):
    me = t.me
    mons = me.all_mons()
    all_tr = bool(mons) and all(m.card.name.startswith("Team Rocket's") for m in mons)
    target = 8 if all_tr else 5
    while len(me.hand) < target and me.draw(1):
        pass
    return True


# ---------------- Team Rocket's Giovanni ----------------
@trainer('supporter', "Switch your Active Team Rocket's Pokémon with 1 of your Benched Team Rocket's Pokémon. If you do, switch in 1 of your opponent's Benched Pokémon to the Active Spot.")
def _team_rockets_giovanni(t):
    me, opp = t.me, t.opp
    if not (me.active and me.active.card.name.startswith("Team Rocket's")):
        return False
    tr_bench = [m for m in me.bench if m.card.name.startswith("Team Rocket's")]
    if not tr_bench:
        return False
    # switch active TR with the readiest benched TR (most energy, then HP)
    newact = max(tr_bench, key=lambda m: (m.total_energy(), m.card.hp))
    old = me.active
    me.bench.remove(newact); me.bench.append(old)
    me.active = newact; newact.came_from_bench = True
    # ...and, having done so, drag up an opponent's benched Pokémon (the easiest to punish: lowest HP,
    # preferring an ex for the extra Prize on a tie)
    if opp.bench:
        tgt = min(opp.bench, key=lambda m: (m.hp_left, not m.card.is_ex))
        opp.bench.remove(tgt); opp.bench.append(opp.active); opp.active = tgt
    return True


# ---------------- Team Rocket's Petrel ----------------
@trainer('supporter', "Search your deck for a Trainer card, reveal it, and put it into your hand. Then, shuffle your deck.")
def _team_rockets_petrel(t):
    return t.game._search_deck_to_hand(t.me, lambda tok: tok[0] == 'T', 1) > 0


# ---------------- Team Rocket's Proton ----------------
@trainer('supporter', "If you go first, you may use this card during your first turn.\n\nSearch your deck for up to 3 Basic Team Rocket's Pokémon, reveal them, and put them into your hand. Then, shuffle your deck.")
def _team_rockets_proton(t):
    # NOTE: the "go first / first turn" sentence is a play-timing legality constraint enforced at the
    # play-decision layer, not in this effect.
    return t.search_pokemon(lambda c: c.stage == 0 and c.name.startswith("Team Rocket's"), 3) > 0


# ---------------- Tyme ----------------
@trainer('supporter', "Tell your opponent the name of a Pokémon in your hand and put that Pokémon face down in front of you. Your opponent guesses that Pokémon's HP, and then you reveal it. If your opponent guessed right, they draw 4 cards. If they guessed wrong, you draw 4 cards. Then, return the Pokémon to your hand.")
def _tyme(t):
    # HEURISTIC: the opponent guessing the exact HP of a Pokémon you deliberately chose is unlikely, so
    # the guess is modeled as correct only ~25% of the time; usually you draw 4. The named Pokémon
    # returns to hand (no net hand change from the reveal itself).
    me, opp = t.me, t.opp
    if not any(tok[0] == 'P' for tok in me.hand):   # need a Pokémon in hand to name
        return False
    if t.rng.random() < 0.25:                       # opponent guessed the HP correctly
        opp.draw(4)
    else:
        me.draw(4)
    return True
