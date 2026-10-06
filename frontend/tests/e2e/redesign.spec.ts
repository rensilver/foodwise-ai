import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { rice } from "../fixtures/catalog";

async function catalog(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.includes("/images/"))
      return route.fulfill({ status: 404 });
    if (url.pathname.endsWith("/recipes/rice"))
      return route.fulfill({ json: rice });
    const offset = Number(url.searchParams.get("offset") || 0);
    return route.fulfill({
      json: {
        items: url.searchParams.get("q") === "missing" ? [] : [rice],
        total: 2,
        limit: 1,
        offset,
      },
    });
  });
}
async function accessible(page: Page) {
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
}
for (const width of [320, 390, 768, 1024, 1440]) {
  test(`discovery, drawer draft retention and recipe details at ${width}px`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await catalog(page);
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: "Tomato rice" }),
    ).toBeVisible();
    await accessible(page);
    await page.screenshot({
      path: info.outputPath(`discovery-${width}.png`),
      fullPage: true,
    });
    if (width < 1120)
      await page
        .getByRole("button", { name: "Menu and preferences", exact: true })
        .click();
    await page.getByText("Edit preferences", { exact: true }).click();
    const input = page.getByLabel("Restriction", { exact: true });
    await input.fill("milk");
    // Preserve the actual input node and its unsubmitted draft through reflow.
    await input.evaluate((node) =>
      node.setAttribute("data-draft-node", "original"),
    );
    await page.setViewportSize({ width: 1440, height: 600 });
    await expect(input).toHaveValue("milk");
    await expect(input).toHaveAttribute("data-draft-node", "original");
    await page.setViewportSize({ width: 390, height: 600 });
    const trigger = page.getByRole("button", {
      name: "Menu and preferences",
      exact: true,
    });
    await trigger.click();
    await expect(input).toHaveValue("milk");
    await page.getByRole("button", { name: "Add restriction" }).click();
    await accessible(page);
    await page.screenshot({
      path: info.outputPath(`drawer-${width}.png`),
      fullPage: true,
    });
    await page.getByRole("button", { name: "Close menu" }).focus();
    await page.keyboard.press("Shift+Tab");
    expect(
      await page.evaluate(() => !!document.activeElement?.closest("dialog")),
    ).toBe(true);
    await page.keyboard.press("Escape");
    await expect(trigger).toBeFocused();
    await expect(page.getByRole("dialog")).toBeHidden();
    await expect(page.locator(".mobile-restrictions")).toContainText("milk");
    await page
      .getByRole("link", { name: "View details for Tomato rice" })
      .click();
    await expect(
      page.getByRole("heading", { name: "Ingredients", exact: true }),
    ).toBeVisible();
    await accessible(page);
    await page.screenshot({
      path: info.outputPath(`detail-${width}.png`),
      fullPage: true,
    });
    await page.getByRole("link", { name: "Return to results" }).click();
    await expect(page).toHaveURL("http://127.0.0.1:3100/");
  });
}
test("catalog preserves filters through pagination and history, and resets explicitly", async ({
  page,
}, info) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await catalog(page);
  await page.goto("/catalog/recipes?q=rice");
  await expect(
    page.getByRole("link", { name: "Recipes", exact: true }),
  ).toHaveAttribute("aria-current", "page");
  await page.getByRole("button", { name: "Italian", exact: true }).click();
  await page.getByRole("button", { name: "Apply filters" }).click();
  await expect(page).toHaveURL(/q=rice&cuisine=Italian$/);
  await page.getByRole("link", { name: "Next page" }).click();
  await expect(page).toHaveURL(/q=rice&cuisine=Italian&offset=1$/);
  await page.goBack();
  await expect(page.getByLabel("Search by name")).toHaveValue("rice");
  await expect(page.getByLabel("Cuisine", { exact: true })).toHaveValue(
    "Italian",
  );
  await page.getByRole("link", { name: "Reset filters", exact: true }).click();
  await expect(page).toHaveURL("http://127.0.0.1:3100/catalog/recipes");
  await expect(page.getByLabel("Search by name")).toHaveValue("");
  await accessible(page);
  await page.screenshot({
    path: info.outputPath("recipe-catalog.png"),
    fullPage: true,
  });
  await page.getByLabel("Search by name").fill("missing");
  await page.getByRole("button", { name: "Apply filters" }).click();
  await expect(page.getByText(/No entries match/)).toBeVisible();
});
test("discovery outage keeps meal requests editable", async ({ page }) => {
  await page.route("**/api/v1/recipes?*", (route) =>
    route.fulfill({ status: 503, json: {} }),
  );
  await page.goto("/");
  await expect(page.getByText(/Recipe preview unavailable/)).toBeVisible();
  await page.getByLabel("Message", { exact: true }).fill("Chickpea dinner");
  await expect(
    page.getByRole("button", { name: "Send", exact: true }),
  ).toBeEnabled();
  await accessible(page);
});
