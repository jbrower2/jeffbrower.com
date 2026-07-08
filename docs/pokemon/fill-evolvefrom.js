#!/usr/bin/env node
"use strict";

/**
 * Back-fills missing `evolveFrom` values into the carddata/*.json cache.
 *
 * For every Stage 1/2 Pokémon whose TCGdex record has a null `evolveFrom`, the
 * shared inferrer (evolve-infer.js) determines its pre-evolution and writes it
 * in, tagging the card with `evolveFromInferred: <source>` to record provenance
 * (so original TCGdex values stay distinguishable from filled ones).
 *
 * Non-destructive and idempotent: existing evolveFrom values are never touched,
 * and re-running fills nothing new. After filling, prints a verification of how
 * many Stage 1/2 Pokémon still lack an evolveFrom (should be 0).
 *
 * Usage: node fill-evolvefrom.js
 */

const fs = require("fs");
const path = require("path");
const { buildInferrer, shouldEvolve } = require("./evolve-infer");

const CARDDATA_DIR = path.join(__dirname, "carddata");
const files = fs.readdirSync(CARDDATA_DIR).filter((f) => f.endsWith(".json"));

// Load every set, keeping a handle to its file and parsed data.
const sets = files.map((f) => ({
  file: path.join(CARDDATA_DIR, f),
  data: JSON.parse(fs.readFileSync(path.join(CARDDATA_DIR, f), "utf8")),
}));
const allCards = sets.flatMap((s) => s.data.cards.filter((c) => !c.__missing && !c.__error));

// Build the inferrer from the full card pool (cross-set fill needs all sets).
const infer = buildInferrer(allCards);

const bySource = {};
const filledDetail = [];
let touchedFiles = 0;

for (const s of sets) {
  let changed = false;
  for (const card of s.data.cards) {
    if (card.__missing || card.__error) continue;
    if (!shouldEvolve(card)) continue;
    if (card.evolveFrom) continue; // never overwrite an existing value

    const { evolveFrom, source } = infer(card);
    if (!evolveFrom || source === "unresolved") continue; // leave truly-unknown alone

    card.evolveFrom = evolveFrom;
    card.evolveFromInferred = source;
    changed = true;
    bySource[source] = (bySource[source] || 0) + 1;
    filledDetail.push(`${s.data.tcgdexId} #${card.localId} ${card.name} <- ${evolveFrom} (${source})`);
  }
  if (changed) {
    fs.writeFileSync(s.file, JSON.stringify(s.data, null, 1) + "\n");
    touchedFiles++;
  }
}

console.log(`Filled ${filledDetail.length} card(s) across ${touchedFiles} file(s):`);
for (const [src, n] of Object.entries(bySource)) console.log(`  ${src}: ${n}`);

// ---- Verification: reload from disk and confirm nothing is still missing ----
const reloaded = files.flatMap((f) => {
  const d = JSON.parse(fs.readFileSync(path.join(CARDDATA_DIR, f), "utf8"));
  return d.cards.filter((c) => !c.__missing && !c.__error).map((c) => ({ ...c, _set: d.tcgdexId }));
});
const stillMissing = reloaded.filter((c) => shouldEvolve(c) && !c.evolveFrom);

console.log("");
if (stillMissing.length === 0) {
  const evolvers = reloaded.filter(shouldEvolve).length;
  console.log(`✓ Verified: all ${evolvers} Stage 1/2 Pokémon now have an evolveFrom (0 missing).`);
} else {
  console.log(`✗ ${stillMissing.length} Stage 1/2 Pokémon STILL missing evolveFrom:`);
  for (const c of stillMissing) console.log(`  ${c._set} #${c.localId} ${c.name} (${c.stage})`);
  process.exitCode = 1;
}
