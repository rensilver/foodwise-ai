import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { PageShell } from "../../src/components/layout/page-shell";
import { SiteHeader } from "../../src/components/layout/site-header";

test("shell marks the current destination and renders contextual controls once", () => {
  render(
    <PageShell
      active="recipes"
      sidebar={
        <label>
          Cuisine
          <input />
        </label>
      }
    >
      <h1>Recipes</h1>
    </PageShell>,
  );
  expect(screen.getByRole("link", { name: "Recipes" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(screen.getAllByLabelText("Cuisine")).toHaveLength(1);
  expect(screen.getByRole("main")).toContainElement(
    screen.getByRole("heading", { name: "Recipes" }),
  );
});

test("header search uses the selected catalog and describes name-only matching", () => {
  render(<SiteHeader />);
  fireEvent.change(screen.getByLabelText("Search category"), {
    target: { value: "restaurants" },
  });
  expect(screen.getByRole("search")).toHaveAttribute(
    "action",
    "/catalog/restaurants",
  );
  expect(screen.getByLabelText("Search restaurants by name")).toHaveAttribute(
    "name",
    "q",
  );
});
