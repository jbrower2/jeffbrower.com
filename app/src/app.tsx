import {
  CssBaseline,
  ThemeProvider,
  createTheme,
  useMediaQuery,
} from "@mui/material";
import { useMemo } from "react";
import { ErrorBoundary, type FallbackProps } from "react-error-boundary";
import { RouterProvider, createHashRouter } from "react-router-dom";

import { Layout } from "./layout";
import { ID_ROOT, pageList } from "./pages";

function fallback({ error }: FallbackProps) {
  console.error(error);
  return <div>{String(error)}</div>;
}

const router = createHashRouter([
  {
    id: ID_ROOT,
    path: "/",
    element: <Layout />,
    children: pageList,
  },
]);

// TODO make themes work in dark and light
const darkTheme = createTheme({
  palette: {
    mode: "dark",
    primary: { main: "#2ce62c" },
    secondary: { main: "#ae08d2" },
  },
});

const lightTheme = createTheme({
  palette: {
    mode: "light",
    primary: { main: "#2ce62c" },
    secondary: { main: "#ae08d2" },
  },
});

export const App = () => {
  const prefersDarkMode = useMediaQuery("(prefers-color-scheme: dark)");

  const theme = useMemo(
    () => (prefersDarkMode ? darkTheme : lightTheme),
    [prefersDarkMode]
  );

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <ErrorBoundary fallbackRender={fallback}>
        <RouterProvider router={router} />
      </ErrorBoundary>
    </ThemeProvider>
  );
};
