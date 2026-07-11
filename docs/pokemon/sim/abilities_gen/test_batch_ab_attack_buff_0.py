#!/usr/bin/env python3
"""Unit tests for batch ab_attack_buff_0 (offensive attack_buff abilities)."""
from effects_testkit import mk, runner
import ability_effects as AB
import abilities_gen.batch_ab_attack_buff_0  # noqa: F401  (registers the abilities)


KEYS = {
    'excited': "- If you have any {D} Mega Evolution Pokémon ex in play, attacks used by this Pokémon do 120 more damage to your opponent's Active Pokémon (before applying Weakness and Resistance).",
    'victory': "- Attacks used by your Evolution {R} Pokémon do 10 more damage to your opponent's Active Pokémon (before applying Weakness and Resistance).",
    'sunny':   "- Attacks used by your {G} Pokémon and {R} Pokémon do 20 more damage to your opponent's Active Pokémon (before applying Weakness and Resistance).",
    'compound': "- Attacks used by this Pokémon do 50 more damage to your opponent's Active Pokémon that has an Ability (before applying Weakness and Resistance).",
    'asalt':   "- Attacks used by your {F} Pokémon do 30 more damage to your opponent's Active Pokémon (before applying Weakness and Resistance).",
}


def fn_of(key):
    return AB.ABILITY_EFFECTS[AB.normalize(key)]['fn']


class FC:
    """Minimal stand-in Card for driving type/stage/ability branches."""
    def __init__(self, name='X', ptype='Colorless', stage=0, is_ex=False, abilities=None):
        self.name = name; self.ptype = ptype; self.stage = stage
        self.is_ex = is_ex; self.abilities = abilities if abilities is not None else []
        self.hp = 100; self.weakness = None; self.retreat = 0; self.attacks = []


TESTS = []
def test(f): TESTS.append(f); return f


# ---- registration integrity: every key matches the real card DB text exactly ----
@test
def t_keys_registered_and_in_card_db():
    from cards import load_cards
    BK, _ = load_cards()
    db = {AB.normalize(a['text']) for c in BK.values() for a in c.abilities}
    for name, key in KEYS.items():
        k = AB.normalize(key)
        assert k in AB.ABILITY_EFFECTS, f'{name} not registered'
        assert AB.ABILITY_EFFECTS[k]['kind'] == 'attack_buff', f'{name} wrong kind'
        assert k in db, f'{name} key does not match any card ability text'


# ---- Seviper: Excited Power (self +120 iff a Darkness Mega ex is in play) ----
@test
def t_excited_power_no_mega():
    ctx, at, df, me, opp = mk()
    ctx.game.players = [me, opp]
    f = fn_of(KEYS['excited'])
    assert f(at, df, ctx.attack, ctx.game) == 0        # nothing on board qualifies


@test
def t_excited_power_dark_mega_ex_present():
    ctx, at, df, me, opp = mk()                        # me.bench has one VANILLA mon
    ctx.game.players = [me, opp]
    me.bench[0].card = FC(name='Mega Sableye ex', ptype='Darkness', is_ex=True)
    f = fn_of(KEYS['excited'])
    assert f(at, df, ctx.attack, ctx.game) == 120


@test
def t_excited_power_wrong_type_or_not_mega():
    ctx, at, df, me, opp = mk()
    ctx.game.players = [me, opp]
    f = fn_of(KEYS['excited'])
    me.bench[0].card = FC(name='Mega Gardevoir ex', ptype='Psychic', is_ex=True)  # Mega ex, wrong type
    assert f(at, df, ctx.attack, ctx.game) == 0
    me.bench[0].card = FC(name='Darkrai ex', ptype='Darkness', is_ex=True)        # Dark ex but not Mega
    assert f(at, df, ctx.attack, ctx.game) == 0
    me.bench[0].card = FC(name='Mega Absol', ptype='Darkness', is_ex=False)       # Mega but not ex
    assert f(at, df, ctx.attack, ctx.game) == 0


