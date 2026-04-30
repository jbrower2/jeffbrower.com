import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import recipes from "../data";

// In-memory state that survives component unmount (e.g. navigating to a recipe
// and back) but resets on full page refresh.
let savedState = null;

// Build a nested tree: { children: Map<string, Node>, recipes: Recipe[], path: string[] }
// Recipes appear at the deepest node of each of their category paths.
function buildTree(items) {
  const root = { children: new Map(), recipes: [], path: [] };
  for (const r of items) {
    for (const cat of r.categories) {
      const segments = cat.split("/");
      let node = root;
      for (const seg of segments) {
        if (!node.children.has(seg)) {
          node.children.set(seg, {
            children: new Map(),
            recipes: [],
            path: [...node.path, seg],
          });
        }
        node = node.children.get(seg);
      }
      node.recipes.push(r);
    }
  }
  return root;
}

// Total distinct recipes under a node (dedup across multi-category recipes).
function countDistinct(node) {
  const slugs = new Set();
  function visit(n) {
    for (const r of n.recipes) slugs.add(r.slug);
    for (const child of n.children.values()) visit(child);
  }
  visit(node);
  return slugs.size;
}

// Collect every ancestor path key (e.g. "Dessert", "Dessert/Cookies") for nodes
// that contain at least one of the matching recipes. Used to auto-expand
// ancestors when filtering.
function ancestorsWithMatch(root, matchSet) {
  const keys = new Set();
  function visit(node) {
    let hasMatch = false;
    for (const r of node.recipes) if (matchSet.has(r.slug)) hasMatch = true;
    for (const child of node.children.values()) {
      if (visit(child)) hasMatch = true;
    }
    if (hasMatch && node.path.length > 0) {
      keys.add(node.path.join("/"));
    }
    return hasMatch;
  }
  visit(root);
  return keys;
}

function TreeNode({ node, expanded, toggle, forceExpand, name, filter }) {
  const key = node.path.join("/");
  if (filter && !forceExpand.has(key)) return null;
  const isOpen = forceExpand.has(key) || expanded.has(key);
  const count = countDistinct(node);
  return (
    <li style={{ listStyle: "none", margin: "2px 0" }}>
      <button
        onClick={() => toggle(key)}
        style={{
          background: "none",
          border: "none",
          padding: "2px 0",
          cursor: "pointer",
          font: "inherit",
          color: "inherit",
          textAlign: "left",
          width: "100%",
        }}
      >
        {isOpen ? "▽" : "▷"} {name} ({count})
      </button>
      {isOpen && (
        <ul style={{ listStyle: "none", padding: 0, margin: "0 0 0 16px" }}>
          {[...node.children.entries()]
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([childName, child]) => (
              <TreeNode
                key={childName}
                node={child}
                name={childName}
                expanded={expanded}
                toggle={toggle}
                forceExpand={forceExpand}
                filter={filter}
              />
            ))}
          {node.recipes.map((r) => {
            if (filter && !r.name.toLowerCase().includes(filter)) return null;
            return (
              <li key={r.slug} style={{ padding: "2px 0" }}>
                <Link to={`/${r.slug}`}>{r.name}</Link>
              </li>
            );
          })}
        </ul>
      )}
    </li>
  );
}

export default function RecipeList() {
  const [filter, setFilter] = useState(() => savedState?.filter ?? "");
  const [showAll, setShowAll] = useState(() => savedState?.showAll ?? false);
  const [expanded, setExpanded] = useState(
    () => savedState?.expanded ?? new Set(),
  );

  useEffect(() => {
    savedState = { filter, showAll, expanded };
  }, [filter, showAll, expanded]);

  const visibleRecipes = useMemo(
    () => (showAll ? recipes : recipes.filter((r) => r.show)),
    [showAll],
  );

  const tree = useMemo(() => buildTree(visibleRecipes), [visibleRecipes]);

  const q = filter.trim().toLowerCase();
  const matchingSlugs = useMemo(() => {
    if (!q) return null;
    return new Set(
      visibleRecipes
        .filter((r) => r.name.toLowerCase().includes(q))
        .map((r) => r.slug),
    );
  }, [q, visibleRecipes]);

  const forceExpand = useMemo(() => {
    if (!matchingSlugs) return new Set();
    return ancestorsWithMatch(tree, matchingSlugs);
  }, [tree, matchingSlugs]);

  function toggle(key) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  const totalDistinct = visibleRecipes.length;
  const matchCount = matchingSlugs ? matchingSlugs.size : totalDistinct;

  return (
    <div>
      <h1>Recipes</h1>
      <input
        type="search"
        placeholder="Filter recipes…"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        autoFocus
        style={{
          width: "100%",
          padding: "6px 10px",
          fontSize: "1rem",
          boxSizing: "border-box",
        }}
      />
      <p
        style={{
          opacity: 0.7,
          margin: "8px 0",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <label
          style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}
        >
          <input
            type="checkbox"
            checked={showAll}
            onChange={(e) => setShowAll(e.target.checked)}
          />
          Show All
        </label>
        <span>
          {matchCount} of {totalDistinct}
        </span>
      </p>
      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {[...tree.children.entries()]
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([name, child]) => (
            <TreeNode
              key={name}
              node={child}
              name={name}
              expanded={expanded}
              toggle={toggle}
              forceExpand={forceExpand}
              filter={q}
            />
          ))}
      </ul>
    </div>
  );
}
