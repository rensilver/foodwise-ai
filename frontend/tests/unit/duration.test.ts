import { expect, test } from "vitest";
import { formatDuration } from "../../src/lib/duration";
test("source durations are formatted only when the whole value is understood", () => {
  expect(formatDuration("PT1H30M")).toBe("1 hr 30 min");
  expect(formatDuration("PT45M")).toBe("45 min");
  expect(formatDuration("30 mins")).toBe("30 mins");
  expect(formatDuration("overnight")).toBe("overnight");
  expect(formatDuration(null)).toBe("Unknown");
});
