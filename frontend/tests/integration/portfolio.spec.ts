import { expect, test, type Page } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { join } from "node:path";
import { database } from "./database";

const destination = process.env.FOODWISE_PORTFOLIO_DIR;
test.skip(
  !destination,
  "Opt-in P11-06 capture requires a private output directory",
);

async function capture(page: Page, filename: string) {
  await expect
    .poll(() =>
      page.locator("img").evaluateAll((images) =>
        images.every((node) => {
          const image = node as HTMLImageElement;
          return image.complete && image.naturalWidth > 0;
        }),
      ),
    )
    .toBe(true);
  await page.evaluate(async () => {
    await document.fonts.ready;
    const label = document.createElement("div");
    label.id = "portfolio-capture-label";
    label.textContent =
      "Portfolio rehearsal · synthetic inputs · controlled inference · trends unavailable";
    Object.assign(label.style, {
      position: "fixed",
      bottom: "4px",
      right: "4px",
      maxWidth: "calc(100vw - 8px)",
      padding: "6px 10px",
      background: "#fff",
      color: "#17251d",
      border: "1px solid #aaa",
      font: "12px sans-serif",
      zIndex: "9999",
    });
    document.body.append(label);
  });
  const visibleText = await page.locator("body").innerText();
  expect(visibleText).not.toMatch(
    /phase9-fixture-password|\.local-tmp|postgresql:\/\/|sk-[A-Za-z0-9]{20}|tvly-[A-Za-z0-9]{20}/,
  );
  await page.screenshot({
    path: join(destination!, filename),
    fullPage: true,
    animations: "disabled",
    mask: [page.locator('input[type="password"]')],
  });
  await page
    .locator("#portfolio-capture-label")
    .evaluate((node) => node.remove());
}

async function send(page: Page, message: string) {
  await page.getByLabel("Message", { exact: true }).fill(message);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Stop", exact: true }),
  ).toBeHidden({
    timeout: 30_000,
  });
}

async function deleteConversation(page: Page) {
  await page
    .getByRole("button", { name: "Delete conversation", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm deletion", exact: true })
    .click();
  await expect(page).toHaveURL("http://127.0.0.1:3100/");
}

test("P11-06 portfolio: text sources, hard restriction, mobile image and admin steps", async ({
  page,
}) => {
  test.setTimeout(90_000);
  await mkdir(destination!, { recursive: true });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.getByLabel("Message", { exact: true })).toBeVisible();
  await capture(page, "01-home.png");

  await page.getByRole("radio", { name: "Cook", exact: true }).check();
  await send(page, "Classic Margherita Pizza");
  await expect(
    page.getByRole("heading", {
      name: "Classic Margherita Pizza",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByText("Sources (", { exact: false }).first().click();
  await expect(page.locator("blockquote").first()).toContainText(
    "Classic Margherita Pizza",
  );
  await capture(page, "02-text-citations.png");
  await page.reload();
  await expect(
    page.getByRole("heading", {
      name: "Classic Margherita Pizza",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByText("Edit preferences", { exact: true }).click();
  await page.getByLabel("Restriction", { exact: true }).fill("milk");
  await page
    .getByRole("button", { name: "Add restriction", exact: true })
    .click();
  await send(page, "Classic Margherita Pizza");
  await expect(
    page.getByText("No supported matches.", { exact: false }).last(),
  ).toBeVisible();
  await expect(page.getByText("milk (allergen, explicit)")).toBeVisible();
  await capture(page, "03-hard-restriction.png");
  await deleteConversation(page);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("radio", { name: "Cook", exact: true }).check();
  await page
    .getByLabel("Add image", { exact: true })
    .setInputFiles("../data/synthetic_recipe_images/recipe1.png");
  await expect(page.getByText("Image ready.", { exact: true })).toBeVisible();
  await send(page, "Classic Margherita Pizza");
  const image = page.getByRole("img", {
    name: "Catalog image associated with Classic Margherita Pizza",
  });
  await expect(image).toBeVisible();
  await expect
    .poll(() =>
      image.evaluate((node) => (node as HTMLImageElement).naturalWidth),
    )
    .toBeGreaterThan(0);
  const conversationId = new URL(page.url()).pathname.split("/").at(-1)!;
  const history = await (
    await page.request.get(`/api/v1/conversations/${conversationId}`)
  ).json();
  expect(
    history.messages
      .at(-1)
      .payload.evidence.some(
        (evidence: { image_score?: number }) =>
          typeof evidence.image_score === "number",
      ),
  ).toBe(true);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await capture(page, "04-image-mobile.png");
  await deleteConversation(page);

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/admin");
  await page
    .getByLabel("Administrator password")
    .fill("phase9-fixture-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Sign out", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Entry category").selectOption("recipe");
  await page
    .getByText("Extract fields from a description", { exact: true })
    .click();
  const name = "Portfolio tomato basil rice";
  await page.getByLabel("Unstructured description").fill(`${name}. Italian.`);
  await page
    .getByRole("button", { name: "Preview fields", exact: true })
    .click();
  await expect(page.getByLabel("Name", { exact: true })).toHaveValue(name);
  expect(
    database("SELECT count(*) FROM recipes WHERE name=%s", [name]),
  ).toEqual([[0]]);
  await capture(page, "05-admin-preview.png");
  await page
    .getByLabel("Ingredients (one per line)")
    .fill("rice\ntomato\nbasil");
  await page
    .getByLabel("Directions (one per line)")
    .fill("Simmer rice with tomato and basil.");
  await page
    .getByRole("button", { name: "Create recipe", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: `Saved ${name}` }),
  ).toBeVisible();
  const edited = `${name} edited`;
  await page.getByLabel("Name", { exact: true }).fill(edited);
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "version 2" }),
  ).toBeVisible();
  await capture(page, "06-admin-saved.png");
  await page
    .getByRole("button", { name: `Delete ${edited}`, exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText(edited);
  await capture(page, "07-delete-confirmation.png");
  await page.getByRole("button", { name: "Keep it", exact: true }).click();
  expect(
    database("SELECT version FROM recipes WHERE name=%s", [edited]),
  ).toEqual([[2]]);
  await page
    .getByRole("button", { name: `Delete ${edited}`, exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm deletion", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Deleted" }),
  ).toBeVisible();
  expect(
    database("SELECT count(*) FROM recipes WHERE name=%s", [edited]),
  ).toEqual([[0]]);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
});
