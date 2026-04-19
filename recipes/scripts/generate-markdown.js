#!/usr/bin/env node
const fs = require("fs");
const path = require("path");

const recipes = require("../src/data/recipes.json");
const OUT_DIR = path.join(__dirname, "..", "src", "data", "recipes");
const INDEX_PATH = path.join(__dirname, "..", "src", "data", "recipes-index.js");

function formatIngredient(ing) {
  let line = `{${ing.quantity}}`;
  if (ing.unit) line += ` ${ing.unit}`;
  line += ` ${ing.name}`;
  if (ing.note) line += `, ${ing.note}`;
  return line;
}

function wrapYield(yieldStr) {
  const m = yieldStr.match(/^(\d+\s+\d+\/\d+|\d+\/\d+|\d+)(.*)$/);
  if (!m) return yieldStr;
  return `{${m[1]}}${m[2]}`;
}

function splitInstructions(text) {
  const parts = text.split(". ");
  if (parts.length > 0) {
    parts[parts.length - 1] = parts[parts.length - 1].replace(/\.\s*$/, "");
  }
  return parts;
}

function recipeToMarkdown(r) {
  const lines = [];
  lines.push(`# ${r.name}`);
  lines.push("");
  if (r.servings != null) {
    lines.push(`- **Servings:** {${r.servings}}`);
  }
  lines.push(`- **Yield:** ${wrapYield(r.yield)}`);
  lines.push("");
  lines.push("## Ingredients");
  lines.push("");
  for (const ing of r.ingredients) {
    lines.push(`- ${formatIngredient(ing)}`);
  }
  lines.push("");
  lines.push("## Instructions");
  lines.push("");
  for (const step of splitInstructions(r.instructions)) {
    lines.push(`1. ${step}`);
  }
  lines.push("");
  return lines.join("\n");
}

function identForSlug(slug) {
  return "r_" + slug.replace(/[^a-z0-9]/gi, "_");
}

function writeIndex(rs) {
  const lines = [];
  for (const r of rs) {
    lines.push(`import ${identForSlug(r.slug)} from "./recipes/${r.slug}.md";`);
  }
  lines.push("");
  lines.push("export default [");
  for (const r of rs) {
    lines.push(
      `  { slug: ${JSON.stringify(r.slug)}, name: ${JSON.stringify(r.name)}, show: ${r.show === true}, markdown: ${identForSlug(r.slug)} },`
    );
  }
  lines.push("];");
  fs.writeFileSync(INDEX_PATH, lines.join("\n") + "\n");
}

function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  let count = 0;
  for (const r of recipes) {
    fs.writeFileSync(
      path.join(OUT_DIR, `${r.slug}.md`),
      recipeToMarkdown(r)
    );
    count++;
  }
  writeIndex(recipes);
  console.log(`Wrote ${count} markdown files to ${OUT_DIR}`);
  console.log(`Wrote index to ${INDEX_PATH}`);
}

main();
