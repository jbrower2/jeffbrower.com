import React from "react";
import { createRoot } from "react-dom/client";
import { HashRouter } from "react-router-dom";
import App from "./App.jsx";

function mount() {
  const container = document.getElementById("root");
  createRoot(container).render(
    <HashRouter>
      <App />
    </HashRouter>,
  );
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", mount);
} else {
  mount();
}
