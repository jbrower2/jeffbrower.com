#!/usr/bin/env python3
"""Unit tests for ability batch ab_on_damaged_0 (Counterattack-style on_damaged reactions).

Keys are pulled straight from the real card printings so the test binds to the exact registered
text. on_damaged signature: fn(atk_mon, dfn_mon, dfn_owner, game). In mk() the attacker is
me.active and the defender is opp.active, so a normal trigger is f(at, df, opp, ctx.game)."""
from effects_testkit import mk, runner
import ability_effects as AB
import abilities_gen.batch_ab_on_damaged_0  # noqa: F401 (registers the batch on import)
from cards import load_cards

BK, BN = load_cards()

# card key -> ability name (source of each registered exact-text key)
BRUXISH = 'SV08:#049/191'          # Counterattack (3 damage counters)
IRON_JUGULIS = 'SV05:#139/162'     # Automated Combat (same text as Counterattack)
SPIRITOMB = 'ME01:#087/132'        # Spiteful Swirl (1 counter, Active {D})
NUMEL = 'ASH:#027/217'             # Incandescent Body (Burn attacker)
TURTONATOR = 'ME03:#017/088'       # Shell Spikes (discard an Energy)
TRR_KOFFING = 'SV10:#125/182'      # Smog Signals (bench up to 2 "Koffing")
KOFFING = 'SV09:#091/159'          # a plain "Koffing" (search target)
WATER_MON = BRUXISH                # a non-Darkness card for the Spiritomb negative branch


def entry_of(card_key, ab_name):
    c = BK[card_key]
    text = next(ab['text'] for ab in c.abilities if ab['name'] == ab_name)
    return AB.ABILITY_EFFECTS[AB.normalize(text)]


# ---------------------------------------------------------------- 3 damage counters (Bruxish / Iron Jugulis)
def t_counterattack_kind():
    assert entry_of(BRUXISH, 'Counterattack')['kind'] == 'on_damaged'


def t_counterattack_hits_active_attacker():
    ctx, at, df, me, opp = mk()
    f = entry_of(BRUXISH, 'Counterattack')['fn']
    f(at, df, opp, ctx.game)                 # df (opp active) damaged -> 3 counters on attacker
    assert at.damage == 30, at.damage


def t_counterattack_even_if_ko():
    # "even if this Pokémon is Knocked Out": df is at lethal damage but still Active -> still fires.
    ctx, at, df, me, opp = mk()
    df.damage = df.max_hp
    entry_of(BRUXISH, 'Counterattack')['fn'](at, df, opp, ctx.game)
    assert at.damage == 30, at.damage


def t_counterattack_only_from_active_spot():
    # Holder damaged on the Bench (not the Active Spot) -> no counterattack.
    ctx, at, df, me, opp = mk()
    benched = opp.bench[0]
    entry_of(BRUXISH, 'Counterattack')['fn'](at, benched, opp, ctx.game)
    assert at.damage == 0, at.damage


def t_iron_jugulis_shares_registration():
    # count=2: Bruxish + Iron Jugulis carry identical text -> one shared registered fn.
    assert entry_of(IRON_JUGULIS, 'Automated Combat')['fn'] is entry_of(BRUXISH, 'Counterattack')['fn']


def t_iron_jugulis_fires():
    # Direct firing of Iron Jugulis's own entry (not just the identity assert): 3 counters = +30.
    ctx, at, df, me, opp = mk()
    entry_of(IRON_JUGULIS, 'Automated Combat')['fn'](at, df, opp, ctx.game)
    assert at.damage == 30, at.damage


def t_counterattack_ignores_shield():
    # Damage counters are NOT an attack "effect" gated by effect_immune (which only blocks Special
    # Conditions, attack_effects.py:113). A Mist-Energy attacker still eats the 3 counters.
    ctx, at, df, me, opp = mk()
    at.special = ['Mist Energy']
    entry_of(BRUXISH, 'Counterattack')['fn'](at, df, opp, ctx.game)
    assert at.damage == 30, at.damage


# ---------------------------------------------------------------- 1 damage counter, Active {D} (Spiritomb)
def t_spiteful_swirl_kind():
    assert entry_of(SPIRITOMB, 'Spiteful Swirl')['kind'] == 'on_damaged'


def t_spiteful_swirl_darkness_active():
    ctx, at, df, me, opp = mk()
    df.card = BK[SPIRITOMB]                   # Active Darkness Pokémon
    entry_of(SPIRITOMB, 'Spiteful Swirl')['fn'](at, df, opp, ctx.game)
    assert at.damage == 10, at.damage


def t_spiteful_swirl_needs_darkness():
    # A non-Darkness Active mon does not satisfy "your Active {D} Pokémon".
    ctx, at, df, me, opp = mk()
    df.card = BK[WATER_MON]                   # Water type, not {D}
    entry_of(SPIRITOMB, 'Spiteful Swirl')['fn'](at, df, opp, ctx.game)
    assert at.damage == 0, at.damage


def t_spiteful_swirl_only_active():
    ctx, at, df, me, opp = mk()
    benched = opp.bench[0]
    benched.card = BK[SPIRITOMB]              # Spiritomb on the bench, not Active -> no fire
    entry_of(SPIRITOMB, 'Spiteful Swirl')['fn'](at, benched, opp, ctx.game)
    assert at.damage == 0, at.damage


# ---------------------------------------------------------------- Burn the attacker (Numel)
def t_incandescent_kind():
    assert entry_of(NUMEL, 'Incandescent Body')['kind'] == 'on_damaged'


def t_incandescent_burns_attacker():
    ctx, at, df, me, opp = mk()
    entry_of(NUMEL, 'Incandescent Body')['fn'](at, df, opp, ctx.game)
    assert at.status.get('Burned') is True


