import { expect, test } from "@playwright/test";
import { database } from "./database";
import type { Schema, StreamEvent } from "../../src/lib/api/client";
import { consumeEvents } from "../../src/lib/api/sse";

for (const category of ["restaurant", "recipe"] as const) {
  test(`P11-05 administrator ${category} preview, cancelled deletion, validation and session recovery`, async ({
    page,
  }) => {
    const name = `Release ${category} basil rice ${Date.now()}`;
    const collection = category === "restaurant" ? "restaurants" : "recipes";
    await page.goto("/admin");
    await page
      .getByLabel("Administrator password")
      .fill("phase9-fixture-password");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
    await page.getByLabel("Entry category").selectOption(category);
    await page
      .getByText("Extract fields from a description", { exact: true })
      .click();
    await page.getByLabel("Unstructured description").fill(`${name}. Italian.`);
    await page.getByRole("button", { name: "Preview fields" }).click();
    await expect(page.getByLabel("Name", { exact: true })).toHaveValue(name);
    expect(
      database(`SELECT count(*) FROM ${collection} WHERE name=%s`, [name]),
    ).toEqual([[0]]);
    // Discard a preview using the explicit New entry action: no write is sent.
    await page.getByRole("button", { name: "New entry", exact: true }).click();
    await expect(page.getByLabel("Name", { exact: true })).toHaveValue("");
    expect(
      database(
        "SELECT count(*) FROM source_records WHERE raw_payload->>'name'=%s",
        [name],
      ),
    ).toEqual([[0]]);
    await page.getByLabel("Unstructured description").fill(`${name}. Italian.`);
    await page.getByRole("button", { name: "Preview fields" }).click();
    await expect(page.getByLabel("Name", { exact: true })).toHaveValue(name);
    if (category === "recipe") {
      await page
        .getByLabel("Ingredients (one per line)")
        .fill("rice\ntomato\nbasil");
      await page
        .getByLabel("Directions (one per line)")
        .fill("Simmer rice with tomato and basil.");
    } else {
      await page.getByLabel("Location", { exact: true }).fill("San Francisco");
      await page
        .getByLabel("Signature dishes (one per line)")
        .fill("Tomato basil rice");
    }
    await page
      .getByRole("button", { name: `Create ${category}`, exact: true })
      .click();
    await expect(
      page.getByRole("status").filter({ hasText: `Saved ${name}` }),
    ).toBeVisible();
    const [[id]] = database(`SELECT id FROM ${collection} WHERE name=%s`, [
      name,
    ]) as [string][];
    function snapshot() {
      return database(
        `SELECT c.name,c.version,d.id,d.text,e.id,e.embedding::text FROM ${collection} c JOIN source_records r ON r.${category}_id=c.id JOIN documents d ON d.source_record_id=r.id JOIN text_embeddings e ON e.document_id=d.id WHERE c.id=%s ORDER BY d.id`,
        [id],
      );
    }
    const before = snapshot();
    expect(before).toHaveLength(1);
    const deleteButton = page.getByRole("button", {
      name: `Delete ${name}`,
      exact: true,
    });
    let deletes = 0;
    page.on("request", (request) => {
      if (request.method() === "DELETE" && request.url().endsWith(`/${id}`))
        deletes++;
    });
    await deleteButton.click();
    await expect(page.getByRole("dialog")).toContainText(name);
    await page.getByRole("button", { name: "Keep it", exact: true }).click();
    await expect(page.getByRole("dialog")).toBeHidden();
    await deleteButton.click();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toBeHidden();
    expect(deletes).toBe(0);
    expect(snapshot()).toEqual(before);

    // The browser receives a real server validation error, retaining its draft.
    const draft = `${name} draft`;
    await page.getByLabel("Name", { exact: true }).fill(draft);
    if (category === "recipe")
      await page
        .getByLabel("Total time (source string)")
        .fill("invalid duration");
    else
      await page
        .getByLabel("Signature dishes (one per line)")
        .fill("x".repeat(4001));
    const failed = page.waitForResponse(
      (response) =>
        response.request().method() === "PATCH" &&
        response.url().endsWith(`/${id}`),
    );
    await page
      .getByRole("button", { name: "Save changes", exact: true })
      .click();
    expect((await failed).status()).toBe(422);
    await expect(page.getByRole("main").getByRole("alert")).toBeVisible();
    await expect(page.getByLabel("Name", { exact: true })).toHaveValue(draft);
    expect(snapshot()).toEqual(before);
    if (category === "recipe")
      await page.getByLabel("Total time (source string)").fill("20 minutes");
    else
      await page
        .getByLabel("Signature dishes (one per line)")
        .fill("Tomato basil rice");

    // Revoke the actual server-side admin session from another tab/API request.
    const grant = await page.request.post("/api/v1/admin/session", {
      headers: { origin: "http://127.0.0.1:3100" },
      data: { password: "phase9-fixture-password" },
    });
    expect(grant.status()).toBe(201);
    expect(
      (
        await page.request.delete("/api/v1/admin/session", {
          headers: {
            origin: "http://127.0.0.1:3100",
            "x-csrf-token": (await grant.json()).csrf_token,
          },
        })
      ).status(),
    ).toBe(204);
    await page
      .getByRole("button", { name: "Save changes", exact: true })
      .click();
    await expect(page.getByRole("main").getByRole("alert")).toContainText(
      "Sign in again; your draft is preserved",
    );
    expect(snapshot()).toEqual(before);
    await expect(page.getByLabel("Name", { exact: true })).toHaveValue(draft);
    await page
      .getByLabel("Administrator password")
      .fill("phase9-fixture-password");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
    await page
      .getByRole("button", { name: "Save changes", exact: true })
      .click();
    await expect(
      page.getByRole("status").filter({ hasText: `Saved ${draft}, version 2` }),
    ).toBeVisible();
    expect(snapshot()[0]).toEqual(expect.arrayContaining([draft, 2]));

    const created = await page.request.post("/api/v1/conversations");
    const conversation = (await created.json()).id;
    async function recommendations() {
      const response = await page.request.post(
        `/api/v1/conversations/${conversation}/messages`,
        {
          data: {
            message: draft,
            categories: [category],
            client_request_id: crypto.randomUUID(),
          },
        },
      );
      expect(response.status()).toBe(200);
      const events: StreamEvent[] = [];
      await consumeEvents(
        new Response(await response.text()),
        conversation,
        (event) => events.push(event),
      );
      expect(events.at(-1)).toMatchObject({
        event: "done",
        outcome: "completed",
      });
      const result = events.find((event) => event.event === "recommendations");
      if (!result || result.event !== "recommendations")
        throw new Error("Missing validated recommendations");
      return result.result;
    }
    const searchable = await recommendations();
    expect(
      searchable.recommendations.some((item) => item.entity.id === id),
    ).toBe(true);
    const history = await (
      await page.request.get(`/api/v1/conversations/${conversation}`)
    ).json();
    const evidence: Schema["CandidateEvidence"][] =
      history.messages.at(-1).payload.evidence;
    expect(
      evidence.some(
        (item) =>
          item.entity.id === id &&
          item.dense_rank != null &&
          item.lexical_rank != null,
      ),
    ).toBe(true);
    await page
      .getByRole("button", { name: `Delete ${draft}`, exact: true })
      .click();
    await page
      .getByRole("button", { name: "Confirm deletion", exact: true })
      .click();
    await expect(
      page.getByRole("status").filter({ hasText: `Deleted ${draft}` }),
    ).toBeVisible();
    expect(snapshot()).toEqual([]);
    expect(
      (await page.request.get(`/api/v1/${collection}/${id}`)).status(),
    ).toBe(404);
    expect(
      (await recommendations()).recommendations.some(
        (item) => item.entity.id === id,
      ),
    ).toBe(false);
    expect(
      (
        await page.request.delete(`/api/v1/conversations/${conversation}`)
      ).status(),
    ).toBe(200);
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await expect(
      page.getByRole("button", { name: "Sign in", exact: true }),
    ).toBeVisible();
  });
}
