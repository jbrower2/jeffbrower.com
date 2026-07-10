# Pokémon — budget "pauper" deck lab

Analysis project over a fixed Pokémon TCG card pool. Goal: design a large catalog of cohesive budget decks, then build a **game simulator** to play them against each other and optimize/compare win rates.

## The format (deck legality)

A deck's three "money" slots:

1. **1 premium** card whose cheapest printing is **≤ $1.00** — in practice always the ex / Mega-ex centerpiece.
2. **2 support** cards, each a rarer-than-uncommon card **≤ $0.50** (two copies of one card, written "×2", uses both slots).
3. **Everything else** must be **Common/Uncommon Pokémon or basic Energy** (unlimited).

Prices = cheapest legal printing at time of analysis; they drift, so re-check. **Deck size is unspecified so far** (assumed standard 60-card PTCG; confirm with the user before the simulator hard-codes it).

## Files in this directory

- **`types.html`** — the card database and read-only source of truth (~2.3 MB, auto-generated report "Pauper cards by type"). Do not hand-edit.
- **`exes.md`** — reference list of every legal ex/Mega-ex, grouped by the energy its line pays for (plus Multi + Colorless). Terse, opinionated one-liners.
- **`decks.md`** — the deck catalog (**165 decks**, ~10–20 per type). Each deck = premium + 2 supports + C/U core + a "why it works" line, ordered strongest → most experimental (weak/experimental ones flagged).
- Site-data scripts that *produce* `types.html` (not part of the deck analysis): `evolve-infer.js`, `fetch-carddata.js`, `fetch-dexid.js`, `fill-evolvefrom.js`, `pauper-report.js`, `report-data.json`, `pricing.csv`, `cards/`, `carddata/`, `evolution-check.html`.

## ⚠️ Parse at the PRINTING level, not by card name

The single biggest data trap. **Many Pokémon have multiple *different* cards under the same name** — 380 names have ≥2 mechanically-distinct printings. Example: two "Palafin" — the SV05 one is a vanilla attacker; the **SV06** one has the **Zero to Hero** ability (the entire Palafin ex archetype depends on it). A name-keyed parser silently drops the alternate and mis-pairs price with mechanics (this exact bug once made us wrongly call Palafin ex "uncastable").

- The pool has **1,836 distinct printings** across **1,118 names** / 615 families. Always key on **set + card number** (each `<tr class="cardrow">`), never on name.
- Each printing carries its **own** price, rarity, and mechanics — don't take min-price-of-name + first-printing-mechanics.
- Where two same-named cards differ, deck entries name the exact printing (e.g. "the SV06 Palafin", "the ASH Miraidon ex", "the SV09 Reshiram ex").

## `types.html` structure (for rebuilding the parser)

- `<section class="family" data-types="grass fire">…</section>` = one evolution line. `data-types` is the union of on-card Pokémon types (NOT the energy it pays — see classification below).
- Header: `<span class="dex">#0001</span><h2>Bulbasaur</h2>`.
- Each `<tr class="cardrow CAT">…</tr>` = one **printing**. `CAT` is the rarity/legality class:
  - `cat-green` = Common/Uncommon (free, unlimited — **never** a support slot)
  - `cat-yellow` = higher rarity, cheapest printing ≤ $1 (fills a paid slot)
  - `cat-red` = > $1 (illegal, never use)
- Species cell: `<div class="cname">Name</div><div class="crarity">Stage Type</div>` + a `catpill` (species colored by its cheapest printing).
- Set/number: `<td class="setcell"><a>SET</a><span class="lid">#NNN</span>`. Price: `<td class="pr">$0.86</td>` (a `tag50` span marks ≤ $0.50). Mechanics: `<td class="mech"><div class="ctext">…</div></td>` with `.meta` (HP/type/stage), `.ab` (abilities), `.atk` (attacks).
- **Energy symbols:** `<span class="en" title="Grass">G</span>`. **The letter is ambiguous — "F" means BOTH Fire and Fighting** — so ALWAYS read the `title` attribute. Titles: Grass, Fire, Water, Lightning, Psychic, Fighting, Darkness, Metal, Colorless. An attack's cost = the leading `en` spans inside the `<b>` of its `.atk` div; `{C}` (Colorless) can be paid by any energy.

## Classification: by ENERGY paid, not by Pokémon type

A card/deck's "type" bucket = the energy its evolution line actually **pays for** (attack costs + energy its abilities attach/move), excluding Colorless — *not* the on-card Pokémon type.

- Scovillain (a Grass/Fire Pokémon) attacks with `{R}` only → **Fire**. Scizor (Metal; pre-evo Scyther is Grass) pays `{M}` → **Metal**.
- 1 energy type → that section. 2–3 genuinely needed → **Multi**. Attackers whose costs are all `{C}` → **Colorless**.
- Cards that *scale with* a specific energy (Mega Meganium / Hydrapple reward `{G}`) go under that type even though the attack cost is colorless.
- **No basic Dragon energy exists** — Dragon Pokémon pay with other-typed energy; bucket them by that.

## Pool is POKÉMON-ONLY

