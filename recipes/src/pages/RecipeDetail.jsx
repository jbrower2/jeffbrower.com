import React, { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { marked } from "marked";
import recipes from "../data/recipes-index.js";
import { Fraction } from "../lib/fraction.js";

const recipesBySlug = Object.fromEntries(recipes.map((r) => [r.slug, r]));

const TOKEN_RE = /\{([^}]+)\}/g;

function findOriginalServings(md) {
  const m = md.match(/\{([^}]+)\}/);
  return m ? m[1] : null;
}

function scaleValue(str, mult) {
  try {
    return Fraction.parse(str).times(mult).toString();
  } catch {
    return str;
  }
}

function attrsToProps(node) {
  const props = {};
  for (const attr of node.attributes) {
    let name = attr.name;
    if (name === "class") name = "className";
    else if (name === "for") name = "htmlFor";
    props[name] = attr.value;
  }
  return props;
}

function splitTextNode(text, state, baseKey) {
  const re = new RegExp(TOKEN_RE.source, "g");
  const parts = [];
  let lastIndex = 0;
  let m;
  let pi = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > lastIndex) parts.push(text.slice(lastIndex, m.index));
    const tokenKey = `${baseKey}-t${pi++}`;
    const idx = state.tokenIndex++;
    if (idx === 0) {
      parts.push(
        React.createElement("input", {
          key: tokenKey,
          type: "text",
          inputMode: "numeric",
          value: state.servingsText,
          onChange: (e) => state.setServingsText(e.target.value),
          style: {
            width: "4em",
            padding: "2px 6px",
            fontSize: "1rem",
            color: state.mult == null ? "#c33" : undefined,
          },
        }),
      );
    } else {
      const scaled = state.mult ? scaleValue(m[1], state.mult) : m[1];
      parts.push(scaled);
    }
    lastIndex = re.lastIndex;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return parts;
}

function walkChildren(parent, state, baseKey) {
  const out = [];
  let i = 0;
  for (const child of parent.childNodes) {
    const childKey = `${baseKey}-${i++}`;
    if (child.nodeType === 3) {
      for (const p of splitTextNode(child.textContent, state, childKey)) {
        out.push(p);
      }
    } else if (child.nodeType === 1) {
      const tag = child.nodeName.toLowerCase();
      const props = attrsToProps(child);
      props.key = childKey;
      const inner = walkChildren(child, state, childKey);
      out.push(React.createElement(tag, props, ...inner));
    }
  }
  return out;
}

export default function RecipeDetail() {
  const { slug } = useParams();
  const recipe = recipesBySlug[slug];
  const markdown = recipe?.markdown ?? "";
  const originalServings = useMemo(
    () => findOriginalServings(markdown),
    [markdown],
  );
  const [servingsText, setServingsText] = useState(originalServings ?? "");

  useEffect(() => {
    setServingsText(originalServings ?? "");
  }, [slug, originalServings]);

  const mult = useMemo(() => {
    if (!originalServings) return new Fraction(1, 1);
    try {
      const f = Fraction.parse(servingsText);
      if (f.num <= 0) return null;
      return f.div(Fraction.parse(originalServings));
    } catch {
      return null;
    }
  }, [servingsText, originalServings]);

  const tree = useMemo(() => {
    if (!markdown) return null;
    const html = marked.parse(markdown);
    const doc = new DOMParser().parseFromString(html, "text/html");
    const state = { tokenIndex: 0, mult, servingsText, setServingsText };
    return walkChildren(doc.body, state, "root");
  }, [markdown, mult, servingsText]);

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

  return (
    <div>
      <p>
        <Link to="/">← All recipes</Link>
      </p>
      {tree}
      <p>
        <Link to="/">← All recipes</Link>
      </p>
    </div>
  );
}
