import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { MealWorkspace } from "../../src/features/chat/meal-workspace";
import { rice } from "../fixtures/catalog";
afterEach(() => vi.unstubAllGlobals());
test("home loads bounded catalog discovery without starting inference", async () => {
  const fetcher = vi.fn(async () =>
    Response.json({ items: [rice], total: 1, limit: 6, offset: 0 }),
  );
  vi.stubGlobal("fetch", fetcher);
  render(<MealWorkspace />);
  expect(
    await screen.findByRole("heading", { name: "Explore recipes" }),
  ).toBeVisible();
  await screen.findByRole("heading", { name: "Tomato rice" });
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(fetcher.mock.calls[0]).toEqual(
    expect.arrayContaining(["/api/v1/recipes?limit=6"]),
  );
  expect(screen.getByText(/Preferences aren’t applied/)).toBeVisible();
});
test("discovery failure leaves the composer and catalog link usable", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json({}, { status: 503 })),
  );
  render(<MealWorkspace />);
  await waitFor(() =>
    expect(screen.getByText(/Recipe preview unavailable/)).toBeVisible(),
  );
  expect(screen.getByLabelText("Message")).toBeEnabled();
  expect(
    screen.getByRole("link", { name: "Browse all recipes" }),
  ).toHaveAttribute("href", "/catalog/recipes");
});
test("saved conversations do not load the home discovery preview", async () => {
  const fetcher = vi.fn(async () =>
    Response.json({ id: "saved", messages: [], preferences: null }),
  );
  vi.stubGlobal("fetch", fetcher);
  render(<MealWorkspace conversationId="saved" />);
  await waitFor(() =>
    expect(screen.queryByText("Loading saved conversation…")).toBeNull(),
  );
  expect(screen.queryByRole("heading", { name: "Explore recipes" })).toBeNull();
  expect(fetcher.mock.calls).toHaveLength(1);
});
