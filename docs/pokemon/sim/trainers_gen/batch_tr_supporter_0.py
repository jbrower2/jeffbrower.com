"""Generated trainer effects — batch tr_supporter_0 (14 Supporters).

Each effect is registered by its EXACT printed text via @trainer('supporter', <text>).
normalize() (in trainer_effects) collapses whitespace and strips a leading "- ", so the
multi-paragraph gate texts key the same whether written with blank lines or single spaces.
"""
from trainer_effects import trainer, TrainerCtx

N_NAMES = ("N's Darmanitan", "N's Zoroark ex", "N's Vanilluxe",
           "N's Klinklang", "N's Reshiram", "N's Zekrom")


# ---- discard helpers (route basic energy to disc_energy like the engine does) ----
def _discard_tok(me, tok):
    if tok[0] == 'E':
        me.disc_energy[tok[1]] += 1
    else:
        me.discard.append(tok)


def _discard_whole_hand(me):
    n = len(me.hand)
    for tok in me.hand:
        _discard_tok(me, tok)
    me.hand = []
    return n


def _discard_one(me):
    """Discard 1 card from hand as a cost — prefer a surplus basic energy, else the first card."""
    if not me.hand:
        return None
    idx = next((i for i, x in enumerate(me.hand) if x[0] == 'E'), 0)
    tok = me.hand.pop(idx)
    _discard_tok(me, tok)
    return tok


# ---- 1. AZ's Tranquility ----
@trainer('supporter', "Switch your Active Pokémon with 1 of your Benched Pokémon. If you moved a Pokémon ex to your Bench in this way, heal 80 damage from that Pokémon.")
def az_tranquility(t):
    me = t.me
    if not me.active or not me.bench:
        return False
    old = me.active
    # "1 of your Benched Pokémon" -> promote the readiest attacker (engine's promote heuristic)
    me.bench.sort(key=lambda m: (m.total_energy(), m.card.hp), reverse=True)
    new_active = me.bench.pop(0)
    new_active.came_from_bench = True
    me.active = new_active
    me.bench.append(old)                       # the old Active moves to the Bench
    if old.card.is_ex:
        old.damage = max(0, old.damage - 80)   # heal 80 from the ex we moved back
    return True


# ---- 2. Acerola's Mischief ----
# Gate: opponent has <=2 Prizes remaining. Effect approximated as a full one-turn damage shield on
# our Active (the mon in the line of fire) via the engine's dr_turn/dr_amount "next turn" reduction.
# CAVEATS (noted): the shield isn't limited to opponent's *ex* attackers, and attack *effects*
# (status &c.) are not prevented — only damage. Fires only in the narrow <=2-prize window.
@trainer('supporter', "You can use this card only if your opponent has 2 or fewer Prize cards remaining.\n\nChoose 1 of your Pokémon in play. During your opponent's next turn, prevent all damage from and effects of attacks done to that Pokémon by your opponent's Pokémon ex.")
def acerola_mischief(t):
    if len(t.opp.prizes) > 2 or t.me.active is None:
        return False
    tgt = t.me.active
    tgt.dr_turn = t.game.turn                   # applies on the opponent's next turn (dr_turn+1 == turn)
    tgt.dr_amount = 10000                       # "prevent all damage"
    return True


# ---- 3. Amarys ----
# Immediate draw 4. The "at the end of this turn, if 5+ cards, discard your hand" drawback needs an
# end-of-turn trainer hook the engine doesn't have, so it is left unmodeled (noted).
@trainer('supporter', "Draw 4 cards. At the end of this turn, if you have 5 or more cards in your hand, discard your hand.")
def amarys(t):
    t.draw(4)
    return True


# ---- 4. Anthea & Concordia ----
# Requires SIX specific "N's" Pokémon in play at once (effectively unreachable). Even when met, the
# "take 3 more Prize cards on KO this turn" needs a KO-time prize hook that doesn't exist -> no-op.
@trainer('supporter', "You can use this card only if you have N's Darmanitan, N's Zoroark ex, N's Vanilluxe, N's Klinklang, N's Reshiram, and N's Zekrom in play.\n\nDuring this turn, if your opponent's Active Pokémon is Knocked Out by damage from an attack used by your N's Pokémon, take 3 more Prize cards.")
def anthea_concordia(t):
    names = {m.card.name for m in t.me.all_mons()}
    if not all(n in names for n in N_NAMES):
        return False
    return False                               # gate met (never, in practice) but prize-bonus unmodelable


