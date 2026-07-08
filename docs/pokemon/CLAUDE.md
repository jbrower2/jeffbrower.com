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
- **`decks.md`** — the deck catalog (**164 decks**, ~10–20 per type). Each deck = premium + 2 supports + C/U core + a "why it works" line, ordered strongest → most experimental (weak/experimental ones flagged).
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

`types.html` contains only Pokémon (+ basic energy). Tools, Stadiums, Special Energy, Supporters, and Fossils are **not** in it — assume they're available as standard Trainer cards. Cards whose abilities require out-of-pool pieces are effectively **dead** here and shouldn't anchor a deck: Festival Lead (needs Festival Grounds), Heliolisk (Canari), Lycanroc (Spiky Energy), Genesect's ACE Nullifier (ACE SPEC), Pidove (Unfezant ex), Munkidori ex's protective ability (needs Pecharunt *ex*, which isn't in the pool).

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
- **`deckgen/`**: the persisted pipeline (`printings.json` + scripts + per-section deck source files).

## Next step: the simulator

Encode the 165 decks as full 60-card lists on `deckgen/printings.json`, then build a match engine (turn structure, energy attach, evolution, attacks/abilities, prizes, special conditions) to compute head-to-head win rates and optimize each deck. Deck size is still unconfirmed (assumed 60) — settle that first.
