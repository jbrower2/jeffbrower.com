import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app";

import "@fontsource/roboto/300.css";
import "@fontsource/roboto/400.css";
import "@fontsource/roboto/500.css";
import "@fontsource/roboto/700.css";

createRoot(document.body.appendChild(document.createElement("div"))).render(
  <StrictMode>
    <App />
  </StrictMode>
);
