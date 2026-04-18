import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import recipes from "../data/recipes.json";

export default function RecipeList() {
  const [filter, setFilter] = useState("");

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return recipes;
    return recipes.filter((r) => r.name.toLowerCase().includes(q));
  }, [filter]);

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
      <p style={{ opacity: 0.7, margin: "8px 0" }}>
        {filtered.length} of {recipes.length}
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