`types.html` contains only Pokémon (+ basic energy). Tools, Stadiums, Supporters, and Fossils are **not** in it — assume they're available as standard Trainer cards (the sim models 197 C/U Trainers via `deckgen/trainers.json`). **Special Energy IS now modeled** — the Standard-legal (reg H/I/J) set lives in `sim/special_energy.py`, so **Lycanroc (needs Spiky Energy) is now playable**. Cards whose abilities require *out-of-pool* pieces are still effectively **dead** and shouldn't anchor a deck: Festival Lead (Festival Grounds), Heliolisk (Canari), Genesect's ACE Nullifier (ACE SPEC), Pidove (Unfezant ex), Munkidori ex's protective ability (needs Pecharunt *ex*, which isn't in the pool).

## Deck conventions (`decks.md`)

Template per deck (keep exactly):

```
**Deck Name** — one-line concept
- Premium: **Exact Card Name** — what it does.
- Supports: **Card A** (role) + **Card B** (role).
- Core: <C/U evolution lines + free engines + which basic Energy>.
- Why: <the specific synergy that makes these cards amplify each other>.
```

- Section order: Grass, Fire, Water, Lightning, Psychic, Fighting, Darkness, Metal, Colorless, Multi, Team Rocket's.
- **Cohesion is the whole point.** Every card must advance the plan. Named-family buffs only work with their group present (a buff that ends up affecting only itself is a failure — the original mistake was Cynthia's Roserade in a deck with no other Cynthia's cards). Named families: Cynthia's (Fighting), Ethan's (Fire), Erika's (Grass), Iono's + Hop's Pincurchin (Lightning), Marnie's (Dark), Steven's + Hop's Zacian (Metal), Larry's (Colorless), Misty's (Water, no ex), Team Rocket's (its own 52-card cross-type toolbox).

## Free (Common/Uncommon) engines worth knowing

- **Lightning:** Eelektrik (Dynamotor — repeatable `{L}` from discard). Magneton (dumps 3 energy from discard but KOs itself — one-shot burst, not an engine).
- **Fighting:** Barbaracle (attach `{F}` from hand). **Psychic:** Grumpig (attach off top 4), Aromatisse (search `{P}`), Dusclops (snipe 5 counters, self-KO). **Metal:** Metang/Metal Maker (attach `{M}` off top 4). **Water:** Dewgong/Wash Out (move `{W}` bench→active), Chansey. **Colorless:** Fan Rotom (turn-1 search), Larry's Komala. **Grass:** Rabsca (bench-shield).

## Card rulings we verified (check exact text, don't trust intuition)

- **Gourgeist ex** Horrifying Rondo scales off **your own** damaged bench, not the opponent's.
- **Palafin ex** only enters play via the SV06 Palafin's Zero to Hero.
- **Kingambit** Supreme Overlord = +30 per **Prize the opponent has taken** (comeback), and only its own attacks.
- **Wild Growth** (Meganium) "provides `{G}{G}`" reliably pays attack costs; whether it also doubles separate "per `{G}` energy" count-effects is a genuine gray area — don't build damage math that depends on it.
- **Drednaw** Impervious Shell only walls single hits of **200+**.
- Several ex have **multiple distinct printings** ≤$1 (e.g. Koraidon ex ×3, Reshiram ex ×2, Miraidon ex ×2) — different attacks; pick and name the printing you mean.

## Data pipeline — `deckgen/` (persisted; run order in `deckgen/README.md`)

- **`parse_printings.py`** → **`printings.json`**: printing-level index (`name -> [printings]`, each with set, id, `cat`, price, `ex` flag, `energy`, abilities, attacks). Reads titles for energy, row class for rarity. **Run this first** — the others read `printings.json`. This is the dataset the simulator should consume.
- **`audit_decks.py`**: cross-checks every deck's premium (needs an ex printing ≤$1) and each support (needs a cat-yellow printing ≤$0.50) against the index; reports hard errors + ambiguous multi-printing names. Invariant: **0 hard errors** (latest: 490 slot-cards).
- **`assemble_decks.py`**: concatenates the per-section source files (`decks_<TYPE>.txt` + optional `_extra`/`_new`) into `../decks.md`. **Edit the section files, not `decks.md` directly**, then re-run.
- **`coverage.py`**: lists legal ex premiums and rare ability-cards not yet used in any deck (finds design gaps).

## Current state

- **`exes.md`**: complete — every legal ex (~145) by energy type, plus Multi and Colorless, with the Palafin/Zero-to-Hero note corrected.
- **`decks.md`**: **165 decks** — Grass 19, Fire 15, Water 20, Lightning 12, Psychic 17, Fighting 16, Darkness 13, Metal 17, Colorless 19, Multi 10, Team Rocket's 7. All verified (0 hard errors).
- **`deckgen/`**: the persisted deck pipeline (`printings.json` + scripts + per-section deck source files).
- **`sim/`**: the match simulator **and coevolutionary optimizer**. Two optimization phases have run — phase-1 (8 rounds) then phase-2 (+10 rounds, after adding Special Energy, engine fixes, generator guards, and archive-and-revert). Final field **median ~53%**, 136/165 in the 30–70 band. Optimized lists + full change history + a browsable HTML report exist.

## Format (confirmed)

Standard PTCG: **exactly 60 cards, max 4 copies** of any non-basic-energy card, unlimited basic energy. The money-slot rule applies **uniformly to Pokémon, Trainers, AND Energy by rarity/price**: Common/Uncommon → free & unlimited; Rare & ≤$0.50 → a support slot; ≤$1 → the premium slot; **>$1 → illegal**. At most **1 card ≤$1.00 + 2 cards ≤$0.50** (3 "money" cards total). Decks are Pokémon + C/U Trainers + basic energy + Standard-legal Special Energy.

**Rotation (2026):** only regulation marks **H / I / J** are legal — **G rotated out April 2026**. The F-mark universal accelerators (Double Turbo / Twin / Reversal) and the G-mark Jet / Luminous energy are all gone; the legal special-energy set is niche (see `sim/special_energy.py`). `deckgen/printings.json` is already filtered H/I/J-clean, so every deck in `decks.md` is rotation-legal.

## Simulator status

`sim/` plays the full 165-deck field and coevolves it. Consumes `deckgen/printings.json`.

**Engine (`engine.py` + `effects.py`).** Core rules (setup/mulligans, 6 prizes, turn loop, energy-cost checks, Weakness ×2, KO/prizes, win by prizes/no-Pokémon/deck-out) + effect layers: (1) energy acceleration; (2) scaling damage (×/+/− with conditions, attack side-effects, **self-discard-for-damage** like Mega Diancie's Garland Ray, and the **Echoed Voice ramp** `mon.ramp`); (3) special conditions + between-turns checkup; (4) heal / damage-reduction / HP-buff / immunity (`incoming_damage`, `team_hp_bonus`); (5) **spread + snipe** (valued in AI attack choice via `effects.spread_value`, credited in telemetry) + ability-lock. An **ace-aware heuristic AI** funds/evolves the ace (incl. on the bench), retreats/Switches to the readiest attacker, and picks KO/value/gust/utility attacks.

**Cards modeled.** Pokémon (from `printings.json`); **197 C/U Trainers** (`deckgen/trainers.json`) via a text-driven resolver (draw/gust/search-poke/search-energy/accel/heal/rare-candy/switch/recover) + archetype selector `decks_build.trainer_package`; and **12 Standard-legal Special Energy** (`sim/special_energy.py`). Energy on a Pokémon is a `Counter` with two pseudo-types — `Colorless` (pays {C} only) and `Wild` (rainbow, pays anything) — so `cost_met` handles special energy; riders modeled: Spiky counter, Growing Grass +20 HP, Magnetic Metal no-retreat, Ignition one-turn {C}{C}{C} burst, Team-Rocket's-only constraint, Prism rainbow-on-Basic, Mist/Rocky/Bubbly effect-shields, Telepathic bench-search.

**Optimizer (`optimize.py`).** Materializes each archetype into an explicit legal 60-card list (card refs: `('P','set:id')` | `('E','Type')` | `('T','Name')` | `('S','Special Energy')`), then coevolutionary hill-climbs. Each round every deck evaluates ~40 small legal on-theme swaps (energy↔Pokémon↔Trainer↔special-energy, quantity shifts) **plus every past version of itself** (**archive-and-revert** — a stale move that the shifting field turned into a regression gets undone) against the current field with common random numbers, and keeps the best above a +1% threshold. **Guards** hold the ace's evolution line, free engines (Eelektrik &c.), and named-family signatures unremovable, with an energy floor. Parallel gauntlet eval (multiprocess). `is_legal` enforces 60 / ≤4-by-name / the money-slot rule (special energy counted by cat). Persists `decklists.json` (population), `history.jsonl` + `archive.json`, `leaderboard.json`, `stats.json` (per-deck ace telemetry: play-rate, online-turn, damage dealt/taken). Long runs use the **`run_optimizer.sh`** daemon (launch detached via Python `start_new_session`; it relaunches the optimizer through any harness reap until an `OPT_DONE` sentinel — resume skips already-done deck-rounds). `--games` sets games/pairing (10 gives ~1,640 games/eval); `--stats` writes telemetry; `--fresh` re-materializes.

**Results.** Field median ~53%, balanced; Special Energy adopted by 51/165 decks (Prism/Spiky/Team-Rocket's — the niche free ones); archive-revert stayed dormant (0 reverts → stable convergence). Phase artifacts kept: `decklists_initial.json` (auto-built baseline), `decklists_phase1.json` + `history_phase1.jsonl`, plus the phase-2 files. A browsable HTML change-log report is published as a claude.ai artifact.

**Remaining (open).** Re-concept ~2 structurally-dead decks — **Energy Gift Express** (Whimsicott's win-condition attack does 0 damage) and **Mega Skarmory Snipe** (Sonic Ripper shuffles all its energy every turn); **no spare ex exist** (all 145 legal budget ex are used as premiums), so rebuild around the existing ace, not a swap. Review the sub-30% cluster (some are genuinely-weak archetypes or dead-ability cards like Munkidori). Optional: Stadiums/Tools, deeper AI sequencing / gust-target choice.
