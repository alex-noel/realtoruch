import type { Draft } from "../marketplaceApi";

const editable = [
  "title",
  "description",
  "city",
  "district",
  "region",
  "address",
  "area_m2",
  "rooms",
  "floor",
  "rent_pln",
  "fees_pln",
  "deposit_pln",
  "commission_pln",
  "property_type",
  "amenities",
] as const;
const equal = (one: unknown, two: unknown) =>
  JSON.stringify(one) === JSON.stringify(two);
export function photoLinks(images: string[]) {
  return images.map((value) => value.trim()).filter(Boolean);
}

export function mergeAdvertEdits(
  original: Draft,
  local: Draft,
  latest: Draft,
): Draft {
  const merged = { ...latest };
  function apply<K extends (typeof editable)[number]>(field: K) {
    if (!equal(original[field], local[field])) merged[field] = local[field];
  }
  editable.forEach(apply);
  const baseLinks = photoLinks(original.images);
  const localLinks = photoLinks(local.images);
  const latestLinks = photoLinks(latest.images);
  if (equal(baseLinks, localLinks)) return merged;
  if (equal(baseLinks, latestLinks)) return { ...merged, images: localLinks };
  const originalSet = new Set(baseLinks);
  // Keep independent additions and respect either editor's removal. The merge
  // choice explicitly prefers the local order if both sides changed photos.
  const links = [
    ...localLinks.filter(
      (url) => !originalSet.has(url) || latestLinks.includes(url),
    ),
    ...latestLinks.filter(
      (url) => !originalSet.has(url) && !localLinks.includes(url),
    ),
  ];
  return { ...merged, images: [...new Set(links)] };
}
