import { defineConfig, devices } from "@playwright/test";
if (!process.env.TEST_DATABASE_URL)
  throw new Error(
    "Set TEST_DATABASE_URL to the isolated localhost foodwise_test database. See evaluation/phase9/README.md.",
  );
const baseURL = "http://127.0.0.1:3100";
export default defineConfig({
  testDir: "./tests/integration",
  forbidOnly: true,
  retries: 0,
  workers: 1,
  timeout: 60_000,
  reporter: "list",
  use: { baseURL, trace: "retain-on-failure" },
  projects: [
    { name: "real-api-chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: [
    {
      command:
        "cd ../backend && uv run --locked python scripts/serve_frontend_fixture.py",
      url: "http://127.0.0.1:8119/api/v1/health/live",
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        OMP_NUM_THREADS: "1",
        MKL_NUM_THREADS: "1",
        OPENBLAS_NUM_THREADS: "1",
      },
    },
    {
      command: "pnpm build && node scripts/start-e2e.mjs",
      url: `${baseURL}/health/live`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        NEXT_TELEMETRY_DISABLED: "1",
        FOODWISE_API_ORIGIN: "http://127.0.0.1:8119",
      },
    },
  ],
});
