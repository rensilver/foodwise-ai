import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { cpSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const root = fileURLToPath(new URL("../", import.meta.url));
const secret = "synthetic-private-canary";

const privateEnvironment = {
  OPENAI_API_KEY: secret, TAVILY_API_KEY: secret, DATABASE_URL: secret,
  ADMIN_PASSWORD_HASH: secret, MEDIA_ROOT: secret, MCP_SERVER_URL: secret,
  POSTGRES_PASSWORD: secret, FOODWISE_DB_PASSWORD: secret,
};

function loadConfiguration(extraEnv = {}, directory = root, development = false) {
  return spawnSync(process.execPath, ["--input-type=module", "-e", `
    import loadConfig from 'next/dist/server/config.js';
    import constants from 'next/constants.js';
    import { getNextPublicEnvironmentVariables, getNextConfigEnv }
      from 'next/dist/lib/static-env.js';
    try {
      const config = await loadConfig.default(
        constants.${development ? "PHASE_DEVELOPMENT_SERVER" : "PHASE_PRODUCTION_BUILD"}, ${JSON.stringify(directory)}
      );
      console.log(JSON.stringify({
        ...getNextPublicEnvironmentVariables(), ...getNextConfigEnv(config)
      }));
    } catch (error) {
      console.error(error.message);
      process.exitCode = 2;
    }
  `], { cwd: root, env: extraEnv, encoding: "utf8", timeout: 15000 });
}

test("clean frontend configuration exposes no browser environment definitions", () => {
  const result = loadConfiguration();
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout), {});
  assert.ok(!result.stdout.includes(secret));
});

test("backend variables are rejected individually without printing values", () => {
  for (const name of [...Object.keys(privateEnvironment), "OPENAI_MODEL", "OPENAI_VISION_MODEL"]) {
    const result = loadConfiguration({ [name]: secret });
    assert.equal(result.status, 2, result.stderr);
    assert.ok(result.stderr.includes(name));
    assert.match(result.stderr, /Remove backend settings/);
    assert.ok(!(result.stdout + result.stderr).includes(secret));
  }
});

test("Next dotenv loading applies the public-variable guard in dev and build", () => {
  const directory = mkdtempSync(join(tmpdir(), "foodwise-public-env-"));
  try {
    cpSync(join(root, "next.config.mjs"), join(directory, "next.config.mjs"));
    writeFileSync(join(directory, ".env.local"), `NEXT_PUBLIC_SECRET=${secret}\n`);
    for (const development of [true, false]) {
      const result = loadConfiguration({}, directory, development);
      assert.equal(result.status, 2, result.stderr);
      assert.match(result.stderr, /Remove NEXT_PUBLIC_/);
      assert.ok(!(result.stdout + result.stderr).includes(secret));
    }
    writeFileSync(join(directory, ".env.local"), `OPENAI_API_KEY=${secret}\n`);
    const result = loadConfiguration({}, directory);
    assert.equal(result.status, 2, result.stderr);
    assert.match(result.stderr, /Remove backend settings/);
    assert.ok(!(result.stdout + result.stderr).includes(secret));
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test("isolated production browser assets contain no private environment values", { timeout: 60000 }, () => {
  const directory = mkdtempSync(join(tmpdir(), "foodwise-client-build-"));
  try {
    cpSync(join(root, "next.config.mjs"), join(directory, "next.config.mjs"));
    cpSync(join(root, "package.json"), join(directory, "package.json"));
    symlinkSync(join(root, "node_modules"), join(directory, "node_modules"), "dir");
    mkdirSync(join(directory, "app"));
    writeFileSync(join(directory, "app/layout.js"),
      "export default function Layout({children}) { return <html><body>{children}</body></html>; }");
    writeFileSync(join(directory, "app/page.js"), `
      'use client';
      export default function Page() {
        return <pre>{JSON.stringify([
          process.env.OPENAI_API_KEY, process.env.TAVILY_API_KEY,
          process.env.DATABASE_URL, process.env.ADMIN_PASSWORD_HASH,
          process.env.MEDIA_ROOT, process.env.MCP_SERVER_URL
        ])}</pre>;
      }
    `);
    const command = [
      join(root, "node_modules/next/dist/bin/next"), "build", directory, "--webpack",
    ];
    const build = (environment) => spawnSync(process.execPath, command, {
      cwd: directory, env: { ...environment, NEXT_TELEMETRY_DISABLED: "1" },
      encoding: "utf8", timeout: 25000,
    });
    const rejected = build(privateEnvironment);
    assert.notEqual(rejected.status, 0);
    assert.match(rejected.stderr, /Remove backend settings/);
    assert.ok(!(rejected.stdout + rejected.stderr).includes(secret));
    const result = build({});
    assert.equal(result.status, 0, result.stdout + result.stderr);
    const assets = readdirSync(join(directory, ".next/static"), { recursive: true })
      .filter((name) => name.endsWith(".js"));
    assert.ok(assets.length > 0, "Browser JavaScript must be produced");
    for (const name of assets) {
      assert.ok(!readFileSync(join(directory, ".next/static", name), "utf8").includes(secret), name);
    }
    assert.ok(!readFileSync(join(directory, ".next/server/app/index.html"), "utf8").includes(secret));
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test("public environment variables fail before bundling without printing values", () => {
  for (const name of ["NEXT_PUBLIC_OPENAI_API_KEY", "NEXT_PUBLIC_DATABASE_URL", "NEXT_PUBLIC_CUSTOM_TOKEN"]) {
    const result = loadConfiguration({ [name]: secret });
    assert.equal(result.status, 2, result.stderr);
    assert.match(result.stderr, /Remove NEXT_PUBLIC_/);
    assert.ok(!result.stderr.includes(secret));
    assert.equal(result.stdout, "");
  }
});
