// Convert todo/Cookie Recipes _ Girl Scout Cookies.html into a markdown
// summary, then compare each extracted recipe against the live recipes in
// src/data/index.js to confirm coverage.
//
// Output:
//   scripts/girl-scout-html.md       — one markdown section per HTML recipe
//   scripts/girl-scout-compare.md    — match report (HTML title → DB slug)

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(__dirname, "..");
const HTML_PATH = path.join(
  REPO,
  "todo",
  "Cookie Recipes _ Girl Scout Cookies.html",
);
const INDEX_PATH = path.join(REPO, "src", "data", "index.js");
const OUT_MD = path.join(__dirname, "girl-scout-html.md");
const OUT_COMPARE = path.join(__dirname, "girl-scout-compare.md");

const html = fs.readFileSync(HTML_PATH, "utf8");
const indexSrc = fs.readFileSync(INDEX_PATH, "utf8");

function decodeEntities(s) {
  return s
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#x27;/g, "'")
    .replace(/&#39;/g, "'")
    .replace(/&mdash;/g, "—")
    .replace(/&ndash;/g, "–")
    .replace(/&hellip;/g, "…")
    .replace(/&#x([0-9a-fA-F]+);/g, (_, h) =>
      String.fromCodePoint(parseInt(h, 16)),
    )
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(parseInt(d, 10)));
}

function stripTags(s) {
  return decodeEntities(s.replace(/<[^>]+>/g, "")).replace(/\s+/g, " ").trim();
}

// Find every <h4>...<b>TITLE</b>...</h4> and slice content between successive
// h4 tags. Each slice is one recipe.
const h4Indices = [];
const h4Re = /<h4[^>]*>[\s\S]*?<\/h4>/g;
let m;
while ((m = h4Re.exec(html)) !== null) {
  h4Indices.push({ start: m.index, end: m.index + m[0].length, raw: m[0] });
}

const recipes = [];
for (let i = 0; i < h4Indices.length; i++) {
  const head = h4Indices[i];
  const next = h4Indices[i + 1];
  // Strip the <h4> tags themselves, then strip remaining inline tags
  // (<b>, <i>) — titles like "<b>Thin Mints</b>® <b>Cupcakes</b>" need the
  // whole inner content, not just the first <b>...</b> chunk.
  const inner = head.raw.replace(/^<h4[^>]*>/, "").replace(/<\/h4>$/, "");
  const title = stripTags(inner);
  if (!title) continue;
  const bodyHtml = html.slice(head.end, next ? next.start : html.length);

  // Pull each <p>...</p> and each <ul>...</ul> block in order.
  const blocks = [];
  const blockRe = /<(p|ul)[^>]*>[\s\S]*?<\/\1>/gi;
  let bm;
  while ((bm = blockRe.exec(bodyHtml)) !== null) {
    blocks.push(bm[0]);
  }

  const sections = [];
  for (const blk of blocks) {
    if (/^<ul/i.test(blk)) {
      const items = [];
      const liRe = /<li[^>]*>([\s\S]*?)<\/li>/gi;
      let li;
      while ((li = liRe.exec(blk)) !== null) {
        items.push(stripTags(li[1]));
      }
      sections.push({ kind: "ul", items });
    } else {
      sections.push({ kind: "p", text: stripTags(blk) });
    }
  }

  recipes.push({ title, sections });
}

// Render markdown summary.
const mdParts = [`# Cookie Recipes (extracted from HTML)\n`];
for (const r of recipes) {
  mdParts.push(`## ${r.title}\n`);
  for (const s of r.sections) {
    if (s.kind === "p") {
      if (s.text) mdParts.push(`${s.text}\n`);
    } else {
      for (const it of s.items) mdParts.push(`- ${it}`);
      mdParts.push("");
    }
  }
}
fs.writeFileSync(OUT_MD, mdParts.join("\n") + "\n");

// Parse slugs + categories from index.js to find Girl-Scout-Cookies recipes.
const addRecipeRe =
  /addRecipe\(\s*"([^"]+)"\s*,\s*\[([\s\S]*?)\]\s*(?:,\s*(true|false)\s*)?,?\s*\)/g;
