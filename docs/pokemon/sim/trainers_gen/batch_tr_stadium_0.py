#!/usr/bin/env python3
"""Generated trainer batch: tr_stadium_0 (14 Stadiums).

Each effect is registered by its EXACT printed text via @trainer('stadium', text).

The 'stadium' kind fn(tctx) -> bool models ONLY the "Once during each player's turn,
that player may ..." optional ACTION a Stadium grants (returns True if it did something).
A Stadium's mere presence is tracked separately by the engine as game.stadium; continuous
PASSIVE auras (flat HP +/-, damage-reduction, condition-immunity, bench-damage prevention,
rules modifiers like "may evolve the turn played") are applied by the engine's combat layers
(effects.py: team_hp_bonus / incoming_damage / checkup / evolve_all) keyed off that presence,
NOT by this action fn. Those stadiums therefore expose no per-turn action -> conservative
no-op (return False), each noted with the hook the engine would need. This mirrors the house
style for unmodeled effects (see batch_tr_supporter_0: black_belts_training / briar).

Model reminders (see engine.py):
  - Deck/hand tokens: ('P', Card) | ('E', type_str) | ('T', trainer_dict) | ('S', special_dict).
  - Top of deck == END of the deck list (draw() does deck.pop()).
  - Discarded basic energy lives in player.disc_energy (a Counter keyed by type name, e.g. 'Lightning').
  - player.played = names of Trainer cards played THIS turn (names only, no type).
"""
import os
import json
from trainer_effects import trainer, TrainerCtx


# --- Supporter-name set (for Community Center's "played a Supporter this turn" gate) ---
# player.played carries only NAMES, so recover trainerType from the source of truth. Robust:
# if the file can't be read the set is empty and the gate simply never fires (conservative).
def _load_supporter_names():
    try:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                         'deckgen', 'trainers.json')
        with open(p) as fh:
            d = json.load(fh)
        return {n for n, v in d.items() if v.get('trainerType') == 'Supporter'}
    except Exception:
        return set()


_SUPPORTER_NAMES = _load_supporter_names()


def _keep_priority(tok):
    """How useful a token is to KEEP in hand now (higher = keep). Used to pick the card to stash
    on top of the deck for Academy at Night: put back the LEAST-useful card."""
    if tok[0] == 'P':
        return 4 if tok[1].stage == 0 else 3      # a Basic can hit the board immediately
    if tok[0] in ('E', 'S'):
        return 2
    return 1                                        # Trainers are the most situational


# ---------------- Academy at Night ----------------
# Real per-turn action: move one card from hand to the top of the deck (drawn next turn).
# The choice of which card is the player's; put back the least-useful one deterministically.
@trainer('stadium', "Once during each player's turn, that player may put a card from their hand on top of their deck.")
def academy_at_night(t):
    if not t.me.hand:
        return False
    tok = min(t.me.hand, key=_keep_priority)
    t.me.hand.remove(tok)
    t.me.deck.append(tok)                           # top of deck == end of list
    return True


# ---------------- Ange Floette ----------------
# Passive: +150 HP to each Mega Floette ex in play (both players); play-restriction = discard a
# Prism Tower already in play. Mega Floette ex is NOT in the pool and Prism Tower is unmodeled, so
# there is nothing to buff and no per-turn action -> conservative no-op (noted).
@trainer('stadium', "You can put this card into play only if you discard a Prism Tower in play, and you can put this card into play during the same turn you play Prism Tower.\nEach Mega Floette ex in play (both yours and your opponent's) gets +150 HP.")
def ange_floette(t):
    return False


# ---------------- Area Zero Underdepths ----------------
# Tera Pokémon expand the Bench to 8 (and force bench-discards when no Tera remains / on leave).
# Tera is not modeled (no Tera flag) and the Bench cap is hard-coded at 5 in the engine -> no-op (noted).
@trainer('stadium', "Each player who has any Tera Pokémon in play can have up to 8 Pokémon on their Bench.\n\nIf a player no longer has any Tera Pokémon in play, that player discards Pokémon from their Bench until they have 5. When this card leaves play, both players discard Pokémon from their Bench until they have 5, and the player who played this card discards first.")
def area_zero_underdepths(t):
    return False


# ---------------- Battle Cage ----------------
# Passive: prevents damage COUNTERS placed on Benched Pokémon by the opponent's attack/Ability
# EFFECTS (spread/snipe) — direct attack damage still lands. No per-turn action; a faithful hook
# would live in the spread/snipe layer (effects.apply_spread / snipe) keyed off game.stadium -> no-op (noted).
@trainer('stadium', "Prevent all damage counters from being placed on Benched Pokémon (both yours and your opponent's) by effects of attacks and Abilities from the opponent's Pokémon. (Damage from attacks is still taken.)")
def battle_cage(t):
    return False


