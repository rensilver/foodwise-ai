import { render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { CatalogDetail } from "../../src/features/catalog/catalog-detail";
import { rice } from "../fixtures/catalog";
afterEach(() => vi.unstubAllGlobals());
test.each([
  "/",
  "/catalog/recipes?q=rice",
  "/conversations/abc",
  "//evil.example",
  "/\\evil.example",
  "https://evil.example",
])("detail validates return destination %s", async (returnTo) => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json(rice)),
  );
  render(
    <CatalogDetail
      entity={{ category: "recipe", id: "rice" }}
      returnTo={returnTo}
    />,
  );
  await screen.findByRole("heading", { name: "Tomato rice" });
  const allowed = [
    "/",
    "/catalog/recipes?q=rice",
    "/conversations/abc",
  ].includes(returnTo);
  expect(
    screen.getByRole("link", { name: "Return to results" }),
  ).toHaveAttribute("href", allowed ? returnTo : "/catalog/recipes");
  expect(screen.getByText("basil", { exact: true })).toBeVisible();
});
