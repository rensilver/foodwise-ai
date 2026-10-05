import { readFileSync, readdirSync } from "node:fs";
import { resolve, relative, dirname } from "node:path";
import ts from "typescript";
import { expect, test } from "vitest";

const sourceRoot = resolve("src");
const files = readdirSync(sourceRoot, { recursive: true })
  .map(String)
  .filter((name) => /\.tsx?$/.test(name) && !name.endsWith("generated.ts"));

test("frontend imports respect presentation and generated-contract boundaries", () => {
  for (const name of files) {
    const source = ts.createSourceFile(
      name,
      readFileSync(resolve(sourceRoot, name), "utf8"),
      ts.ScriptTarget.Latest,
      true,
    );
    const layer = name.split("/")[0];
    for (const statement of source.statements) {
      if (
        !ts.isImportDeclaration(statement) ||
        !ts.isStringLiteral(statement.moduleSpecifier)
      )
        continue;
      const specifier = statement.moduleSpecifier.text;
      expect(specifier, name).not.toMatch(
        /^(?:openai|langfuse|@langfuse|@opentelemetry|pg|postgres|prisma|@prisma|@langchain)(?:\/|$)/,
      );
      if (!specifier.startsWith(".")) continue;
      const target = relative(
        sourceRoot,
        resolve(dirname(resolve(sourceRoot, name)), specifier),
      );
      expect(target, name).not.toMatch(/^\.\./);
      if (layer === "features") expect(target, name).not.toMatch(/^app\//);
      if (layer === "lib")
        expect(target, name).not.toMatch(/^(?:app|features|components)\//);
      if (layer === "components")
        expect(target, name).not.toMatch(/^(?:app|features)\//);
    }
    if (name.endsWith("/page.tsx")) {
      expect(source.text, name).not.toMatch(
        /\b(?:fetch|useState|useEffect)\s*\(/,
      );
    }
    if (layer !== "app") expect(source.text, name).not.toMatch(/process\.env/);
  }
});

test("standalone packaging includes styling, local assets and its internal API origin", () => {
  const dockerfile = readFileSync(
    resolve("../infra/frontend.Dockerfile"),
    "utf8",
  );
  expect(dockerfile).toContain("frontend/postcss.config.mjs");
  expect(dockerfile).toContain("COPY frontend/public ./public");
  expect(dockerfile).toContain("/app/public ./public");
  const compose = readFileSync(resolve("../compose.yaml"), "utf8");
  const frontend = compose.slice(compose.indexOf("\n  frontend:"));
  expect(frontend).toContain("FOODWISE_API_ORIGIN: http://backend:8000");
  expect(frontend).not.toMatch(/(?:env_file|OPENAI|DATABASE_URL|LANGFUSE)/);
});
