import { defineConfig, devices } from "@playwright/test";

const baseURL = "http://127.0.0.1:3100";

export default defineConfig({
  testDir: "./tests/e2e",
  forbidOnly: true,
  retries: 0,
  workers: 1,
  reporter: "list",
  use: { baseURL, trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "pnpm build && node scripts/start-e2e.mjs",
    url: `${baseURL}/health/live`,
    reuseExistingServer: false,
    timeout: 300_000,
    env: { NEXT_TELEMETRY_DISABLED: "1" },
  },
});
