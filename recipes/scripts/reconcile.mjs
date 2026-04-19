// One-shot reconciliation between the archive at
// /Volumes/nasty/docs/recipes/web/*.htm and recipes/src/data/*.md.
// Emits recipes/scripts/reconcile-report.md.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const EXTERNAL_DIR = "/Volumes/nasty/docs/recipes/web";
const CURRENT_DIR = path.resolve(__dirname, "..", "src", "data");
const REPORT_PATH = path.resolve(__dirname, "reconcile-report.md");

const SKIP_EXTERNAL = new Set(["_recipe.htm", "index.htm"]);
// Handled specially (embedded into ice-cream.md).
const FLAVORS_FILE = "Dessert.IceCream.Flavors.htm";

// External filename → current slug. null means "intentionally absent"
// (to be ported or handled specially). Anything not in this map uses
// defaultSlug() on the last segment of the filename.
const EXTERNAL_TO_CURRENT = {
  // Bread + matching Muffins merged in current.
  "Dessert.Bread.BananaBread.htm": "banana-bread-muffins",
  "Dessert.Muffins.BananaMuffins.htm": "banana-bread-muffins",
  "Dessert.Bread.BananaOrangeBread.htm": "banana-orange-bread-muffins",
  "Dessert.Muffins.BananaOrangeMuffins.htm": "banana-orange-bread-muffins",
  "Dessert.Bread.BlueberryBread.htm": "blueberry-bread-muffins",
  "Dessert.Muffins.BlueberryMuffins.htm": "blueberry-bread-muffins",
  "Dessert.Bread.CherryBananaBread.htm": "cherry-banana-bread-muffins",
  "Dessert.Muffins.CherryBananaMuffins.htm": "cherry-banana-bread-muffins",
  "Dessert.Bread.CinnamonBread.htm": "cinnamon-bread-muffins",
  "Dessert.Bread.Cornbread.htm": "cornbread-muffins",
  "Dessert.Muffins.CornbreadMuffins.htm": "cornbread-muffins",
  "Dessert.Bread.MapleSyrupBread.htm": "maple-syrup-bread-muffins",
  "Dessert.Bread.OrangeCinnamonSwirlBread.htm":
    "orange-cinnamon-swirl-bread-muffins",
  "Dessert.Bread.PineapplePumpkinBread.htm": "pineapple-pumpkin-bread-muffins",
  "Dessert.Muffins.PineapplePumpkinMuffins.htm":
    "pineapple-pumpkin-bread-muffins",
  "Dessert.Bread.PumpkinBread.htm": "pumpkin-bread-muffins",
  "Dessert.Muffins.PumpkinMuffins.htm": "pumpkin-bread-muffins",

  // Pies merged.
  "Dessert.Pie.ApplePie.htm": "apple-pear-pie",
  "Dessert.Pie.PearPie.htm": "apple-pear-pie",

  // Pretzels merged.
  "Dessert.Candy.ChocolateCoveredPretzelBraids.htm":
    "chocolate-covered-pretzels",
  "Dessert.Candy.ChocolateCoveredPretzelSnaps.htm":
    "chocolate-covered-pretzels",

  // Pie crusts merged (graham cracker + oreo → one combined).
  "Dessert.Pie.PieCrusts.GrahamCrackerPieCrust.htm":
    "oreo-graham-cracker-pie-crust",
  "Dessert.Pie.PieCrusts.OreoPieCrust.htm": "oreo-graham-cracker-pie-crust",

  // Cannolis: peppermint/pumpkin collapse filling-only (no shell variants exist);
  // chocolate keeps separate shell + filling-variant files.
  "Dessert.Cannolis.Shells.ChocolateCannoliShells.htm":
    "chocolate-cannoli-shells",
  "Dessert.Cannolis.Filling.ChocolateCannoliFilling.htm": "chocolate-cannolis",
  "Dessert.Cannolis.Filling.PeppermintCannoliFilling.htm":
    "peppermint-cannolis",
  "Dessert.Cannolis.Filling.PumpkinCannoliFilling.htm": "pumpkin-cannolis",

  // "and" embedded in CamelCase without word boundaries — explicit map
  // since defaultSlug can't tell "Blackand" from a real word.
  "Dessert.Cookies.BlackandWhiteCookies.htm": "black-and-white-cookies",
  "Dessert.Fudge.CookiesandCreamFudge.htm": "cookies-and-cream-fudge",

  // Cheesecake shells all collapse to one.
  "Dessert.Cake.Cheesecake.Shells.CannoliShellCheesecakeShell.htm":
    "cheesecake-shell",
  "Dessert.Cake.Cheesecake.Shells.GrahamCrackerCheesecakeShell.htm":
    "cheesecake-shell",
  "Dessert.Cake.Cheesecake.Shells.OreoCheesecakeShell.htm": "cheesecake-shell",

  // Renames.
  "Dessert.Brownies.PeanutButterSwirlBrownies.htm": "peanut-swirl-brownies",
  "Dessert.Cookies.DoubleChocolateCookies.htm":
    "chocolate-chocolate-chip-cookies",
  "Dessert.Cookies.PumpkinCookies.htm": "pumpkin-drop-cookies",
  "Dessert.Frosting.Frosting.ChocolateChipCookieDoughFrosting.htm":
    "cookie-dough-frosting",
  "Dessert.Cookies.SpritzgebackCookies.htm": "spritzgeback-cookies",
  "Dessert.Cake.Cheesecake.PumpkinCheesecake.htm":
    "pumpkin-cheesecake-flavoring",
  "Dessert.Cake.Cheesecake.RaspberryCheesecake.htm":
    "raspberry-cheesecake-flavoring",
  "Dessert.Frosting.Frosting.VanillaFrosting.htm":
    "vanilla-frosting-whoopie-pie-filling",
};

