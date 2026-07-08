# sim — Pokémon pauper match simulator

Plays the decks in `../decks.md` head-to-head to compute win rates. Consumes the
printing-level card data from `../deckgen/printings.json`. Python 3 stdlib only.

```sh
cd docs/pokemon/sim
python3 cards.py                 # sanity-check the card model
python3 decks_build.py           # verify all 165 archetypes build to a legal 60
python3 sim_run.py               # flagship-of-each-section round-robin (fast)
python3 sim_run.py --all --games 16   # full 165-deck round-robin (~20s)
python3 sim_run.py --section G --games 60
```

## Files
- **`cards.py`** — data-derived `Card` model (HP, stage, evolves_from, type, weakness, retreat, is_ex, attacks with parsed base damage). Cards keyed by (set, id) so same-name variants stay distinct.
- **`decks_build.py`** — parses each archetype's Premium/Supports from `../deckgen/decks_*.txt` and auto-builds a legal 60-card list (premium + C/U evo line + ≤2 supports + a backup basic + basic energy). Heuristic lists, not tuned.
- **`engine.py`** — the match engine + heuristic AI + `run_match`.
- **`sim_run.py`** — round-robin runner and win-rate ranking.

## Format modeled
60-card decks, max 4 copies of a non-energy card, unlimited basic energy; the price
rule is a physical-copy cap (1 card ≤$1 + 2 cards ≤$0.50). No Trainer cards — the
data pool is Pokémon-only — so decklists are Pokémon + basic energy.

## Fidelity: effect registry (`effects.py`)

**Core rules:** setup/mulligans, 6 prizes, turn loop (draw / bench / evolve / one
energy attach / attack), energy-cost checks, Weakness ×2, KO + prizes (2 for ex),
win by prizes / no-Pokémon / deck-out, a greedy AI.

**Effect layers implemented:**
- **(1) Energy acceleration** — `ABILITY_ACCEL` handlers (Dynamotor, Inferno Fandango,
  Electric Streamer, Golden Flame, Metal Maker, Stone Arms, Wash Out, Metal Road) plus
  from-hand / from-discard / from-deck helpers. Discard-energy pool is tracked.
- **(2) Scaling damage** — generic evaluator for `×` / `+` / `-` attacks: per-energy,
  per-bench, per-prize, per-damage-counter, per-type-in-play, coin-flip, and `if <cond>`
  bonuses (ex / evolution / stage-2 / damaged / burned-poisoned / bench-damaged / etc.).
  Plus attack side-effects: recoil, self-energy discard, and cooldowns.
- **(3) Special conditions** — Burn/Poison/Sleep/Paralysis/Confusion: applied by attacks,
  resolved at a between-turns Checkup (poison tick incl. heavy-poison amounts, burn +
  coin-off, sleep coin-off), Sleep/Paralysis block attacking, Confusion is a coin flip.

- **(4) Healing / damage reduction / HP buffs / immunity** — `incoming_damage()` applies
  immunity (vs-ex like Crustle/Sylveon, ≥200 like Drednaw, coin-prevent, ability-immunity),
  flat reductions (self "takes N less" + team "take N less", incl. energy/name-conditioned
  Aurorus/Klinklang/Carbink/Curly-Wall), and temp "-N next turn" self-buffs; `team_hp_bonus()`
  adds +HP auras (Ludicolo); attack + `HEAL_ABILITIES` handlers heal.
- **(5) Spread + ability-lock** — `apply_spread()` deals bench damage (KOs benched → prizes);
  `abilities_disabled()` shuts off a player's abilities under Flutter Mane / Iron Thorns.

**Piloting upgrades done:** realistic auto-lists (sensible energy count + backup attacker
lines, `decks_build.py` also returns each deck's *ace*), an **ace-aware AI** (`engine`:
builds/funds the ace even on the bench, evolves the ace line, retreats to promote the
readiest attacker, KO/value attack selection), and **utility attacks** (draw / search-to-hand
so setup decks dig for their pieces). Validated: 0 draws, ~120/165 decks in a 30–70% band.

**The dominant remaining factor is structural: the pool is Pokémon-only (no Trainers).**
Fast Basic / accel decks (Lightning ~80%, Fighting ~74% section avg) attack on turn 2, while
singleton Stage-2 evolution decks (Grass ~34%) can't reliably set up without Trainer support
(Rare Candy, draw supporters, ball search). This is an accurate model *of a trainerless
format*, but it under-represents how complex/evolution decks perform in real Pokémon.

**Biggest next lever — a generic "consistency shell":** give every deck a standard abstract
Trainer engine (draw-supporter, Pokémon search, switch, a Rare-Candy-style stage skip) since
the data has no real Trainer cards. That's what lets evolution/combo decks come online and
makes cross-archetype win rates trustworthy. Then: niche effects (gust targeting,
per-special-condition scaling, Punk-Up/X-Boot search-accel, disruption) and AI polish.

## Extending

Scaling: `effects.eval_count` / `eval_cond`. Energy accel: `effects.ABILITY_ACCEL`.
Heal: `effects.HEAL_ABILITIES`. Reduction/immunity: `effects.incoming_damage`. Spread:
`effects.apply_spread`. Re-run `sim_run.py --all` after each change and watch the ranking move.
