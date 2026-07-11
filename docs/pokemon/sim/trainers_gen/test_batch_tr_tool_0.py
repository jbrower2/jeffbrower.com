# -*- coding: utf-8 -*-
"""Unit tests for trainer batch tr_tool_0 (14 Pokémon Tools).

Tool effects are exercised via their registered hook signature (called directly through
TE.TRAINER_EFFECTS), with bare Mons built by `_mkmon` so on-card type / name / ex / weakness
can be set precisely. Registration texts below are byte-exact (straight apostrophe, standard é)."""
from collections import Counter
from effects_testkit import mk, runner
import trainer_effects as TE
import trainers_gen.batch_tr_tool_0            # noqa: F401  (registers the effects)
from cards import Card
from engine import Mon


# --- EXACT registration texts (must normalize-match batch_tr_tool_0.py) -----------------------
ADVERSITY = "If the Pokémon this card is attached to has Weakness to your opponent's Active Pokémon's type, is in the Active Spot, and is damaged by an attack from your opponent's Pokémon (even if this Pokémon is Knocked Out), draw 3 cards."
HANDHELD_FAN = "If the Pokémon this card is attached to is in the Active Spot and is damaged by an attack from your opponent's Pokémon (even if this Pokémon is Knocked Out), move an Energy from the Attacking Pokémon to 1 of your opponent's Benched Pokémon."
AIR_BALLOON = "The Retreat Cost of the Pokémon this card is attached to is {C}{C} less."
GRAVITY = "As long as the Pokémon this card is attached to is in the Active Spot, the Retreat Cost of both Active Pokémon is {C} more."
ANCIENT_BOOST = "The Ancient Pokémon this card is attached to gets +60 HP, recovers from all Special Conditions, and can't be affected by any Special Conditions."
CYNTHIA_WEIGHT = "The Cynthia's Pokémon this card is attached to gets +70 HP."
CORE_MEMORY = "The Mega Zygarde ex this card is attached to can use the attack on this card. (You still need the necessary Energy to use this attack.)"
COUNTER_GAIN = "If you have more Prize cards remaining than your opponent, attacks used by the Pokémon this card is attached to cost {C} less."
BABIRI = "If the Pokémon this card is attached to is damaged by an attack from your opponent's {M} Pokémon, it takes 60 less damage (after applying Weakness and Resistance), and discard this card."
COLBUR = "If the Pokémon this card is attached to is damaged by an attack from your opponent's {D} Pokémon, it takes 60 less damage (after applying Weakness and Resistance), and discard this card."
HABAN = "If the Pokémon this card is attached to is damaged by an attack from your opponent's {N} Pokémon, it takes 60 less damage (after applying Weakness and Resistance), and discard this card."
MOCHI = "Attacks used by the Poisoned Pokémon this card is attached to do 40 more damage to your opponent's Active Pokémon (before applying Weakness and Resistance)."
BRAVE = "If the Pokémon this card is attached to doesn't have a Rule Box, the attacks it uses do 30 more damage to your opponent's Active Pokémon ex (before applying Weakness and Resistance). (Pokémon ex, Pokémon V, etc. have Rule Boxes.)"
FUTURE_BOOST = "The Future Pokémon this card is attached to has no Retreat Cost, and the attacks it uses do 20 more damage to your opponent's Active Pokémon (before applying Weakness and Resistance)."

KINDS = {
    ADVERSITY: 'tool_ondamaged', HANDHELD_FAN: 'tool_ondamaged',
    AIR_BALLOON: 'tool_retreat', GRAVITY: 'tool_retreat',
    ANCIENT_BOOST: 'tool_hp', CYNTHIA_WEIGHT: 'tool_hp', CORE_MEMORY: 'tool_hp', COUNTER_GAIN: 'tool_hp',
    BABIRI: 'tool_dr', COLBUR: 'tool_dr', HABAN: 'tool_dr',
    MOCHI: 'tool_attack_buff', BRAVE: 'tool_attack_buff', FUTURE_BOOST: 'tool_attack_buff',
}

ATK = {'name': 'X', 'dmg': 0, 'cost': [], 'text': ''}     # dummy attack dict (unused by these buffs)


def fn(text):
    return TE.TRAINER_EFFECTS[TE.normalize(text)]['fn']


def _mkmon(name='TestMon', ptype='Colorless', is_ex=False, weakness=None, hp=130):
    """A bare Mon with chosen name / on-card type / ex flag / weakness, for driving Tool hooks."""
    c = Card.__new__(Card)
    c.name = name; c.set = 'X'; c.id = '0'; c.cat = 'cat-green'; c.price = 0.0
    c.is_ex = is_ex; c.energy = []; c.hp = hp; c.stage = 0; c.evolves_from = None
    c.ptype = ptype; c.weakness = weakness; c.retreat = 1; c.attacks = []; c.abilities = []
    return Mon(c)


