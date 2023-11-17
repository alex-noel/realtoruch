import { describe, expect, it } from "vitest";
import {
  removeFilterSummary,
  resetFiltersForCity,
  summarizeFilters,
} from "../src/filterSummary";
import { DEFAULT_FILTERS } from "../src/types";

describe("filter summaries and reset behavior", () => {
  it("shows default apartments without counting them as a deviation", () => {
    expect(summarizeFilters(DEFAULT_FILTERS)).toEqual({
      items: [{ key: "property_type", label: "Apartments" }],
      deviationCount: 0,
    });
  });

  it("omits all property types because it is not an applied constraint", () => {
    expect(
      summarizeFilters({ ...DEFAULT_FILTERS, property_type: "all" }),
    ).toEqual({
      items: [],
      deviationCount: 1,
    });
  });

  it("summarizes applied rent, area, advertiser, commission, risk, and map constraints", () => {
    const filters = {
      ...DEFAULT_FILTERS,
      min_price: 2000,
      max_price: 5000,
      min_area: 50.5,
      max_area: 80,
      advertiser: "private",
      no_commission: true,
      hide_suspicious: true,
      polygon: "1,2;3,4",
    };
    const result = summarizeFilters(filters);
    expect(result.items.map(({ label }) => label)).toEqual([
      "Apartments",
      "Base rent ≥ 2 000 PLN",
      "Base rent < 5 000 PLN",
      "Area ≥ 50,5 m²",
      "Area ≤ 80 m²",
      "Direct offers",
      "Explicitly zero commission",
      "Hide risk signals",
      "Drawn map area",
    ]);
    expect(result.deviationCount).toBe(8);
  });

  it("removes one summary constraint while preserving the rest", () => {
    const filters = {
      ...DEFAULT_FILTERS,
      city: "Warszawa",
      min_price: 2000,
      min_area: 50,
      no_commission: true,
    };
    const result = removeFilterSummary(filters, "min_area");
    expect(result.min_area).toBeUndefined();
    expect(result.min_price).toBe(2000);
    expect(result.no_commission).toBe(true);
    expect(result.city).toBe("Warszawa");
  });

  it("preserves area precision and labels legacy inclusive rent maxima", () => {
    const summary = summarizeFilters({
      ...DEFAULT_FILTERS,
      max_price: 5000,
      max_price_exclusive: false,
      min_area: 50.555,
      max_area: 0.0000001,
    });
    expect(summary.items.map(({ label }) => label)).toEqual([
      "Apartments",
      "Base rent ≤ 5 000 PLN",
      "Area ≥ 50,555 m²",
      "Area ≤ 0,0000001 m²",
    ]);
  });

  it("resets filters to defaults for the selected city and clears query and polygon", () => {
    const reset = resetFiltersForCity({
      ...DEFAULT_FILTERS,
      city: "Warszawa",
      q: "Old Town",
      polygon: "1,2;3,4",
      min_price: 4000,
      no_commission: true,
      property_type: "house",
    });
    expect(reset.city).toBe("Warszawa");
    expect(reset.q).toBe("");
    expect(reset.polygon).toBeUndefined();
    expect(reset.min_price).toBeUndefined();
    expect(reset.no_commission).toBe(false);
    expect(reset.property_type).toBe("apartment");
    expect(summarizeFilters(reset).deviationCount).toBe(0);
  });
});
