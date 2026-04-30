// Strict pair comparison between scripts/converted/*.md (produced by
// convert-htm-to-md.mjs) and the corresponding src/data/<slug>.md file.
//
// For each converted external file, locates the current slug via the same
// EXTERNAL_TO_CURRENT map used by reconcile.mjs (falling back to defaultSlug),
// then:
//
//   1. Normalizes both sides (unicode punctuation, whitespace, case).
//   2. For each converted ingredient/instruction, checks for an EXACT
//      normalized match in the corresponding current list.
//   3. Classifies the pair:
//        STRICT     — counts equal AND same lines in same order.
//        SUBSET     — every converted line appears in current (possibly with
//                     current adding extras or reordering). Safe to delete if
//                     nothing important missing — needs a scan of the extras.
//        DIVERGENT  — at least one converted line is not present in current.
//                     Keep the external.
//
// Writes scripts/compare-report.md grouped by classification, with per-pair
// details (missing lines, extra lines in current, etc.) for manual review.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CONVERTED_DIR = path.resolve(__dirname, "converted");
const CURRENT_DIR = path.resolve(__dirname, "..", "src", "data");
const REPORT_PATH = path.resolve(__dirname, "compare-report.md");

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
  "Dessert.Bread.OrangeCinnamonSwirlBread.htm": "orange-cinnamon-swirl-bread-muffins",
  "Dessert.Bread.PineapplePumpkinBread.htm": "pineapple-pumpkin-bread-muffins",
  "Dessert.Muffins.PineapplePumpkinMuffins.htm": "pineapple-pumpkin-bread-muffins",
  "Dessert.Bread.PumpkinBread.htm": "pumpkin-bread-muffins",
  "Dessert.Muffins.PumpkinMuffins.htm": "pumpkin-bread-muffins",
  "Dessert.Pie.ApplePie.htm": "apple-pear-pie",
  "Dessert.Pie.PearPie.htm": "apple-pear-pie",
  "Dessert.Candy.ChocolateCoveredPretzelBraids.htm": "chocolate-covered-pretzels",
  "Dessert.Candy.ChocolateCoveredPretzelSnaps.htm": "chocolate-covered-pretzels",
  "Dessert.Pie.PieCrusts.GrahamCrackerPieCrust.htm": "oreo-graham-cracker-pie-crust",
  "Dessert.Pie.PieCrusts.OreoPieCrust.htm": "oreo-graham-cracker-pie-crust",
  "Dessert.Cannolis.Shells.ChocolateCannoliShells.htm": "chocolate-cannoli-shells",
  "Dessert.Cannolis.Filling.ChocolateCannoliFilling.htm": "chocolate-cannolis",
  "Dessert.Cannolis.Filling.PeppermintCannoliFilling.htm": "peppermint-cannolis",
  "Dessert.Cannolis.Filling.PumpkinCannoliFilling.htm": "pumpkin-cannolis",
  "Dessert.Cookies.BlackandWhiteCookies.htm": "black-and-white-cookies",
  "Dessert.Fudge.CookiesandCreamFudge.htm": "cookies-and-cream-fudge",
  "Dessert.Cake.Cheesecake.Shells.CannoliShellCheesecakeShell.htm": "cheesecake-shell",
  "Dessert.Cake.Cheesecake.Shells.GrahamCrackerCheesecakeShell.htm": "cheesecake-shell",
  "Dessert.Cake.Cheesecake.Shells.OreoCheesecakeShell.htm": "cheesecake-shell",
  "Dessert.Brownies.PeanutButterSwirlBrownies.htm": "peanut-swirl-brownies",
  "Dessert.Cookies.DoubleChocolateCookies.htm": "chocolate-chocolate-chip-cookies",
  "Dessert.Cookies.PumpkinCookies.htm": "pumpkin-drop-cookies",
  "Dessert.Frosting.Frosting.ChocolateChipCookieDoughFrosting.htm": "cookie-dough-frosting",
  "Dessert.Cookies.SpritzgebackCookies.htm": "spritzgeback-cookies",
  "Dessert.Cake.Cheesecake.PumpkinCheesecake.htm": "pumpkin-cheesecake-flavoring",
  "Dessert.Cake.Cheesecake.RaspberryCheesecake.htm": "raspberry-cheesecake-flavoring",
  "Dessert.Frosting.Frosting.VanillaFrosting.htm": "vanilla-frosting-whoopie-pie-filling",
};

