#!/usr/bin/env python3
"""Effect batch: mill_0.

Deck-discard / deck-manipulation ("mill") attacks: discard the top card(s) of a deck
(opponent's = mill toward deck-out; own = thin / fuel), look at + reorder a deck, or
discard-and-copy a Supporter's / Pokémon's effect.

Modeling conventions (match the engine + the draw_0 batch):
- "Top of deck" == the END of the token list — Player.draw() pops from the end, and prizes
  are dealt off the end, so deck[-1] is the next card drawn.
- A discarded/milled card is routed exactly like the engine's own KO handling: a basic-energy
  token ('E', type) goes to that player's `disc_energy` Counter (so it stays available to that
  player's own accel/retrieval, which is correct — a milled basic energy sits in the discard);
  every other token (Pokémon / Trainer / Special Energy) appends to `discard`.
- Discards stop cleanly on an empty deck (the engine's deck-out loss fires separately when a
  player actually tries to draw from an empty deck — milling to 0 is not itself a loss).
- "If you played <Trainer> this turn" gates now read the engine's per-turn play log via
  ctx.played_this_turn(name) — e.g. the Tarragon mill fires exactly when the Supporter Tarragon
  was played this turn. The "Ancient Supporter" gate stays floored: "Ancient" is a card TRAIT,
  not a single named card, and the engine exposes no trait lookup, so its bonus never fires (the
  base single-mill / damage is always correct — never a speculative bonus).
"""
from attack_effects import effect, EffectCtx, STATUSES
import attack_effects as AE


def _discard_top(player, n):
    """Discard the top `n` cards of `player`'s deck. Energy -> disc_energy, else -> discard.
    Stops early (no crash) if the deck empties."""
    for _ in range(n):
        if not player.deck:
            break
        tok = player.deck.pop()
        if tok[0] == 'E':
            player.disc_energy[tok[1]] += 1
        else:
            player.discard.append(tok)


def _apply_supporter_effect(ctx, tdict):
    """Resolve a Supporter card's effect via the engine's generic text-driven resolvers
    (the same categorization used by Game.play_trainers). Best-effort; unknown categories no-op."""
    g, me, opp = ctx.game, ctx.me, ctx.opp
    eff = tdict.get('effect', '')
    cat = g._tcat(tdict.get('name', ''), eff)
    try:
        if cat == 'DRAW':
            g._do_draw(me, eff)
        elif cat == 'ACCEL':
            g._do_accel(me, eff)
        elif cat == 'HEAL':
            g._do_heal(me, eff)
        elif cat == 'SEARCHPOKE':
            g._do_search_poke(me, eff)
        elif cat == 'SEARCHNRG':
            g._search_deck_to_hand(me, lambda x: x[0] == 'E', 2)
        elif cat == 'BENCH':
            g._do_search_poke(me, eff, to_bench=True)
        elif cat == 'GUST':
            g._gust(me, opp)
        elif cat == 'CANDY':
            g._rare_candy(me)
        elif cat == 'RECOVER':
            g._do_recover(me)
        # SWITCH / OTHER: no modeled board change
    except Exception:
        pass


# ---------------------------------------------------------------- mill the OPPONENT's deck

@effect("Discard the top card of your opponent's deck.")
def _mill_opp_1(ctx):
    _discard_top(ctx.opp, 1)
    return ctx.base


@effect("Discard the top 2 cards of your opponent's deck.")
def _mill_opp_2(ctx):
    _discard_top(ctx.opp, 2)
    return ctx.base


@effect("Discard the top card of your opponent's deck. If you played an Ancient Supporter card from your hand during this turn, discard 3 more cards in this way.")
def _mill_opp_ancient(ctx):
    _discard_top(ctx.opp, 1)                       # always discard the first card
    # +3 more only if an Ancient Supporter was played this turn — the sim never records this,
    # so the bonus stays off (never applied speculatively). Base single-mill is always correct.
    if getattr(ctx.me, 'played_ancient_supporter_this_turn', False):
        _discard_top(ctx.opp, 3)
    return ctx.base


