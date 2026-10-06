import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { Recommendations } from "../../src/features/recommendations/recommendations";
import { recommendations, rice } from "../fixtures/catalog";
afterEach(() => vi.unstubAllGlobals());
test("source excerpts, unknown dietary evidence and linked images stay attached to recipe group", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json(rice)),
  );
  render(<Recommendations event={recommendations} />);
  await waitFor(() =>
    expect(screen.getByRole("heading", { name: "Tomato rice" })).toBeVisible(),
  );
  expect(
    screen.getByRole("heading", { name: "Recipes to cook" }),
  ).toBeVisible();
  expect(screen.getByText("Dietary evidence: unknown.")).toBeVisible();
  expect(
    screen.getByText("Current trend information is unavailable."),
  ).toBeVisible();
  expect(screen.getByRole("img").getAttribute("src")).toMatch(
    /\/api\/v1\/recipes\/rice\/images\/rice-image$/,
  );
});
test("untrusted HTML is escaped and unsafe citation URLs are never linked", async () => {
  const unsafe = {
    ...recommendations,
    evidence: [
      {
        ...recommendations.evidence[0],
        citations: [
          {
            ...recommendations.evidence[0].citations[0],
            excerpt: "<script>steal()</script>",
            url: "javascript:steal()",
          },
        ],
      },
    ],
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json(rice)),
  );
  const { container } = render(<Recommendations event={unsafe} />);
  await waitFor(() =>
    expect(screen.getByRole("heading", { name: "Tomato rice" })).toBeVisible(),
  );
  expect(container.querySelector("script")).toBeNull();
  expect(container.querySelector('a[href^="javascript:"]')).toBeNull();
});

test("full canonical ingredients remain available and repeated limitations appear once per candidate", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json(rice)),
  );
  render(
    <Recommendations
      event={{
        ...recommendations,
        result: {
          ...recommendations.result,
          recommendations: [
            {
              ...recommendations.result.recommendations[0],
              limitations: [
                "Cross-contact is not verified.",
                "Cross-contact is not verified.",
              ],
            },
          ],
        },
      }}
    />,
  );
  await screen.findByRole("heading", { name: "Tomato rice" });
  const disclosure = screen
    .getByText("Ingredients", { exact: true })
    .closest("details")!;
  disclosure.open = true;
  expect(screen.getByText("basil", { exact: true })).toBeVisible();
  expect(screen.getAllByText("Cross-contact is not verified.")).toHaveLength(1);
});
