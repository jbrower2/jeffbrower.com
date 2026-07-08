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

## ⚠️ v1 fidelity: base combat only

**Implemented:** setup/mulligans, 6 prizes, turn loop (draw / bench / evolve / one
energy attach / retreat / attack), energy-cost checks, **base** attack damage,
Weakness ×2, KO + prizes (2 for ex), win by prizes / no-Pokémon / deck-out, a greedy AI.

**Not yet modeled:** attack/ability **text effects** — scaling damage ("×"/"+"
attacks use their printed base as a floor), energy acceleration, healing, spread,
status (burn/poison/sleep/etc.), search, and disruption.

**Therefore the current ranking is a raw-damage baseline, not a verdict.** Combo,
status, control, and energy-scaling decks (burn, Symphonia, Eelektrik, poison,
spread, Palafin, Zero-to-Hero, etc.) are systematically **under**-valued right now —
their payoffs simply don't fire. Big-printed-number Basics look artificially strong.

## Next layer: the effect registry (to make results meaningful)

The engine has two clean hooks:
- `Game.best_attack` — where an attack's **damage** is computed (add scaling/conditional handlers here).
- `Game.ai_main` — where **abilities** resolve each turn (add accel/heal/search/status handlers here).

Plan: a registry mapping ability/attack name → handler, implemented in impact order —
(1) energy acceleration abilities (Dynamotor, Golden Flame, Metal Maker, Wash Out, Regi-charges),
(2) common scaling-damage patterns (per-energy, per-bench, per-prize, per-damage-counter),
(3) status (burn/poison checkup, sleep/paralysis skip-turn), (4) heal + damage reduction,
(5) spread + gust + disruption. Re-run `sim_run.py --all` after each layer and watch the
ranking re-shape toward the cohesive archetypes.
