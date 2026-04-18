import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import recipes from "../data/recipes.json";

export default function RecipeList() {
  const [filter, setFilter] = useState("");
  const [showAll, setShowAll] = useState(false);

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return recipes.filter((r) => {
      if (!showAll && r.show !== true) return false;
      if (q && !r.name.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [filter, showAll]);

  return (
    <div>
      <h1>Recipes</h1>
      <input
        type="search"
        placeholder="Filter recipes…"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        autoFocus
        style={{ width: "100%", padding: "6px 10px", fontSize: "1rem", boxSizing: "border-box" }}
      />
      <p style={{ opacity: 0.7, margin: "8px 0", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <label style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
          <input
            type="checkbox"
            checked={showAll}
            onChange={(e) => setShowAll(e.target.checked)}
          />
          Show All
        </label>
        <span>
          {filtered.length} of {showAll ? recipes.length : recipes.filter((r) => r.show === true).length}
        </span>
      </p>
      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {filtered.map((r) => (
          <li key={r.slug} style={{ padding: "4px 0" }}>
            <Link to={`/${r.slug}`}>{r.name}</Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
