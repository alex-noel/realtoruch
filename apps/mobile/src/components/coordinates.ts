export function readCoordinate(value: string, limit: number): number | null {
  const decimal = value.trim().replace(",", ".");
  if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(decimal)) return null;
  const number = Number(decimal);
  return Number.isFinite(number) && Math.abs(number) <= limit ? number : null;
}
