"use strict";

/**
 * Shared evolution pre-evolution inference.
 *
 * Many TCGdex entries are Stage 1/2 Pokémon with a null `evolveFrom`. Since a
 * species' pre-evolution is fixed, we infer it — first from another printing of
 * the same species that DOES carry `evolveFrom` (high confidence), then from a
 * curated evolution map for species absent from that data.
 *
 * Used by fill-evolvefrom.js (to write values back into carddata/*.json) and by
 * pauper-report.js (to build evolution families and the verification page).
 */

// Curated pre-evolution for species that never carry evolveFrom in the data.
// Keyed by the "core" name (owner prefix stripped, " ex"/"Mega " removed); the
// owner prefix is re-applied to the result. Regional forms are keyed in full.
const BASE_PREEVO = {
  Aurorus: "Amaura", Beautifly: "Silcoon", Camerupt: "Numel", Cascoon: "Wurmple",
  Dewgong: "Seel", Diggersby: "Bunnelby", Dragonair: "Dratini", Drapion: "Skorupi",
  Dustox: "Cascoon", Empoleon: "Prinplup", Flygon: "Vibrava", Gengar: "Haunter",
  Gliscor: "Gligar", Gloom: "Oddish", Golduck: "Psyduck", Granbull: "Snubbull",
  Honchkrow: "Murkrow", Linoone: "Zigzagoon", Luxray: "Luxio", Mamoswine: "Piloswine",
  Mismagius: "Misdreavus", Pawmo: "Pawmi", Prinplup: "Piplup", Raticate: "Rattata",
  Silcoon: "Wurmple", Toxtricity: "Toxel", Vileplume: "Gloom", Wigglytuff: "Jigglypuff",
  Victreebel: "Weepinbell", Weepinbell: "Bellsprout", Trevenant: "Phantump",
  Braviary: "Rufflet", Dudunsparce: "Dunsparce", Staraptor: "Staravia", Staravia: "Starly",
  Dugtrio: "Diglett", Exeggutor: "Exeggcute", Vanillish: "Vanillite", Vanilluxe: "Vanillish",
  "Galarian Linoone": "Galarian Zigzagoon", "Galarian Obstagoon": "Galarian Linoone",
};

// Fossil/Restored Pokémon: revived from a Fossil item in the same set, matching
// TCGdex's own convention (e.g. Tyrunt <- "Antique Jaw Fossil"). The item is a
// Trainer, so it roots the family among Pokémon.
const FOSSIL_PREEVO = { Amaura: "Antique Sail Fossil" };

const OWNER_RE = /^((?:Team Rocket's|Erika's|Larry's|Hop's|N's|Cynthia's|Ethan's|Iono's|Marnie's|Misty's|Steven's|Brock's|Arven's|Lillie's)\s)/;

function stripDecorations(name) {
  return name.replace(/\s+ex$/, "").replace(/^Mega\s+/, "").trim();
}

/**
 * Build an inferrer over the full card list (needed for cross-set fill).
 * Returns inferEvolveFrom(card) -> { evolveFrom, source } where source is:
 *   "tcgdex"     — the card already carries it (no inference)
 *   "cross-set"  — filled from another printing of the same species
 *   "fossil"     — Restored Pokémon, from a Fossil item
 *   "inferred"   — from the curated evolution map
 *   "unresolved" — could not determine (evolveFrom is null)
 */
function buildInferrer(allCards) {
  // species name -> {evolveFrom value -> count}, from cards that carry evolveFrom
  const speciesEF = new Map();
  for (const c of allCards) {
    if (c.category === "Pokemon" && c.evolveFrom && !c.evolveFromInferred) {
      if (!speciesEF.has(c.name)) speciesEF.set(c.name, new Map());
      const m = speciesEF.get(c.name);
      m.set(c.evolveFrom, (m.get(c.evolveFrom) || 0) + 1);
    }
  }
  return function inferEvolveFrom(card) {
    if (card.evolveFrom && !card.evolveFromInferred) return { evolveFrom: card.evolveFrom, source: "tcgdex" };
    const name = card.name;
    if (speciesEF.has(name)) {
      const best = [...speciesEF.get(name).entries()].sort((a, b) => b[1] - a[1])[0][0];
      return { evolveFrom: best, source: "cross-set" };
    }
    const core = stripDecorations(name);
    if (FOSSIL_PREEVO[core]) return { evolveFrom: FOSSIL_PREEVO[core], source: "fossil" };
    const owner = (name.match(OWNER_RE) || [""])[0];
    const bare = stripDecorations(name.slice(owner.length));
    const base = BASE_PREEVO[name] || BASE_PREEVO[core] || BASE_PREEVO[bare];
    if (base) {
      const val = owner && !base.startsWith(owner.trim()) ? owner + base : base;
      return { evolveFrom: val, source: "inferred" };
    }
    return { evolveFrom: null, source: "unresolved" };
  };
}

// True for a Stage 1/2 Pokémon that should have an evolveFrom.
function shouldEvolve(card) {
  return card.category === "Pokemon" && (card.stage === "Stage1" || card.stage === "Stage2");
}

module.exports = { BASE_PREEVO, FOSSIL_PREEVO, buildInferrer, shouldEvolve };