@effect("If you played Tarragon from your hand during this turn, discard the top 3 cards of your opponent's deck.")
def _tarragon_mill(ctx):
    # Damage (base 80 on Hippowdon) is unconditional; the mill fires only if the Supporter Tarragon
    # was played from hand this turn (tracked in me.played via ctx.played_this_turn).
    if ctx.played_this_turn('Tarragon'):
        _discard_top(ctx.opp, 3)
    return ctx.base


# ---------------------------------------------------------------- discard from YOUR OWN deck

@effect("Discard the top card of your deck.")
def _mill_self_1(ctx):
    _discard_top(ctx.me, 1)
    return ctx.base


# ---------------------------------------------------------------- look / reorder (info only)

@effect("Look at the top 5 cards of your opponent's deck and put them back in any order.")
def _look_opp_5(ctx):
    # Pure information + reorder; "put them back in any order" includes leaving the order as-is,
    # and the sim has no card-quality signal to reorder on, so this is a no-op on board state.
    return ctx.base


@effect("Look at the top card of your deck. You may discard that card.")
def _look_self_may_discard(ctx):
    # Optional self-discard. With no signal to judge the peeked card useless, decline the discard
    # (a legal choice for "you may"); leaves the deck intact.
    return ctx.base


@effect("Look at the top card of your opponent's deck. You may have your opponent shuffle their deck.")
def _look_opp_may_shuffle(ctx):
    # Optional opponent-shuffle. Declined (a legal "you may" choice); no board change.
    return ctx.base


# ---------------------------------------------------------------- discard-and-copy attacks

@effect("Discard the top card of your deck, and if that card is a Supporter card, use the effect of that card as the effect of this attack.")
def _discard_use_supporter(ctx):
    # Ninetales (ME01): discard the top card of YOUR deck; if it's a Supporter, resolve its effect.
    me = ctx.me
    if me.deck:
        tok = me.deck.pop()
        if tok[0] == 'E':
            me.disc_energy[tok[1]] += 1
        else:
            me.discard.append(tok)
            if tok[0] == 'T' and tok[1].get('trainerType') == 'Supporter':
                _apply_supporter_effect(ctx, tok[1])
    return ctx.base


@effect("Discard the top card of your deck, and if that card is a Pokémon that doesn't have a Rule Box, choose 1 of its attacks and use it as this attack. (Pokémon ex, Pokémon V, etc. have Rule Boxes.)")
def _discard_copy_attack(ctx):
    # Slowking (SV07): discard the top card of YOUR deck; if it's a non-Rule-Box Pokémon, copy one
    # of its attacks as THIS attack (no energy cost paid). In this pool a Rule Box == a Pokémon ex.
    me = ctx.me
    if not me.deck:
        return ctx.base
    tok = me.deck.pop()
    if tok[0] == 'E':
        me.disc_energy[tok[1]] += 1
        return ctx.base
    me.discard.append(tok)
    if tok[0] != 'P':
        return ctx.base                            # Trainer / Special Energy -> nothing to copy
    card = tok[1]
    if getattr(card, 'is_ex', False):
        return ctx.base                            # has a Rule Box -> can't copy
    attacks = getattr(card, 'attacks', None) or []
    if not attacks:
        return ctx.base
    chosen = max(attacks, key=lambda a: a.get('dmg', 0))   # "choose 1" -> take the biggest hitter
    sub = EffectCtx(ctx.me, ctx.opp, ctx.attacker, ctx.defender, ctx.game, chosen)
    fn = AE.ATTACK_EFFECTS.get(AE.normalize(chosen.get('text', '')))
    if fn is None:
        return sub.base                            # vanilla / unmodeled copied attack -> its base
    try:
        return fn(sub)                             # resolve the copied attack's full effect + damage
    except Exception:
        return sub.base