const dbRecipes = [];
let am;
while ((am = addRecipeRe.exec(indexSrc)) !== null) {
  const slug = am[1];
  const cats = am[2]
    .split(",")
    .map((c) => c.trim().replace(/^"|"$/g, ""))
    .filter(Boolean);
  dbRecipes.push({ slug, cats });
}
const gsSlugs = dbRecipes
  .filter((r) => r.cats.includes("Collections/Girl Scout Cookies"))
  .map((r) => r.slug);

function normalize(s) {
  return s
    .toLowerCase()
    .replace(/['']/g, "")
    .replace(/®|™|©/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

// Manual aliases for HTML titles whose slug doesn't normalize directly.
const ALIASES = {
  "thin-mints-cupcakes": ["thin-mints-cupcakes"],
  "thin-mints-popcorn": ["thin-mints-popcorn"],
  "thin-mints-white-chocolate-biscotti": ["thin-mints-white-chocolate-biscotti"],
  "smores-frosted-crispy-bars": ["smores-frosted-crispy-bars"],
  "smores-ice-cream": ["smores-ice-cream"],
  "smores-peanut-butter-pudgy-pie": ["smores-peanut-butter-pudgy-pie"],
  "smores-summertime-cheesecake": ["smores-summertime-cheesecake"],
};

const slugSet = new Set(dbRecipes.map((r) => r.slug));
const gsSet = new Set(gsSlugs);

const rows = [];
const missing = [];
for (const r of recipes) {
  const norm = normalize(r.title);
  const candidates = (ALIASES[norm] || []).concat([norm]);
  let matchedSlug = null;
  for (const c of candidates) {
    if (slugSet.has(c)) {
      matchedSlug = c;
      break;
    }
  }
  // Loose substring fallback against Girl Scout collection slugs.
  if (!matchedSlug) {
    const tokens = norm.split("-").filter((t) => t.length >= 4);
    const hit = gsSlugs.find((s) =>
      tokens.every((t) => s.includes(t)),
    );
    if (hit) matchedSlug = hit;
  }
  rows.push({ title: r.title, norm, slug: matchedSlug });
  if (!matchedSlug) missing.push(r.title);
}

const cmpParts = [
  `# Girl Scout HTML → DB Comparison\n`,
  `HTML recipes found: **${recipes.length}**\n`,
  `DB recipes tagged \`Collections/Girl Scout Cookies\`: **${gsSlugs.length}**\n`,
  `\n## Per-recipe match\n`,
  `| HTML title | Matched DB slug | In GS collection? |`,
  `| --- | --- | --- |`,
];
for (const row of rows) {
  const inCol = row.slug && gsSet.has(row.slug) ? "yes" : "no";
  cmpParts.push(
    `| ${row.title} | ${row.slug ?? "**missing**"} | ${row.slug ? inCol : "—"} |`,
  );
}
cmpParts.push("");
if (missing.length === 0) {
  cmpParts.push(`## Result\n`);
  cmpParts.push(
    `All ${recipes.length} HTML recipes have a corresponding entry in the DB.`,
  );
  const allInCollection = rows.every((r) => r.slug && gsSet.has(r.slug));
  if (allInCollection) {
    cmpParts.push(
      `All matched entries are tagged with \`Collections/Girl Scout Cookies\`.`,
    );
  } else {
    cmpParts.push(`Some matched entries are NOT in the Girl Scout collection.`);
  }
} else {
  cmpParts.push(`## Missing\n`);
  for (const t of missing) cmpParts.push(`- ${t}`);
}

// Also list DB-only slugs (in collection but not in HTML).
const matchedSlugSet = new Set(rows.map((r) => r.slug).filter(Boolean));
const dbOnly = gsSlugs.filter((s) => !matchedSlugSet.has(s));
cmpParts.push(`\n## DB recipes in Girl Scout collection without an HTML match\n`);
if (dbOnly.length === 0) cmpParts.push(`(none)`);
else for (const s of dbOnly) cmpParts.push(`- ${s}`);

fs.writeFileSync(OUT_COMPARE, cmpParts.join("\n") + "\n");

console.log(`Wrote ${OUT_MD}`);
console.log(`Wrote ${OUT_COMPARE}`);
console.log(`HTML recipes: ${recipes.length}`);
console.log(`GS collection: ${gsSlugs.length}`);
console.log(`Unmatched: ${missing.length}`);
