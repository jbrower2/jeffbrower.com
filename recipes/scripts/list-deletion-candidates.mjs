// Lists external HTML files from /Volumes/nasty/docs/recipes/web that the
// reconcile script considers "matched" to a current markdown file
// (fuzzy: word-set ingredient match + step count within 1). Those are
// deletion candidates from the external archive.
//
// Prints two groups to stdout:
//   MATCHED   — safe-to-delete per fuzzy criteria
//   DIFFERS   — current markdown diverges from external; keep external for now

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const EXTERNAL_DIR = "/Volumes/nasty/docs/recipes/web";
const CURRENT_DIR = path.resolve(__dirname, "..", "src", "data");

const SKIP_EXTERNAL = new Set(["_recipe.htm", "index.htm"]);
const FLAVORS_FILE = "Dessert.IceCream.Flavors.htm";

const EXTERNAL_TO_CURRENT = {
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
  "Dessert.Pie.ApplePie.htm": "apple-pear-pie",
  "Dessert.Pie.PearPie.htm": "apple-pear-pie",
  "Dessert.Candy.ChocolateCoveredPretzelBraids.htm":
    "chocolate-covered-pretzels",
  "Dessert.Candy.ChocolateCoveredPretzelSnaps.htm":
    "chocolate-covered-pretzels",
  "Dessert.Pie.PieCrusts.GrahamCrackerPieCrust.htm":
    "oreo-graham-cracker-pie-crust",
  "Dessert.Pie.PieCrusts.OreoPieCrust.htm": "oreo-graham-cracker-pie-crust",
  "Dessert.Cannolis.Shells.ChocolateCannoliShells.htm":
    "chocolate-cannoli-shells",
  "Dessert.Cannolis.Filling.ChocolateCannoliFilling.htm": "chocolate-cannolis",
  "Dessert.Cannolis.Filling.PeppermintCannoliFilling.htm":
    "peppermint-cannolis",
  "Dessert.Cannolis.Filling.PumpkinCannoliFilling.htm": "pumpkin-cannolis",
  "Dessert.Cookies.BlackandWhiteCookies.htm": "black-and-white-cookies",
  "Dessert.Fudge.CookiesandCreamFudge.htm": "cookies-and-cream-fudge",
  "Dessert.Cake.Cheesecake.Shells.CannoliShellCheesecakeShell.htm":
    "cheesecake-shell",
  "Dessert.Cake.Cheesecake.Shells.GrahamCrackerCheesecakeShell.htm":
    "cheesecake-shell",
  "Dessert.Cake.Cheesecake.Shells.OreoCheesecakeShell.htm": "cheesecake-shell",
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
  return path.basename(filename, ".htm").split(".").slice(0, -1).join("/");
}

function parseExternal(filePath) {
  const html = fs.readFileSync(filePath, "utf8");
  const ingredientRegex =
    /<span class="variableIngredient"\s+data-amount="([^"]*)"\s+data-unit="([^"]*)"\s+data-name="([^"]*)"><\/span>/g;
  const ingredients = [...html.matchAll(ingredientRegex)].map(
    ([, amount, unit, name]) => ({ amount, unit, name }),
  );
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
  return { ingredients, directions };
}

