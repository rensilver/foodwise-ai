import { expect, test } from "@playwright/test";
import { PRODUCT_NAME } from "../../src/lib/product";

test("the production scaffold serves its page and liveness endpoint", async ({
  page,
  request,
}) => {
  const browserErrors: string[] = [];
  const scriptStatuses: number[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  page.on("response", (response) => {
    if (response.url().includes("/_next/static/") && response.url().endsWith(".js")) {
      scriptStatuses.push(response.status());
    }
  });
  await page.goto("/");

  await expect(page).toHaveTitle(PRODUCT_NAME);
  await expect(page.getByRole("main")).toBeVisible();
  await expect(
    page.getByRole("heading", { level: 1, name: PRODUCT_NAME }),
  ).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  expect(browserErrors).toEqual([]);
  expect(scriptStatuses.length).toBeGreaterThan(0);
  expect(scriptStatuses.every((status) => status === 200)).toBe(true);

  const health = await request.get("/health/live");
  expect(health.status()).toBe(200);
  expect(await health.json()).toEqual({ status: "alive" });
});
