# jeffbrower.com

Personal site deployed via GitHub Pages + Jekyll. Each app under `docs/<app>/` is a separately-built SPA mounted into a Jekyll page.

## Recipes (`recipes/` → `docs/recipes/`)

Read-only recipe browser. React + esbuild SPA. Sources are markdown files in `recipes/src/data/`, bundled into the JS via esbuild's `--loader:.md=text`.

### Build

```
cd recipes && npm run build
```

Outputs to `../docs/recipes/index.js`. Always rebuild after editing markdown or `src/data/index.js`.

### Adding a recipe

1. Write the markdown file at `recipes/src/data/<slug>.md`.
2. Add an `addRecipe(slug, categories, shown?)` call to `recipes/src/data/index.js`, placed alongside related recipes. File order IS display order.
3. `npm run build`.

### Categories

`recipes/src/data/index.js` is an imperative builder:

- A top-of-file `CATEGORIES` Set lists every valid category path. `addRecipe` validates inputs at module-load time — unknown categories throw.
- Categories are slash-separated strings like `"Dessert/Cookies/Pizzelles"`. A recipe can belong to multiple — pass an array like `["Dessert/Bread", "Dessert/Muffins"]` for a bread-or-muffin variant; it'll render under both nodes.
- `shown` is an optional third parameter. Pass `true` only for curated recipes that appear by default; omit it for legacy archive recipes only visible behind the "Show All" toggle. Don't flip an existing recipe's `shown` status without being asked.

To introduce a new category, add the string to `CATEGORIES` first, then use it.

The `RecipeList` page renders these as a collapsible tree. Filter/expanded state lives in a module-level variable so navigating to a recipe and back (via the "All recipes" link) restores the view, but a full page refresh resets it.

### Markdown structure

```md
# Recipe Name

Optional intro blurb paragraph(s) — placed ABOVE the metadata, not below.

- **Servings:** {N}
- **Yield:** {N} units, optional descriptive text
- [Source](https://...)        ← only if a source URL exists
- **Prep Time:** N minutes
- **Cook Time:** N minutes
- **Chill Time:** N minutes     ← include any timing labels the source uses (Active Time, Rest Time, etc.)
- **Total Time:** N minutes

## Ingredients

### Optional Subsection            ← e.g. Dough, Filling, Frosting

- {qty} unit ({grams} g) ingredient name, optional notes

## Instructions

1. Step text.
1. Use `1.` for every line — markdown auto-numbers.

## Notes

- **Storage:** ...
- **\*Label:** notes keyed to an asterisk footnote in ingredients
```

### `{...}` token-wrapping rules

The first `{...}` in the file becomes the editable servings input. Every other `{...}` scales by `current / original`.

**Wrap** (scales with servings):
- Ingredient quantities.
- Equivalent measures together: `{1} cup ({16} Tbsp; {226} g) butter`.
- Servings + matching count in yield: `**Servings:** {16}` / `**Yield:** {16} cookies`.
- Divided portions in instructions when needed to specify which portion (e.g., `Add {6} cups marshmallows ... fold in the remaining {2} cups`).
- Proportional alternatives in notes (e.g., "use {3} cups flour for flatter cookies").

**Don't wrap** (stays static):
- Physical attributes: pan sizes (`9x13`), can sizes (`(10-oz.)`), tortilla diameters (`(10")`), box sizes (`(15 ounce) box`).
- Oven temperatures.
- Times anywhere (cook times, chill times, storage durations, "about 1 hour").
- Per-unit portioning ("1/3 cup of mixture per tortilla", "2 tablespoons dough per cookie").
- Adjustment amounts ("add 1/4 cup more if too thin").

For canned/boxed items, wrap the **count**, not the package size: `{2} (10-oz.) cans` or `{1} (15 ounce) box`.

### Source-recipe normalization

When importing a recipe from a URL or image:

**Drop:**
- Author / "Recipe by" line.
- Course, Cuisine, Categories.
- Calories / nutrition disclaimers.
- Equipment lists.
- Ratings / review counts.
- Affiliate-link "Special Tools" sections.
- Dead cross-recipe links from notes (when they point to recipes we don't have).

**Preserve:**
- Intro blurb (above metadata).
- All timing labels the source uses.
- Yield text.
- Ingredient text as-is, including "optional", "softened", "packed", "divided", brand suggestions.
- Asterisk footnotes (escape as `\*` in markdown).

**In instructions:** drop quantities that *redundantly* restate the ingredient line. Keep quantities that specify which portion of a divided ingredient (and wrap those so they scale).

**Notes section:** convert prose tips to a bullet list with `**Label:**` prefixes (`**Storage:**`, `**Make ahead:**`, `**\*Flour:**`). Consolidate multiple footnotes that share an asterisk count into one bullet.

### Cross-recipe links

Use HashRouter URLs: `[recipe name](#/slug)`.

## Other apps

(Add per-app sections here as conventions emerge — `mft-gift-cards/`, etc.)
