import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
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
        <header className="site-header">
          <nav aria-label="Main navigation" className="site-nav">
            <Link href="/" className="brand">
              {PRODUCT_NAME}
            </Link>
            <Link href="/">Find a meal</Link>
            <Link href="/catalog/restaurants">Catalog</Link>
            <Link href="/admin">Administration</Link>
          </nav>
        </header>
        {children}
      </body>
    </html>
  );
}
