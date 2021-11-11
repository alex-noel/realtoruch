import { describe, expect, it } from "vitest";
import { vi } from "vitest";
import { describeSource } from "../src/components/SourceStatus";
import type { SourceHealth } from "../src/types";

vi.mock("react-native", () => ({
  Platform: { OS: "web" },
  StyleSheet: { create: (styles: unknown) => styles },
}));
vi.mock("../src/components/UI", () => ({ Button: () => null }));

const now = Date.parse("2026-11-11T12:01:00Z");
const provider: SourceHealth = {
  name: "otodom",
  enabled: true,
  cadence_minutes: 60,
  last_observed_at: "2026-11-11T11:45:00Z",
  stored_adverts: 2,
  health: {
    city: "Kraków",
    status: "succeeded",
    started_at: "2026-11-11T09:50:00Z",
    finished_at: "2026-11-11T10:00:00Z",
    last_success_at: "2026-11-11T10:00:00Z",
    errors: [],
    limited: false,
  },
};

describe("city source collection status", () => {
  it("keeps the failed noon attempt separate from the delayed 10:00 success", () => {
    const health = {
      ...provider.health!,
      status: "failed" as const,
      started_at: "2026-11-11T11:50:00Z",
      finished_at: "2026-11-11T12:00:00Z",
      errors: [{ kind: "Raw private exception text", http_status: 500 }],
    };
    const status = describeSource({ ...provider, health }, now);
    expect(status).toMatchObject({
      state: "failed",
      freshness: "delayed",
      label: "Collection failed",
      lastSuccess: "2026-11-11T10:00:00Z",
      latestAttempt: "2026-11-11T12:00:00Z",
      latestObservation: "2026-11-11T11:45:00Z",
    });
    expect(JSON.stringify(status)).not.toContain("Raw private exception text");
  });

  it("labels disabled OLX and keeps stored adverts distinct from collection", () => {
    expect(
      describeSource(
        {
          ...provider,
          name: "olx",
          enabled: false,
          health: null,
          cadence_minutes: null,
          last_observed_at: null,
          stored_adverts: 1,
        },
        now,
      ),
    ).toMatchObject({
      provider: "OLX",
      state: "disabled",
      freshness: "unknown",
      lastSuccess: null,
      latestAttempt: null,
      label: "Automatic collection unavailable",
      storedAdverts: "1 stored advert. Stored adverts can include imports.",
    });
  });

  it("treats exactly twice the configured cadence as fresh", () => {
    const boundary = Date.parse("2026-11-11T12:00:00Z");
    expect(describeSource(provider, boundary).state).toBe("fresh");
    expect(describeSource(provider, boundary + 1).state).toBe("delayed");
    expect(
      describeSource({ ...provider, cadence_minutes: 120 }, now).state,
    ).toBe("fresh");
  });

  it.each([
    null,
    "unknown",
    "2026-02-30T10:00:00Z",
    "2026-11-11T12:02:00Z",
    "2026-11-11T10:00:00",
  ])(
    "keeps a missing, impossible or future success (%s) unknown",
    (last_success_at) => {
      expect(
        describeSource(
          { ...provider, health: { ...provider.health!, last_success_at } },
          now,
        ),
      ).toMatchObject({
        freshness: "unknown",
        state: "unknown",
        lastSuccess: null,
      });
    },
  );

  it.each([null, 0, -1, 0.5, 10_081, Number.NaN])(
    "keeps invalid cadence (%s) unknown",
    (cadence_minutes) => {
      expect(
        describeSource({ ...provider, cadence_minutes }, now).freshness,
      ).toBe("unknown");
    },
  );

  it("distinguishes never collected, running, partial, interrupted and access-blocked attempts", () => {
    expect(describeSource({ ...provider, health: null }, now).state).toBe(
      "never-collected",
    );
    const status = (changes: Partial<NonNullable<SourceHealth["health"]>>) =>
      describeSource(
        { ...provider, health: { ...provider.health!, ...changes } },
        now,
      ).state;
    expect(status({ status: "running", finished_at: null })).toBe("collecting");
    expect(status({ status: "partial" })).toBe("partial");
    expect(status({ status: "succeeded", limited: true })).toBe("partial");
    expect(status({ status: "interrupted" })).toBe("failed");
    expect(
      status({
        status: "failed",
        errors: [{ kind: "SourceAccessError", http_status: 403 }],
      }),
    ).toBe("access-blocked");
    expect(
      status({
        status: "failed",
        errors: [{ kind: "SourceAccessError", http_status: 429 }],
      }),
    ).toBe("access-blocked");
    expect(
      status({
        status: "failed",
        errors: [{ kind: "SourceAccessError", http_status: null }],
      }),
    ).toBe("access-blocked");
  });
});
