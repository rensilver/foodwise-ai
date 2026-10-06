import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
export function database(query: string, values: unknown[] = []): unknown[] {
  const code =
    'import json,os,sys,psycopg\nwith psycopg.connect(os.environ["TEST_DATABASE_URL"]) as connection:\n rows=connection.execute(sys.argv[1],json.loads(sys.argv[2])).fetchall()\n print(json.dumps(rows,default=str))';
  return JSON.parse(
    execFileSync(
      "../backend/.venv/bin/python",
      ["-c", code, query, JSON.stringify(values)],
      { encoding: "utf8" },
    ),
  );
}
export function providerCounts(): {
  profile_calls: number;
  cancelled_calls: number;
} {
  return JSON.parse(
    readFileSync(
      // Relative artifact roots use the fixture server's backend working directory.
      resolve(
        "../backend",
        process.env.FOODWISE_BROWSER_ARTIFACTS ??
          "../.local-tmp/phase9/integration",
        "provider-counts.json",
      ),
      "utf8",
    ),
  );
}
