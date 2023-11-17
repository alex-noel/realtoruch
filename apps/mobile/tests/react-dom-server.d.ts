declare module "react-dom/server" {
  import { ReactNode } from "react";
  export function renderToStaticMarkup(element: ReactNode): string;
}