@test
def t_excited_power_opponent_mega_does_not_count():
    # "If YOU have any {D} Mega Evolution Pokémon ex in play" — an opponent's does NOT trigger it.
    ctx, at, df, me, opp = mk()
    ctx.game.players = [me, opp]
    opp.bench[0].card = FC(name='Mega Sharpedo ex', ptype='Darkness', is_ex=True)  # on the OPPONENT's side
    f = fn_of(KEYS['excited'])
    assert f(at, df, ctx.attack, ctx.game) == 0
    # and it fires only when the qualifier is on the attacker's own side
    me.bench[0].card = FC(name='Mega Gengar ex', ptype='Darkness', is_ex=True)
    assert f(at, df, ctx.attack, ctx.game) == 120


@test
def t_excited_power_no_players_safe():
    ctx, at, df, me, opp = mk()                        # game.players unset -> owner None -> 0, no crash
    f = fn_of(KEYS['excited'])
    assert f(at, df, ctx.attack, ctx.game) == 0


# ---- Victini: Victory Cheer (your Evolution Fire +10) ----
@test
def t_victory_cheer_fire_evolution():
    ctx, at, df, me, opp = mk()
    f = fn_of(KEYS['victory'])
    at.card = FC(ptype='Fire', stage=1)
    assert f(at, df, ctx.attack, ctx.game) == 10
    at.card = FC(ptype='Fire', stage=2)
    assert f(at, df, ctx.attack, ctx.game) == 10


@test
def t_victory_cheer_basic_or_wrong_type():
    ctx, at, df, me, opp = mk()
    f = fn_of(KEYS['victory'])
    at.card = FC(ptype='Fire', stage=0)                # Basic Fire (like Victini itself) -> no buff
    assert f(at, df, ctx.attack, ctx.game) == 0
    at.card = FC(ptype='Water', stage=1)               # Evolution but wrong type
    assert f(at, df, ctx.attack, ctx.game) == 0


# ---- Lilligant: Sunny Day (your Grass or Fire +20) ----
@test
def t_sunny_day_grass_and_fire():
    ctx, at, df, me, opp = mk()
    f = fn_of(KEYS['sunny'])
    at.card = FC(ptype='Grass', stage=0)
    assert f(at, df, ctx.attack, ctx.game) == 20
    at.card = FC(ptype='Fire', stage=2)
    assert f(at, df, ctx.attack, ctx.game) == 20


@test
def t_sunny_day_other_type():
    ctx, at, df, me, opp = mk()
    f = fn_of(KEYS['sunny'])
    at.card = FC(ptype='Water', stage=1)
    assert f(at, df, ctx.attack, ctx.game) == 0
    at.card = FC(ptype='Lightning', stage=0)
    assert f(at, df, ctx.attack, ctx.game) == 0


# ---- Galvantula: Compound Eyes (self +50 vs a defender that has an Ability) ----
@test
def t_compound_eyes_defender_with_ability():
    ctx, at, df, me, opp = mk()
    f = fn_of(KEYS['compound'])
    df.card = FC(abilities=[{'name': 'Some Ability', 'text': '- foo'}])
    assert f(at, df, ctx.attack, ctx.game) == 50


@test
def t_compound_eyes_defender_without_ability():
    ctx, at, df, me, opp = mk()
    f = fn_of(KEYS['compound'])
    df.card = FC(abilities=[])
    assert f(at, df, ctx.attack, ctx.game) == 0
    assert f(at, None, ctx.attack, ctx.game) == 0      # no defender -> 0, no crash


# ---- Garganacl: Powerful a-Salt (your Fighting +30) ----
@test
def t_powerful_a_salt_fighting():
    ctx, at, df, me, opp = mk()
    f = fn_of(KEYS['asalt'])
    at.card = FC(ptype='Fighting', stage=2)
    assert f(at, df, ctx.attack, ctx.game) == 30


@test
def t_powerful_a_salt_other_type():
    ctx, at, df, me, opp = mk()
    f = fn_of(KEYS['asalt'])
    at.card = FC(ptype='Grass', stage=1)
    assert f(at, df, ctx.attack, ctx.game) == 0
    at.card = FC(ptype='Colorless', stage=0)
    assert f(at, df, ctx.attack, ctx.game) == 0


if __name__ == '__main__':
    p, f = runner(TESTS)
    print(f'{p} pass {f} fail')
    raise SystemExit(1 if f else 0)