TESTS = []
def test(f): TESTS.append(f); return f


# ------------------------------------------------------------------- registration
@test
def t_all_registered_with_expected_kind():
    assert len(KINDS) == 14
    for text, kind in KINDS.items():
        e = TE.TRAINER_EFFECTS[TE.normalize(text)]
        assert e['kind'] == kind, (text, e['kind'])


# ------------------------------------------------------------------- tool_retreat
@test
def t_air_balloon_minus_two():
    ctx, at, df, me, opp = mk()
    assert fn(AIR_BALLOON)(_mkmon('Holder'), me, ctx.game) == -2


@test
def t_gravity_gemstone_plus_one_only_while_active():
    ctx, at, df, me, opp = mk()
    holder = _mkmon('Holder'); me.active = holder
    assert fn(GRAVITY)(holder, me, ctx.game) == 1          # holder in Active Spot -> +{C}
    me.active = _mkmon('Other')                            # holder now benched
    assert fn(GRAVITY)(holder, me, ctx.game) == 0


# ------------------------------------------------------------------- tool_hp
@test
def t_ancient_booster_plus60_for_ancient_only():
    ctx, at, df, me, opp = mk()
    for nm in ('Great Tusk', 'Roaring Moon', 'Raging Bolt ex', 'Koraidon', 'Koraidon ex'):
        assert fn(ANCIENT_BOOST)(_mkmon(nm), me, ctx.game) == 60, nm
    for nm in ('Iron Hands', 'Miraidon', 'Pikachu'):       # Future / other -> not Ancient
        assert fn(ANCIENT_BOOST)(_mkmon(nm), me, ctx.game) == 0, nm


@test
def t_cynthias_power_weight_plus70_for_family_only():
    ctx, at, df, me, opp = mk()
    assert fn(CYNTHIA_WEIGHT)(_mkmon("Cynthia's Garchomp ex"), me, ctx.game) == 70
    assert fn(CYNTHIA_WEIGHT)(_mkmon("Cynthia's Roselia"), me, ctx.game) == 70
    assert fn(CYNTHIA_WEIGHT)(_mkmon('Pikachu'), me, ctx.game) == 0


@test
def t_core_memory_and_counter_gain_are_hp_noops():
    ctx, at, df, me, opp = mk()
    assert fn(CORE_MEMORY)(_mkmon('Mega Zygarde ex'), me, ctx.game) == 0
    assert fn(COUNTER_GAIN)(_mkmon('Holder'), me, ctx.game) == 0


# ------------------------------------------------------------------- tool_dr (Berries)
@test
def t_babiri_reduces_and_discards_vs_metal():
    ctx, at, df, me, opp = mk()
    holder = _mkmon('Holder'); holder.tools = ['Babiri Berry']
    assert fn(BABIRI)(100, _mkmon('M', ptype='Metal'), holder, me, ctx.game) == 40
    assert 'Babiri Berry' not in holder.tools                                   # one-shot: detached
    assert any(t[0] == 'T' and t[1]['name'] == 'Babiri Berry' for t in me.discard)


@test
def t_babiri_ignores_non_metal_and_is_kept():
    ctx, at, df, me, opp = mk()
    holder = _mkmon('Holder'); holder.tools = ['Babiri Berry']
    for typ in ('Fire', 'Water', 'Darkness', 'Dragon', 'Colorless'):
        assert fn(BABIRI)(100, _mkmon('X', ptype=typ), holder, me, ctx.game) == 100, typ
    assert holder.tools == ['Babiri Berry'] and me.discard == []               # untouched


@test
def t_colbur_reduces_vs_darkness_only():
    ctx, at, df, me, opp = mk()
    holder = _mkmon('Holder'); holder.tools = ['Colbur Berry']
    assert fn(COLBUR)(100, _mkmon('D', ptype='Darkness'), holder, me, ctx.game) == 40
    holder2 = _mkmon('Holder2'); holder2.tools = ['Colbur Berry']
    assert fn(COLBUR)(100, _mkmon('M', ptype='Metal'), holder2, me, ctx.game) == 100
    assert holder2.tools == ['Colbur Berry']


@test
def t_haban_reduces_vs_dragon_only():
    ctx, at, df, me, opp = mk()
    holder = _mkmon('Holder'); holder.tools = ['Haban Berry']
    assert fn(HABAN)(100, _mkmon('N', ptype='Dragon'), holder, me, ctx.game) == 40
    holder2 = _mkmon('Holder2'); holder2.tools = ['Haban Berry']
    assert fn(HABAN)(100, _mkmon('P', ptype='Psychic'), holder2, me, ctx.game) == 100


@test
def t_berry_floors_at_zero():
    ctx, at, df, me, opp = mk()
    holder = _mkmon('Holder'); holder.tools = ['Haban Berry']
    assert fn(HABAN)(50, _mkmon('N', ptype='Dragon'), holder, me, ctx.game) == 0


