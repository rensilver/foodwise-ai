import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { rice, recommendations } from "../fixtures/catalog";
const id = recommendations.conversation_id;
const cafe = {
  ...rice,
  data: {
    id: "cafe",
    name: "Basil cafe",
    source_id: "fixture",
    source_record_id: "cafe",
    cuisine: "Italian",
    location: "San Francisco",
    price_band: 2,
  },
  images: [],
  citations: [
    {
      ...rice.citations[0],
      id: "doc-cafe",
      document_id: "doc-cafe",
      record_id: "cafe",
      entity: { category: "restaurant", id: "cafe" },
      excerpt: "Italian cafe in San Francisco.",
    },
  ],
};
const both = {
  ...recommendations,
  result: {
    ...recommendations.result,
    recommendations: [
      ...recommendations.result.recommendations,
      {
        entity: { category: "restaurant", id: "cafe" },
        explanation: "Italian cafe in San Francisco.",
        citation_ids: ["doc-cafe"],
        limitations: [],
      },
    ],
  },
  evidence: [
    ...recommendations.evidence,
    {
      ...recommendations.evidence[0],
      entity: { category: "restaurant", id: "cafe" },
      citations: cafe.citations,
    },
  ],
};
async function mock(page: Page, result: object = both) {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/recipes")
      return route.fulfill({
        json: { items: [], total: 0, offset: 0, limit: 6 },
      });
    if (path.endsWith("/messages"))
      return route.fulfill({
        contentType: "text/event-stream",
        body: `event: recommendations\ndata: ${JSON.stringify(result)}\n\nevent: done\ndata: ${JSON.stringify({ event: "done", conversation_id: id, run_id: recommendations.run_id, outcome: "completed" })}\n\n`,
      });
    if (path.endsWith("/images/rice-image"))
      return route.fulfill({ status: 404 });
    if (path.endsWith("/recipes/rice")) return route.fulfill({ json: rice });
    if (path.endsWith("/restaurants/cafe"))
      return route.fulfill({ json: cafe });
    if (path.endsWith("/conversations"))
      return route.fulfill({
        json: { id, created_at: "2026-10-05T12:00:00Z" },
      });
    return route.fulfill({
      json: {
        id,
        messages: [
          {
            id: "m",
            role: "assistant",
            run_id: recommendations.run_id,
            payload: result,
          },
        ],
        preferences: null,
      },
    });
  });
}
async function axe(page: Page) {
  const scan = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(scan.violations).toEqual([]);
}
for (const width of [320, 390, 768, 1440])
  test(`accessible first use and meal results at ${width}px`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await mock(page);
    await page.goto("/");
    await page.keyboard.press("Tab");
    await expect(
      page.getByRole("link", { name: "Skip to content" }),
    ).toBeFocused();
    await axe(page);
    await page.screenshot({
      path: info.outputPath(`first-use-${width}.png`),
      fullPage: true,
    });
    await page
      .getByLabel("Message", { exact: true })
      .fill("Italian tomato rice");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "Basil cafe" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Tomato rice" }),
    ).toBeVisible();
    await expect(
      page.getByText("Image unavailable.", { exact: false }),
    ).toBeVisible();
    await page.getByText("Sources (1)", { exact: true }).first().click();
    await axe(page);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: info.outputPath(`results-sources-${width}.png`),
      fullPage: true,
    });
    await page.getByRole("button", { name: "Delete conversation" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await axe(page);
    await page.keyboard.press("Escape");
    await expect(
      page.getByRole("button", { name: "Delete conversation" }),
    ).toBeFocused();
  });
