export type FilterNumberResult =
  | { valid: true; value: number | undefined }
  | { valid: false; reason: "format" | "integer" | "safe-integer" };

/** Parse a non-negative decimal using either a comma or a dot separator. */
export function parseFilterNumber(
  raw: string,
  integer = false,
): FilterNumberResult {
  const text = raw.trim();
  if (!text) return { valid: true, value: undefined };
  if (integer) {
    if (!/^\d+$/.test(text)) return { valid: false, reason: "integer" };
  } else if (!/^\d+(?:[.,]\d+)?$/.test(text)) {
    return { valid: false, reason: "format" };
  }
  const value = Number(text.replace(",", "."));
  if (integer && !Number.isSafeInteger(value))
    return { valid: false, reason: "safe-integer" };
  return Number.isFinite(value)
    ? { valid: true, value }
    : { valid: false, reason: "format" };
}
