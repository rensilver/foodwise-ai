import type { Metadata } from "next";
import type { ReactNode } from "react";
import { SiteHeader } from "../components/layout/site-header";
import { PRODUCT_NAME } from "../lib/product";
import "./globals.css";
export const metadata: Metadata = {
  title: PRODUCT_NAME,
  description:
    "Choose where to eat or what to cook from a local synthetic teaching catalog.",
};
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a href="#main" className="skip-link">
          Skip to content
        </a>
        <SiteHeader />
        {children}
      </body>
    </html>
  );
}