function defaultSlug(filename) {
  const name = path.basename(filename, ".htm").split(".").pop();
  return name
    .replace(/'/g, "")
    .replace(/([a-z])([A-Z])/g, "$1-$2")
    .replace(/([A-Z])([A-Z][a-z])/g, "$1-$2")
    .replace(/\band\b/gi, "-and-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .toLowerCase();
}

function slugFor(filename) {
  if (filename in EXTERNAL_TO_CURRENT) return EXTERNAL_TO_CURRENT[filename];
  return defaultSlug(filename);
}

function categoryPathFor(filename) {
  const parts = path.basename(filename, ".htm").split(".");
  return parts.slice(0, -1).join("/");
}

function externalTitle(filename) {
  const last = path.basename(filename, ".htm").split(".").pop();
  return last
    .replace(/'/g, "")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/([A-Z])([A-Z][a-z])/g, "$1 $2")
    .replace(/\band\b/gi, "and");
}

// -------- External HTML parsing --------

function parseExternal(filePath) {
  const html = fs.readFileSync(filePath, "utf8");
  const filename = path.basename(filePath);

  const h1 = html.match(/<h1>([^<]+)<\/h1>/);
  const servings = html.match(/data-default="([^"]+)"\s+id="Servings"/);
  const yieldDefault = html.match(/data-default="([^"]+)"\s+id="Yield"/);
  // Unit text appears between `/>` and `<br` after the Yield input.
  const yieldUnitMatch = html.match(/id="Yield"[^>]*\/>\s*([^<]*?)\s*<br/);

  const ingredientRegex =
    /<span class="variableIngredient"\s+data-amount="([^"]*)"\s+data-unit="([^"]*)"\s+data-name="([^"]*)"><\/span>/g;
  const ingredients = [...html.matchAll(ingredientRegex)].map(
    ([, amount, unit, name]) => ({ amount, unit, name }),
  );

  // Grab the <ol>...</ol> that contains the Directions.
  const olMatch = html.match(/<ol>([\s\S]+?)<\/ol>/);
  const directions = [];
  if (olMatch) {
    const liRegex = /<li>([\s\S]+?)<\/li>/g;
    for (const m of olMatch[1].matchAll(liRegex)) {
      const text = m[1]
        .replace(/<[^>]+>/g, "")
        .replace(/\s+/g, " ")
        .trim();
      if (text) directions.push(text);
    }
  }

  return {
    filename,
    title: h1 ? h1[1].trim() : externalTitle(filename),
    categoryPath: categoryPathFor(filename),
    servings: servings ? servings[1] : null,
    yieldDefault: yieldDefault ? yieldDefault[1] : null,
    yieldUnit: yieldUnitMatch ? yieldUnitMatch[1].trim() : "",
    ingredients,
    directions,
  };
}

