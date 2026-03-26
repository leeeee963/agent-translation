import { createBrowserRouter } from "react-router";
import { TranslationApp } from "./components/TranslationApp";
import { TermLibraryPage } from "./components/TermLibraryPage";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: TranslationApp,
  },
  {
    path: "/library",
    Component: TermLibraryPage,
  },
  {
    path: "*",
    Component: () => (
      <div className="size-full flex items-center justify-center">
        <p>页面未找到</p>
      </div>
    ),
  },
]);
