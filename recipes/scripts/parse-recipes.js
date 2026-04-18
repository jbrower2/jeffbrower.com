#!/usr/bin/env node
const fs = require("fs");
const path = require("path");

const RECIPES_PATH = "/Volumes/nasty/docs/recipes/Recipes.txt";
const BACKUP_PATH = "/Volumes/nasty/docs/recipes/Backup.txt";
const OUT_PATH = path.join(__dirname, "..", "src", "data", "recipes.json");

const KNOWN_UNITS = new Set([
  "cup",
  "tbsp",
  "tsp",
  "stick",
  "oz",
  "lb",
  "fl oz",
]);

function slugify(name) {
  return name
    .replace(/['\u2019]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function splitOnFirstNColons(line, n) {
  const positions = [];
  for (let i = 0; i < line.length && positions.length < n; i++) {
    if (line[i] === ":") positions.push(i);
  }
  if (positions.length < n) {
    throw new Error(
      `Expected at least ${n} colons, found ${positions.length} in line: ${line}`
    );
  }
  const fields = [];
  let start = 0;
  for (const pos of positions) {
    fields.push(line.slice(start, pos));
    start = pos + 1;
  }
  fields.push(line.slice(start));
  return fields;
}

function parseIngredient(chunk, ctx) {
  const m = chunk.match(/^(\d+\s+\d+\/\d+|\d+\/\d+|\d+)\s+(.+)$/);
  if (!m) {
    throw new Error(`[${ctx}] Ingredient regex failed: "${chunk}"`);
  }
  const quantity = m[1];
  let rest = m[2];

  let unit = null;
  if (/^fl\s+oz(\s+|$)/.test(rest)) {
    unit = "fl oz";
    rest = rest.replace(/^fl\s+oz\s*/, "");
  } else {
    const tokenMatch = rest.match(/^(\S+)\s+(.+)$/);
    if (tokenMatch && KNOWN_UNITS.has(tokenMatch[1].toLowerCase())) {
      unit = tokenMatch[1];
      rest = tokenMatch[2];
    }
  }

  if (rest.length === 0) {
    throw new Error(`[${ctx}] Ingredient name is empty: "${chunk}"`);
  }

  let name = rest;
  let note = null;
  const commaIdx = rest.indexOf(", ");
  if (commaIdx !== -1) {
    name = rest.slice(0, commaIdx);
    note = rest.slice(commaIdx + 2);
  }

  for (const [k, v] of Object.entries({ quantity, unit, name, note })) {
    if (v != null && v !== v.trim()) {
      throw new Error(
        `[${ctx}] Ingredient "${chunk}" has stray whitespace in ${k}: "${v}"`
      );
    }
  }

  return { quantity, unit, name, note };
}

function formatIngredient({ quantity, unit, name, note }) {
  return `${quantity}${unit ? " " + unit : ""} ${name}${note ? ", " + note : ""}`;
}

function formatLine({ name, servings, yield: yieldStr, ingredients, instructions }) {
  return `${name}:${servings ?? 0}:${yieldStr}:${ingredients.map(formatIngredient).join(";")}:${instructions}`;
}

function parseLine(line, source, lineNum) {
  const ctx = `${source}:${lineNum}`;
  const fields = splitOnFirstNColons(line, 4);
  if (fields.length !== 5) {
    throw new Error(`[${ctx}] Expected 5 fields, got ${fields.length}`);
  }
  for (let i = 0; i < fields.length; i++) {
    if (fields[i].length === 0) {
      throw new Error(`[${ctx}] Field ${i} is empty in: ${line}`);
    }
  }
  const [name, servingsStr, yieldStr, ingredientsRaw, instructions] = fields;

  if (!/^\d+$/.test(servingsStr)) {
    throw new Error(`[${ctx}] Servings is not all digits: "${servingsStr}"`);
  }
  const servings = parseInt(servingsStr, 10) || null;

  const ingredients = ingredientsRaw
    .split(";")
    .map((c, i) => parseIngredient(c, `${ctx} ingr#${i}`));

  const recipe = {
    name,
    slug: slugify(name),
    servings,
    yield: yieldStr,
    ingredients,
    instructions,
  };

  const reconstructed = formatLine(recipe);
  if (reconstructed !== line) {
    let i = 0;
    while (
      i < Math.min(reconstructed.length, line.length) &&
      reconstructed[i] === line[i]
    ) {
      i++;
    }
    throw new Error(
      `[${ctx}] Round-trip mismatch at index ${i}:\n` +
        `  input:  ${line}\n` +
        `  output: ${reconstructed}\n` +
        `  diverge from: "${line.slice(i, i + 40)}…" vs "${reconstructed.slice(i, i + 40)}…"`
    );
  }

  return recipe;
}

const ONE_OFFS = [
  {
    name: "Butterbeer",
    slug: "butterbeer",
    servings: 4,
    yield: "4 glasses",
    ingredients: [
      { quantity: "1", unit: "cup", name: "Brown Sugar", note: "light or dark" },
      { quantity: "2", unit: "tbsp", name: "Water", note: null },
      { quantity: "6", unit: "tbsp", name: "Butter", note: null },
      { quantity: "1/2", unit: "tsp", name: "Salt", note: null },
      { quantity: "1/2", unit: "tsp", name: "Cider Vinegar", note: null },
      { quantity: "3/4", unit: "cup", name: "Heavy Cream", note: "divided" },
      { quantity: "1/2", unit: "tsp", name: "Rum Extract", note: null },
      { quantity: "48", unit: "oz", name: "Cream Soda", note: "four 12-oz bottles" },
    ],
    instructions:
      "In a small saucepan over medium, combine the brown sugar and water. Bring to a gentle boil and cook, stirring often, until the mixture reads 240 F on a candy thermometer. Stir in the butter, salt, vinegar and 1/4 cup heavy cream. Set aside to cool to room temperature. Once the mixture has cooled, stir in the rum extract. In a medium bowl, combine 2 tablespoons of the brown sugar mixture and the remaining 1/2 cup of heavy cream. Use an electric mixer to beat until just thickened, but not completely whipped, about 2 to 3 minutes. To serve, divide the brown sugar mixture between 4 tall glasses (about 1/4 cup for each glass). Add 1/4 cup of cream soda to each glass, then stir to combine. Fill each glass nearly to the top with additional cream soda, then spoon the whipped topping over each.",
  },
  {
    name: "Prime Rib",
    slug: "prime-rib",
    servings: 12,
    yield: "12 servings",
    ingredients: [
      { quantity: "10", unit: "lb", name: "Prime Rib", note: "bone-in" },
      { quantity: "1", unit: "stick", name: "Butter", note: "melted" },
      { quantity: "10", unit: null, name: "Garlic Cloves", note: null },
      { quantity: "1 1/2", unit: "tbsp", name: "Oregano", note: null },
      { quantity: "1", unit: "tbsp", name: "Thyme", note: null },
      { quantity: "1", unit: "tbsp", name: "Rosemary", note: null },
      { quantity: "1 1/2", unit: "tbsp", name: "Salt", note: null },
      { quantity: "2", unit: "tsp", name: "Black Pepper", note: null },
    ],
    instructions:
      "Combine all seasoning ingredients (butter, garlic, oregano, thyme, rosemary, salt, and black pepper) in a small bowl. Remove the prime rib from the fridge and season it. Let sit for 45 minutes before cooking. Place in a roasting pan on a roasting rack, fat side up. Cook at 450 for 20 minutes, then reduce to 325. Cook until internal temperature reaches 120. Let rest for 15 minutes before serving — internal temperature will continue rising to about 130.",
  },
];

function readRecipeFile(p, { allowDupes }) {
  const raw = fs.readFileSync(p, "utf8");
  const lines = raw.split("\n").map((l) => l.replace(/\r$/, ""));
  const result = new Map(); // name -> Array<{line, lineNum}>
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.length === 0) {
      if (i !== lines.length - 1) {
        throw new Error(`[${p}] Blank line at line ${i + 1}`);
      }
      continue;
    }
    if (line !== line.trim()) {
      throw new Error(`[${p}] Padded/whitespace line at ${i + 1}: "${line}"`);
    }
    const colonIdx = line.indexOf(":");
    if (colonIdx === -1) {
      throw new Error(`[${p}] No colon at line ${i + 1}: ${line}`);
    }
    const name = line.slice(0, colonIdx);
    if (result.has(name)) {
      if (!allowDupes) {
        const prev = result.get(name)[0];
        throw new Error(
          `[${p}] Duplicate recipe name "${name}" at lines ${prev.lineNum} and ${i + 1}`
        );
      }
      result.get(name).push({ line, lineNum: i + 1 });
    } else {
      result.set(name, [{ line, lineNum: i + 1 }]);
    }
  }
  return result;
}

