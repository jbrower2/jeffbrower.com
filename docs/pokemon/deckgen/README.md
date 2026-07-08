# deckgen — Pokémon pauper deck pipeline

Tooling that turns the card database (`../types.html`) into verified deck data.
See `../CLAUDE.md` for the format rules, classification method, and card-data gotchas.

## Run order

```sh
cd docs/pokemon/deckgen
python3 parse_printings.py    # types.html -> printings.json (printing-level card index)
python3 audit_decks.py        # verify every deck's paid slots against printings.json
python3 assemble_decks.py     # section files -> ../decks.md
python3 coverage.py           # (optional) list legal cards not yet used in a deck
```

Requires only Python 3 stdlib. `parse_printings.py` must run first (it produces
`printings.json`, which the others read).

## Files

- **`parse_printings.py`** → **`printings.json`** — every card *printing* kept
  separate (`name -> [ {set, id, cat, price, ex, energy, abils, atks, sig}, ... ]`).
  This is the source of truth; the simulator should consume it. Never dedupe by
  name — 380 names have ≥2 mechanically-distinct printings (see CLAUDE.md).
- **`audit_decks.py`** — checks each deck's Premium (needs an ex printing ≤ $1) and
  each Support (needs a cat-yellow printing ≤ $0.50). Invariant: **0 hard errors**.
- **`assemble_decks.py`** — concatenates the section source files into `../decks.md`.
  **Edit the `decks_*.txt` files here, not `decks.md` directly**, then re-run this.
- **`coverage.py`** — lists legal ex premiums and rare ability-cards not yet used in
  any deck, to find design gaps.
- **`parse_trainers.py`** → **`trainers.json`** — the 197 Common/Uncommon Trainers
  (Supporter/Item/Stadium/Tool + effect text) pulled from `../carddata/*.json`. Legal
  and unlimited under the "rest must be Common/Uncommon" rule; the simulator's decklists
  and Trainer engine consume this.
- **`decks_<TYPE>.txt`** (+ optional `_extra`, `_new`) — the deck source, one file
  per section (G R W L P F D M C MULTI TR). Deck template:

  ```
  **Deck Name** — one-line concept
  - Premium: **Exact Card Name** — what it does.
  - Supports: **Card A** (role) + **Card B** (role).
  - Core: <C/U evolution lines + free engines + which basic Energy>.
  - Why: <the specific synergy>.
  ```

## Regenerating after a data refresh

If `../types.html` is regenerated with new prices/cards, re-run `parse_printings.py`
then `audit_decks.py`; fix any hard errors (a card's cheapest legal printing may have
crossed a price threshold), then `assemble_decks.py`.
