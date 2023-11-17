import { describe, expect, it } from "vitest";
import { parseFilterNumber } from "../src/filterNumbers";

describe("filter number parsing", () => {
  it("accepts comma and dot decimals for area values", () => {
    expect(parseFilterNumber("50,5")).toEqual({ valid: true, value: 50.5 });
    expect(parseFilterNumber("50.5")).toEqual({ valid: true, value: 50.5 });
  });

  it("keeps blanks unset and rejects malformed, negative, nonfinite, and partial values", () => {
    expect(parseFilterNumber("  ")).toEqual({ valid: true, value: undefined });
    for (const raw of [
      "50,",
      "50..5",
      "50,5.1",
      "-50",
      "Infinity",
      "NaN",
      "1e2",
      ".5",
      "+5",
    ]) {
      expect(parseFilterNumber(raw).valid, raw).toBe(false);
    }
  });

  it("requires rent values to be whole PLN amounts", () => {
    expect(parseFilterNumber("5000", true)).toEqual({
      valid: true,
      value: 5000,
    });
    expect(parseFilterNumber("5000.5", true)).toEqual({
      valid: false,
      reason: "integer",
    });
    expect(parseFilterNumber("5,000", true)).toEqual({
      valid: false,
      reason: "integer",
    });
    expect(parseFilterNumber(String(Number.MAX_SAFE_INTEGER), true)).toEqual({
      valid: true,
      value: Number.MAX_SAFE_INTEGER,
    });
    expect(parseFilterNumber("9007199254740992", true)).toEqual({
      valid: false,
      reason: "safe-integer",
    });
  });
});
