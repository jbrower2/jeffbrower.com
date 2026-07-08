#!/usr/bin/env node
"use strict";

/**
 * Backfills national Pokédex numbers (`dexId`) into carddata/*.json.
 *
 * The original fetch didn't cache dexId. This fetches one representative card
 * per unique Pokémon species name from TCGdex (dexId is constant per species),
 * then stamps `dexId` onto every matching Pokémon card. Non-destructive and
 * idempotent: existing fields (incl. filled evolveFrom) are untouched, and
 * cards that already carry dexId are skipped.
 *
 * Usage: node fetch-dexid.js
 */

const fs = require("fs");
const path = require("path");

const API = "https://api.tcgdex.net/v2/en";
const CARDDATA_DIR = path.join(__dirname, "carddata");
const CONCURRENCY = 12;
const RETRIES = 4;

// National Pokédex numbers for species TCGdex omits dexId on entirely. Keyed by
// the base species (owner / regional / Mega / ex decorations stripped).
const DEX_FALLBACK = {
  Oddish: 43, Gloom: 44, Vileplume: 45, Bellsprout: 69, Weepinbell: 70, Victreebel: 71,
  Tangela: 114, Kangaskhan: 115, Diglett: 50, Dugtrio: 51, Exeggcute: 102, Exeggutor: 103,
  Voltorb: 100, Dratini: 147, Dragonair: 148, Dragonite: 149, Hitmontop: 237, Entei: 244,
  Wurmple: 265, Silcoon: 266, Beautifly: 267, Cascoon: 268, Dustox: 269, Zigzagoon: 263,
  Linoone: 264, Obstagoon: 862, Camerupt: 323, Zangoose: 335, Regice: 378, Registeel: 379,
  Mismagius: 429, Honchkrow: 430, Froslass: 478, Audino: 531, Scrafty: 560, Vanillite: 582,
  Vanillish: 583, Vanilluxe: 584, Eelektross: 604, Stunfisk: 618, Rufflet: 627, Braviary: 628,
  Mandibuzz: 630, Starly: 396, Staravia: 397, Staraptor: 398, Dunsparce: 206, Azumarill: 184,
  Phantump: 708, Trevenant: 709, Carbink: 703, Hawlucha: 701, Hoopa: 720, Komala: 775,
  Togedemaru: 777, Pincurchin: 871, Dudunsparce: 982, Glastrier: 896, Spectrier: 897,
};
const OWNER_RE = /^(?:Team Rocket's|Erika's|Larry's|Hop's|N's|Cynthia's|Ethan's|Iono's|Marnie's|Misty's|Steven's|Brock's|Arven's|Lillie's)\s/;
const REGION_RE = /^(?:Galarian|Alolan|Hisuian|Paldean)\s/;
const baseSpecies = (name) => name.replace(/\s+ex$/, "").replace(/^Mega\s+/, "").replace(OWNER_RE, "").replace(REGION_RE, "").trim();

async function getJSON(url, attempt = 0) {
  try {
    const res = await fetch(url);
    if (res.status === 404) return null;
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    if (attempt >= RETRIES) throw err;
    await new Promise((r) => setTimeout(r, 500 * 2 ** attempt));
    return getJSON(url, attempt + 1);
  }
}

(async () => {
  const files = fs.readdirSync(CARDDATA_DIR).filter((f) => f.endsWith(".json"));
  const sets = files.map((f) => ({
    file: path.join(CARDDATA_DIR, f),
    data: JSON.parse(fs.readFileSync(path.join(CARDDATA_DIR, f), "utf8")),
  }));

  // Seed name -> dexId from any card that already carries it; collect ALL
  // printings of the rest (TCGdex omits dexId on some individual printings, so
  // we must try each until one yields it).
  const nameToDex = new Map();
  const printingsByName = new Map(); // name -> [{tcgdexId, localId}, ...]
  for (const s of sets) {
    for (const c of s.data.cards) {
      if (c.__missing || c.__error || c.category !== "Pokemon") continue;
      if (Array.isArray(c.dexId) && c.dexId.length) { nameToDex.set(c.name, c.dexId); continue; }
      if (!printingsByName.has(c.name)) printingsByName.set(c.name, []);
      printingsByName.get(c.name).push({ tcgdexId: s.data.tcgdexId, localId: c.localId });
    }
  }
  for (const n of nameToDex.keys()) printingsByName.delete(n);

  // For each remaining species, try its printings until one returns a dexId.
  const names = [...printingsByName.keys()];
  let cursor = 0, done = 0;
  async function worker() {
    while (cursor < names.length) {
      const name = names[cursor++];
      let dex = null;
      for (const { tcgdexId, localId } of printingsByName.get(name)) {
        try {
          const card = await getJSON(`${API}/sets/${encodeURIComponent(tcgdexId)}/${encodeURIComponent(localId)}`);
          if (Array.isArray(card && card.dexId) && card.dexId.length) { dex = card.dexId; break; }
        } catch (err) {
          /* try the next printing */
        }
      }
      nameToDex.set(name, dex);
      if (++done % 25 === 0) process.stdout.write(`\rresolved ${done}/${names.length}`);
    }
  }
  await Promise.all(Array.from({ length: CONCURRENCY }, worker));
  process.stdout.write(`\rresolved ${done}/${names.length}\n`);

  // Fallback for species TCGdex has no dexId for anywhere: derive from the base
  // species' national dex number.
  let fromFallback = 0;
  for (const [name, dex] of nameToDex) {
    if (dex) continue;
    const fb = DEX_FALLBACK[baseSpecies(name)];
    if (fb) { nameToDex.set(name, [fb]); fromFallback++; }
  }
  if (fromFallback) console.log(`Applied dex fallback for ${fromFallback} species.`);

  // Stamp dexId onto every Pokémon card that lacks it; write changed files.
  let stamped = 0, touched = 0;
  for (const s of sets) {
    let changed = false;
    for (const c of s.data.cards) {
      if (c.__missing || c.__error || c.category !== "Pokemon") continue;
      if (Array.isArray(c.dexId) && c.dexId.length) continue;
      const dex = nameToDex.get(c.name);
      if (dex) { c.dexId = dex; changed = true; stamped++; }
    }
    if (changed) { fs.writeFileSync(s.file, JSON.stringify(s.data, null, 1) + "\n"); touched++; }
  }

  const missing = [...nameToDex].filter(([, v]) => !v).map(([n]) => n);
  console.log(`Stamped dexId on ${stamped} cards across ${touched} file(s).`);
  console.log(`Unique Pokémon species: ${nameToDex.size}; without dexId: ${missing.length}${missing.length ? " -> " + missing.slice(0, 20).join(", ") : ""}`);
})();
