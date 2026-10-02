import type { Metadata } from "next";
import type { ReactNode } from "react";
import { PRODUCT_NAME } from "../lib/product";

export const metadata: Metadata = {
  title: PRODUCT_NAME,
  description: "Local restaurant and recipe recommendation project.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}
