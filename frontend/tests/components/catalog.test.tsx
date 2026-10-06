import { render, screen, waitFor } from "@testing-library/react";
import { expect, test, vi, afterEach } from "vitest";
import { CatalogBrowser } from "../../src/features/catalog/catalog-browser";
import { rice } from "../fixtures/catalog";
afterEach(() => vi.unstubAllGlobals());
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
test("recipe browse omits restaurant-only filters and retains query on detail return", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json({ items: [rice], total: 1, limit: 12, offset: 0 }),
    ),
  );
  render(<CatalogBrowser category="recipe" query="q=rice&cuisine=Italian" />);
  await waitFor(() =>
    expect(screen.getByRole("heading", { name: "Tomato rice" })).toBeVisible(),
  );
  expect(screen.queryByLabelText("Location")).toBeNull();
  expect(screen.queryByLabelText("Maximum source price band")).toBeNull();
  expect(
    screen
      .getByRole("link", { name: "View details for Tomato rice" })
      .getAttribute("href"),
  ).toContain("returnTo=");
});

test("changing a catalog query hides old results while the new request is pending", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json({ items: [rice], total: 1, limit: 12, offset: 0 }),
    )
    .mockImplementation(() => new Promise(() => {}));
  vi.stubGlobal("fetch", fetcher);
  const { rerender } = render(
    <CatalogBrowser category="recipe" query="q=rice" />,
  );
  await screen.findByRole("heading", { name: "Tomato rice" });
  rerender(<CatalogBrowser category="recipe" query="q=pasta" />);
  expect(screen.queryByRole("heading", { name: "Tomato rice" })).toBeNull();
  expect(screen.getByLabelText("Search by name")).toHaveValue("pasta");
  expect(screen.getByRole("status")).toHaveTextContent("Loading catalog");
});