test("strict empty evidence, error and clarification states remain accessible", async ({
  page,
}, info) => {
  const empty = {
    ...recommendations,
    result: {
      recommendations: [],
      limitations: ["No candidates have supported peanut compliance."],
    },
  };
  await mock(page, empty);
  await page.goto("/");
  await page
    .getByLabel("Message", { exact: true })
    .fill("Strict peanut allergy");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(
    page.getByText("No supported matches.", { exact: false }),
  ).toBeVisible();
  await axe(page);
  await page.screenshot({
    path: info.outputPath("strict-no-match.png"),
    fullPage: true,
  });
  await page.unrouteAll({ behavior: "wait" });
  await mock(page, {
    event: "clarification",
    conversation_id: id,
    run_id: recommendations.run_id,
    question: "Which city would you like?",
  });
  await page.reload();
  await expect(page.getByText("Which city would you like?")).toBeVisible();
  await axe(page);
  await page.unrouteAll({ behavior: "wait" });
  await mock(page, {
    event: "error",
    conversation_id: id,
    run_id: recommendations.run_id,
    code: "dependency_unavailable",
    retryable: true,
  });
  await page.reload();
  await expect(page.getByRole("main").getByRole("alert")).toBeVisible();
  await axe(page);
});
test("pending activity, interruption, draft retention and 200% equivalent zoom", async ({
  page,
}, info) => {
  await page.setViewportSize({ width: 720, height: 450 });
  await mock(page);
  await page.route("**/api/v1/conversations/*/messages", async (route) =>
    route.fulfill({
      contentType: "text/event-stream",
      body: `data: ${JSON.stringify({ event: "progress", conversation_id: id, run_id: recommendations.run_id, agent: "nutrition_expert", activity: "started" })}\n\n`,
    }),
  );
  await page.goto("/");
  await page.getByLabel("Message", { exact: true }).fill("rice");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "Connection interrupted",
  );
  await expect(page.getByLabel("Message", { exact: true })).toHaveValue("rice");
  await axe(page);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("interrupted.png"),
    fullPage: true,
  });
});
for (const width of [390, 1440])
  test(`administrator conflict and expiry recovery at ${width}px`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width, height: 900 });
    let conflict = false;
    await page.route("**/api/v1/**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith("/session"))
        return route.fulfill({
          json: {
            csrf_token: "fixture-csrf",
            expires_at: "2099-01-01T00:00:00Z",
          },
        });
      if (route.request().method() === "PATCH") {
        conflict = true;
        return route.fulfill({
          status: 409,
          json: { error: { code: "conflict", message: "Conflict" } },
        });
      }
      if (path.endsWith("/restaurants/cafe"))
        return route.fulfill({
          json: conflict
            ? {
                ...cafe,
                version: 2,
                data: { ...cafe.data, name: "Latest cafe" },
              }
            : cafe,
        });
      return route.fulfill({
        json: { items: [cafe], total: 1, limit: 100, offset: 0 },
      });
    });
    await page.goto("/admin");
    await axe(page);
    await page.getByLabel("Administrator password").fill("fixture-password");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.getByLabel("Existing entry").selectOption("cafe");
    await expect(page.getByLabel("Name", { exact: true })).toHaveValue(
      "Basil cafe",
    );
    await page.getByLabel("Name", { exact: true }).fill("My unsaved cafe");
    await page
      .getByRole("button", { name: "Save changes", exact: true })
      .click();
    await expect(
      page.getByRole("heading", {
        name: "Latest record: Latest cafe, version 2",
      }),
    ).toBeVisible();
    await expect(page.getByLabel("Name", { exact: true })).toHaveValue(
      "My unsaved cafe",
    );
    await axe(page);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: info.outputPath(`admin-conflict-${width}.png`),
      fullPage: true,
    });
    await page
      .getByRole("button", { name: "Keep my draft with latest version" })
      .click();
    await page.route("**/api/v1/admin/restaurants/cafe", (route) =>
      route.fulfill({
        status: 401,
        json: { error: { code: "unauthorized", message: "Session expired" } },
      }),
    );
    await page
      .getByRole("button", { name: "Save changes", exact: true })
      .click();
    await expect(
      page.getByRole("button", { name: "Sign in", exact: true }),
    ).toBeVisible();
    await expect(page.getByLabel("Name", { exact: true })).toHaveValue(
      "My unsaved cafe",
    );
    await axe(page);
  });