@test
def t_berry_conservative_noop_without_attacker():
    ctx, at, df, me, opp = mk()
    holder = _mkmon('Holder'); holder.tools = ['Babiri Berry']
    assert fn(BABIRI)(100, None, holder, me, ctx.game) == 100                   # never fire blind
    assert holder.tools == ['Babiri Berry']


# ------------------------------------------------------------------- tool_attack_buff
@test
def t_binding_mochi_plus40_only_when_poisoned():
    ctx, at, df, me, opp = mk()
    poisoned = _mkmon('Holder'); poisoned.status = {'Poisoned': True}
    assert fn(MOCHI)(poisoned, df, ATK, ctx.game) == 40
    assert fn(MOCHI)(_mkmon('Holder2'), df, ATK, ctx.game) == 0                 # no status


@test
def t_brave_bangle_plus30_no_rulebox_vs_ex():
    ctx, at, df, me, opp = mk()
    holder = _mkmon('Holder', is_ex=False)
    assert fn(BRAVE)(holder, _mkmon('Boss', is_ex=True), ATK, ctx.game) == 30
    # holder HAS a Rule Box (ex) -> no bonus
    assert fn(BRAVE)(_mkmon('ExHolder', is_ex=True), _mkmon('Boss', is_ex=True), ATK, ctx.game) == 0
    # defender is not a Pokémon ex -> no bonus
    assert fn(BRAVE)(holder, _mkmon('Plain', is_ex=False), ATK, ctx.game) == 0


@test
def t_future_booster_plus20_for_future_only():
    ctx, at, df, me, opp = mk()
    for nm in ('Iron Hands', 'Iron Crown ex', 'Miraidon', 'Miraidon ex'):
        assert fn(FUTURE_BOOST)(_mkmon(nm), df, ATK, ctx.game) == 20, nm
    for nm in ('Great Tusk', 'Koraidon', 'Pikachu'):        # Ancient / other -> not Future
        assert fn(FUTURE_BOOST)(_mkmon(nm), df, ATK, ctx.game) == 0, nm


# ------------------------------------------------------------------- tool_ondamaged
@test
def t_adversity_policy_draws3_on_weakness_hit_while_active():
    ctx, at, df, me, opp = mk()
    holder = _mkmon('Holder', ptype='Grass', weakness='Fire'); me.active = holder
    fn(ADVERSITY)(_mkmon('Attacker', ptype='Fire'), holder, me, ctx.game)
    assert len(me.hand) == 3


@test
def t_adversity_policy_no_draw_without_weakness_match():
    ctx, at, df, me, opp = mk()
    holder = _mkmon('Holder', ptype='Grass', weakness='Fire'); me.active = holder
    fn(ADVERSITY)(_mkmon('Attacker', ptype='Water'), holder, me, ctx.game)      # not weak to Water
    assert len(me.hand) == 0


@test
def t_adversity_policy_no_draw_when_benched():
    ctx, at, df, me, opp = mk()
    holder = _mkmon('Holder', ptype='Grass', weakness='Fire')
    me.active = _mkmon('SomethingElse')                                         # holder is NOT Active
    fn(ADVERSITY)(_mkmon('Attacker', ptype='Fire'), holder, me, ctx.game)
    assert len(me.hand) == 0


@test
def t_handheld_fan_moves_energy_to_attackers_bench():
    ctx, at, df, me, opp = mk()                             # opp has 1 benched Pokémon by default
    ctx.game.players = [me, opp]                            # holder side = me; attacker side = opp
    holder = _mkmon('Holder'); me.active = holder
    attacker = df                                           # opp.active is the Attacking Pokémon
    attacker.energy = Counter({'Fire': 2})
    before = opp.bench[0].energy.get('Fire', 0)
    fn(HANDHELD_FAN)(attacker, holder, me, ctx.game)
    assert attacker.energy.get('Fire', 0) == 1             # one Energy left the attacker
    assert opp.bench[0].energy.get('Fire', 0) == before + 1 # ...and landed on its bench


@test
def t_handheld_fan_noop_when_no_bench_or_not_active():
    # No benched opponent Pokémon -> nothing to move to (no crash).
    ctx, at, df, me, opp = mk(opp_bench=0)
    ctx.game.players = [me, opp]
    holder = _mkmon('Holder'); me.active = holder
    df.energy = Counter({'Fire': 1})
    fn(HANDHELD_FAN)(df, holder, me, ctx.game)
    assert df.energy.get('Fire', 0) == 1
    # Holder not in the Active Spot -> effect does not fire.
    ctx2, at2, df2, me2, opp2 = mk()
    ctx2.game.players = [me2, opp2]
    df2.energy = Counter({'Water': 1})
    benched = _mkmon('Benched')                            # not me2.active
    fn(HANDHELD_FAN)(df2, benched, me2, ctx2.game)
    assert df2.energy.get('Water', 0) == 1                 # unchanged


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
