import { spawnSync } from "node:child_process";
import { readFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const target = join(root, "src/lib/api/generated.ts");
const check = process.argv.includes("--check");
const temporary = check
  ? mkdtempSync(join(tmpdir(), "foodwise-api-contracts-"))
  : null;
try {
  const output = temporary ? join(temporary, "generated.ts") : target;
  const result = spawnSync(
    process.execPath,
    [
      join(root, "node_modules/openapi-typescript/bin/cli.js"),
      join(root, "src/lib/api/openapi.json"),
      "--output",
      output,
    ],
    { encoding: "utf8" },
  );
  if (result.status !== 0) {
    process.stderr.write(result.stderr);
    process.exitCode = 1;
  } else if (
    check &&
    readFileSync(output, "utf8") !== readFileSync(target, "utf8")
  ) {
    console.error("API type drift: run pnpm api:generate.");
    process.exitCode = 1;
  } else {
    console.log(
      check ? "API types match the OpenAPI schema." : "API types generated.",
    );
  }
} finally {
  if (temporary) rmSync(temporary, { recursive: true, force: true });
}