function defaultSlug(filename) {
  const name = path.basename(filename, ".md").split(".").pop();
  return name
    .replace(/'/g, "")
    .replace(/([a-z])([A-Z])/g, "$1-$2")
    .replace(/([A-Z])([A-Z][a-z])/g, "$1-$2")
    .replace(/\band\b/gi, "-and-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .toLowerCase();
}

function slugForConvertedFile(convertedFile) {
  // convertedFile is like "Dessert.Bread.AppleBread.md". The original htm name
  // was "...htm", so swap extension to look up EXTERNAL_TO_CURRENT.
  const htmName = convertedFile.replace(/\.md$/, ".htm");
  if (htmName in EXTERNAL_TO_CURRENT) return EXTERNAL_TO_CURRENT[htmName];
  return defaultSlug(convertedFile);
}

// ---------- Parsing ----------

function parseMd(md) {
  const lines = md.split("\n");
  const name = (lines[0] || "").replace(/^#\s*/, "").trim();
  const ingredients = [];
  const instructions = [];
  let section = null;
  for (const raw of lines) {
    const line = raw.replace(/\r$/, "");
    if (/^##\s+Ingredients\b/i.test(line)) { section = "ing"; continue; }
    if (/^##\s+Instructions\b/i.test(line)) { section = "ins"; continue; }
    if (/^##\s+/.test(line)) { section = null; continue; }
    if (/^###\s+/.test(line)) continue;
    if (section === "ing" && /^-\s+/.test(line)) {
      ingredients.push(line.replace(/^-\s+/, "").trim());
    }
    if (section === "ins" && /^\d+\.\s+/.test(line)) {
      instructions.push(line.replace(/^\d+\.\s+/, "").trim());
    }
  }
  return { name, ingredients, instructions };
}

// ---------- Normalization ----------

// Normalize text so cosmetic differences don't count:
//   - Lowercase
//   - Strip `{...}` tokens entirely (so "{1}" vs "1" collide) — but preserve
//     their raw contents so "{1 3/4}" and "1 3/4" both collapse to the same
//     numeric string.
//   - Unicode: × → x, curly apostrophes/quotes → straight, en/em dash → "-"
//   - Collapse runs of whitespace / punctuation-adjacent spaces
//   - Trim
function norm(s) {
  return s
    .replace(/\{([^}]*)\}/g, "$1") // strip braces, keep content
    .replace(/[\u2018\u2019\u02BC\uFF07]/g, "'")
    .replace(/[\u201C\u201D]/g, '"')
    .replace(/[\u00D7]/g, "x") // multiplication sign → x
    .replace(/[\u2013\u2014]/g, "-") // en/em dash → hyphen
    .replace(/\u2026/g, "...")
    .replace(/°/g, "") // degree symbol is cosmetic ("325°F" = "325 F")
    .replace(/'/g, "") // apostrophe differences ("Nana's" = "Nanas", "confectioners'" = "confectioners")
    .toLowerCase()
    // collapse whitespace around "x" when between digits (8.5 x 4.5 → 8.5x4.5)
    .replace(/(\d)\s*x\s*(\d)/g, "$1x$2")
    // strip whitespace between a digit and a unit letter ("325 f" → "325f")
    .replace(/(\d)\s+([a-z])/g, "$1$2")
    // strip trailing . or .) at end (container) vs (container.) equivalence
    .replace(/\.\s*\)\s*$/, ")")
    .replace(/\.\s*$/, "")
    .replace(/\s+/g, " ")
    .trim();
}

// ---------- Comparison ----------

function classifyPair(converted, current) {
  const normCurIng = current.ingredients.map(norm);
  const normCurIns = current.instructions.map(norm);
  const normCnvIng = converted.ingredients.map(norm);
  const normCnvIns = converted.instructions.map(norm);

  const missingIng = [];
  const missingIns = [];

  for (let i = 0; i < normCnvIng.length; i++) {
    if (!normCurIng.includes(normCnvIng[i])) {
      missingIng.push({ i, raw: converted.ingredients[i] });
    }
  }
  for (let i = 0; i < normCnvIns.length; i++) {
    if (!normCurIns.includes(normCnvIns[i])) {
      missingIns.push({ i, raw: converted.instructions[i] });
    }
  }

  // Extra lines in current (ingredients or instructions that don't correspond
  // to any converted line). Helpful for "NEAR" review.
  const extraIng = [];
  const extraIns = [];
  for (let i = 0; i < normCurIng.length; i++) {
    if (!normCnvIng.includes(normCurIng[i])) {
      extraIng.push({ i, raw: current.ingredients[i] });
    }
  }
  for (let i = 0; i < normCurIns.length; i++) {
    if (!normCnvIns.includes(normCurIns[i])) {
      extraIns.push({ i, raw: current.instructions[i] });
    }
  }

  const divergent = missingIng.length > 0 || missingIns.length > 0;
  const strictSameOrder =
    !divergent &&
    normCnvIng.length === normCurIng.length &&
    normCnvIns.length === normCurIns.length &&
    normCnvIng.every((l, i) => l === normCurIng[i]) &&
    normCnvIns.every((l, i) => l === normCurIns[i]);

  let category;
  if (strictSameOrder) category = "STRICT";
  else if (!divergent) category = "SUBSET";
  else category = "DIVERGENT";

  return {
    category,
    missingIng, missingIns,
    extraIng, extraIns,
    titleMatch: norm(converted.name) === norm(current.name),
  };
}

// ---------- Main ----------

function main() {
  if (!fs.existsSync(CONVERTED_DIR)) {
    console.error(`Run convert-htm-to-md.mjs first; ${CONVERTED_DIR} missing`);
    process.exit(1);
  }

  const convertedFiles = fs.readdirSync(CONVERTED_DIR)
    .filter((f) => f.endsWith(".md"))
    .sort();

  const currentFiles = new Set(
    fs.readdirSync(CURRENT_DIR)
      .filter((f) => f.endsWith(".md"))
      .map((f) => path.basename(f, ".md")),
  );

  // slug → external filenames mapped to it (for merge awareness)
  const slugToExternals = {};
  for (const f of convertedFiles) {
    const slug = slugForConvertedFile(f);
    (slugToExternals[slug] ||= []).push(f);
  }

  const results = [];
  for (const f of convertedFiles) {
    const slug = slugForConvertedFile(f);
    const merged = slugToExternals[slug].length > 1;
    const converted = parseMd(
      fs.readFileSync(path.join(CONVERTED_DIR, f), "utf8"),
    );
    if (!currentFiles.has(slug)) {
      results.push({
        file: f, slug, merged, category: "MISSING",
        reason: `No current md at ${slug}.md`,
        converted, current: null, detail: null,
      });
      continue;
    }
    const current = parseMd(
      fs.readFileSync(path.join(CURRENT_DIR, `${slug}.md`), "utf8"),
    );
    const detail = classifyPair(converted, current);
    results.push({
      file: f, slug, merged,
      category: detail.category,
      converted, current, detail,
    });
  }

  // --- Emit report ---
  const by = {};
  for (const r of results) (by[r.category] ||= []).push(r);

  const lines = [];
  lines.push("# Strict converted↔current comparison");
  lines.push("");
  lines.push(`- Converted files: ${convertedFiles.length}`);
  for (const cat of ["STRICT", "SUBSET", "DIVERGENT", "MISSING"]) {
    lines.push(`- ${cat}: ${(by[cat] || []).length}`);
  }
  lines.push("");
  lines.push("Classification:");
  lines.push("- **STRICT** — ingredient and instruction counts equal, every line matches in order post-normalization. Safe to delete external.");
  lines.push("- **SUBSET** — every converted line appears in current (possibly current has additions/reordering). Usually safe; skim the `+ extra` lines to confirm the additions are editorial (notes, clarifications), not a different recipe.");
  lines.push("- **DIVERGENT** — at least one converted line is not in current. Keep external.");
  lines.push("- **MISSING** — converted maps to a current slug that doesn't exist. Should be rare.");
  lines.push("");

  for (const cat of ["STRICT", "SUBSET", "DIVERGENT", "MISSING"]) {
    const group = by[cat] || [];
    lines.push(`## ${cat} (${group.length})`);
    lines.push("");
    if (group.length === 0) {
      lines.push("_None._");
      lines.push("");
      continue;
    }
    for (const r of group) {
      const mergedTag = r.merged ? " [merged]" : "";
      const titleTag = r.detail && !r.detail.titleMatch
        ? ` [title differs: "${r.converted.name}" vs "${r.current?.name}"]`
        : "";
      lines.push(`### ${r.file} → ${r.slug}.md${mergedTag}${titleTag}`);
      lines.push(
        `- Counts — converted: ${r.converted.ingredients.length} ing / ${r.converted.instructions.length} ins; current: ${r.current?.ingredients.length ?? "?"} ing / ${r.current?.instructions.length ?? "?"} ins`,
      );
      if (r.detail) {
        if (r.detail.missingIng.length) {
          lines.push("- **Missing ingredients (converted not in current):**");
          for (const { raw } of r.detail.missingIng) {
            lines.push(`  - \`${raw}\``);
          }
        }
        if (r.detail.missingIns.length) {
          lines.push("- **Missing instructions (converted not in current):**");
          for (const { raw } of r.detail.missingIns) {
            lines.push(`  - \`${raw}\``);
          }
        }
        if (cat === "SUBSET" || cat === "DIVERGENT") {
          if (r.detail.extraIng.length) {
            lines.push("- **Extra ingredients in current (not in converted):**");
            for (const { raw } of r.detail.extraIng) {
              lines.push(`  - \`${raw}\``);
            }
          }
          if (r.detail.extraIns.length) {
            lines.push("- **Extra instructions in current (not in converted):**");
            for (const { raw } of r.detail.extraIns) {
              lines.push(`  - \`${raw}\``);
            }
          }
        }
      } else if (r.reason) {
        lines.push(`- ${r.reason}`);
      }
      lines.push("");
    }
  }

  fs.writeFileSync(REPORT_PATH, lines.join("\n"));
  console.log(`Wrote ${REPORT_PATH}`);
  for (const cat of ["STRICT", "SUBSET", "DIVERGENT", "MISSING"]) {
    console.log(`  ${cat}: ${(by[cat] || []).length}`);
  }
}

main();
