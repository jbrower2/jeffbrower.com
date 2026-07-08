#!/usr/bin/env node
"use strict";

/**
 * Pokémon TCG "Pauper" format analyzer.
 *
 * Reads TCGplayer pricing export (pricing.csv), restricts to the sets that can
 * contain regulation-mark "H" (or above) cards (Standard 2026-27), and groups
 * price records in two levels:
 *
 *   1. printings — records grouped by collector number (e.g. 110/086); covers
 *      holo / reverse holo / pattern-variant / stamped versions of one printing
 *   2. cards — printings grouped by card name, so alternate-art reprints
 *      (Illustration Rare, Ultra Rare, ...) merge into the base card
 *
 * Name grouping is validated against TCGdex card data (fetch-carddata.js):
 * matched printings use the official card name, and printings only stay in the
 * same group when their card text (abilities/attacks/effect) is identical —
 * same-name-but-different-text cards are split into separate groups.
 *
 * A card qualifies at a price cutoff if ANY of its versions has a "Near Mint"
 * condition TCG Market Price at or below the cutoff.
 *
 * Outputs:
 *   index.html       — per-set legality stats at each cutoff
 *   cards/<slug>.html — per-set drill-down: every card with image, text,
 *                       versions, prices, and cheapest-tier badge
 *   report-data.json  — machine-readable data
 *
 * Usage: node pauper-report.js [path/to/pricing.csv]
 */

const fs = require("fs");
const path = require("path");
const { buildInferrer, shouldEvolve } = require("./evolve-infer");

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

// Legality cutoffs to compare: a card qualifies at a cutoff if any Near Mint
// version's market price is at or below it.
const PRICE_CAPS_CENTS = [50, 100];
const zeroByCap = () => Object.fromEntries(PRICE_CAPS_CENTS.map((c) => [c, 0]));
const fmtCap = (c) => (c >= 100 ? `$${(c / 100).toFixed(2)}` : `${c}¢`);

// Sets that can contain regulation mark "H" or above cards (Standard 2026-27),
// in rough release order; promo/special sets grouped at the end.
// Values are the matching TCGdex set ids (see fetch-carddata.js).
const TARGET_SETS = new Map([
  ["SV05: Temporal Forces", "sv05"],
  ["SV06: Twilight Masquerade", "sv06"],
  ["SV: Shrouded Fable", "sv06.5"],
  ["SV07: Stellar Crown", "sv07"],
  ["SV08: Surging Sparks", "sv08"],
  ["SV: Prismatic Evolutions", "sv08.5"],
  ["SV09: Journey Together", "sv09"],
  ["SV10: Destined Rivals", "sv10"],
  ["SV: Black Bolt", "sv10.5b"],
  ["SV: White Flare", "sv10.5w"],
  ["ME01: Mega Evolution", "me01"],
  ["ME02: Phantasmal Flames", "me02"],
  ["ME: Ascended Heroes", "me02.5"],
  ["ME03: Perfect Order", "me03"],
  ["ME04: Chaos Rising", "me04"],
  ["McDonald's Promos 2024", "2024sv"],
  ["SV: Scarlet & Violet Promo Cards", "svp"],
  ["ME: Mega Evolution Promo", "mep"],
]);

// The set's "special" playable rarity — "ex" cards are printed as Double Rare
// in both the Scarlet & Violet and Mega Evolution eras.
const SPECIAL_RARITY = "Double Rare";

// Rarity rank order: also used to pick a merged card's rarity (the lowest,
// i.e. most-common, rarity among its printings is the "base" printing).
// Rarities encountered in the data but missing here are appended alphabetically.
const RARITY_ORDER = [
  "Common",
  "Uncommon",
  "Rare",
  "Holo Rare",
  "Double Rare",
  "ACE SPEC Rare",
  "Radiant Rare",
  "Mega Attack Rare",
  "Black White Rare",
  "Illustration Rare",
  "Ultra Rare",
  "Special Illustration Rare",
  "Hyper Rare",
  "Mega Hyper Rare",
  "Promo",
];
const rarityRank = (r) => {
  const i = RARITY_ORDER.indexOf(r);
  return i === -1 ? RARITY_ORDER.length : i;
};

// The 2026-2027 Standard pool is cards with regulation mark "H" or later.
const MIN_REG_MARK = "H";

// TCGdex has no regulation marks for the McDonald's Promos 2024 set; supply them
// here (keyed by collector number) so the H+ ones aren't wrongly dropped. Only
// #011 (Roaring Moon) and #015 (Drampa) are H+; the rest are D-G.
const MCDONALDS_REGMARKS = {
  1: "D", 2: "G", 3: "G", 4: "E", 5: "D", 6: "F", 7: "D", 8: "G",
  9: "E", 10: "G", 11: "H", 12: "G", 13: "E", 14: "D", 15: "H",
};

// True if a report card belongs to the 2026-2027 Standard pool (reg mark H+).
// Basic energies carry no mark but are always legal.
function inStandard(card, setName) {
  const t = card.tcgdex;
  if (t && t.category === "Energy" && !t.regulationMark) return true;
  let mark = card.regulationMark;
  if (!mark && setName === "McDonald's Promos 2024") mark = MCDONALDS_REGMARKS[parseInt(card.printings[0].number, 10)] || null;
  return typeof mark === "string" && mark >= MIN_REG_MARK;
}

// ---------------------------------------------------------------------------
// CSV parsing (RFC 4180: quoted fields, escaped quotes, newlines in fields)
// ---------------------------------------------------------------------------

function parseCSV(text) {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;
  let rowHasContent = false; // distinguishes a blank line from a quoted empty field ("")
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        field += c;
      }
    } else if (c === '"') {
      inQuotes = true;
      rowHasContent = true;
    } else if (c === ",") {
      row.push(field);
      field = "";
      rowHasContent = true;
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      if (rowHasContent || row.length > 0 || field !== "") {
        row.push(field);
        rows.push(row);
      }
      row = [];
      field = "";
      rowHasContent = false;
    } else {
      field += c;
      rowHasContent = true;
    }
  }
  if (rowHasContent || row.length > 0 || field !== "") {
    row.push(field);
    rows.push(row);
  }
  return rows;
}

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

// Parse a price string into integer cents, or null if absent/invalid.
function priceCents(s) {
  if (!s) return null;
  const cleaned = s.replace(/[$,]/g, "").trim();
  if (!cleaned) return null; // whitespace-only must not parse as $0.00
  const v = Number(cleaned);
  if (!Number.isFinite(v)) return null;
  return Math.round(v * 100);
}

// Printing identity: collector number, uppercased with whitespace removed so
// that "SVP 200" and "SVP200" group together.
function normalizeNumber(num) {
  return num.trim().toUpperCase().replace(/\s+/g, "");
}

// Key used to match a TCGplayer collector number against a TCGdex localId:
// numerator only, letter prefix ("SVP200" -> "200") and leading zeros dropped,
// lowercased ("065a" -> "65a").
function numberKey(normNumber) {
  let n = normNumber.split("/")[0];
  n = n.replace(/^[A-Z]+(?=\d)/, "");
  n = n.replace(/^0+(?=.)/, "");
  return n.toLowerCase();
}

// Strip variant qualifiers and the (inconsistently present) collector number
// from a TCGplayer product name: "Banette - 091/217 (Dusk Ball)" -> "Banette".
function cleanProductName(name, normNumber) {
  let n = name.trim();
  let prev;
  do {
    prev = n;
    n = n.replace(/\s*\[[^\]]*\]\s*$/, ""); // "[Staff]"
    n = n.replace(/\s*\([^()]*\)\s*$/, ""); // "(Poke Ball Pattern)", "(Prerelease)"
  } while (n !== prev);
  const m = n.match(/^(.*\S)\s+-\s+(\S+)$/);
  if (m) {
    const cand = normalizeNumber(m[2]);
    if (
      cand === normNumber ||
      numberKey(cand) === numberKey(normNumber) ||
      cand === normNumber.split("/")[0]
    ) {
      n = m[1].trim();
    }
  }
  return n;
}

// Text signature of a TCGdex card: two cards are "the same card" only if this
// matches (name is checked separately). Field order is fixed for stability.
// `suffix` and `evolveFrom` are deliberately excluded: both are redundant with
// name/stage and TCGdex is inconsistent about them across alt-art entries
// (e.g. suffix "ex" vs null, evolveFrom typos), which caused false splits.
function textSignature(card) {
  const clean = (v) => {
    if (v == null) return null;
    if (typeof v === "string") return v.replace(/\s+/g, " ").trim();
    if (Array.isArray(v)) return v.map(clean);
    if (typeof v === "object") return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, clean(x)]));
    return v;
  };
  return JSON.stringify(clean({
    category: card.category ?? null,
    hp: card.hp ?? null,
    types: card.types ?? null,
    stage: card.stage ?? null,
    trainerType: card.trainerType ?? null,
    energyType: card.energyType ?? null,
    effect: card.effect ?? null,
    abilities: card.abilities ?? null,
    attacks: (card.attacks ?? []).map((a) => ({
      cost: a.cost ?? null,
      name: a.name ?? null,
      effect: a.effect ?? null,
      damage: a.damage == null ? null : String(a.damage), // "220" vs 220
    })),
  }));
}

