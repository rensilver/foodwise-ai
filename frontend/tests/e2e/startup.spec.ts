import { expect, test } from "@playwright/test";
import { PRODUCT_NAME } from "../../src/lib/product";
import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";

test("actual production browser assets exclude backend credentials and telemetry SDKs", () => {
  const roots = [".next/static", ".next/server/app"];
  let checked = 0;
  for (const root of roots) {
    for (const name of readdirSync(root, { recursive: true }).map(String)) {
      if (!name.endsWith(root.endsWith("/static") ? ".js" : ".html")) continue;
      const content = readFileSync(resolve(root, name), "utf8");
      expect(content, name).not.toMatch(
        /synthetic-private-canary|LANGFUSE_(?:SECRET_KEY|PUBLIC_KEY|BASE_URL|HOST)|@langfuse|langfuse\.com|OTEL_EXPORTER_OTLP_HEADERS/,
      );
      checked += 1;
    }
  }
  expect(checked).toBeGreaterThan(0);
  const manifest = JSON.parse(readFileSync("package.json", "utf8"));
  expect(
    Object.keys({ ...manifest.dependencies, ...manifest.devDependencies }).join(
      " ",
    ),
  ).not.toMatch(/langfuse|opentelemetry/);
});
test("production workspace serves local fonts, branding and liveness", async ({
  page,
  request,
}) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  await page.goto("/");
  await expect(page).toHaveTitle(PRODUCT_NAME);
  await expect(
    page.getByRole("heading", { name: "What sounds good?" }),
  ).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  expect(
    await page.evaluate(async () => {
      await document.fonts.ready;
      return (
        document.fonts.check("600 40px Bricolage") &&
        document.fonts.check('400 16px "Source Sans"')
      );
    }),
  ).toBe(true);
  expect(browserErrors).toEqual([]);
  expect(await (await request.get("/health/live")).json()).toEqual({
    status: "alive",
  });
});
