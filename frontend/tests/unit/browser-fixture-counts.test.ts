// @vitest-environment node
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, relative, resolve } from "node:path";
import { afterEach, expect, test, vi } from "vitest";
import { providerCounts } from "../integration/database";

const directories: string[] = [];
afterEach(() => {
  vi.unstubAllEnvs();
  for (const directory of directories.splice(0))
    rmSync(directory, { recursive: true, force: true });
});

test("browser counters come from this run's configured artifact directory", () => {
  const directory = mkdtempSync(join(tmpdir(), "foodwise-browser-counts-"));
  directories.push(directory);
  vi.stubEnv("FOODWISE_BROWSER_ARTIFACTS", directory);
  writeFileSync(
    join(directory, "provider-counts.json"),
    JSON.stringify({ profile_calls: 41, cancelled_calls: 17 }),
  );
  expect(providerCounts()).toEqual({ profile_calls: 41, cancelled_calls: 17 });
});

test("a missing current-run receipt cannot fall back to old browser counters", () => {
  const directory = mkdtempSync(join(tmpdir(), "foodwise-browser-counts-"));
  directories.push(directory);
  vi.stubEnv("FOODWISE_BROWSER_ARTIFACTS", directory);
  expect(() => providerCounts()).toThrow();
});

test("relative artifact roots match the backend fixture server's working directory", () => {
  const directory = mkdtempSync(join(tmpdir(), "foodwise-browser-counts-"));
  directories.push(directory);
  vi.stubEnv(
    "FOODWISE_BROWSER_ARTIFACTS",
    relative(resolve("../backend"), directory),
  );
  writeFileSync(
    join(directory, "provider-counts.json"),
    JSON.stringify({ profile_calls: 3, cancelled_calls: 2 }),
  );
  expect(providerCounts()).toEqual({ profile_calls: 3, cancelled_calls: 2 });
});