function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function setSlug(setName) {
  return setName.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

// ---------------------------------------------------------------------------
// Load pricing CSV -> printings grouped by (set, collector number)
// ---------------------------------------------------------------------------

const csvPath = process.argv[2] || path.join(__dirname, "pricing.csv");
const rows = parseCSV(fs.readFileSync(csvPath, "utf8"));
const header = rows[0];
const col = {};
header.forEach((h, i) => (col[h] = i));
for (const required of ["Set Name", "Product Name", "Number", "Rarity", "Condition", "TCG Market Price"]) {
  if (!(required in col)) throw new Error(`Missing expected CSV column: ${required}`);
}

/** @type {Map<string, Map<string, object>>} set -> normNumber -> printing */
const printingsBySet = new Map();
for (const name of TARGET_SETS.keys()) printingsBySet.set(name, new Map());

const warnings = [];
let skippedNoNumber = 0;
let skippedCodeCards = 0;

for (let i = 1; i < rows.length; i++) {
  const r = rows[i];
  const setName = r[col["Set Name"]];
  if (!printingsBySet.has(setName)) continue;

  const rarity = r[col["Rarity"]];
  const number = r[col["Number"]];
  const condition = r[col["Condition"]];
  const product = r[col["Product Name"]];

  if (rarity === "Code Card") {
    skippedCodeCards++;
    continue;
  }
  if (!number.trim()) {
    // Sealed products (booster boxes, ETBs, ...) have no collector number.
    skippedNoNumber++;
    if (condition !== "Unopened" && rarity !== "") {
      warnings.push(`Row ${i}: dropped no-number row that looks like a card: ${setName} | ${product} | ${rarity} | ${condition}`);
    }
    continue;
  }

  const key = normalizeNumber(number);
  const group = printingsBySet.get(setName);
  let printing = group.get(key);
  if (!printing) {
    printing = {
      number: number.trim(),
      normNumber: key,
      products: new Map(), // product name -> rarity
      nmVersions: [], // one entry per Near Mint row = one version of this printing
    };
    group.set(key, printing);
  }
  if (!printing.products.has(product)) printing.products.set(product, rarity);

  if (condition.startsWith("Near Mint")) {
    printing.nmVersions.push({
      product,
      condition,
      priceCents: priceCents(r[col["TCG Market Price"]]),
    });
  }
}

// ---------------------------------------------------------------------------
// Load TCGdex card data (optional cache produced by fetch-carddata.js)
// ---------------------------------------------------------------------------

const CARDDATA_DIR = path.join(__dirname, "carddata");
/** @type {Map<string, Map<string, object>>} tcgdex set id -> numberKey -> card */
const tcgdexBySet = new Map();
/** @type {Array<object>} every TCGdex card across all sets (with _setName/_tcgdexId) */
const allTcgdexCards = [];
for (const [setName, tcgdexId] of TARGET_SETS) {
  const file = path.join(CARDDATA_DIR, `${tcgdexId}.json`);
  if (!fs.existsSync(file)) {
    warnings.push(`No TCGdex card data for ${setName} (${file} missing) — name grouping is unvalidated there`);
    continue;
  }
  const data = JSON.parse(fs.readFileSync(file, "utf8"));
  const byKey = new Map();
  for (const card of data.cards) {
    if (card.__missing || card.__error) continue;
    const key = card.localId.toLowerCase().replace(/^0+(?=.)/, "");
    if (byKey.has(key)) warnings.push(`TCGdex ${tcgdexId}: duplicate localId key ${key}`);
    byKey.set(key, card);
    allTcgdexCards.push({ ...card, _setName: setName, _tcgdexId: tcgdexId });
  }
  tcgdexBySet.set(tcgdexId, byKey);
}

// ---------------------------------------------------------------------------
// Evolution: resolve missing evolveFrom links (see evolve-infer.js)
// ---------------------------------------------------------------------------
//
// Many TCGdex entries are Stage 1/2 Pokémon with a null evolveFrom. Cards that
// fill-evolvefrom.js has back-filled carry an `evolveFromInferred` marker naming
// the source; any card still lacking evolveFrom is inferred on the fly here so
// evolution families link even before the cache is written. The verification
// page (evolution-check.html) lists every non-original value for human review.

const inferEvolveFrom = buildInferrer(allTcgdexCards);

const evoInferences = new Map(); // species name -> audit record (non-original values)
const stillMissing = []; // Stage 1/2 Pokémon with no derivable evolveFrom
for (const c of allTcgdexCards) {
  if (!shouldEvolve(c)) continue;
  let evolveFrom, source;
  if (c.evolveFromInferred) {
    evolveFrom = c.evolveFrom;
    source = c.evolveFromInferred;
  } else if (c.evolveFrom) {
    continue; // original TCGdex value — not part of the audit
  } else {
    const inf = inferEvolveFrom(c);
    evolveFrom = inf.evolveFrom;
    source = inf.source;
  }
  if (!evolveFrom || source === "unresolved") {
    stillMissing.push(c);
    continue;
  }
  let rec = evoInferences.get(c.name);
  if (!rec) {
    rec = { name: c.name, stage: c.stage, type: (c.types || [])[0] || null, evolveFrom, source, printings: [] };
    evoInferences.set(c.name, rec);
  }
  rec.printings.push({ setName: c._setName, tcgdexId: c._tcgdexId, localId: c.localId, image: c.image || null });
  if (!rec.image && c.image) rec.image = c.image;
}
// Fall back to any printing of the same species so every entry shows art.
const imageByName = new Map();
for (const c of allTcgdexCards) if (c.image && !imageByName.has(c.name)) imageByName.set(c.name, c.image);
for (const rec of evoInferences.values()) {
  if (!rec.image) rec.image = rec.printings.find((p) => p.image)?.image || imageByName.get(rec.name) || null;
}
if (stillMissing.length) {
  warnings.push(`${stillMissing.length} Stage 1/2 card(s) still missing evolveFrom: ${[...new Set(stillMissing.map((c) => c.name))].join(", ")}`);
}

// ---------------------------------------------------------------------------
// Resolve printings, then group printings into cards by (name, text)
// ---------------------------------------------------------------------------

// A few printings contain products with conflicting rarities (e.g. a pattern
// variant tagged differently). Prefer the rarity of the "base" product — the
// one with no parenthetical qualifier — falling back to the shortest name.
function resolvePrinting(printing) {
  const entries = [...printing.products.entries()];
  const base = entries.filter(([name]) => !name.includes("("));
  const pool = base.length > 0 ? base : entries;
  pool.sort((a, b) => a[0].length - b[0].length || a[0].localeCompare(b[0]));
  const rarity = pool[0][1] || "(none)";
  const allRarities = new Set(entries.map(([, r]) => r));
  if (allRarities.size > 1) {
    warnings.push(
      `Rarity conflict for #${printing.number} (${entries.map(([n, r]) => `${n}=${r}`).join("; ")}) -> using "${rarity}"`
    );
  }
  return { baseProduct: pool[0][0], rarity };
}

const setStats = [];
const validationTotals = { verified: 0, partial: 0, unmatched: 0, split: 0, nameMismatches: 0 };
let regExcluded = 0; // report cards dropped for being below regulation mark H

for (const [setName, tcgdexId] of TARGET_SETS) {
  const tcgdex = tcgdexBySet.get(tcgdexId) || new Map();
  const printings = [...printingsBySet.get(setName).values()].sort((a, b) =>
    a.normNumber.localeCompare(b.normNumber, undefined, { numeric: true })
  );

  const nameMismatches = [];

  // A TCGdex localId key may be claimed by two different TCGplayer printings:
  // e.g. Shrouded Fable has both "001/064" (a real set card) and a bare "1"
  // (a deck-exclusive energy TCGdex files elsewhere), and the SVP promo set
  // has both "022" (a real promo) and "022/167" (a stamped card from another
  // set). On collision, the printing whose number format (slash vs bare)
  // matches the majority of the set's printings wins the match — that format
  // is the one TCGdex's localIds correspond to.
  const slashCount = printings.filter((p) => p.normNumber.includes("/")).length;
  const majoritySlash = slashCount * 2 >= printings.length;
  const keyClaims = new Map();
  for (const p of printings) {
    const k = numberKey(p.normNumber);
    if (!keyClaims.has(k)) keyClaims.set(k, []);
    keyClaims.get(k).push(p);
  }
  function tcgdexFor(p) {
    const k = numberKey(p.normNumber);
    const claimants = keyClaims.get(k);
    if (claimants.length > 1 && p.normNumber.includes("/") !== majoritySlash) {
      const winner = claimants.find((q) => q.normNumber.includes("/") === majoritySlash);
      if (winner) {
        warnings.push(`${setName}: #${p.number} left unmatched — TCGdex key "${k}" belongs to #${winner.number}`);
        return null;
      }
    }
    return tcgdex.get(k) || null;
  }

  // Annotate each printing with its resolved rarity, TCGdex match, and name.
  for (const p of printings) {
    const { baseProduct, rarity } = resolvePrinting(p);
    p.rarity = rarity;
    p.rank = rarityRank(rarity);
    const prices = p.nmVersions.map((v) => v.priceCents).filter((x) => x !== null);
    p.minPriceCents = prices.length ? Math.min(...prices) : null;
    p.tcgdex = tcgdexFor(p);
    p.sig = p.tcgdex ? textSignature(p.tcgdex) : null;
    const cleaned = cleanProductName(baseProduct, p.normNumber);
    p.cardName = p.tcgdex ? p.tcgdex.name : cleaned;
    if (p.tcgdex && cleaned.toLowerCase() !== p.tcgdex.name.toLowerCase()) {
      nameMismatches.push(`#${p.number}: TCGplayer "${cleaned}" vs TCGdex "${p.tcgdex.name}"`);
    }
  }

  // Group printings by card name.
  const byName = new Map();
  for (const p of printings) {
    if (!byName.has(p.cardName)) byName.set(p.cardName, []);
    byName.get(p.cardName).push(p);
  }

  // Within a name group, split by text signature: printings only merge if
  // their card text is identical. Unmatched printings (no TCGdex data) attach
  // to the lowest-rarity subgroup.
  let cards = [];
  for (const [cardName, group] of byName) {
    const sigs = [...new Set(group.map((p) => p.sig).filter((s) => s !== null))];
    let subgroups;
    if (sigs.length <= 1) {
      subgroups = [group];
    } else {
      validationTotals.split++;
      const bySig = new Map(sigs.map((s) => [s, []]));
      const unmatched = [];
      for (const p of group) (p.sig ? bySig.get(p.sig) : unmatched).push(p);
      subgroups = [...bySig.values()];
      // attach unmatched printings to the subgroup with the lowest base rarity
      if (unmatched.length) {
        subgroups.sort((a, b) => Math.min(...a.map((p) => p.rank)) - Math.min(...b.map((p) => p.rank)));
        subgroups[0].push(...unmatched);
      }
    }

    for (const sub of subgroups) {
      sub.sort((a, b) => a.normNumber.localeCompare(b.normNumber, undefined, { numeric: true }));
      const matched = sub.filter((p) => p.tcgdex);
      const status =
        matched.length === sub.length ? "verified" : matched.length > 0 ? "partial" : "unmatched";
      validationTotals[status]++;
      const minPrices = sub.map((p) => p.minPriceCents).filter((x) => x !== null);
      const minPriceCents = minPrices.length ? Math.min(...minPrices) : null;
      const legalAt = {};
      for (const cap of PRICE_CAPS_CENTS) legalAt[cap] = minPriceCents !== null && minPriceCents <= cap;
      const basePrinting = [...sub].sort((a, b) => a.rank - b.rank)[0];
      const ref = matched[0] ? matched[0].tcgdex : null;
      cards.push({
        name: cardName,
        displayName: subgroups.length > 1 ? `${cardName} (#${sub[0].number})` : cardName,
        rarity: basePrinting.rarity,
        printings: sub,
        versions: sub.reduce((n, p) => n + p.nmVersions.length, 0),
        minPriceCents,
        legalAt,
        status,
        split: subgroups.length > 1,
        tcgdex: ref,
        regulationMark: ref ? ref.regulationMark : null,
        image: (matched.find((p) => p.tcgdex.image) || { tcgdex: {} }).tcgdex.image || null,
      });
    }
  }
  cards.sort((a, b) => a.printings[0].normNumber.localeCompare(b.printings[0].normNumber, undefined, { numeric: true }));

  validationTotals.nameMismatches += nameMismatches.length;

  // Restrict to the Standard pool: only regulation mark H or later.
  const excludedByReg = cards.length;
  cards = cards.filter((c) => inStandard(c, setName));
  regExcluded += excludedByReg - cards.length;

  const byRarity = new Map();
  for (const c of cards) {
    let tally = byRarity.get(c.rarity);
    if (!tally) byRarity.set(c.rarity, (tally = { total: 0, legal: zeroByCap() }));
    tally.total++;
    for (const cap of PRICE_CAPS_CENTS) if (c.legalAt[cap]) tally.legal[cap]++;
  }

  const totals = {
    cards: cards.length,
    printings: printings.length,
    variations: cards.reduce((n, c) => n + c.versions, 0),
    legal: Object.fromEntries(PRICE_CAPS_CENTS.map((cap) => [cap, cards.filter((c) => c.legalAt[cap]).length])),
    noPrice: cards.filter((c) => c.minPriceCents === null).length,
    verified: cards.filter((c) => c.status === "verified").length,
    unmatched: cards.filter((c) => c.status === "unmatched").length,
  };
  setStats.push({ setName, tcgdexId, slug: setSlug(setName), totals, byRarity, cards, nameMismatches });
}

// ---------------------------------------------------------------------------
// Report helpers
// ---------------------------------------------------------------------------

function pct(legal, total) {
  return total === 0 ? null : (100 * legal) / total;
}

function fmtPct(p) {
  return p === null ? "—" : `${p.toFixed(1)}%`;
}

function fmtPrice(cents) {
  return cents === null ? "—" : `$${(cents / 100).toFixed(2)}`;
}

function allRarities() {
  const seen = new Set();
  for (const s of setStats) for (const r of s.byRarity.keys()) seen.add(r);
  const ordered = RARITY_ORDER.filter((r) => seen.has(r));
  const extra = [...seen].filter((r) => !RARITY_ORDER.includes(r)).sort();
  return [...ordered, ...extra];
}

// Color a percentage cell from red (0%) to green (100%).
function pctCell(tally, cls = "") {
  const classes = cls ? ` ${cls}` : "";
  if (!tally || tally.total === 0) return `<td class="na${classes}">—</td>`;
  const p = pct(tally.legal, tally.total);
  const hue = Math.round((p / 100) * 120); // 0 = red, 120 = green
  return (
    `<td class="pct${classes}" style="background:hsl(${hue},70%,88%)">` +
    `<span class="v">${fmtPct(p)}</span> <span class="n">${tally.legal}/${tally.total}</span></td>`
  );
}

// Per-rarity tally for one set at one price cutoff, or null if the set has
// no cards of that rarity.
function capTally(s, rarityName, cap) {
  const t = s.byRarity.get(rarityName);
  return t ? { legal: t.legal[cap], total: t.total } : null;
}

// Lowest price cutoff a card qualifies at, as a colored badge.
function tierBadge(card) {
  const cap = PRICE_CAPS_CENTS.find((c) => card.legalAt[c]);
  if (cap !== undefined) {
    const i = PRICE_CAPS_CENTS.indexOf(cap);
    const hue = Math.round(120 - (i / (PRICE_CAPS_CENTS.length - 1)) * 90);
    return `<span class="badge" style="background:hsl(${hue},70%,85%)">≤ ${fmtCap(cap)}</span>`;
  }
  if (card.minPriceCents !== null) return `<span class="badge over">> ${fmtCap(PRICE_CAPS_CENTS.at(-1))}</span>`;
  return `<span class="badge noprice">no price</span>`;
}

const STATUS_ICON = {
  verified: `<span class="st ok" title="All printings matched to TCGdex; card text identical">✓</span>`,
  partial: `<span class="st warn" title="Some printings missing from TCGdex — grouped by name only">◐</span>`,
  unmatched: `<span class="st bad" title="No TCGdex match — grouping unvalidated">?</span>`,
};

// --- Type-index helpers ------------------------------------------------------

// Pokémon TCG energy types, in display order, with card-border colors. In the
// TCG, video-game "Normal" Pokémon are the "Colorless" type.
const TYPE_META = new Map([
  ["Grass", { color: "#5aa469", label: "Grass" }],
  ["Fire", { color: "#e0632c", label: "Fire" }],
  ["Water", { color: "#3a9bdc", label: "Water" }],
  ["Lightning", { color: "#e6b422", label: "Lightning" }],
  ["Psychic", { color: "#9a5ba6", label: "Psychic" }],
  ["Fighting", { color: "#b8542c", label: "Fighting" }],
  ["Darkness", { color: "#4a4a63", label: "Darkness" }],
  ["Metal", { color: "#8a97a5", label: "Metal" }],
  ["Dragon", { color: "#b7952f", label: "Dragon" }],
  ["Colorless", { color: "#b9b4a8", label: "Colorless (Normal)" }],
]);
const TYPE_ORDER = [...TYPE_META.keys()];
const typeColor = (t) => (TYPE_META.get(t) ? TYPE_META.get(t).color : "#999");
const typeSlug = (t) => t.toLowerCase().replace(/[^a-z]/g, "");

const STAGE_RANK = { Basic: 0, Stage1: 1, Stage2: 2 };
const stageRank = (s) => (s in STAGE_RANK ? STAGE_RANK[s] : 3);
const stageLabel = (s) => (s === "Stage1" ? "Stage 1" : s === "Stage2" ? "Stage 2" : s || "—");

const RARITY_ABBR = {
  Common: "C", Uncommon: "U", Rare: "R", "Holo Rare": "RH", "Double Rare": "ex",
  "ACE SPEC Rare": "ACE", "Illustration Rare": "IR", "Ultra Rare": "UR",
  "Special Illustration Rare": "SIR", "Hyper Rare": "HR", "Mega Attack Rare": "MAR",
  "Mega Hyper Rare": "MHR", "Black White Rare": "BWR", "Radiant Rare": "K", Promo: "P",
};
const rarityAbbr = (r) => RARITY_ABBR[r] || r;

// Short per-set code for compact tiles ("SV05: Temporal Forces" -> "SV05").
const SET_CODE = new Map([
  ["SV05: Temporal Forces", "SV05"], ["SV06: Twilight Masquerade", "SV06"],
  ["SV: Shrouded Fable", "SFA"], ["SV07: Stellar Crown", "SV07"],
  ["SV08: Surging Sparks", "SV08"], ["SV: Prismatic Evolutions", "PRE"],
  ["SV09: Journey Together", "SV09"], ["SV10: Destined Rivals", "SV10"],
  ["SV: Black Bolt", "BLK"], ["SV: White Flare", "WHT"],
  ["ME01: Mega Evolution", "ME01"], ["ME02: Phantasmal Flames", "ME02"],
  ["ME: Ascended Heroes", "ASH"], ["ME03: Perfect Order", "ME03"],
  ["ME04: Chaos Rising", "ME04"], ["McDonald's Promos 2024", "MCD24"],
  ["SV: Scarlet & Violet Promo Cards", "SVP"], ["ME: Mega Evolution Promo", "MEP"],
]);
const setCode = (name) => SET_CODE.get(name) || name;

// Stable in-page anchor id for a card, based on its first printing's number.
function cardAnchor(card) {
  return "c-" + card.printings[0].normNumber.toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

// A small colored type chip.
function typeChip(t, extra = "") {
  const m = TYPE_META.get(t);
  const dark = t === "Colorless" || t === "Lightning" || t === "Metal";
  return `<span class="chip${extra ? " " + extra : ""}" style="background:${m ? m.color : "#999"};color:${dark ? "#222" : "#fff"}">${esc(m ? m.label.replace(" (Normal)", "") : t)}</span>`;
}

// Legality category for a card copy, by rarity then price:
//   green  — Common/Uncommon (always usable, regardless of price)
//   yellow — higher rarity at or below the $1.00 cap
//   red    — higher rarity above $1.00
//   none   — no Near Mint price to judge
const CAP_TOP = PRICE_CAPS_CENTS[PRICE_CAPS_CENTS.length - 1]; // $1.00
function copyCategory(rarity, cents) {
  if (rarity === "Common" || rarity === "Uncommon") return "green";
  if (cents === null) return "none";
  return cents > CAP_TOP ? "red" : "yellow";
}

const SHARED_CSS = `
  :root { color-scheme: light; }
  body { font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
         margin: 2rem auto; max-width: 1500px; padding: 0 1rem; color: #1a1a2e; }
  h1 { margin-bottom: 0.25rem; }
  .subtitle { color: #555; margin-top: 0; }
  table { border-collapse: collapse; width: 100%; margin: 1rem 0 2rem; font-size: 0.85rem; }
  th, td { border: 1px solid #ccc; padding: 0.35rem 0.5rem; text-align: right; }
  thead th { background: #2c2c54; color: #fff; }
  thead th.cap { font-size: 1rem; text-align: center; }
  tbody th { text-align: left; background: #f4f4fb; white-space: nowrap; }
  tbody th a { color: inherit; }
  td.na { color: #999; text-align: center; }
  td.pct .v { font-weight: 600; }
  td.pct .n { color: #666; font-size: 0.72rem; white-space: nowrap; display: block; }
  td.num { font-variant-numeric: tabular-nums; }
  tfoot td, tfoot th { background: #eaeaf5; font-weight: 600; }
  .notes { background: #f8f8ff; border: 1px solid #ddd; border-radius: 8px; padding: 1rem 1.5rem; font-size: 0.9rem; }
  .notes li { margin: 0.3rem 0; }
  .wrap { overflow-x: auto; }
  .gs { border-left: 3px solid #2c2c54; }
  .badge { display: inline-block; padding: 0.1rem 0.45rem; border-radius: 999px; font-weight: 600; font-size: 0.8rem; white-space: nowrap; }
  .badge.over { background: #fdd; color: #922; }
  .badge.noprice { background: #eee; color: #777; }
  .st { font-weight: 700; }
  .st.ok { color: #1a7f37; }
  .st.warn { color: #b58900; }
  .st.bad { color: #b02a2a; }
`;

// ---------------------------------------------------------------------------
// Main report page
// ---------------------------------------------------------------------------

const rarities = allRarities();
const generated = new Date().toISOString().replace("T", " ").slice(0, 16) + " UTC";

// The rarity columns shown under each price-cutoff group in the summary.
const SUMMARY_RARITIES = ["Common", "Uncommon", "Rare", SPECIAL_RARITY];
const GROUP_WIDTH = SUMMARY_RARITIES.length + 1; // + "All" column

const summaryRows = setStats
  .map((s) => {
    const groups = PRICE_CAPS_CENTS.map((cap) => {
      const cells = SUMMARY_RARITIES.map((r, i) => pctCell(capTally(s, r, cap), i === 0 ? "gs" : "")).join("");
      const overall = pctCell({ legal: s.totals.legal[cap], total: s.totals.cards });
      return cells + overall;
    }).join("");
    return `<tr>
      <th scope="row"><a href="cards/${s.slug}.html">${esc(s.setName)}</a></th>
      ${groups}
      <td class="num gs">${s.totals.cards}</td>
      <td class="num">${s.totals.variations}</td>
    </tr>`;
  })
  .join("\n");

const summaryHeadTop =
  `<th rowspan="2">Set</th>` +
  PRICE_CAPS_CENTS.map((cap) => `<th colspan="${GROUP_WIDTH}" class="gs cap">≤ ${fmtCap(cap)}</th>`).join("") +
  `<th rowspan="2" class="gs">Cards<br>(dedup.)</th><th rowspan="2">Variations</th>`;
const summaryHeadBottom = PRICE_CAPS_CENTS.map(
  () =>
    `<th class="gs">Common</th><th>Uncommon</th><th>Rare</th><th>${esc(SPECIAL_RARITY)}<br>(ex)</th><th>All</th>`
).join("");

const breakdownHeader = rarities.map((r) => `<th>${esc(r)}</th>`).join("");
const breakdownSections = PRICE_CAPS_CENTS.map((cap) => {
  const rowsHtml = setStats
    .map((s) => {
      const cells = rarities.map((r) => pctCell(capTally(s, r, cap))).join("");
      return `<tr><th scope="row">${esc(s.setName)}</th>${cells}</tr>`;
    })
    .join("\n");
  return `<h3>Cards ≤ ${fmtCap(cap)}</h3>
<div class="wrap">
<table>
<thead><tr><th>Set</th>${breakdownHeader}</tr></thead>
<tbody>
${rowsHtml}
</tbody>
</table>
</div>`;
}).join("\n");

const grandTotals = setStats.reduce(
  (acc, s) => {
    acc.cards += s.totals.cards;
    acc.variations += s.totals.variations;
    for (const cap of PRICE_CAPS_CENTS) acc.legal[cap] += s.totals.legal[cap];
    return acc;
  },
  { cards: 0, variations: 0, legal: zeroByCap() }
);
const footerGroups = PRICE_CAPS_CENTS.map(
  (cap) =>
    `<td class="na gs" colspan="${GROUP_WIDTH - 1}"></td>` +
    pctCell({ legal: grandTotals.legal[cap], total: grandTotals.cards })
).join("");

const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Pokémon TCG Pauper Format Report</title>
<style>${SHARED_CSS}</style>
</head>
<body>
<h1>Pokémon TCG “Pauper” Format Report</h1>
<p class="subtitle">Standard 2026–2027 card pool (regulation mark H+ sets). A card qualifies at a price
cutoff if <em>any</em> Near&nbsp;Mint version of it — including alternate-art printings — has a TCGplayer
market price at or below the cutoff.
Cutoffs compared: <strong>${PRICE_CAPS_CENTS.map(fmtCap).join(" / ")}</strong>.
Click a set name to drill into its cards. Generated ${generated}.</p>
<p class="subtitle"><a href="types.html">→ Browse cards by type</a> · <a href="evolution-check.html">→ Evolution data review</a> (${evoInferences.size} inferred pre-evolutions)</p>

<h2>Summary by set</h2>
<div class="wrap">
<table>
<thead>
<tr>${summaryHeadTop}</tr>
<tr>${summaryHeadBottom}</tr>
</thead>
<tbody>
${summaryRows}
</tbody>
<tfoot>
<tr>
  <th>Total</th>
  ${footerGroups}
  <td class="num gs">${grandTotals.cards}</td>
  <td class="num">${grandTotals.variations}</td>
</tr>
</tfoot>
</table>
</div>

<h2>Full rarity breakdown by price cutoff</h2>
${breakdownSections}

<h2>Methodology</h2>
<div class="notes">
<ul>
  <li><strong>Card pool:</strong> the 2026–2027 Standard pool — cards with a regulation mark of “H” or later,
      drawn from the ${TARGET_SETS.size} sets that can contain them. Cards with an earlier mark (e.g. reprints in
      promo sets) are excluded using TCGdex regulation-mark data; basic energies are always included.</li>
  <li><strong>Card identity:</strong> price records are first grouped into printings by collector number
      (holofoil, reverse holofoil, Poké/Master Ball patterns, and stamped versions of a printing count
      together), then printings are merged into one card when they share the same card name — so
      alternate-art reprints (Illustration Rare, Ultra Rare, …) count as the base card.</li>
  <li><strong>Text validation:</strong> card names and text come from TCGdex. Printings are only merged when
      their ability/attack/effect text is identical; same-name cards with different text are kept separate.
      ✓ = fully text-verified, ◐ = some printings missing from TCGdex, ? = unvalidated (name-only grouping).</li>
  <li><strong>Legality:</strong> a card qualifies at a price cutoff if <em>any</em> of its versions has a
      “Near Mint” condition TCG Market Price at or below the cutoff (${PRICE_CAPS_CENTS.map(fmtCap).join(", ")};
      all inclusive). Cards with no Near Mint market price on any version never qualify.</li>
  <li><strong>Rarity:</strong> a merged card takes the rarity of its most common printing, so an ex with
      Ultra Rare alt arts counts once, as ${esc(SPECIAL_RARITY)}. “ex” cards are printed at ${esc(SPECIAL_RARITY)}
      rarity in both the Scarlet &amp; Violet and Mega Evolution eras.</li>
  <li><strong>Variations:</strong> each distinct Near Mint product/printing combination
      (normal, holofoil, reverse holofoil, pattern or stamped variant) counts as one variation.</li>
  <li><strong>Excluded:</strong> sealed products (no collector number) and code cards.</li>
</ul>
</div>
</body>
</html>
`;

// ---------------------------------------------------------------------------
// Per-set drill-down pages
// ---------------------------------------------------------------------------

function costSymbols(cost) {
  if (!cost || !cost.length) return "";
  return cost.map((c) => `<span class="en" title="${esc(c)}">${esc(c[0])}</span>`).join("");
}

function cardTextHTML(t) {
  if (!t) return "";
  const parts = [];
  const meta = [];
  if (t.category === "Pokemon") {
    if (t.stage) meta.push(esc(t.stage));
    if (t.hp) meta.push(`${t.hp} HP`);
    if (t.types && t.types.length) meta.push(esc(t.types.join("/")));
    if (t.evolveFrom) meta.push(`evolves from ${esc(t.evolveFrom)}`);
    if (t.weaknesses && t.weaknesses.length)
      meta.push(`weak: ${t.weaknesses.map((w) => esc(`${w.type || ""} ${w.value || ""}`.trim())).join(", ")}`);
    if (t.retreat != null) meta.push(`retreat ${t.retreat}`);
  } else if (t.trainerType) meta.push(esc(t.trainerType));
  else if (t.energyType) meta.push(`${esc(t.energyType)} Energy`);
  if (t.regulationMark) meta.push(`reg. ${esc(t.regulationMark)}`);
  if (meta.length) parts.push(`<div class="meta">${meta.join(" · ")}</div>`);
  for (const a of t.abilities || []) {
    parts.push(`<div class="ab"><b>${esc(a.type || "Ability")}: ${esc(a.name || "")}</b> - ${esc(a.effect || "")}</div>`);
  }
  for (const a of t.attacks || []) {
    parts.push(
      `<div class="atk"><b>${costSymbols(a.cost)} ${esc(a.name || "")}</b>` +
        (a.damage ? ` <span class="dmg">${esc(a.damage)}</span>` : ` -`) +
        (a.effect ? ` ${esc(a.effect)}` : "") +
        `</div>`
    );
  }
  if (t.effect) parts.push(`<div class="fx">${esc(t.effect)}</div>`);
  return parts.join("");
}

const CARDS_DIR = path.join(__dirname, "cards");
fs.mkdirSync(CARDS_DIR, { recursive: true });

const PAGE_CSS = `${SHARED_CSS}
  .cardrow td { vertical-align: top; text-align: left; }
  .thumb { width: 96px; min-width: 96px; }
  .thumb img { width: 96px; border-radius: 5px; display: block; }
  .thumb .noimg { width: 96px; height: 133px; background: #eee; border-radius: 5px;
                  display: flex; align-items: center; justify-content: center; color: #999; font-size: 0.7rem; }
  .cname { font-weight: 700; font-size: 1rem; }
  .crarity { color: #666; font-size: 0.8rem; }
  .ctext { max-width: 560px; font-size: 0.78rem; color: #333; }
  .ctext .meta { color: #777; margin-bottom: 0.15rem; }
  .ctext .ab b { color: #a33; }
  .ctext .atk b { color: #223a8f; }
  .ctext .dmg { display: inline-block; min-width: 0.8rem; padding: 0 0.3rem; border-radius: 7px;
                background: #223a8f; color: #fff; font-size: 0.7rem; font-weight: 700; text-align: center; }
  .ctext > div { margin-bottom: 0.2rem; }
  .en { display: inline-block; width: 1rem; height: 1rem; border-radius: 50%; background: #ddd;
        text-align: center; line-height: 1rem; font-size: 0.65rem; font-weight: 700; margin-right: 1px; }
  .versions { font-size: 0.78rem; border-collapse: collapse; margin: 0; }
  .versions td { border: none; border-bottom: 1px solid #eee; padding: 0.15rem 0.5rem 0.15rem 0; text-align: left; }
  .versions td.pr { text-align: right; font-variant-numeric: tabular-nums; }
  .versions td.cheap { color: #1a7f37; font-weight: 600; }
  .minp { font-size: 1rem; font-weight: 700; white-space: nowrap; }
  .backlink { margin-bottom: 1rem; display: inline-block; }
  #imgpop { position: fixed; display: none; z-index: 100; pointer-events: none; }
  #imgpop img { width: 480px; border-radius: 14px; box-shadow: 0 10px 34px rgba(0,0,0,0.45); display: block; }
`;

// Hover popup: shows the high-res card image, following the cursor and
// clamped to the viewport. Images load lazily on first hover.
const POPUP_SCRIPT = `
<div id="imgpop"><img alt=""></div>
<script>
(function () {
  var pop = document.getElementById("imgpop");
  var popImg = pop.querySelector("img");
  function move(e) {
    var w = 480, h = 671; // standard card aspect ratio at popup width
    var x = e.clientX + 20, y = e.clientY - h / 3;
    if (x + w > innerWidth - 8) x = e.clientX - w - 20;
    y = Math.max(8, Math.min(y, innerHeight - h - 8));
    pop.style.left = x + "px";
    pop.style.top = y + "px";
  }
  document.querySelectorAll("[data-hi]").forEach(function (el) {
    el.addEventListener("mouseenter", function (e) {
      popImg.src = el.dataset.hi;
      pop.style.display = "block";
      move(e);
    });
    el.addEventListener("mousemove", move);
    el.addEventListener("mouseleave", function () {
      pop.style.display = "none";
      popImg.removeAttribute("src");
    });
  });
})();
</script>`;

for (const s of setStats) {
  const cardRows = s.cards
    .map((c) => {
      const versionRows = c.printings
        .flatMap((p) =>
          p.nmVersions.map((v) => {
            const kind = v.condition.replace(/^Near Mint\s*/, "") || "Normal";
            const variantNote = v.product !== c.name ? cleanVariantNote(v.product, c.name) : "";
            const cheap = v.priceCents !== null && v.priceCents === c.minPriceCents;
            return `<tr>
              <td>#${esc(p.number)}</td>
              <td>${esc(p.rarity)}</td>
              <td>${esc(kind)}${variantNote ? ` <span style="color:#888">${esc(variantNote)}</span>` : ""}</td>
              <td class="pr${cheap ? " cheap" : ""}">${fmtPrice(v.priceCents)}</td>
            </tr>`;
          })
        )
        .join("");
      const img = c.image
        ? `<img loading="lazy" src="${esc(c.image)}/low.webp" data-hi="${esc(c.image)}/high.webp" alt="${esc(c.name)}">`
        : `<div class="noimg">no image</div>`;
      return `<tr class="cardrow">
        <td class="thumb">${img}</td>
        <td>
          <div class="cname">${esc(c.displayName)} ${STATUS_ICON[c.status]}</div>
          <div class="crarity">${esc(c.rarity)} · ${c.printings.length} printing${c.printings.length === 1 ? "" : "s"}, ${c.versions} version${c.versions === 1 ? "" : "s"}</div>
          <div class="ctext">${cardTextHTML(c.tcgdex)}</div>
        </td>
        <td><table class="versions">${versionRows}</table></td>
        <td style="text-align:right">
          <div class="minp">${fmtPrice(c.minPriceCents)}</div>
          ${tierBadge(c)}
        </td>
      </tr>`;
    })
    .join("\n");

  const capsRow = PRICE_CAPS_CENTS.map(
    (cap) => `<td class="pct">${fmtPct(pct(s.totals.legal[cap], s.totals.cards))} <span class="n">${s.totals.legal[cap]}/${s.totals.cards}</span></td>`
  ).join("");

  const validationBits = [];
  if (s.totals.unmatched > 0) validationBits.push(`${s.totals.unmatched} card(s) have no TCGdex match (grouped by name only)`);
  const splitCards = s.cards.filter((c) => c.split);
  if (splitCards.length) validationBits.push(`split by differing card text: ${splitCards.map((c) => esc(c.displayName)).join(", ")}`);
  if (s.nameMismatches.length) validationBits.push(`name differences (TCGdex name used): ${s.nameMismatches.slice(0, 12).map(esc).join("; ")}${s.nameMismatches.length > 12 ? ` … +${s.nameMismatches.length - 12} more` : ""}`);

  const page = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>${esc(s.setName)} — Pauper drill-down</title>
<style>${PAGE_CSS}</style>
</head>
<body>
<a class="backlink" href="../index.html">← back to summary</a>
<h1>${esc(s.setName)}</h1>
<p class="subtitle">${s.totals.cards} cards (${s.totals.printings} printings, ${s.totals.variations} Near Mint versions) ·
${s.totals.verified} text-verified · generated ${generated}</p>

<table>
<thead><tr>${PRICE_CAPS_CENTS.map((cap) => `<th>≤ ${fmtCap(cap)}</th>`).join("")}</tr></thead>
<tbody><tr>${capsRow}</tr></tbody>
</table>

${validationBits.length ? `<div class="notes"><ul>${validationBits.map((b) => `<li>${b}</li>`).join("")}</ul></div>` : ""}

<div class="wrap">
<table>
<thead><tr><th></th><th>Card</th><th>Versions (Near Mint market price)</th><th>Cheapest</th></tr></thead>
<tbody>
${cardRows}
</tbody>
</table>
</div>
${POPUP_SCRIPT}
</body>
</html>
`;
  fs.writeFileSync(path.join(CARDS_DIR, `${s.slug}.html`), page);
}

// Describes how a product differs from the base card ("(Poke Ball Pattern)" etc).
function cleanVariantNote(product, cardName) {
  let note = product;
  if (note.toLowerCase().startsWith(cardName.toLowerCase())) note = note.slice(cardName.length);
  note = note.replace(/^\s*-\s*\S+\s*/, " "); // drop " - 123/456"
  return note.trim();
}

// ---------------------------------------------------------------------------
// Evolution verification page
// ---------------------------------------------------------------------------

const EVO_SOURCE_META = {
  "cross-set": { label: "Auto-filled from another set", cls: "ok", desc: "This species carries this evolveFrom on a printing in another set; copied verbatim from TCGdex." },
  fossil: { label: "Fossil / Restored", cls: "warn", desc: "Revived from a Fossil item card in the same set (matching TCGdex's convention for other fossils)." },
  inferred: { label: "Inferred from evolution line", cls: "warn", desc: "Not present anywhere in TCGdex data; filled from the known Pokémon evolution line. Please verify." },
  unresolved: { label: "Unresolved", cls: "bad", desc: "Could not determine — needs manual entry." },
};
const EVO_ORDER = ["inferred", "fossil", "cross-set", "unresolved"];

function evoPageHTML() {
  const recs = [...evoInferences.values()];
  const bySource = new Map(EVO_ORDER.map((s) => [s, []]));
  for (const r of recs) (bySource.get(r.source) || bySource.set(r.source, []).get(r.source)).push(r);

  const totalCards = recs.reduce((n, r) => n + r.printings.length, 0);
  const sections = EVO_ORDER.filter((s) => (bySource.get(s) || []).length).map((source) => {
    const meta = EVO_SOURCE_META[source];
    const list = bySource.get(source).sort((a, b) => a.name.localeCompare(b.name));
    const rows = list
      .map((r) => {
        const img = r.image
          ? `<img loading="lazy" src="${esc(r.image)}/low.webp" data-hi="${esc(r.image)}/high.webp" alt="${esc(r.name)}">`
          : `<div class="noimg">no image</div>`;
        const setList = r.printings
          .map((p) => `<a href="cards/${setSlug(p.setName)}.html">${esc(setCode(p.setName))}</a> <span class="lid">#${esc(p.localId)}</span>`)
          .join(", ");
        return `<tr class="cardrow">
          <td class="thumb">${img}</td>
          <td>
            <div class="cname">${esc(r.name)}</div>
            <div class="crarity">${r.type ? typeChip(r.type) + " " : ""}${esc(stageLabel(r.stage))} · ${r.printings.length} card${r.printings.length === 1 ? "" : "s"}</div>
          </td>
          <td class="evo"><span class="arrow">evolves from</span> <b>${r.evolveFrom ? esc(r.evolveFrom) : "—"}</b></td>
          <td class="sets">${setList}</td>
        </tr>`;
      })
      .join("\n");
    return `<h2>${esc(meta.label)} <span class="cnt">${list.length} species</span></h2>
<p class="sourcedesc st-${meta.cls}">${esc(meta.desc)}</p>
<div class="wrap"><table>
<thead><tr><th></th><th>Card</th><th>Inferred pre-evolution</th><th>Appears in</th></tr></thead>
<tbody>
${rows}
</tbody></table></div>`;
  }).join("\n");

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Evolution data — missing evolveFrom review</title>
<style>${PAGE_CSS}
  .evo { text-align: left; white-space: nowrap; }
  .evo .arrow { color: #888; font-size: 0.75rem; }
  .evo b { font-size: 0.95rem; }
  .sets { text-align: left; font-size: 0.8rem; }
  .sets .lid { color: #999; }
  .cnt { font-size: 0.8rem; font-weight: 400; color: #666; }
  .sourcedesc { font-size: 0.85rem; margin-top: -0.4rem; max-width: 900px; }
  .sourcedesc.st-ok { color: #1a7f37; } .sourcedesc.st-warn { color: #9a7000; } .sourcedesc.st-bad { color: #b02a2a; }
  .chip { display:inline-block; padding:0.05rem 0.4rem; border-radius:999px; font-size:0.72rem; font-weight:600; }
  .banner { border-radius: 8px; padding: 0.7rem 1.1rem; margin: 1rem 0 1.5rem; font-weight: 600; }
  .banner.ok { background: #e6f6ea; border: 1px solid #9ad0aa; color: #14682f; }
  .banner.bad { background: #fdeaea; border: 1px solid #e0a0a0; color: #a31f1f; }
</style>
</head>
<body>
<a class="backlink" href="index.html">← back to summary</a>
<h1>Evolution data — <code>evolveFrom</code> review</h1>
<p class="subtitle">${recs.length} species (${totalCards} cards) are Stage&nbsp;1/2 Pokémon whose original TCGdex record had no
<code>evolveFrom</code>. Each pre-evolution below has been written into the <code>carddata/</code> cache so evolution
families link correctly. Hover a card for a larger image. Generated ${generated}.</p>
<div class="banner ${stillMissing.length === 0 ? "ok" : "bad"}">
  ${stillMissing.length === 0
    ? "✓ Verified: every Stage 1/2 Pokémon across all 18 sets now has an evolveFrom (0 missing)."
    : `⚠ ${stillMissing.length} Stage 1/2 card(s) still missing evolveFrom: ${esc([...new Set(stillMissing.map((c) => c.name))].join(", "))}`}
</div>
${sections}
${POPUP_SCRIPT}
</body>
</html>
`;
}

fs.writeFileSync(path.join(__dirname, "evolution-check.html"), evoPageHTML());

// ---------------------------------------------------------------------------
// Type index: Pokémon grouped into evolution families, filterable by type
// ---------------------------------------------------------------------------
//
// One page listing every evolution family once. A family's "types" is the union
// of the types of all its members across all sets, so a family that spans types
// (e.g. Charizard: Fire + a Darkness promo) shows under every one of them. The
// type buttons filter client-side, keeping whole families visible.

// 1. Species nodes from TCGdex (Pokémon only), keyed by exact card name.
const speciesNodes = new Map();
for (const c of allTcgdexCards) {
  if (c.category !== "Pokemon") continue;
  let n = speciesNodes.get(c.name);
  if (!n) {
    n = { name: c.name, types: new Set(), stages: new Set(), evolveFrom: c.evolveFrom || null, image: c.image || null, priced: [], dexId: null };
    speciesNodes.set(c.name, n);
  }
  for (const t of c.types || []) n.types.add(t);
  if (c.stage) n.stages.add(c.stage);
  if (!n.evolveFrom && c.evolveFrom) n.evolveFrom = c.evolveFrom;
  if (!n.image && c.image) n.image = c.image;
  if (n.dexId == null && Array.isArray(c.dexId) && c.dexId.length) n.dexId = Math.min(...c.dexId);
}

// 2. Attach priced cards (from the report) to their species node, by name.
for (const s of setStats) {
  for (const c of s.cards) {
    if (!c.tcgdex || c.tcgdex.category !== "Pokemon") continue;
    const node = speciesNodes.get(c.name);
    if (!node) continue;
    node.priced.push({
      setName: s.setName,
      slug: s.slug,
      number: c.printings[0].number,
      rarity: c.rarity,
      versions: c.versions,
      minPriceCents: c.minPriceCents,
      legalAt: c.legalAt,
      image: c.image || null,
      tcgdex: c.tcgdex,
    });
    if (!node.image && c.image) node.image = c.image;
  }
}
// Cheapest Near Mint price across every set/version, legality per cutoff, and
// the best (most usable) legality category among the species' copies.
const CAT_RANK = { green: 0, yellow: 1, red: 2, none: 3 };
for (const n of speciesNodes.values()) {
  const prices = n.priced.map((p) => p.minPriceCents).filter((x) => x !== null);
  n.cheapestCents = prices.length ? Math.min(...prices) : null;
  n.legalAt = {};
  for (const cap of PRICE_CAPS_CENTS) n.legalAt[cap] = n.cheapestCents !== null && n.cheapestCents <= cap;
  n.minStage = Math.min(...[...n.stages].map(stageRank), 9);
  let best = "none";
  for (const p of n.priced) {
    const cat = copyCategory(p.rarity, p.minPriceCents);
    if (CAT_RANK[cat] < CAT_RANK[best]) best = cat;
  }
  n.bestCategory = best;
}

// 3. Union species into families via evolveFrom (edges within our pool only).
const ufParent = new Map();
const ufFind = (x) => {
  if (!ufParent.has(x)) ufParent.set(x, x);
  let r = x;
  while (ufParent.get(r) !== r) r = ufParent.get(r);
  while (ufParent.get(x) !== r) { const nx = ufParent.get(x); ufParent.set(x, r); x = nx; }
  return r;
};
const ufUnion = (a, b) => ufParent.set(ufFind(a), ufFind(b));
for (const name of speciesNodes.keys()) ufFind(name);
for (const n of speciesNodes.values()) {
  if (n.evolveFrom && speciesNodes.has(n.evolveFrom)) ufUnion(n.name, n.evolveFrom);
}
const familyGroups = new Map();
for (const name of speciesNodes.keys()) {
  const r = ufFind(name);
  if (!familyGroups.has(r)) familyGroups.set(r, []);
  familyGroups.get(r).push(speciesNodes.get(name));
}

// 4. Assemble family records: type union, member order, root label. Only
// species with at least one Standard-pool printing (a priced copy) are shown,
// and the type union is computed over just those members.
const typeIndex = [...familyGroups.values()]
  .map((allMembers) => {
    const members = allMembers.filter((m) => m.priced.length > 0);
    if (members.length === 0) return null;
    members.sort((a, b) => a.minStage - b.minStage || a.name.localeCompare(b.name));
    const memberNames = new Set(members.map((m) => m.name));
    const types = new Set();
    for (const m of members) for (const t of m.types) types.add(t);
    const orderedTypes = [...types].sort((a, b) => TYPE_ORDER.indexOf(a) - TYPE_ORDER.indexOf(b));
    const roots = members.filter((m) => !m.evolveFrom || !memberNames.has(m.evolveFrom));
    const rootMembers = roots.length ? roots : members;
    const label = rootMembers.map((m) => m.name).sort().join(" / ");
    // Sort key: the base (root) Pokémon's national Pokédex number.
    const rootDex = rootMembers.map((m) => m.dexId).filter((x) => x != null);
    const baseDex = rootDex.length ? Math.min(...rootDex) : Infinity;
    return { members, types: orderedTypes, label, baseDex };
  })
  .filter(Boolean);
typeIndex.sort((a, b) => a.baseDex - b.baseDex || a.label.localeCompare(b.label));

// Per-type family counts, for the filter buttons.
const familiesPerType = Object.fromEntries(TYPE_ORDER.map((t) => [t, 0]));
for (const fam of typeIndex) for (const t of fam.types) familiesPerType[t]++;

fs.writeFileSync(path.join(__dirname, "types.html"), typesPageHTML());

function typesPageHTML() {
  const filterButtons =
    `<button data-type="all" class="tf active">All <span class="bc">${typeIndex.length}</span></button>` +
    TYPE_ORDER.map((t) => {
      const m = TYPE_META.get(t);
      const dark = t === "Colorless" || t === "Lightning" || t === "Metal";
      return `<button data-type="${typeSlug(t)}" class="tf" style="--tc:${m.color};--tt:${dark ? "#222" : "#fff"}">${esc(m.label)} <span class="bc">${familiesPerType[t]}</span></button>`;
    }).join("");

  const familyBlocks = typeIndex
    .map((fam) => {
      const typeAttr = fam.types.map(typeSlug).join(" ");
      const typeChips = fam.types.map((t) => typeChip(t)).join(" ");
      const memberRows = fam.members
        .map((m) => {
          const mTypes = [...m.types].sort((a, b) => TYPE_ORDER.indexOf(a) - TYPE_ORDER.indexOf(b)).map((t) => typeChip(t)).join(" ");
          const catPill = { green: "Common/Uncommon", yellow: "≤ $1.00", red: "&gt; $1.00", none: "not in pool" }[m.bestCategory];
          const speciesCell = (rowspan) => `<td class="species cat-${m.bestCategory}"${rowspan > 1 ? ` rowspan="${rowspan}"` : ""}>
              <div class="cname">${esc(m.name)}</div>
              <div class="crarity">${esc(stageLabel([...m.stages][0] || ""))} ${mTypes}</div>
              <span class="catpill cat-${m.bestCategory}">${catPill}</span>
            </td>`;
          // One row per copy (each set's printing), cheapest first.
          const copies = m.priced.slice().sort((a, b) => (a.minPriceCents ?? 9e9) - (b.minPriceCents ?? 9e9));
          if (copies.length === 0) {
            return `<tr class="cardrow cat-none spstart">${speciesCell(1)}<td colspan="4" class="na">— not in the price pool —</td></tr>`;
          }
          return copies
            .map((p, i) => {
              const cat = copyCategory(p.rarity, p.minPriceCents);
              // Red (over-$1) copies hide the inline thumbnail to save space, but
              // keep a small hover target that still shows the full image.
              const thumb = !p.image
                ? cat === "red"
                  ? ""
                  : `<div class="noimg">no image</div>`
                : cat === "red"
                ? `<span class="peek" data-hi="${esc(p.image)}/high.webp" title="hover to preview">⌕</span>`
                : `<img loading="lazy" src="${esc(p.image)}/low.webp" data-hi="${esc(p.image)}/high.webp" alt="${esc(m.name)}">`;
              // ≤ $0.50 tag: only meaningful for yellow (higher-rarity) cards;
              // green Common/Uncommon are always legal so the sub-tier is noise.
              const half = cat === "yellow" && p.minPriceCents !== null && p.minPriceCents <= PRICE_CAPS_CENTS[0];
              return `<tr class="cardrow cat-${cat}${i === 0 ? " spstart" : ""}">
                ${i === 0 ? speciesCell(copies.length) : ""}
                <td class="thumb">${thumb}</td>
                <td class="setcell"><a href="cards/${p.slug}.html">${esc(setCode(p.setName))}</a>
                    <span class="lid">#${esc(p.number)}</span>
                    <div class="sub">${esc(rarityAbbr(p.rarity))} · ${p.versions} ver${p.versions === 1 ? "" : "s"}</div></td>
                <td class="mech"><div class="ctext">${cardTextHTML(p.tcgdex)}</div></td>
                <td class="pr">${fmtPrice(p.minPriceCents)}${half ? ` <span class="tag50">≤50¢</span>` : ""}</td>
              </tr>`;
            })
            .join("\n");
        })
        .join("\n");
      return `<section class="family" data-types="${typeAttr}">
        <div class="famhead">${Number.isFinite(fam.baseDex) ? `<span class="dex">#${String(fam.baseDex).padStart(4, "0")}</span>` : ""}<h2>${esc(fam.label)}</h2> ${typeChips} <span class="mc">${fam.members.length} Pokémon</span></div>
        <table><tbody>${memberRows}</tbody></table>
      </section>`;
    })
    .join("\n");

  const totalSpecies = speciesNodes.size;
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Pauper cards by type</title>
<style>${PAGE_CSS}
  .typefilters { position: sticky; top: 0; background: #fff; padding: 0.8rem 0; margin: 0 0 1rem;
                 border-bottom: 2px solid #2c2c54; z-index: 50; display: flex; flex-wrap: wrap; gap: 0.4rem; }
  .tf { border: 2px solid #ccc; background: #f4f4fb; border-radius: 999px; padding: 0.3rem 0.8rem;
        font-size: 0.85rem; font-weight: 600; cursor: pointer; color: #333; }
  .tf[data-type="all"].active { background: #2c2c54; color: #fff; border-color: #2c2c54; }
  .tf:not([data-type="all"]).active { background: var(--tc); color: var(--tt); border-color: var(--tc); }
  .tf .bc { opacity: 0.7; font-weight: 400; font-size: 0.78rem; }
  .family { border: 1px solid #ddd; border-radius: 10px; padding: 0.4rem 1rem 0.8rem; margin: 0 0 1rem; }
  .famhead { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; border-bottom: 1px solid #eee; }
  .famhead h2 { margin: 0.4rem 0; font-size: 1.1rem; }
  .famhead .dex { color: #888; font-variant-numeric: tabular-nums; font-weight: 700; font-size: 0.9rem; }
  .famhead .mc { color: #888; font-size: 0.8rem; margin-left: auto; }
  .family table { margin: 0.3rem 0 0; }
  .family td { border: none; border-bottom: 1px solid #f0f0f0; vertical-align: middle; }
  .cardrow.spstart td { border-top: 2px solid #b6b6c9; }
  .species { background: #f7f7fc; min-width: 190px; border-right: 2px solid #b6b6c9; }
  /* Species label cell tinted by its best (lowest) copy category. */
  .species.cat-green { background: #e3f4e8; }
  .species.cat-yellow { background: #f9f0cf; }
  .species.cat-red { background: #f9dede; }
  .species.cat-none { background: #ececf2; }
  /* Compact thumbnails (half the drill-down size) on this dense index. */
  .thumb, .thumb img { width: 48px; min-width: 48px; }
  .thumb .noimg { width: 48px; height: 66px; font-size: 0.6rem; }
  .peek { display: inline-block; width: 1.5rem; text-align: center; color: #a31f1f; cursor: zoom-in;
          font-size: 1.1rem; line-height: 1; border: 1px solid #e0a0a0; border-radius: 4px; padding: 0.1rem 0; }
  .species .cname { font-size: 0.98rem; }
  .species .crarity { margin: 0.1rem 0 0.25rem; }
  .setcell { white-space: nowrap; }
  .setcell .lid { color: #999; font-size: 0.8rem; }
  .setcell .sub { color: #777; font-size: 0.72rem; margin-top: 0.1rem; }
  .pr { white-space: nowrap; text-align: right; font-variant-numeric: tabular-nums; font-weight: 600; }
  .pr .tag50 { color: #14682f; font-size: 0.68rem; font-weight: 700; border: 1px solid #9ad0aa; border-radius: 4px; padding: 0 0.2rem; }
  .mech { text-align: left; }
  .mech .ctext { max-width: 620px; }
  /* Legality categories: green = Common/Uncommon, yellow = higher rarity ≤ $1, red = > $1 */
  .cardrow.cat-green { background: #e7f6ea; }
  .cardrow.cat-yellow { background: #fdf7e0; }
  .cardrow.cat-red { background: #fdecec; }
  .cardrow.cat-red .pr { color: #a31f1f; }
  .cardrow.cat-none { opacity: 0.6; }
  .catpill { display: inline-block; padding: 0.05rem 0.45rem; border-radius: 999px; font-size: 0.72rem; font-weight: 700; }
  .catpill.cat-green { background: #cfeed7; color: #14682f; }
  .catpill.cat-yellow { background: #f6ecc4; color: #7a5c00; }
  .catpill.cat-red { background: #f7d4d4; color: #a31f1f; }
  .catpill.cat-none { background: #eee; color: #777; }
  .chip { display:inline-block; padding:0.05rem 0.4rem; border-radius:999px; font-size:0.7rem; font-weight:600; }
  .legend { display: flex; gap: 1rem; flex-wrap: wrap; font-size: 0.8rem; margin: 0 0 0.8rem; color: #444; }
  .legend .sw { display: inline-block; width: 0.85rem; height: 0.85rem; border-radius: 3px; vertical-align: -1px; margin-right: 0.25rem; }
  #count { color: #555; font-size: 0.9rem; margin: 0 0 1rem; }
</style>
</head>
<body>
<a class="backlink" href="index.html">← back to summary</a>
<h1>Pauper cards by type</h1>
<p class="subtitle">All ${totalSpecies} Pokémon across the ${TARGET_SETS.size} sets, grouped into ${typeIndex.length}
evolution families. A family appears under <em>every</em> type any of its members takes, so cross-type lines
(e.g. a Fire line with a Darkness promo) stay together. Prices are the cheapest Near&nbsp;Mint version across all
sets; the badge shows the lowest cutoff each Pokémon qualifies at. Hover a card for a larger image. Generated ${generated}.</p>
<div class="typefilters">${filterButtons}</div>
<div class="legend">
  <span><span class="sw" style="background:#e7f6ea;border:1px solid #9ad0aa"></span>Common / Uncommon — always legal</span>
  <span><span class="sw" style="background:#fdf7e0;border:1px solid #e3cf8a"></span>Higher rarity ≤ $1.00</span>
  <span><span class="sw" style="background:#fdecec;border:1px solid #e0a0a0"></span>Over $1.00</span>
  <span><span class="sw" style="background:#eee;border:1px solid #ccc"></span>No Near Mint price</span>
</div>
<div id="count"></div>
${familyBlocks}
${POPUP_SCRIPT}
<script>
(function () {
  var selected = new Set();
  var fams = Array.prototype.slice.call(document.querySelectorAll(".family"));
  var btns = Array.prototype.slice.call(document.querySelectorAll(".tf"));
  var countEl = document.getElementById("count");
  function apply() {
    var shownF = 0, shownS = 0, shownC = 0;
    fams.forEach(function (f) {
      var types = f.dataset.types ? f.dataset.types.split(" ") : [];
      var vis = selected.size === 0 || types.some(function (t) { return selected.has(t); });
      f.style.display = vis ? "" : "none";
      if (vis) { shownF++; shownS += f.querySelectorAll("td.species").length; shownC += f.querySelectorAll("tr.cardrow").length; }
    });
    btns.forEach(function (b) {
      var on = b.dataset.type === "all" ? selected.size === 0 : selected.has(b.dataset.type);
      b.classList.toggle("active", on);
    });
    countEl.textContent =
      "Showing " + shownF + " families · " + shownS + " Pokémon · " + shownC + " cards" +
      (selected.size === 0 ? "" : " of type " + Array.from(selected).join(", "));
  }
  btns.forEach(function (b) {
    b.addEventListener("click", function () {
      if (b.dataset.type === "all") selected.clear();
      else { var t = b.dataset.type; selected.has(t) ? selected.delete(t) : selected.add(t); }
      apply();
    });
  });
  apply();
})();
</script>
</body>
</html>
`;
}

// ---------------------------------------------------------------------------
// Write outputs
// ---------------------------------------------------------------------------

const outHtml = path.join(__dirname, "index.html");
fs.writeFileSync(outHtml, html);

const jsonData = {
  generated,
  priceCapsCents: PRICE_CAPS_CENTS,
  evolutionInferences: [...evoInferences.values()].map((r) => ({
    name: r.name,
    stage: r.stage,
    type: r.type,
    inferredEvolveFrom: r.evolveFrom,
    source: r.source,
    sets: r.printings.map((p) => `${p.setName} #${p.localId}`),
  })),
  sets: setStats.map((s) => ({
    setName: s.setName,
    tcgdexId: s.tcgdexId,
    totals: s.totals,
    byRarity: Object.fromEntries([...s.byRarity.entries()].sort()),
    cards: s.cards.map((c) => ({
      name: c.displayName,
      rarity: c.rarity,
      status: c.status,
      minNearMintPrice: c.minPriceCents === null ? null : c.minPriceCents / 100,
      legalAt: c.legalAt,
      versions: c.versions,
      printings: c.printings.map((p) => ({
        number: p.number,
        rarity: p.rarity,
        minNearMintPrice: p.minPriceCents === null ? null : p.minPriceCents / 100,
        versions: p.nmVersions.length,
      })),
    })),
  })),
};
const outJson = path.join(__dirname, "report-data.json");
fs.writeFileSync(outJson, JSON.stringify(jsonData, null, 2));

// ---------------------------------------------------------------------------
// Console summary
// ---------------------------------------------------------------------------

console.log(`Parsed ${rows.length - 1} CSV rows; skipped ${skippedNoNumber} sealed/no-number rows and ${skippedCodeCards} code-card rows.`);
console.log(
  `Cards: ${grandTotals.cards} (from ${setStats.reduce((n, s) => n + s.totals.printings, 0)} printings) — ` +
    `${validationTotals.verified} text-verified, ${validationTotals.partial} partial, ${validationTotals.unmatched} unmatched, ` +
    `${validationTotals.split} name-groups split by text, ${validationTotals.nameMismatches} name mismatches`
);
console.log(`Excluded ${regExcluded} card(s) below regulation mark ${MIN_REG_MARK} (not in 2026-2027 Standard).\n`);

const pad = (s, n) => String(s).padEnd(n);
const padL = (s, n) => String(s).padStart(n);
for (const cap of PRICE_CAPS_CENTS) {
  console.log(`--- Cutoff: <= ${fmtCap(cap)} ---`);
  console.log(
    pad("Set", 34) + padL("Common", 9) + padL("Uncommon", 10) + padL("Rare", 8) + padL("DblRare", 9) + padL("All", 8) + padL("Cards", 7) + padL("Vars", 7)
  );
  for (const s of setStats) {
    const p = (name) => {
      const t = capTally(s, name, cap);
      return t ? fmtPct(pct(t.legal, t.total)) : "—";
    };
    console.log(
      pad(s.setName, 34) +
        padL(p("Common"), 9) +
        padL(p("Uncommon"), 10) +
        padL(p("Rare"), 8) +
        padL(p(SPECIAL_RARITY), 9) +
        padL(fmtPct(pct(s.totals.legal[cap], s.totals.cards)), 8) +
        padL(s.totals.cards, 7) +
        padL(s.totals.variations, 7)
    );
  }
  console.log("");
}

if (warnings.length) {
  console.log(`${warnings.length} warning(s):`);
  for (const w of warnings.slice(0, 40)) console.log("  - " + w);
  if (warnings.length > 40) console.log(`  … +${warnings.length - 40} more`);
}
const evoBySource = {};
for (const r of evoInferences.values()) evoBySource[r.source] = (evoBySource[r.source] || 0) + 1;
console.log(
  `\nEvolution: ${evoInferences.size} species missing evolveFrom — ` +
    Object.entries(evoBySource).map(([s, n]) => `${n} ${s}`).join(", ")
);

console.log(`\nWrote ${outHtml}`);
console.log(`Wrote ${outJson}`);
console.log(`Wrote ${setStats.length} drill-down pages in ${CARDS_DIR}/`);
console.log(`Wrote evolution-check.html`);
