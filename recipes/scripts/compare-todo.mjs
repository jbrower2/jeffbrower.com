// Compares each converted markdown file in scripts/todo-converted/ against the
// corresponding current recipe at src/data/<slug>.md.
//
// Produces scripts/todo-compare-report.md. For each converted file:
//   - MATCHED:  current recipe exists; per-ingredient/instruction diff shown.
//     Classified as STRICT, SUBSET, or DIVERGENT (same semantics as
//     compare-converted.mjs).
//   - NEW:      no corresponding current recipe (this source represents a
//     recipe we don't have yet).
//   - REFERENCE: not a single recipe — e.g. a cross-recipe summary.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CONVERTED_DIR = path.resolve(__dirname, "todo-converted");
const CURRENT_DIR = path.resolve(__dirname, "..", "src", "data");
const REPORT_PATH = path.resolve(__dirname, "todo-compare-report.md");

// One entry per converted file. slug=null means NEW (no current match).
// "kind" classifies the source; "slugs" is the list of current recipes it
// overlaps (multiple if the source yields >1 recipe, e.g. cake+cupcakes).
const MAP = [
  { file: "Brownies.md",                                         kind: "match",     slugs: [] /* no current brownies recipe matches */ },
  { file: "chili.md",                                             kind: "match",     slugs: [] },
  { file: "Chocolate Chip Cookies.md",                           kind: "match",     slugs: [] /* "Award Winning Soft" pudding-mix variant — not in app */ },
  { file: "Chocolate Pumpkin Cake and Cupcakes Recipe.md",       kind: "match",     slugs: ["chocolate-pumpkin-cake", "chocolate-pumpkin-cupcakes"] },
  { file: "Crushed Red Pepper Hummus.md",                        kind: "match",     slugs: [] },
  { file: "Dark Chocolate Candy Cane Cookies.md",                kind: "match",     slugs: [] },
  { file: "dirty rice.md",                                        kind: "match",     slugs: ["dirty-rice"] },
  { file: "Double Chocolate Chip Cookies.md",                     kind: "match",     slugs: ["double-chocolate-chip-cookies"] },
  { file: "Flavors.md",                                           kind: "match",     slugs: ["ice-cream"] },
  { file: "Gingerbread.md",                                       kind: "match",     slugs: [] /* existing gingerbread-cookies.md is a different formula */ },
  { file: "Mrs. Sigg's Snickerdoodles.md",                        kind: "match",     slugs: ["mrs-siggs-snickerdoodles"] },
  { file: "Neapolitan Dough.md",                                  kind: "match",     slugs: [] },
  { file: "Pizza Sauce.md",                                       kind: "match",     slugs: [] },
  { file: "Pumpkin Cookies.md",                                   kind: "match",     slugs: ["pumpkin-drop-cookies"] },
  { file: "Raspberry and Almond Shortbread Thumbprints.md",       kind: "match",     slugs: ["raspberry-thumbprint-cookies"] },
  { file: "Recipes.md",                                           kind: "reference" /* cross-recipe totals spreadsheet */ },
  { file: "Red Velvet Crinkle Cookies.md",                        kind: "match",     slugs: [] },
  { file: "Reese's Stuffed Peanut Butter Cookies.md",             kind: "match",     slugs: [] },
  { file: "Salsa.md",                                             kind: "match",     slugs: [] /* salsa-morada.md is a different recipe */ },
  { file: "Sugar Cookies Recipe.md",                              kind: "match",     slugs: [] /* existing sugar-cookies.md uses buttermilk; Alton Brown version uses milk */ },
  { file: "Yellow Cake.md",                                       kind: "match",     slugs: [] },
];

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

function norm(s) {
  return s
    .replace(/\{([^}]*)\}/g, "$1")
    .replace(/[\u2018\u2019\u02BC\uFF07]/g, "'")
    .replace(/[\u201C\u201D]/g, '"')
    .replace(/[\u00D7]/g, "x")
    .replace(/[\u2013\u2014]/g, "-")
    .replace(/\u2026/g, "...")
    .replace(/°/g, "")
    .replace(/'/g, "")
    .toLowerCase()
    .replace(/(\d)\s*x\s*(\d)/g, "$1x$2")
    .replace(/(\d)\s+([a-z])/g, "$1$2")
    .replace(/\.\s*\)\s*$/, ")")
    .replace(/\.\s*$/, "")
    .replace(/\s+/g, " ")
    .trim();
}

