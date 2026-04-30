// Converts each external HTML recipe at /Volumes/nasty/docs/recipes/web/*.htm
// to a markdown file in scripts/converted/ using the same schema the current
// recipes follow.
//
// Output filename mirrors the external filename: Dessert.Bread.AppleBread.htm
// → scripts/converted/Dessert.Bread.AppleBread.md. Keep the dotted name so
// traceability back to the archive is obvious.
//
// Schema emitted:
//
//   # Title
//
//   - **Servings:** {N}
//   - **Yield:** {M} unit         (omitted if yield is blank)
//
//   ## Ingredients
//
//   - {amount} unit Title Cased Ingredient Name[, lowercase tail]
//
//   ## Instructions
//
//   1. Step text...
//
// Deliberately minimal: external HTML has no intro, source, timings, or notes,
// so the converted file has none either.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const EXTERNAL_DIR = "/Volumes/nasty/docs/recipes/web";
const OUT_DIR = path.resolve(__dirname, "converted");

const SKIP_EXTERNAL = new Set([
  "_recipe.htm",
  "index.htm",
  "Dessert.IceCream.Flavors.htm", // embedded into ice-cream.md; no 1:1 pair
]);

function titleCaseIngredient(name) {
  // Current recipes Title Case words before the first comma; everything after
  // the first comma stays lowercase.
  const commaIdx = name.indexOf(",");
  const head = commaIdx === -1 ? name : name.slice(0, commaIdx);
  const tail = commaIdx === -1 ? "" : name.slice(commaIdx);
  // Split on spaces only — hyphens are internal to a word
  // ("all-purpose" → "All-purpose", not "All-Purpose").
  const cased = head
    .split(" ")
    .map((w) => (w.length ? w[0].toUpperCase() + w.slice(1) : w))
    .join(" ");
  return cased + tail;
}

function parseExternal(filePath) {
  const html = fs.readFileSync(filePath, "utf8");

  const h1 = html.match(/<h1>([^<]+)<\/h1>/);
  const servings = html.match(/data-default="([^"]+)"\s+id="Servings"/);
  const yieldDefault = html.match(/data-default="([^"]+)"\s+id="Yield"/);
  const yieldUnitMatch = html.match(/id="Yield"[^>]*\/>\s*([^<]*?)\s*<br/);

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

  return {
    title: h1 ? h1[1].trim() : "",
    servings: servings ? servings[1] : "",
    yieldDefault: yieldDefault ? yieldDefault[1] : "",
    yieldUnit: yieldUnitMatch ? yieldUnitMatch[1].trim() : "",
    ingredients,
    directions,
  };
}

function toMarkdown(r) {
  const lines = [];
  lines.push(`# ${r.title}`);
  lines.push("");
  lines.push(`- **Servings:** {${r.servings}}`);
  if (r.yieldDefault !== "") {
    const unit = r.yieldUnit ? ` ${r.yieldUnit}` : "";
    lines.push(`- **Yield:** {${r.yieldDefault}}${unit}`);
  }
  lines.push("");
  lines.push("## Ingredients");
  lines.push("");
  for (const { amount, unit, name } of r.ingredients) {
    const cased = titleCaseIngredient(name);
    if (unit) {
      lines.push(`- {${amount}} ${unit} ${cased}`);
    } else {
      lines.push(`- {${amount}} ${cased}`);
    }
  }
  lines.push("");
  lines.push("## Instructions");
  lines.push("");
  for (const step of r.directions) {
    lines.push(`1. ${step}`);
  }
  lines.push("");
  return lines.join("\n");
}

function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const files = fs
    .readdirSync(EXTERNAL_DIR)
    .filter((f) => f.endsWith(".htm") && !SKIP_EXTERNAL.has(f))
    .sort();

  let written = 0;
  for (const f of files) {
    const parsed = parseExternal(path.join(EXTERNAL_DIR, f));
    const md = toMarkdown(parsed);
    const outName = f.replace(/\.htm$/, ".md");
    fs.writeFileSync(path.join(OUT_DIR, outName), md);
    written += 1;
  }

  console.log(`Wrote ${written} markdown files to ${OUT_DIR}`);
}

main();