function parseMarkdown(md) {
  const ingredients = [];
  const instructions = [];
  let section = null;
  for (const raw of md.split("\n")) {
    const line = raw.replace(/\r$/, "");
    if (/^##\s+Ingredients\b/i.test(line)) { section = "ing"; continue; }
    if (/^##\s+Instructions\b/i.test(line)) { section = "ins"; continue; }
    if (/^##\s+/.test(line)) { section = null; continue; }
    if (/^###\s+/.test(line)) continue;
    if (section === "ing" && /^-\s+/.test(line)) ingredients.push(line.replace(/^-\s+/, "").trim());
    if (section === "ins" && /^\d+\.\s+/.test(line)) instructions.push(line.replace(/^\d+\.\s+/, "").trim());
  }
  return { ingredients, instructions };
}

function stripTokens(s) { return s.replace(/\{[^}]*\}/g, "").replace(/\s+/g, " ").trim(); }

const NOISE_TOKENS = new Set([
  "a","an","and","of","or","the","to","for","in","on","with","fine","finely","large","small","medium","whole","plus","more","as","needed","taste","optional","topping","garnish","softened","room","temperature","divided","packed","melted","chopped","minced","crushed","grated","shredded","sifted","firmly","freshly","ground","pure","toasted","unsalted","salted","sweetened","unsweetened","cup","cups","tbsp","tsp","teaspoon","teaspoons","tablespoon","tablespoons","oz","ounce","ounces","lb","lbs","pound","pounds","g","gram","grams","ml","pinch","dash","can","cans","box","package",
]);
const SYNONYMS = new Map([
  ["confectioner","powdered"],["powdered","powdered"],["icing","powdered"],
  ["semisweet","bittersweet"],["bittersweet","bittersweet"],
  ["bicarbonate","baking"],["kosher","salt"],["scallion","green"],["cilantro","coriander"],
]);
function stem(w){ return w.length>3 && w.endsWith("s") ? w.slice(0,-1) : w; }
function wordSet(s) {
  return new Set(
    s.toLowerCase().replace(/[^a-z0-9]+/g," ").trim().split(/\s+/)
     .filter(w => w && !NOISE_TOKENS.has(w) && !/^\d+$/.test(w))
     .map(w => { const st = stem(w); return SYNONYMS.get(st) || st; })
  );
}
function extMatches(extWords, curSets) {
  if (extWords.size === 0) return true;
  for (const cur of curSets) {
    let all = true;
    for (const w of extWords) { if (!cur.has(w)) { all = false; break; } }
    if (all) return true;
  }
  return false;
}

function main() {
  const externalFiles = fs.readdirSync(EXTERNAL_DIR)
    .filter(f => f.endsWith(".htm") && !SKIP_EXTERNAL.has(f)).sort();
  const currentFiles = fs.readdirSync(CURRENT_DIR).filter(f => f.endsWith(".md"));
  const currentSlugs = new Set(currentFiles.map(f => path.basename(f, ".md")));
  const currentBySlug = {};
  for (const f of currentFiles) {
    const slug = path.basename(f, ".md");
    currentBySlug[slug] = parseMarkdown(fs.readFileSync(path.join(CURRENT_DIR, f), "utf8"));
  }

  // slug -> list of external filenames mapped to it (for "merged" detection)
  const bySlug = {};
  for (const f of externalFiles) {
    if (f === FLAVORS_FILE) continue;
    const slug = slugFor(f);
    if (!currentSlugs.has(slug)) continue;
    (bySlug[slug] ||= []).push(f);
  }

  const matched = []; // { file, slug, category }
  const differs = []; // same shape, plus reason
  const special = [{ file: FLAVORS_FILE, note: "embedded into ice-cream.md" }];

  for (const [slug, files] of Object.entries(bySlug)) {
    const cur = currentBySlug[slug];
    const curSets = cur.ingredients.map(l => wordSet(stripTokens(l)));
    const merged = files.length > 1;
    for (const f of files) {
      const ext = parseExternal(path.join(EXTERNAL_DIR, f));
      const missing = ext.ingredients
        .map(i => ({ name: i.name, words: wordSet(i.name) }))
        .filter(({ words }) => !extMatches(words, curSets))
        .map(({ name }) => name);
      const stepDrift = !merged && Math.abs(cur.instructions.length - ext.directions.length) > 1;
      const bad = missing.length > 0 || stepDrift;
      const entry = { file: f, slug, category: categoryPathFor(f) };
      if (bad) {
        const reasons = [];
        if (missing.length) reasons.push(`missing: ${missing.join(", ")}`);
        if (stepDrift) reasons.push(`step drift ${ext.directions.length}→${cur.instructions.length}`);
        differs.push({ ...entry, reason: reasons.join("; ") });
      } else {
        matched.push(entry);
      }
    }
  }

  // Print report.
  const byCat = (items) => {
    const g = {};
    for (const e of items) (g[e.category] ||= []).push(e);
    return Object.keys(g).sort().map(c => [c, g[c].sort((a,b) => a.file.localeCompare(b.file))]);
  };

  console.log(`=== MATCHED (${matched.length}) — safe to delete from ${EXTERNAL_DIR} ===\n`);
  for (const [cat, items] of byCat(matched)) {
    console.log(`## ${cat}`);
    for (const { file, slug } of items) console.log(`  ${file}  →  ${slug}.md`);
    console.log("");
  }

  console.log(`=== DIFFERS (${differs.length}) — keep external, current diverges ===\n`);
  for (const [cat, items] of byCat(differs)) {
    console.log(`## ${cat}`);
    for (const { file, slug, reason } of items) console.log(`  ${file}  →  ${slug}.md  [${reason}]`);
    console.log("");
  }

  console.log(`=== SPECIAL ===`);
  for (const { file, note } of special) console.log(`  ${file}  —  ${note}`);
  console.log("");
  console.log(`TOTAL external: ${externalFiles.length}  |  MATCHED: ${matched.length}  |  DIFFERS: ${differs.length}  |  SPECIAL: ${special.length}`);
}

main();
