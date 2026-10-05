import { describe, expect, it, vi } from "vitest";
import {
  historyPath,
  localInputValue,
  parseCustomRange,
  presets,
  randomUsage,
  summarize,
} from "../src/lib/usage";

describe("time filters", () => {
  it.each(presets)("sends the $value preset to Django", (preset) => {
    expect(historyPath({ kind: "preset", value: preset.value })).toBe(
      `/api/user/actions?timeframe=${preset.value}`,
    );
  });
  it("converts local datetime values to UTC and sends only custom bounds", () => {
    const filter = parseCustomRange("2026-10-03T09:00", "2026-10-03T12:00");
    expect(filter).toEqual({
      kind: "custom",
      start: new Date("2026-10-03T09:00").toISOString(),
      end: new Date("2026-10-03T12:00").toISOString(),
    });
    const url = new URL(historyPath(filter), "http://localhost");
    expect(url.searchParams.has("timeframe")).toBe(false);
    expect(url.searchParams.get("start_date")).toBe(
      new Date("2026-10-03T09:00").toISOString(),
    );
  });
  it("rejects missing, invalid and reversed dates", () => {
    expect(() => parseCustomRange("", "2026-10-03T12:00")).toThrow(
      "valid start and end",
    );
    expect(() => parseCustomRange("bad", "also bad")).toThrow();
    expect(() =>
      parseCustomRange("2026-10-04T12:00", "2026-10-03T12:00"),
    ).toThrow("on or after");
  });
  it("accepts an equal start and end", () => {
    expect(parseCustomRange("2026-10-03T12:00", "2026-10-03T12:00").kind).toBe(
      "custom",
    );
  });
  it("formats datetime-local inputs using local calendar components", () => {
    expect(localInputValue(new Date(2026, 9, 3, 9, 5))).toBe(
      "2026-10-03T09:05",
    );
  });
});

describe("usage statistics and simulation", () => {
  it("finds the newest record regardless of input ordering and preserves input", () => {
    const records = [
      { usage_id: 1, usage: 20, timestamp: "2026-10-03T09:00:00Z" },
      { usage_id: 2, usage: 80, timestamp: "2026-10-03T10:00:00Z" },
    ];
    const stats = summarize(records);
    expect(stats).toMatchObject({
      latest: 80,
      average: 50,
      peak: 80,
      count: 2,
    });
    expect(stats.ordered.map((record) => record.usage_id)).toEqual([2, 1]);
    expect(records[0].usage_id).toBe(1);
  });
  it("represents missing measurements separately from zero usage", () => {
    expect(summarize([])).toMatchObject({
      latest: null,
      average: null,
      peak: null,
      count: 0,
    });
    expect(
      summarize([{ usage_id: 1, usage: 0, timestamp: "2026-10-03T09:00:00Z" }]),
    ).toMatchObject({ latest: 0, average: 0, peak: 0, count: 1 });
  });
  it("generates numbers including both 0 and 100", () => {
    const random = vi.spyOn(Math, "random");
    random.mockReturnValue(0);
    expect(randomUsage()).toBe(0);
    random.mockReturnValue(0.999999);
    expect(randomUsage()).toBe(100);
    random.mockRestore();
  });
});
