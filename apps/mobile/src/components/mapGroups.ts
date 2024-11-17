import type { Listing } from "../types";

type Coordinate = { latitude: number; longitude: number };
type Pixel = { x: number; y: number };
type Viewport = { width: number; height: number };
type Region = Coordinate & { latitudeDelta: number; longitudeDelta: number };

export type MapGroup = {
  key: string;
  coordinate: Coordinate;
  homes: Listing[];
};

export const MAP_MARKER_SIZE = { width: 80, height: 44 };

export function groupMapHomes(
  homes: readonly Listing[],
  project: (coordinate: Coordinate) => Pixel,
): MapGroup[] {
  const points = homes.flatMap((home) => {
    const { lat, lon } = home;
    if (
      home.status !== "active" || lat === null || lon === null ||
      !Number.isFinite(lat) || !Number.isFinite(lon) ||
      Math.abs(lat) > 90 || Math.abs(lon) > 180
    ) return [];
    const coordinate = { latitude: lat, longitude: lon };
    return [{ home, coordinate, pixel: project(coordinate) }];
  });
  const parents = points.map((_, index) => index);
  function root(index: number) {
    while (parents[index] !== index) index = parents[index];
    return index;
  }
  // Join intersecting marker boxes, including chains of overlaps. There are
  // only up to 24 homes on a discovery page.
  for (let index = 0; index < points.length; index++) {
    const a = points[index].pixel;
    for (let previous = 0; previous < index; previous++) {
      const b = points[previous].pixel;
      if (
        Math.abs(a.x - b.x) < MAP_MARKER_SIZE.width &&
        Math.abs(a.y - b.y) < MAP_MARKER_SIZE.height
      ) parents[root(index)] = root(previous);
    }
  }
  const groups = new Map<number, MapGroup>();
  points.forEach(({ home, coordinate }, index) => {
    const parent = root(index);
    const group = groups.get(parent);
    if (group) group.homes.push(home);
    else groups.set(parent, { key: home.id, coordinate, homes: [home] });
  });
  return [...groups.values()];
}

export function projectNativeMapPoint(coordinate: Coordinate, region: Region, viewport: Viewport): Pixel {
  const longitudeOffset = (coordinate.longitude - region.longitude + 540) % 360 - 180;
  return {
    x: longitudeOffset * viewport.width / Math.max(region.longitudeDelta, Number.EPSILON),
    y: (coordinate.latitude - region.latitude) * viewport.height / Math.max(region.latitudeDelta, Number.EPSILON),
  };
}
