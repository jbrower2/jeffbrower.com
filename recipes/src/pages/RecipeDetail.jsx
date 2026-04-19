import React, { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import recipes from "../data/recipes.json";
import { Fraction } from "../lib/fraction.js";

const recipesBySlug = Object.fromEntries(recipes.map((r) => [r.slug, r]));

function scaleQuantity(quantityStr, mult) {
  const f = Fraction.parse(quantityStr);
  return f.times(mult).toString();
}

export default function RecipeDetail() {
  const { slug } = useParams();
  const recipe = recipesBySlug[slug];

  if (!recipe) {
    return (
      <div>
        <p>Recipe not found.</p>
        <p>
          <Link to="/">← Back to all recipes</Link>
        </p>
      </div>
    );
  }

  const original = recipe.servings;
  const [servingsText, setServingsText] = useState(String(original ?? ""));

  const mult = useMemo(() => {
    if (original == null) return new Fraction(1, 1);
    try {
      const f = Fraction.parse(servingsText);
      if (f.num <= 0) return null;
      return f.div(new Fraction(original, 1));
    } catch {
      return null;
    }
  }, [servingsText, original]);

  return (
    <div>
      <p>
        <Link to="/">← All recipes</Link>
      </p>
      <h1>{recipe.name}</h1>

      {original != null && (
        <p>
          <label>
            Servings:{" "}
            <input
              type="text"
              inputMode="numeric"
              value={servingsText}
              onChange={(e) => setServingsText(e.target.value)}
              style={{
                width: "5em",
                padding: "2px 6px",
                fontSize: "1rem",
                color: mult == null ? "#c33" : undefined,
              }}
            />
          </label>
          {original != null && (
            <span style={{ marginLeft: "1em", opacity: 0.7 }}>
              (original: {original})
            </span>
          )}
        </p>
      )}

      <p style={{ opacity: 0.7 }}>
        <strong>Yield:</strong> {recipe.yield}
      </p>

      <h2>Ingredients</h2>
      <ul>
        {recipe.ingredients.map((ing, i) => {
          const qty = mult ? scaleQuantity(ing.quantity, mult) : ing.quantity;
          return (
            <li key={i}>
              {qty}
              {ing.unit ? ` ${ing.unit}` : ""} {ing.name}
              {ing.note ? `, ${ing.note}` : ""}
            </li>
          );
        })}
      </ul>

      <h2>Instructions</h2>
      <p style={{ whiteSpace: "pre-wrap", lineHeight: 1.6 }}>
        {recipe.instructions}
      </p>

      <p>
        <Link to="/">← All recipes</Link>
      </p>
    </div>
  );
}
