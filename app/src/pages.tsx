import { Cookie as CookieIcon, Home as HomeIcon } from "@mui/icons-material";
import { useMemo } from "react";
import { useMatches } from "react-router-dom";
import { Cookies } from "./cookies";
import { Home } from "./home";

export type PageId = "home" | "cookies";

export interface Page {
  readonly id: PageId;
  readonly path: string;
  readonly icon: JSX.Element;
  readonly title: string;
  readonly element: JSX.Element;
}

export type Pages = Readonly<Record<PageId, Page>>;

export const ID_ROOT = "root";

export const pages: Pages = {
  home: {
    id: "home",
    path: "/",
    icon: <HomeIcon />,
    title: "Home",
    element: <Home />,
  },
  cookies: {
    id: "cookies",
    path: "/cookies",
    icon: <CookieIcon />,
    title: "Cookie Recipes",
    element: <Cookies />,
  },
};

export const pageList: Page[] = Object.values(pages);

export const useCurrentPage = (): Page => {
  const matches = useMatches();

  return useMemo(() => {
    for (const match of matches) {
      const page = pages[match.id as PageId];
      if (page) {
        document.title = `${page.title} | jeffbrower.com`;
        return page;
      }
    }

    console.error("Not on a known page:", matches);
    throw new Error("Not on a known page");
  }, [matches]);
};