# ---- 5. Bianca's Devotion ----
@trainer('supporter', "Heal all damage from 1 of your Pokémon that has 30 HP or less remaining.")
def biancas_devotion(t):
    cands = [m for m in t.me.all_mons() if m and m.hp_left <= 30 and m.damage > 0]
    if not cands:
        return False
    tgt = max(cands, key=lambda m: m.damage)
    tgt.damage = 0                             # heal ALL damage from that Pokémon
    return True


# ---- 6. Billy & O'Nare ----
@trainer('supporter', "Draw 2 cards. Then, if you have 10 or more cards in your hand, draw 2 more cards.")
def billy_onare(t):
    t.draw(2)
    if len(t.me.hand) >= 10:
        t.draw(2)
    return True


# ---- 7. Black Belt's Training ----
# A "during this turn, +40 damage to the opponent's Active ex" offensive team buff. The engine's
# damage path (effects.team_attack_bonus) reads only ability sources, not played Supporters, so there
# is no faithful hook -> conservative no-op (noted). Revisit if a played-supporter buff hook is added.
@trainer('supporter', "During this turn, attacks used by your Pokémon do 40 more damage to your opponent's Active Pokémon ex (before applying Weakness and Resistance).")
def black_belts_training(t):
    return False


# ---- 8. Boss's Orders ----
@trainer('supporter', "Switch in 1 of your opponent's Benched Pokémon to the Active Spot.")
def bosss_orders(t):
    return t.gust()


# ---- 9. Briar ----
# "If your opponent's Active is KO'd by your Tera Pokémon this turn, take 1 more Prize." Tera is not
# modeled (no Tera flag) and there is no KO-time prize hook -> conservative no-op (noted).
@trainer('supporter', "You can use this card only if your opponent has exactly 2 Prize cards remaining.\n\nDuring this turn, if your opponent's Active Pokémon is Knocked Out by damage from an attack used by your Tera Pokémon, take 1 more Prize card.")
def briar(t):
    return False


# ---- 10. Brock's Scouting ----
@trainer('supporter', "Search your deck for up to 2 Basic Pokémon or 1 Evolution Pokémon, reveal them, and put them into your hand. Then, shuffle your deck.")
def brocks_scouting(t):
    got = t.search_pokemon(lambda c: c.stage == 0, 2)   # prefer 2 Basics (more board development)
    if got == 0:
        got = t.search_pokemon(lambda c: c.stage > 0, 1)
    return got > 0


# ---- 11. Canari ----
# Cost: discard another card from hand. Effect: search up to 4 {L} Pokémon to hand. Only pay the cost
# when there is at least one {L} Pokémon to fetch (avoids whiffing the discard).
@trainer('supporter', "You can use this card only if you discard another card from your hand.\n\nSearch your deck for up to 4 {L} Pokémon, reveal them, and put them into your hand. Then, shuffle your deck.")
def canari(t):
    if not t.me.hand:                                   # need another card to discard
        return False
    if not any(x[0] == 'P' and x[1].ptype == 'Lightning' for x in t.me.deck):
        return False
    _discard_one(t.me)
    return t.search_pokemon(lambda c: c.ptype == 'Lightning', 4) > 0


# ---- 12. Caretaker ----
# Draw 2. The "if Community Center is in play, shuffle this Caretaker back instead of discarding"
# recycle needs the played card's own token (not available here) -> unmodeled (noted).
@trainer('supporter', "Draw 2 cards. If you drew any cards in this way and if Community Center is in play, shuffle this Caretaker into your deck instead of discarding it.")
def caretaker(t):
    t.draw(2)
    return True


# ---- 13. Carmine ----
@trainer('supporter', "If you go first, you may use this card during your first turn.\n\nDiscard your hand and draw 5 cards.")
def carmine(t):
    _discard_whole_hand(t.me)
    t.draw(5)
    return True


# ---- 14. Cassiopeia ----
# Legality gate: it must be the last card in hand. Assuming the integration removes the played
# Supporter from hand before resolving (as the legacy resolver does), "last card" => hand now empty.
@trainer('supporter', "You can use this card only when it is the last card in your hand.\n\nSearch your deck for up to 2 cards and put them into your hand. Then, shuffle your deck.")
def cassiopeia(t):
    if len(t.me.hand) != 0:
        return False
    return t.game._search_deck_to_hand(t.me, lambda tok: True, 2) > 0
