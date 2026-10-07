import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    // Keep local validation bounded on memory-constrained development machines.
    maxWorkers: 1,
    environment: "jsdom",
    include: ["tests/components/**/*.test.tsx", "tests/unit/**/*.test.ts"],
    setupFiles: ["./tests/setup.ts"],
  },
});
