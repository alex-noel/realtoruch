import { describe, expect, it } from "vitest";
import {
  ownerNumbersFrom,
  validateOwner,
  type OwnerNumberKey,
} from "../src/ownerValidation";
import type { Draft } from "../src/marketplaceApi";
const draft: Draft = {
  title: "A valid rental",
  description: "A sufficiently long description of this rental.",
  city: "Kraków",
  district: "",
  region: "",
  address: "Testowa 13",
  lat: 50.06,
  lon: 19.94,
  rent_pln: 4000,
  fees_pln: null,
  deposit_pln: null,
  commission_pln: 0,
  area_m2: 50,
  rooms: 2,
  floor: null,
  property_type: "apartment",
  amenities: ["unknown-stored-value"],
  images: [],
};
const validate = (
  overrides: Partial<Draft> = {},
  raw: Partial<Record<OwnerNumberKey, string>> = {},
  lat = "50.06",
  lon = "19.94",
  images = "",
) =>
  validateOwner(
    { ...draft, ...overrides },
    { ...ownerNumbersFrom(draft), ...raw },
    lat,
    lon,
    images,
  );
describe("owner validation matches AdvertBody bounds", () => {
  it("preserves comma decimals, negative floor, optional null, zero and unknown amenities", () => {
    const result = validate(
      {},
      { area_m2: "50,5", floor: "-2", fees_pln: "0" },
    );
    expect(result.errors).toEqual({});
    expect(result.value).toMatchObject({
      area_m2: 50.5,
      floor: -2,
      fees_pln: 0,
      deposit_pln: null,
      amenities: ["unknown-stored-value"],
    });
  });
  it.each<[OwnerNumberKey, string]>([
    ["rent_pln", "0"],
    ["rent_pln", "1000001"],
    ["rent_pln", "2.5"],
    ["area_m2", "0"],
    ["area_m2", "10000.1"],
    ["area_m2", "50,"],
    ["rooms", "1.5"],
    ["rooms", "101"],
    ["floor", "-3"],
    ["floor", "201"],
    ["fees_pln", "-1"],
    ["fees_pln", "1000001"],
    ["deposit_pln", "10000001"],
    ["commission_pln", "1000001"],
    ["rooms", ""],
    ["area_m2", "NaN"],
  ])("rejects %s=%s without changing other fields", (key, value) => {
    const result = validate({}, { [key]: value });
    expect(result.value).toBeUndefined();
    expect(Object.keys(result.errors)).toEqual([key]);
  });
  it("accepts all exact server maxima and Poland boundaries", () => {
    expect(
      validate(
        {},
        {
          rent_pln: "1000000",
          fees_pln: "1000000",
          deposit_pln: "10000000",
          commission_pln: "1000000",
          area_m2: "10000",
          rooms: "100",
          floor: "200",
        },
        "49",
        "24.2",
      ).errors,
    ).toEqual({});
    expect(validate({}, {}, "55", "14").errors).toEqual({});
  });
  it.each([
    ["48.99", "19.9", "lat"],
    ["50", "24.21", "lon"],
    ["51.", "19.9", "lat"],
    ["", "19.9", "lat"],
  ])("rejects invalid Poland coordinates %s/%s", (lat, lon, key) => {
    expect(Object.keys(validate({}, {}, lat, lon).errors)).toEqual([key]);
  });
  it("validates required text and optional text maxima", () => {
    expect(
      Object.keys(
        validate({
          title: " bad ",
          description: "short",
          city: "K",
          address: "x",
          district: "x".repeat(101),
          region: "x".repeat(101),
        }).errors,
      ),
    ).toEqual([
      "title",
      "description",
      "city",
      "district",
      "region",
      "address",
    ]);
    expect(
      validate({
        title: "x".repeat(241),
        description: "x".repeat(20001),
        city: "x".repeat(101),
        address: "x".repeat(241),
      }).value,
    ).toBeUndefined();
  });
  it("preserves valid HTTPS links and rejects unsafe or over-limit input", () => {
    expect(
      validate(
        {},
        {},
        "50",
        "19",
        "https://example.test/a\n\nhttps://example.test/b",
      ).value?.images,
    ).toHaveLength(2);
    for (const links of [
      "http://example.test/a",
      "https://user:secret@example.test/a",
      "not a URL",
      Array(31).fill("https://example.test/a").join("\n"),
    ])
      expect(validate({}, {}, "50", "19", links).errors.images).toBeTruthy();
    expect(
      validate({ amenities: Array(41).fill("unknown") }).errors.amenities,
    ).toBeTruthy();
  });
});