// -------- Current markdown parsing --------

function parseMarkdown(slug, md) {
  const lines = md.split("\n");
  const name = (lines[0] || "").replace(/^#\s*/, "").trim();

  const ingredients = [];
  const instructions = [];
  let section = null;
  for (const raw of lines) {
    const line = raw.replace(/\r$/, "");
    if (/^##\s+Ingredients\b/i.test(line)) {
      section = "ing";
      continue;
    }
    if (/^##\s+Instructions\b/i.test(line)) {
      section = "ins";
      continue;
    }
    if (/^##\s+/.test(line)) {
      section = null;
      continue;
    }
    if (/^###\s+/.test(line)) continue; // subsection headers inside a section
    if (section === "ing" && /^-\s+/.test(line)) {
      ingredients.push(line.replace(/^-\s+/, "").trim());
    }
    if (section === "ins" && /^\d+\.\s+/.test(line)) {
      instructions.push(line.replace(/^\d+\.\s+/, "").trim());
    }
  }
  return { slug, name, ingredients, instructions };
}

function stripTokens(s) {
  return s
    .replace(/\{[^}]*\}/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

// Word-set ingredient matching. Lowercase + strip non-alphanumerics, drop
// noise tokens, depluralize, then compare as sets so word order and small
// descriptor differences don't trigger false positives.
const NOISE_TOKENS = new Set([
  "a",
  "an",
  "and",
  "of",
  "or",
  "the",
  "to",
  "for",
  "in",
  "on",
  "with",
  "fine",
  "finely",
  "large",
  "small",
  "medium",
  "whole",
  "plus",
  "more",
  "as",
  "needed",
  "taste",
  "optional",
  "topping",
  "garnish",
  "softened",
  "room",
  "temperature",
  "divided",
  "packed",
  "melted",
  "chopped",
  "minced",
  "crushed",
  "grated",
  "shredded",
  "sifted",
  "firmly",
  "freshly",
  "ground",
  "pure",
  "toasted",
  "unsalted",
  "salted",
  "sweetened",
  "unsweetened",
  "cup",
  "cups",
  "tbsp",
  "tsp",
  "teaspoon",
  "teaspoons",
  "tablespoon",
  "tablespoons",
  "oz",
  "ounce",
  "ounces",
  "lb",
  "lbs",
  "pound",
  "pounds",
  "g",
  "gram",
  "grams",
  "ml",
  "pinch",
  "dash",
  "can",
  "cans",
  "box",
  "package",
]);
// Synonyms: each key maps to its canonical form. Applied post-stem.
const SYNONYMS = new Map([
  ["confectioner", "powdered"],
  ["powdered", "powdered"],
  ["icing", "powdered"], // "icing sugar" == "powdered sugar"
  ["semisweet", "bittersweet"], // often interchangeable in ingredients
  ["bittersweet", "bittersweet"],
  ["bicarbonate", "baking"], // "bicarbonate of soda" == "baking soda"
  ["kosher", "salt"],
  ["scallion", "green"], // "scallion" ~ "green onion"
  ["cilantro", "coriander"],
]);
// Light stemming: drop trailing 's' on words >3 chars so eggs==egg.
function stem(w) {
  if (w.length > 3 && w.endsWith("s")) return w.slice(0, -1);
  return w;
}
function wordSet(s) {
  return new Set(
    s
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, " ")
      .trim()
      .split(/\s+/)
      .filter((w) => w && !NOISE_TOKENS.has(w) && !/^\d+$/.test(w))
      .map((w) => {
        const stemmed = stem(w);
        return SYNONYMS.get(stemmed) || stemmed;
      }),
  );
}

function ingredientWordSets(current) {
  return current.ingredients.map((line) => wordSet(stripTokens(line)));
}

function externalWordSets(ext) {
  return ext.ingredients.map((i) => ({
    name: i.name,
    words: wordSet(i.name),
  }));
}

// ext ingredient matches if all its words appear in some current ingredient's set.
// If ext has no words (rare: blank name), skip.
function extMatches(extWords, curSets) {
  if (extWords.size === 0) return true;
  for (const cur of curSets) {
    let all = true;
    for (const w of extWords) {
      if (!cur.has(w)) {
        all = false;
        break;
      }
    }
    if (all) return true;
  }
  return false;
}

// -------- Main --------

function main() {
  const externalFiles = fs
    .readdirSync(EXTERNAL_DIR)
    .filter((f) => f.endsWith(".htm") && !SKIP_EXTERNAL.has(f))
    .sort();

  const currentFiles = fs
    .readdirSync(CURRENT_DIR)
    .filter((f) => f.endsWith(".md"))
    .sort();
  const currentSlugs = new Set(
    currentFiles.map((f) => path.basename(f, ".md")),
  );

  // Parse current markdown.
  const currentBySlug = {};
  for (const f of currentFiles) {
    const slug = path.basename(f, ".md");
    const md = fs.readFileSync(path.join(CURRENT_DIR, f), "utf8");
    currentBySlug[slug] = parseMarkdown(slug, md);
  }

  // Which slugs were mapped from external.
  const externalBySlug = {}; // slug → array of external recipes
  const externalByFilename = {}; // filename → parsed external
  const missingInCurrent = []; // external for which slug doesn't exist
  const specialCases = []; // filename explicitly mapped to null

  for (const f of externalFiles) {
    if (f === FLAVORS_FILE) {
      specialCases.push({ file: f, reason: "embedded into ice-cream.md" });
      continue;
    }
    const ext = parseExternal(path.join(EXTERNAL_DIR, f));
    externalByFilename[f] = ext;
    const slug = slugFor(f);
    if (slug === null) {
      missingInCurrent.push({ file: f, ext });
      continue;
    }
    if (!currentSlugs.has(slug)) {
      missingInCurrent.push({ file: f, ext, expectedSlug: slug });
      continue;
    }
    (externalBySlug[slug] ||= []).push({ file: f, ext });
  }

  // Current-only: slugs in current that aren't covered by any external mapping.
  const coveredSlugs = new Set(Object.keys(externalBySlug));
  const currentOnly = [...currentSlugs].filter((s) => !coveredSlugs.has(s));

  // Content compare: for each mapped pair, compare ingredient counts and
  // step counts.
  const contentDiffs = [];
  for (const slug of Object.keys(externalBySlug)) {
    const cur = currentBySlug[slug];
    for (const { file, ext } of externalBySlug[slug]) {
      const curIngCount = cur.ingredients.length;
      const curInsCount = cur.instructions.length;
      const extIngCount = ext.ingredients.length;
      const extInsCount = ext.directions.length;

      // If two externals merge into one current, current may have MORE
      // ingredients (combined) or instructions — only flag shortfalls per-file
      // when the count is fewer than a single external's (suggests drift).
      const missingIngredients = [];
      const curSets = ingredientWordSets(cur);
      for (const { name, words } of externalWordSets(ext)) {
        if (!extMatches(words, curSets)) {
          missingIngredients.push(name);
        }
      }

      const merged = externalBySlug[slug].length > 1;
      const significantDiff =
        missingIngredients.length > 0 ||
        (!merged && Math.abs(curInsCount - extInsCount) > 1);

      if (significantDiff) {
        contentDiffs.push({
          slug,
          file,
          ext,
          cur,
          curIngCount,
          curInsCount,
          extIngCount,
          extInsCount,
          missingIngredients,
          merged,
        });
      }
    }
  }

  // Encoding fixes detection: any current slug containing "-ck-" or similar
  // (simple heuristic; just flag spritzgeb-ck-cookies explicitly).
  const encodingFixes = [];
  if (currentSlugs.has("spritzgeb-ck-cookies")) {
    encodingFixes.push({
      slug: "spritzgeb-ck-cookies",
      suggested: "spritzgeback-cookies",
      reason: "'ä' lost in original slug generation",
    });
  }

  // --- Build suggested addRecipe(...) calls for the new index.js.
  // Group by category path (from external); within category, sort by display
  // name. Recipes with multiple category paths get all paths listed.
  const categorySet = new Set();
  const slugToCategoryPaths = {};
  for (const slug of Object.keys(externalBySlug)) {
    const paths = new Set();
    for (const { ext } of externalBySlug[slug]) {
      paths.add(ext.categoryPath);
      categorySet.add(ext.categoryPath);
    }
    slugToCategoryPaths[slug] = [...paths];
  }

  // For current-only slugs, don't guess a category — mark as "???".
  for (const slug of currentOnly) {
    slugToCategoryPaths[slug] = ["???"];
  }

  // Ordering for the addRecipe suggestions:
  // 1. Sort external categories alphabetically.
  // 2. Each category's recipes: alphabetical by current recipe name.
  const categoryOrder = [...categorySet].sort();
  const addRecipeLines = [];
  const emitted = new Set();
  for (const cat of categoryOrder) {
    const slugsInCat = Object.entries(slugToCategoryPaths)
      .filter(([slug, paths]) => paths.includes(cat) && !emitted.has(slug))
      .map(([slug]) => slug);
    if (slugsInCat.length === 0) continue;
    const sorted = slugsInCat.sort((a, b) => {
      const na = currentBySlug[a]?.name || a;
      const nb = currentBySlug[b]?.name || b;
      return na.localeCompare(nb);
    });
    addRecipeLines.push(`  // ${cat}`);
    for (const slug of sorted) {
      const paths = slugToCategoryPaths[slug];
      const catsArg = JSON.stringify(paths);
      addRecipeLines.push(`  addRecipe(${JSON.stringify(slug)}, ${catsArg});`);
      emitted.add(slug);
    }
    addRecipeLines.push("");
  }

  // Current-only goes last with ??? placeholder.
  if (currentOnly.length) {
    addRecipeLines.push(
      "  // --- current-only (post-archive additions; assign a category) ---",
    );
    for (const slug of currentOnly.sort()) {
      addRecipeLines.push(`  addRecipe(${JSON.stringify(slug)}, ["???"]);`);
    }
  }

  // --- Emit report.
  const lines = [];
  lines.push("# Recipe archive reconciliation");
  lines.push("");
  lines.push(
    `- External: ${externalFiles.length} HTML files scanned (from ${EXTERNAL_DIR})`,
  );
  lines.push(
    `- Current: ${currentFiles.length} markdown files scanned (from ${CURRENT_DIR})`,
  );
  lines.push(`- Special: ${FLAVORS_FILE} → embed into ice-cream.md`);
  lines.push("");

  lines.push("## Missing in current");
  lines.push("");
  if (missingInCurrent.length === 0) {
    lines.push("_None._");
  } else {
    for (const { file, ext, expectedSlug } of missingInCurrent) {
      const slugNote = expectedSlug
        ? `(expected slug: \`${expectedSlug}\`)`
        : "(intentionally absent per EXTERNAL_TO_CURRENT)";
      lines.push(`- \`${file}\` ${slugNote}`);
      if (ext) {
        lines.push(`  - Title: ${ext.title}`);
        lines.push(`  - Category: \`${ext.categoryPath}\``);
        lines.push(
          `  - Ingredients: ${ext.ingredients.length}, Directions: ${ext.directions.length}`,
        );
      }
    }
  }
  lines.push("");

  lines.push("## Mismatched content");
  lines.push("");
  if (contentDiffs.length === 0) {
    lines.push("_No significant drift detected._");
  } else {
    for (const d of contentDiffs) {
      lines.push(`### ${d.cur.name} (\`${d.slug}\`)`);
      lines.push(
        `- External: \`${d.file}\` (${d.extIngCount} ingredients, ${d.extInsCount} directions)`,
      );
      lines.push(
        `- Current: \`${d.slug}.md\` (${d.curIngCount} ingredients, ${d.curInsCount} instructions)${d.merged ? " [merged recipe]" : ""}`,
      );
      if (d.missingIngredients.length) {
        lines.push("- **External ingredients not found in current:**");
        for (const m of d.missingIngredients) {
          lines.push(`  - ${m}`);
        }
      }
      lines.push("");
    }
  }

  lines.push("## Current-only (no archive source)");
  lines.push("");
  if (currentOnly.length === 0) {
    lines.push("_None._");
  } else {
    lines.push("These post-archive additions need manual category assignment:");
    lines.push("");
    for (const slug of currentOnly.sort()) {
      const cur = currentBySlug[slug];
      lines.push(`- \`${slug}\` — ${cur.name}`);
    }
  }
  lines.push("");

  lines.push("## Encoding fixes");
  lines.push("");
  if (encodingFixes.length === 0) {
    lines.push("_None._");
  } else {
    for (const { slug, suggested, reason } of encodingFixes) {
      lines.push(`- \`${slug}\` → \`${suggested}\` (${reason})`);
    }
  }
  lines.push("");

  lines.push("## Merge/rename audit");
  lines.push("");
  lines.push(
    "External files mapped to a non-default slug (merged or renamed):",
  );
  lines.push("");
  for (const [file, target] of Object.entries(EXTERNAL_TO_CURRENT)) {
    if (target === null) continue;
    const dflt = defaultSlug(file);
    if (dflt === target) continue; // trivial mapping, not interesting
    lines.push(
      `- \`${file}\` → \`${target}\` (default would have been \`${dflt}\`)`,
    );
  }
  lines.push("");

  lines.push("## Suggested `addRecipe` calls for new `index.js`");
  lines.push("");
  lines.push(
    "Copy the block below into `recipes/src/data/index.js` between the",
  );
  lines.push("`const recipes = [];` and `export default recipes;` lines.");
  lines.push("Reorder within a category by hand as desired.");
  lines.push(
    'Recipes listed with `["???"]` are post-archive additions — assign real categories.',
  );
  lines.push("");
  lines.push("```js");
  for (const line of addRecipeLines) lines.push(line);
  lines.push("```");
  lines.push("");

  lines.push("## Discovered category taxonomy");
  lines.push("");
  lines.push("```js");
  lines.push("const CATEGORIES = new Set([");
  for (const c of categoryOrder) {
    lines.push(`  ${JSON.stringify(c)},`);
  }
  lines.push("]);");
  lines.push("```");
  lines.push("");

  fs.writeFileSync(REPORT_PATH, lines.join("\n"));
  console.log(`Wrote ${REPORT_PATH}`);
  console.log(
    `External: ${externalFiles.length}, Current: ${currentFiles.length}`,
  );
  console.log(`Missing in current: ${missingInCurrent.length}`);
  console.log(`Content diffs: ${contentDiffs.length}`);
  console.log(`Current-only: ${currentOnly.length}`);
  console.log(`Encoding fixes: ${encodingFixes.length}`);
}

main();