function classifyPair(converted, current) {
  const normCurIng = current.ingredients.map(norm);
  const normCurIns = current.instructions.map(norm);
  const normCnvIng = converted.ingredients.map(norm);
  const normCnvIns = converted.instructions.map(norm);

  const missingIng = [];
  const missingIns = [];
  for (let i = 0; i < normCnvIng.length; i++) {
    if (!normCurIng.includes(normCnvIng[i])) {
      missingIng.push(converted.ingredients[i]);
    }
  }
  for (let i = 0; i < normCnvIns.length; i++) {
    if (!normCurIns.includes(normCnvIns[i])) {
      missingIns.push(converted.instructions[i]);
    }
  }
  const extraIng = [];
  const extraIns = [];
  for (let i = 0; i < normCurIng.length; i++) {
    if (!normCnvIng.includes(normCurIng[i])) {
      extraIng.push(current.ingredients[i]);
    }
  }
  for (let i = 0; i < normCurIns.length; i++) {
    if (!normCnvIns.includes(normCurIns[i])) {
      extraIns.push(current.instructions[i]);
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

function main() {
  const convertedFiles = new Set(
    fs.readdirSync(CONVERTED_DIR).filter((f) => f.endsWith(".md")),
  );
  for (const entry of MAP) {
    if (!convertedFiles.has(entry.file)) {
      throw new Error(`MAP references missing file: ${entry.file}`);
    }
  }
  for (const f of convertedFiles) {
    if (!MAP.find((m) => m.file === f)) {
      throw new Error(`Converted file not in MAP: ${f}`);
    }
  }

  const results = [];
  for (const entry of MAP) {
    const converted = parseMd(
      fs.readFileSync(path.join(CONVERTED_DIR, entry.file), "utf8"),
    );

    if (entry.kind === "reference") {
      results.push({
        ...entry,
        category: "REFERENCE",
        converted,
      });
      continue;
    }

    if (!entry.slugs || entry.slugs.length === 0) {
      results.push({
        ...entry,
        category: "NEW",
        converted,
      });
      continue;
    }

    const comparisons = [];
    for (const slug of entry.slugs) {
      const currentPath = path.join(CURRENT_DIR, `${slug}.md`);
      if (!fs.existsSync(currentPath)) {
        comparisons.push({
          slug,
          category: "MISSING_FILE",
          reason: `src/data/${slug}.md does not exist`,
        });
        continue;
      }
      const current = parseMd(fs.readFileSync(currentPath, "utf8"));
      const detail = classifyPair(converted, current);
      comparisons.push({ slug, category: detail.category, current, detail });
    }

    // Aggregate category across comparisons: STRICT < SUBSET < DIVERGENT
    const order = { STRICT: 0, SUBSET: 1, DIVERGENT: 2, MISSING_FILE: 3 };
    const worst = comparisons.reduce(
      (w, c) => (order[c.category] > order[w] ? c.category : w),
      "STRICT",
    );

    results.push({
      ...entry,
      category: worst,
      converted,
      comparisons,
    });
  }

  // Emit report
  const by = {};
  for (const r of results) (by[r.category] ||= []).push(r);

  const lines = [];
  lines.push("# Todo folder ↔ current recipes");
  lines.push("");
  lines.push(`- Converted files: ${results.length}`);
  for (const cat of ["STRICT", "SUBSET", "DIVERGENT", "NEW", "REFERENCE", "MISSING_FILE"]) {
    lines.push(`- ${cat}: ${(by[cat] || []).length}`);
  }
  lines.push("");
  lines.push("Classification:");
  lines.push("- **STRICT** — ingredients and instructions match line-for-line (post-normalization, same order).");
  lines.push("- **SUBSET** — every converted line appears in current; current may have added notes/extra steps.");
  lines.push("- **DIVERGENT** — at least one converted line is NOT in the current recipe. The recipes differ.");
  lines.push("- **NEW** — converted represents a recipe we don't have in the app.");
  lines.push("- **REFERENCE** — source file is not a single recipe (e.g. multi-recipe summary).");
  lines.push("");

  for (const cat of ["STRICT", "SUBSET", "DIVERGENT", "NEW", "REFERENCE", "MISSING_FILE"]) {
    const group = by[cat] || [];
    lines.push(`## ${cat} (${group.length})`);
    lines.push("");
    if (group.length === 0) { lines.push("_None._"); lines.push(""); continue; }

    for (const r of group) {
      if (r.category === "NEW") {
        lines.push(`### ${r.file}`);
        lines.push(`- Converted title: "${r.converted.name}"`);
        lines.push(`- No matching current recipe.`);
        lines.push("");
        continue;
      }
      if (r.category === "REFERENCE") {
        lines.push(`### ${r.file}`);
        lines.push(`- Converted title: "${r.converted.name}"`);
        lines.push(`- Source is a reference / summary file, not a single recipe.`);
        lines.push("");
        continue;
      }
      for (const c of r.comparisons) {
        const titleTag = c.detail && !c.detail.titleMatch
          ? ` [title differs: "${r.converted.name}" vs "${c.current?.name}"]`
          : "";
        lines.push(`### ${r.file} → ${c.slug}.md${titleTag}`);
        if (c.category === "MISSING_FILE") {
          lines.push(`- ${c.reason}`);
          lines.push("");
          continue;
        }
        lines.push(
          `- Counts — converted: ${r.converted.ingredients.length} ing / ${r.converted.instructions.length} ins; current: ${c.current.ingredients.length} ing / ${c.current.instructions.length} ins`,
        );
        lines.push(`- Per-slug category: **${c.category}**`);
        if (c.detail.missingIng.length) {
          lines.push("- **Missing in current (converted has, current does not):**");
          for (const raw of c.detail.missingIng) lines.push(`  - \`${raw}\``);
        }
        if (c.detail.missingIns.length) {
          lines.push("- **Missing instructions in current:**");
          for (const raw of c.detail.missingIns) lines.push(`  - \`${raw}\``);
        }
        if (cat === "SUBSET" || cat === "DIVERGENT") {
          if (c.detail.extraIng.length) {
            lines.push("- **Extra in current (current has, converted does not):**");
            for (const raw of c.detail.extraIng) lines.push(`  - \`${raw}\``);
          }
          if (c.detail.extraIns.length) {
            lines.push("- **Extra instructions in current:**");
            for (const raw of c.detail.extraIns) lines.push(`  - \`${raw}\``);
          }
        }
        lines.push("");
      }
    }
  }

  fs.writeFileSync(REPORT_PATH, lines.join("\n"));
  console.log(`Wrote ${REPORT_PATH}`);
  for (const cat of ["STRICT", "SUBSET", "DIVERGENT", "NEW", "REFERENCE", "MISSING_FILE"]) {
    console.log(`  ${cat}: ${(by[cat] || []).length}`);
  }
}

main();
