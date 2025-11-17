import type { Draft } from "./marketplaceApi";
import { parseFilterNumber } from "./filterNumbers";
export const ownerNumberRules = {
  rent_pln: {
    label: "MONTHLY BASE RENT (PLN)",
    min: 1,
    max: 1000000,
    integer: true,
    optional: false,
  },
  fees_pln: {
    label: "FEES (PLN; LEAVE BLANK IF UNKNOWN)",
    min: 0,
    max: 1000000,
    integer: true,
    optional: true,
  },
  deposit_pln: {
    label: "DEPOSIT (PLN)",
    min: 0,
    max: 10000000,
    integer: true,
    optional: true,
  },
  commission_pln: {
    label: "COMMISSION (PLN; 0 IF NONE)",
    min: 0,
    max: 1000000,
    integer: true,
    optional: true,
  },
  area_m2: {
    label: "AREA (M²)",
    min: 0,
    max: 10000,
    integer: false,
    optional: false,
  },
  rooms: { label: "ROOMS", min: 1, max: 100, integer: true, optional: false },
  floor: { label: "FLOOR", min: -2, max: 200, integer: true, optional: true },
} as const;
export type OwnerNumberKey = keyof typeof ownerNumberRules;
export type OwnerNumbers = Record<OwnerNumberKey, string>;
export type OwnerField = keyof Draft;
export type OwnerErrors = Partial<Record<OwnerField, string>>;
export const ownerNumbersFrom = (draft: Draft): OwnerNumbers =>
  Object.fromEntries(
    Object.keys(ownerNumberRules).map((key) => [
      key,
      draft[key as OwnerNumberKey] == null
        ? ""
        : String(draft[key as OwnerNumberKey]),
    ]),
  ) as OwnerNumbers;
export function validateOwner(
  draft: Draft,
  raw: OwnerNumbers,
  latitude: string,
  longitude: string,
  photoLinks: string,
): { errors: OwnerErrors; value?: Draft } {
  const errors: OwnerErrors = {};
  const value = { ...draft, amenities: [...draft.amenities] };
  for (const [key, min, max] of [
    ["title", 5, 240],
    ["description", 20, 20000],
    ["city", 2, 100],
    ["district", 0, 100],
    ["region", 0, 100],
    ["address", 3, 240],
  ] as const) {
    const text = draft[key].trim();
    if (text.length < min || text.length > max)
      errors[key] = min
        ? `Enter ${min}–${max} characters.`
        : `Use at most ${max} characters.`;
    value[key] = text;
  }
  for (const key of Object.keys(ownerNumberRules) as OwnerNumberKey[]) {
    const rule = ownerNumberRules[key],
      text = raw[key].trim();
    const parsed =
      key === "floor" && /^-\d+$/.test(text)
        ? { valid: Number.isSafeInteger(Number(text)), value: Number(text) }
        : parseFilterNumber(text, rule.integer);
    if (!text && rule.optional) {
      (value[key] as number | null) = null;
      continue;
    }
    if (
      !parsed.valid ||
      parsed.value === undefined ||
      parsed.value < rule.min ||
      parsed.value > rule.max ||
      (key === "area_m2" && parsed.value === 0)
    ) {
      errors[key] =
        `Enter ${rule.integer ? "a whole number" : "a number"} ${key === "area_m2" ? "greater than 0 and up to" : `from ${rule.min} to`} ${rule.max}.${rule.optional ? " Leave blank if unknown." : ""}`;
    } else (value[key] as number) = parsed.value;
  }
  for (const [key, text, min, max] of [
    ["lat", latitude, 49, 55],
    ["lon", longitude, 14, 24.2],
  ] as const) {
    const parsed = parseFilterNumber(text);
    if (
      !parsed.valid ||
      parsed.value === undefined ||
      parsed.value < min ||
      parsed.value > max
    )
      errors[key] =
        `Enter a ${key === "lat" ? "latitude" : "longitude"} from ${min} to ${max} for a home in Poland.`;
    else value[key] = parsed.value;
  }
  const links = photoLinks
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  if (links.length > 30) errors.images = "Use at most 30 photo links.";
  else if (
    links.some((link) => {
      try {
        const url = new URL(link);
        return url.protocol !== "https:" || !!url.username || !!url.password;
      } catch {
        return true;
      }
    })
  )
    errors.images =
      "Use complete HTTPS photo links without credentials, one per line.";
  value.images = links;
  if (value.amenities.length > 40)
    errors.amenities = "Use at most 40 amenities.";
  return Object.keys(errors).length ? { errors } : { errors, value };
}
