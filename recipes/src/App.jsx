import React from "react";
import { Routes, Route } from "react-router-dom";
import RecipeList from "./pages/RecipeList.jsx";
import RecipeDetail from "./pages/RecipeDetail.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<RecipeList />} />
      <Route path="/:slug" element={<RecipeDetail />} />
    </Routes>
  );
}
