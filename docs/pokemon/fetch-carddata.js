#!/usr/bin/env node
"use strict";

/**
 * Fetches card data (name, text, images, regulation marks) for all Pauper
 * format sets from TCGdex (https://tcgdex.dev) and caches it under carddata/.
 *
 * Idempotent: sets that already have a cache file are skipped. Delete a
 * carddata/<id>.json file to force a re-fetch.
 *
 * Usage: node fetch-carddata.js
 */

const fs = require("fs");
const path = require("path");

// TCGplayer set name -> TCGdex set id
const SET_MAP = {
  "SV05: Temporal Forces": "sv05",
  "SV06: Twilight Masquerade": "sv06",
  "SV: Shrouded Fable": "sv06.5",
  "SV07: Stellar Crown": "sv07",
  "SV08: Surging Sparks": "sv08",
  "SV: Prismatic Evolutions": "sv08.5",
  "SV09: Journey Together": "sv09",
  "SV10: Destined Rivals": "sv10",
  "SV: Black Bolt": "sv10.5b",
  "SV: White Flare": "sv10.5w",
  "ME01: Mega Evolution": "me01",
  "ME02: Phantasmal Flames": "me02",
  "ME: Ascended Heroes": "me02.5",
  "ME03: Perfect Order": "me03",
  "ME04: Chaos Rising": "me04",
  "McDonald's Promos 2024": "2024sv",
  "SV: Scarlet & Violet Promo Cards": "svp",
  "ME: Mega Evolution Promo": "mep",
};

const OUT_DIR = path.join(__dirname, "carddata");
const API = "https://api.tcgdex.net/v2/en";
const CONCURRENCY = 12;
const RETRIES = 4;

async function getJSON(url, attempt = 0) {
  try {
    const res = await fetch(url);
    if (res.status === 404) return null;
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    if (attempt >= RETRIES) throw new Error(`${url}: ${err.message}`);
    await new Promise((r) => setTimeout(r, 500 * 2 ** attempt));
    return getJSON(url, attempt + 1);
  }
}

// Keep only the fields the report needs.
function slim(card) {
  return {
    localId: card.localId,
    name: card.name,
    category: card.category,
    dexId: card.dexId ?? null,
    rarity: card.rarity ?? null,
    regulationMark: card.regulationMark ?? null,
    hp: card.hp ?? null,
    types: card.types ?? null,
    stage: card.stage ?? null,
    suffix: card.suffix ?? null,
    evolveFrom: card.evolveFrom ?? null,
    trainerType: card.trainerType ?? null,
    energyType: card.energyType ?? null,
    effect: card.effect ?? null,
    abilities: card.abilities ?? null,
    attacks: card.attacks ?? null,
    weaknesses: card.weaknesses ?? null,
    retreat: card.retreat ?? null,
    image: card.image ?? null,
  };
}

async function fetchSet(tcgdexId) {
  const outFile = path.join(OUT_DIR, `${tcgdexId}.json`);
  if (fs.existsSync(outFile)) {
    const cached = JSON.parse(fs.readFileSync(outFile, "utf8"));
    console.log(`${tcgdexId}: cached (${cached.cards.length} cards)`);
    return;
  }
  const set = await getJSON(`${API}/sets/${encodeURIComponent(tcgdexId)}`);
  if (!set || !set.cards) throw new Error(`set ${tcgdexId} not found`);

  const briefs = set.cards;
  const cards = new Array(briefs.length);
  let done = 0;
  let failed = 0;
  let cursor = 0;
  async function worker() {
    while (cursor < briefs.length) {
      const i = cursor++;
      const b = briefs[i];
      try {
        const card = await getJSON(`${API}/sets/${encodeURIComponent(tcgdexId)}/${encodeURIComponent(b.localId)}`);
        cards[i] = card ? slim(card) : { localId: b.localId, name: b.name, __missing: true };
      } catch (err) {
        failed++;
        cards[i] = { localId: b.localId, name: b.name, __error: err.message };
      }
      done++;
      if (done % 50 === 0) process.stdout.write(`\r${tcgdexId}: ${done}/${briefs.length}`);
    }
  }
  await Promise.all(Array.from({ length: CONCURRENCY }, worker));
  process.stdout.write(`\r${tcgdexId}: ${done}/${briefs.length} fetched, ${failed} failed\n`);

  fs.writeFileSync(
    outFile,
    JSON.stringify({ tcgdexId, setName: set.name, fetched: new Date().toISOString(), cards }, null, 1)
  );
}

(async () => {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  for (const [tcgplayerName, tcgdexId] of Object.entries(SET_MAP)) {
    try {
      await fetchSet(tcgdexId);
    } catch (err) {
      console.error(`FAILED ${tcgplayerName} (${tcgdexId}): ${err.message}`);
      process.exitCode = 1;
    }
  }
  console.log("done");
})();
