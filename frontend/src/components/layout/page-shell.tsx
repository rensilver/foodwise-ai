"use client";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { BookOpen, CookingPot, MapPin, Menu, Settings, X } from "lucide-react";
import { Button } from "../ui/button";
const destinations = [
  { key: "meal", href: "/", label: "Find a meal", icon: CookingPot },
  {
    key: "recipes",
    href: "/catalog/recipes",
    label: "Recipes",
    icon: BookOpen,
  },
  {
    key: "restaurants",
    href: "/catalog/restaurants",
    label: "Restaurants",
    icon: MapPin,
  },
  { key: "admin", href: "/admin", label: "Administration", icon: Settings },
] as const;

export function PageShell({
  active,
  sidebar,
  sidebarLabel = "Menu",
  children,
  className = "",
}: {
  active: "meal" | "recipes" | "restaurants" | "admin";
  sidebar?: ReactNode;
  sidebarLabel?: string;
  children: ReactNode;
  className?: string;
}) {
  const panel = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const [desktop, setDesktop] = useState(true);
  const [open, setOpen] = useState(false);
  const titleId = useId();
  // A native dialog keeps the exact same editor subtree mounted at every width.
  // showModal supplies focus containment, Escape and an inert background.
  useEffect(() => {
    const media = window.matchMedia("(min-width: 1120px)");
    function sync() {
      const dialog = panel.current!;
      const focused = dialog.contains(document.activeElement);
      dialog.close();
      setDesktop(media.matches);
      setOpen(false);
      if (media.matches) dialog.show();
      else if (focused) trigger.current?.focus();
    }
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);
  function close() {
    if (desktop) return;
    panel.current?.close();
    setOpen(false);
    trigger.current?.focus();
  }
  return (
    <div className="page-shell">
      <div className="mobile-toolbar">
        <Button
          ref={trigger}
          variant="secondary"
          aria-haspopup="dialog"
          aria-expanded={open}
          onClick={() => {
            panel.current?.showModal();
            setOpen(true);
          }}
        >
          <Menu size={18} aria-hidden="true" />
          {sidebarLabel}
        </Button>
      </div>
      <dialog
        ref={panel}
        className="sidebar"
        role={desktop ? "complementary" : "dialog"}
        aria-labelledby={titleId}
        onCancel={(event) => {
          event.preventDefault();
          close();
        }}
        onClick={(event) => {
          if (event.target === event.currentTarget && !desktop) close();
        }}
      >
        <div className="sidebar-inner">
          <div className="drawer-heading">
            <h2 id={titleId}>{sidebarLabel}</h2>
            <Button variant="secondary" aria-label="Close menu" onClick={close}>
              <X size={20} aria-hidden="true" />
            </Button>
          </div>
          <nav aria-label="Main navigation" className="sidebar-nav">
            {destinations.map(({ key, href, label, icon: Icon }) => (
              <Link
                key={key}
                href={href}
                aria-current={active === key ? "page" : undefined}
                onClick={close}
                className={key === "admin" ? "admin-link" : undefined}
              >
                <Icon size={19} aria-hidden="true" />
                {label}
              </Link>
            ))}
          </nav>
          {sidebar && <div className="sidebar-context">{sidebar}</div>}
          <p className="sidebar-footnote note">
            A little inspiration for your next meal. Explore the sources behind
            every suggestion.
          </p>
        </div>
      </dialog>
      <main id="main" className={`workspace ${className}`}>
        {children}
      </main>
    </div>
  );
}