# ---------------- Community Center ----------------
# Real per-turn action, gated: if the player played a Supporter from hand this turn, they may heal
# 10 from EACH of their Pokémon. player.played has names only, so classify via the Supporter set.
@trainer('stadium', "Once during each player's turn, if they played a Supporter card from their hand this turn, they may heal 10 damage from each of their Pokémon.")
def community_center(t):
    if not any(n in _SUPPORTER_NAMES for n in t.me.played):
        return False
    did = False
    for m in t.me.all_mons():
        if m.damage > 0:
            m.damage = max(0, m.damage - 10)
            did = True
    return did


# ---------------- Dizzying Valley ----------------
# Passive rules-mod: a Confused Pokémon stays Confused through evolve/devolve. The engine already
# carries status forward on evolution (evolve_all copies mon.status) and devolve is unmodeled, so
# this matches current behavior with no per-turn action -> no-op (noted).
@trainer('stadium', "Confused Pokémon (both yours and your opponent's) don't recover from that Special Condition when they evolve or devolve.")
def dizzying_valley(t):
    return False


# ---------------- Festival Grounds ----------------
# Passive: every energized Pokémon (both players) sheds and is immune to all Special Conditions.
# Continuous condition-immunity aura; a faithful hook belongs in the status/checkup layer
# (effects.set_status / checkup) keyed off game.stadium. No per-turn action -> no-op (noted).
@trainer('stadium', "Each Pokémon that has any Energy attached (both yours and your opponent's) recovers from all Special Conditions and can't be affected by any Special Conditions.")
def festival_grounds(t):
    return False


# ---------------- Forest of Vitality ----------------
# Passive rules-mod: {G} Pokémon may evolve the turn they are played (except turn 1). The engine's
# evolve_all enforces turns >= 1; bypassing it for {G} needs a stadium-keyed exception there.
# No per-turn action -> no-op (noted).
@trainer('stadium', "Each player's {G} Pokémon can evolve into {G} Pokémon during the turn they play those Pokémon, except during their first turn.")
def forest_of_vitality(t):
    return False


# ---------------- Full Metal Lab ----------------
# Passive: {M} Pokémon (both players) take 30 less from the opponent's attacks. Damage-reduction
# aura; hook belongs in effects.incoming_damage keyed off game.stadium. No per-turn action -> no-op (noted).
@trainer('stadium', "{M} Pokémon (both yours and your opponent's) take 30 less damage from attacks from the opponent's Pokémon (after applying Weakness and Resistance).")
def full_metal_lab(t):
    return False


# ---------------- Granite Cave ----------------
# Passive: Steven's Pokémon (both players) take 30 less from the opponent's attacks. Same shape as
# Full Metal Lab, gated on the "Steven's" name family. No per-turn action -> no-op (noted).
@trainer('stadium', "Steven's Pokémon (both yours and your opponent's) take 30 less damage from attacks from the opponent's Pokémon (after applying Weakness and Resistance).")
def granite_cave(t):
    return False


# ---------------- Gravity Mountain ----------------
# Passive: each Stage 2 Pokémon (both players) gets -30 HP. Negative-HP aura; hook belongs in the
# max_hp / is_ko path keyed off game.stadium. No per-turn action -> no-op (noted).
@trainer('stadium', "Each Stage 2 Pokémon in play (both yours and your opponent's) gets -30 HP.")
def gravity_mountain(t):
    return False


# ---------------- Jamming Tower ----------------
# Passive: all attached Pokémon Tools (both players) are switched off. Tool-lock aura; a faithful
# hook would make the tool query API (tool_hp / tool_dr / ...) return neutral while game.stadium is
# this card. No per-turn action -> no-op (noted).
@trainer('stadium', "Pokémon Tools attached to each Pokémon (both yours and your opponent's) have no effect.")
def jamming_tower(t):
    return False


# ---------------- Levincia ----------------
# Real per-turn action: put up to 2 Basic {L} Energy from the discard pile into hand. Discarded
# basic energy lives in disc_energy (Counter by type); {L} == 'Lightning'. Returns cards as ('E','Lightning').
@trainer('stadium', "Once during each player's turn, that player may put up to 2 Basic {L} Energy cards from their discard pile into their hand.")
def levincia(t):
    moved = 0
    while moved < 2 and t.me.disc_energy.get('Lightning', 0) > 0:
        t.me.disc_energy['Lightning'] -= 1
        t.me.hand.append(('E', 'Lightning'))
        moved += 1
    return moved > 0


# ---------------- Lively Stadium ----------------
# Passive: each Basic Pokémon (both players) gets +30 HP. Flat-HP aura; hook belongs in the
# team_hp_bonus / max_hp path keyed off game.stadium. No per-turn action -> no-op (noted).
@trainer('stadium', "Each Basic Pokémon in play (both yours and your opponent's) gets +30 HP.")
def lively_stadium(t):
    return False
