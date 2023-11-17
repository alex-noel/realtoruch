import { DEFAULT_FILTERS, type Filters } from "./types";

export type FilterSummaryKey =
  | "q"
  | "district"
  | "min_price"
  | "max_price"
  | "polygon"
  | "min_area"
  | "max_area"
  | "rooms"
  | "advertiser"
  | "no_commission"
  | "hide_suspicious"
  | "property_type"
  | "amenity";

export type FilterSummaryItem = {
  key: FilterSummaryKey;
  label: string;
};

export type FilterSummary = {
  items: FilterSummaryItem[];
  deviationCount: number;
};

const deviations: (keyof Filters)[] = [
  "q",
  "district",
  "min_price",
  "max_price",
  "polygon",
  "min_area",
  "max_area",
  "rooms",
  "advertiser",
  "no_commission",
  "hide_suspicious",
  "property_type",
  "amenity",
];

function decimalText(value: number) {
  const text = String(value);
  const [coefficient, exponentText] = text.toLowerCase().split("e");
  if (exponentText === undefined) return coefficient;
  const exponent = Number(exponentText);
  const sign = coefficient.startsWith("-") ? "-" : "";
  const unsigned = sign ? coefficient.slice(1) : coefficient;
  const decimalAt = unsigned.indexOf(".");
  const digits = unsigned.replace(".", "");
  const position = (decimalAt < 0 ? unsigned.length : decimalAt) + exponent;
  if (position <= 0) return `${sign}0.${"0".repeat(-position)}${digits}`;
  if (position >= digits.length)
    return `${sign}${digits}${"0".repeat(position - digits.length)}`;
  return `${sign}${digits.slice(0, position)}.${digits.slice(position)}`;
}

const format = (value: number) => {
  const [whole, fraction] = decimalText(value).split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  return fraction ? `${grouped},${fraction}` : grouped;
};

const amenityLabel: Record<string, string> = {
  balcony: "Balcony",
  pets: "Pets welcome",
  parking: "Parking",
  furnished: "Furnished",
  lift: "Lift",
  dishwasher: "Dishwasher",
};

export function summarizeFilters(filters: Filters): FilterSummary {
  const items: FilterSummaryItem[] = [];
  if (filters.property_type !== "all") {
    items.push({
      key: "property_type",
      label:
        filters.property_type === "apartment"
          ? "Apartments"
          : filters.property_type === "room"
            ? "Rooms"
            : `${filters.property_type[0]?.toUpperCase() ?? ""}${filters.property_type.slice(1)}s`,
    });
  }
  if (filters.q) items.push({ key: "q", label: `Search: ${filters.q}` });
  if (filters.district)
    items.push({ key: "district", label: `Neighborhood: ${filters.district}` });
  if (filters.min_price != null)
    items.push({
      key: "min_price",
      label: `Base rent ≥ ${format(filters.min_price)} PLN`,
    });
  if (filters.max_price != null)
    items.push({
      key: "max_price",
      label: `Base rent ${filters.max_price_exclusive ? "<" : "≤"} ${format(filters.max_price)} PLN`,
    });
  if (filters.min_area != null)
    items.push({
      key: "min_area",
      label: `Area ≥ ${format(filters.min_area)} m²`,
    });
  if (filters.max_area != null)
    items.push({
      key: "max_area",
      label: `Area ≤ ${format(filters.max_area)} m²`,
    });
  if (filters.rooms != null)
    items.push({
      key: "rooms",
      label: `${filters.rooms} ${filters.rooms === 1 ? "room" : "rooms"}`,
    });
  if (filters.advertiser !== "all")
    items.push({
      key: "advertiser",
      label: filters.advertiser === "private" ? "Direct offers" : "Agencies",
    });
  if (filters.amenity)
    items.push({
      key: "amenity",
      label: amenityLabel[filters.amenity] ?? filters.amenity,
    });
  if (filters.no_commission)
    items.push({ key: "no_commission", label: "Explicitly zero commission" });
  if (filters.hide_suspicious)
    items.push({ key: "hide_suspicious", label: "Hide risk signals" });
  if (filters.polygon) items.push({ key: "polygon", label: "Drawn map area" });

  return {
    items,
    deviationCount: deviations.filter(
      (key) => !Object.is(filters[key], DEFAULT_FILTERS[key]),
    ).length,
  };
}

export function removeFilterSummary(
  filters: Filters,
  key: FilterSummaryKey,
): Filters {
  switch (key) {
    case "q":
      return { ...filters, q: "" };
    case "district":
      return { ...filters, district: "" };
    case "min_price":
      return { ...filters, min_price: undefined };
    case "max_price":
      return { ...filters, max_price: undefined };
    case "polygon":
      return { ...filters, polygon: undefined };
    case "min_area":
      return { ...filters, min_area: undefined };
    case "max_area":
      return { ...filters, max_area: undefined };
    case "rooms":
      return { ...filters, rooms: undefined };
    case "advertiser":
      return { ...filters, advertiser: "all" };
    case "no_commission":
      return { ...filters, no_commission: false };
    case "hide_suspicious":
      return { ...filters, hide_suspicious: false };
    case "property_type":
      return { ...filters, property_type: "all" };
    case "amenity":
      return { ...filters, amenity: "" };
  }
}

export function resetFiltersForCity(filters: Filters): Filters {
  return { ...DEFAULT_FILTERS, city: filters.city, q: "", polygon: undefined };
}
