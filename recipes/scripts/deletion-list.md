# External archive — deletion verdict

From 156 converted comparisons (STRICT 83, SUBSET 17, DIVERGENT 56) plus 3 non-recipe skips:

- **Safe to delete: 149** (STRICT 83 + SUBSET 17 + DIVERGENT 47 classified as cosmetic/merged/expanded + 2 UI shells)
- **Keep: 10** (9 real divergences + 1 not-yet-ported)

## KEEP (10)

Content not preserved in current — would lose information if deleted.

### Bread variant instructions lost to muffin-only

These externals have bread-specific temp/pan/time that the merged `*-bread-muffins` current file replaced with muffin-only steps.

- `Dessert.Bread.BlueberryBread.htm` — 325°F / loaf pan / 1 hr (current is 380→400°F / muffin tin / 20–25 min)
- `Dessert.Bread.Cornbread.htm` — 325°F / loaf pan / 1 hr (current is 400°F / muffin tin / 15 min)
- `Dessert.Bread.PineapplePumpkinBread.htm` — 325°F / loaf pan / 1 hr (current is 350°F / muffin tin / 20–25 min)

### Muffin variant instructions lost to bread-only

Reverse direction — these externals have muffin-specific steps the merged current file dropped.

- `Dessert.Muffins.BananaMuffins.htm` — 400°F / muffin tin / 15 min (current is 325°F / 9×5×3 loaf / 1 hr 10 min)
- `Dessert.Muffins.BananaOrangeMuffins.htm` — 400°F / muffin tin / 15 min (current is 350°F / loaf / 1 hr)
- `Dessert.Muffins.CherryBananaMuffins.htm` — 400°F / muffin tin / 15 min (current is 325°F / 8.5×4.5×2.5 loaf / 1 hr)

### Replaced with a different recipe

Current uses a different source recipe; external content is not preserved.

- `Dessert.Cookies.DoubleChocolateCookies.htm` — current `chocolate-chocolate-chip-cookies.md` is the allrecipes version (sugar/butter/cocoa method). Note: `double-chocolate-chip-cookies.md` also exists but is yet a _third_ recipe (justsotasty.com).
- `Dessert.Frosting.Frosting.CreamCheeseFrosting.htm` — current is the sugarspunrun version with different ingredient ratios.

### Substantive ingredient change

- `Dessert.Cookies.PumpkinCookies.htm` — external has 1 tsp allspice + 1 tsp nutmeg; current `pumpkin-drop-cookies.md` has 1/4 tsp each (4× less).

### Not yet ported

- `Dessert.IceCream.Flavors.htm` — ~50 flavor insert recipes. Planned for embedding into `ice-cream.md` as a Flavors section but not done yet.

## DELETE — sample verification

Non-obvious picks worth calling out:

- **`Dessert.Donuts.CinnamonRolls.htm`** — mapping in `compare-converted.mjs` pointed to `cinnamon-rolls.md` (the modern replacement, which is a different recipe). The external content is actually preserved verbatim in `cinnamon-rolls-old.md`. Safe to delete.
- **All 3 Cheesecake Shells + both Pretzel variants + Apple/Pear Pie + both pie crusts + 3 cannoli fillings** — merged-recipe false positives. Current file combines the variants with "or" ingredients and notes.
- **Gelato / IceCream / Sherbet / Sorbet** — only diff is "Add flavoring" replaced by more specific variants ("Add fruit ingredients", "Stir in fruit mixture"). IceCream also halved (12→6 yolks); same recipe at half scale.
- **AppleMuffins, CornbreadMuffins** — ingredient amounts scaled 1.5× in external; same recipe in current at smaller batch size.
- **Encoding-only diffs**: EggnogFudge, NutellaFudge, ChocolateChipCupcakes, WatermelonPie — `°F` and `'` characters corrupted in source HTML.
- **Sentence-split diffs**: OrangeCinnamonSwirlBread, MintChocolateFudge, ButterPecanFudge, PeanutButterFudge, AppleFritters, FunnelCake, ShortbreadCookies — external broke sentences on `.` inside dimensions/parentheticals; current merged them.