function main() {
  console.log("Reading sources…");
  const recipesMap = readRecipeFile(RECIPES_PATH, { allowDupes: false });
  const backupMap = readRecipeFile(BACKUP_PATH, { allowDupes: true });
  const recipesCount = [...recipesMap.values()].reduce((n, a) => n + a.length, 0);
  const backupCount = [...backupMap.values()].reduce((n, a) => n + a.length, 0);
  console.log(`  Recipes.txt: ${recipesCount} recipes (${recipesMap.size} unique names)`);
  console.log(`  Backup.txt:  ${backupCount} recipes (${backupMap.size} unique names)`);

  const survivors = new Map();
  let exactDupes = 0;
  let diffCount = 0;
  let backupOnly = 0;

  for (const [name, [primary]] of recipesMap) {
    const backupEntries = backupMap.get(name) || [];
    for (const b of backupEntries) {
      if (b.line === primary.line) {
        exactDupes++;
      } else {
        diffCount++;
        console.log(`\n--- Diff for "${name}" (Recipes.txt wins) ---`);
        console.log(`  Recipes.txt:${primary.lineNum}: ${primary.line}`);
        console.log(`  Backup.txt:${b.lineNum}: ${b.line}`);
      }
    }
    survivors.set(name, {
      line: primary.line,
      source: "Recipes.txt",
      lineNum: primary.lineNum,
    });
  }
  for (const [name, entries] of backupMap) {
    if (recipesMap.has(name)) continue;
    backupOnly++;
    const [first, ...rest] = entries;
    if (rest.length > 0) {
      console.log(`\nFrom backup only: "${name}" — ${entries.length} variants, keeping line ${first.lineNum}`);
      for (const r of rest) {
        console.log(`  (dropped) Backup.txt:${r.lineNum}: ${r.line}`);
      }
    } else {
      console.log(`\nFrom backup only: "${name}" (Backup.txt:${first.lineNum})`);
    }
    survivors.set(name, {
      line: first.line,
      source: "Backup.txt",
      lineNum: first.lineNum,
    });
  }

  console.log(`\n  Exact duplicates merged: ${exactDupes}`);
  console.log(`  Non-exact name diffs:    ${diffCount}`);
  console.log(`  Added from backup only:  ${backupOnly}`);
  console.log(`  Survivors to parse:      ${survivors.size}`);

  console.log("\nParsing & round-trip-validating…");
  const recipes = [];
  for (const [, info] of survivors) {
    recipes.push(parseLine(info.line, info.source, info.lineNum));
  }

  console.log(`\nAppending ${ONE_OFFS.length} hand-transcribed one-offs…`);
  const slugSet = new Set();
  for (const r of [...recipes, ...ONE_OFFS]) {
    if (slugSet.has(r.slug)) {
      throw new Error(`Duplicate slug "${r.slug}" (name: "${r.name}")`);
    }
    slugSet.add(r.slug);
  }
  recipes.push(...ONE_OFFS);

  recipes.sort((a, b) =>
    a.name.toLowerCase().localeCompare(b.name.toLowerCase())
  );

  fs.mkdirSync(path.dirname(OUT_PATH), { recursive: true });
  fs.writeFileSync(OUT_PATH, JSON.stringify(recipes, null, 2));
  console.log(`\n✓ Wrote ${recipes.length} recipes to ${OUT_PATH}`);
}

main();
