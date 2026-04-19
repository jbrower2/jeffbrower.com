#!/usr/bin/env node
const fs = require("fs");
const path = require("path");

const recipes = require("../src/data/recipes.json");
const OUT_DIR = path.join(__dirname, "..", "src", "data", "recipes");

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
  console.log(`Wrote ${count} markdown files to ${OUT_DIR}`);
}

main();