def t_incandescent_respects_shield():
    # Burned is a Special Condition -> Mist Energy on the attacker blocks it (effect_immune()).
    ctx, at, df, me, opp = mk()
    at.special = ['Mist Energy']
    entry_of(NUMEL, 'Incandescent Body')['fn'](at, df, opp, ctx.game)
    assert not at.status.get('Burned')


def t_incandescent_only_active():
    ctx, at, df, me, opp = mk()
    benched = opp.bench[0]
    entry_of(NUMEL, 'Incandescent Body')['fn'](at, benched, opp, ctx.game)
    assert not at.status.get('Burned')


# ---------------------------------------------------------------- discard an Energy (Turtonator)
def t_shell_spikes_kind():
    assert entry_of(TURTONATOR, 'Shell Spikes')['kind'] == 'on_damaged'


def t_shell_spikes_discards_and_routes():
    ctx, at, df, me, opp = mk(atk_energy={'Fire': 2})
    ctx.game.players = [me, opp]              # enable discard routing to the attacker's owner (me)
    entry_of(TURTONATOR, 'Shell Spikes')['fn'](at, df, opp, ctx.game)
    assert at.energy['Fire'] == 1, at.energy  # one pip removed
    assert me.disc_energy['Fire'] == 1, me.disc_energy


def t_shell_spikes_only_active():
    ctx, at, df, me, opp = mk(atk_energy={'Fire': 2})
    benched = opp.bench[0]
    entry_of(TURTONATOR, 'Shell Spikes')['fn'](at, benched, opp, ctx.game)
    assert at.energy['Fire'] == 2, at.energy  # not Active -> nothing discarded


def t_shell_spikes_no_energy_noop():
    # Attacker with no energy -> safe no-op (no crash). (mk's `atk_energy={}` falls back to a
    # default, so clear it explicitly.)
    ctx, at, df, me, opp = mk()
    at.energy.clear()
    ctx.game.players = [me, opp]
    entry_of(TURTONATOR, 'Shell Spikes')['fn'](at, df, opp, ctx.game)
    assert at.total_energy() == 0


def t_shell_spikes_ignores_shield():
    # Energy discard is not effect-shielded either: a Mist-Energy attacker still loses a pip.
    ctx, at, df, me, opp = mk(atk_energy={'Fire': 2})
    at.special = ['Mist Energy']
    ctx.game.players = [me, opp]
    entry_of(TURTONATOR, 'Shell Spikes')['fn'](at, df, opp, ctx.game)
    assert at.energy['Fire'] == 1, at.energy
    assert me.disc_energy['Fire'] == 1, me.disc_energy


def t_shell_spikes_wild_pip_not_routed():
    # A special-energy pseudo-type pip ('Wild') is removed from the attacker but NOT routed to
    # disc_energy (which only tracks basic types) -- mirrors attack_effects._pull_energy.
    ctx, at, df, me, opp = mk(atk_energy={'Wild': 1})
    ctx.game.players = [me, opp]
    entry_of(TURTONATOR, 'Shell Spikes')['fn'](at, df, opp, ctx.game)
    assert at.total_energy() == 0, at.energy           # pip removed
    assert sum(me.disc_energy.values()) == 0, me.disc_energy  # nothing routed to discard


# ---------------------------------------------------------------- bench up to 2 "Koffing" (Team Rocket's Koffing)
def t_smog_signals_kind():
    assert entry_of(TRR_KOFFING, 'Smog Signals')['kind'] == 'on_damaged'


def t_smog_signals_benches_two_koffing():
    ctx, at, df, me, opp = mk()
    opp.deck = [('P', BK[KOFFING])] * 3 + opp.deck   # 3 Koffing available in the deck
    n_bench0 = len(opp.bench)
    entry_of(TRR_KOFFING, 'Smog Signals')['fn'](at, df, opp, ctx.game)
    koffing_benched = sum(1 for m in opp.bench if 'Koffing' in m.card.name)
    assert koffing_benched == 2, koffing_benched
    assert len(opp.bench) == n_bench0 + 2
    left = sum(1 for tok in opp.deck if tok[0] == 'P' and 'Koffing' in tok[1].name)
    assert left == 1, left                            # 3 - 2 benched = 1 remaining


def t_smog_signals_only_active():
    ctx, at, df, me, opp = mk()
    opp.deck = [('P', BK[KOFFING])] * 3 + opp.deck
    benched = opp.bench[0]
    n_bench0 = len(opp.bench)
    entry_of(TRR_KOFFING, 'Smog Signals')['fn'](at, benched, opp, ctx.game)
    assert len(opp.bench) == n_bench0                 # not Active -> no search
    assert not any('Koffing' in m.card.name for m in opp.bench)


TESTS = [
    t_counterattack_kind,
    t_counterattack_hits_active_attacker,
    t_counterattack_even_if_ko,
    t_counterattack_only_from_active_spot,
    t_iron_jugulis_shares_registration,
    t_iron_jugulis_fires,
    t_counterattack_ignores_shield,
    t_spiteful_swirl_kind,
    t_spiteful_swirl_darkness_active,
    t_spiteful_swirl_needs_darkness,
    t_spiteful_swirl_only_active,
    t_incandescent_kind,
    t_incandescent_burns_attacker,
    t_incandescent_respects_shield,
    t_incandescent_only_active,
    t_shell_spikes_kind,
    t_shell_spikes_discards_and_routes,
    t_shell_spikes_only_active,
    t_shell_spikes_no_energy_noop,
    t_shell_spikes_ignores_shield,
    t_shell_spikes_wild_pip_not_routed,
    t_smog_signals_kind,
    t_smog_signals_benches_two_koffing,
    t_smog_signals_only_active,
]

if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
