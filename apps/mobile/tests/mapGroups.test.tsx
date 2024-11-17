import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { Listing } from "../src/types";

vi.mock("react-native", async () => vi.importActual("react-native-web"));
vi.mock("react-native-safe-area-context", () => ({ SafeAreaView: "div" }));
vi.mock("lucide-react-native/icons/check", () => ({ default: "span" }));
vi.mock("lucide-react-native/icons/x", () => ({ default: "span" }));
vi.mock("react-native-maps", () => ({
  default: ({ children }: { children: React.ReactNode }) => <section>{children}</section>,
  Marker: ({
    accessibilityLabel,
    coordinate,
    children,
  }: {
    accessibilityLabel?: string;
    coordinate: { latitude: number; longitude: number };
    children: React.ReactNode;
  }) => <div aria-label={accessibilityLabel} data-anchor={`${coordinate.latitude},${coordinate.longitude}`}>{children}</div>,
  Polygon: () => null,
  Polyline: () => null,
}));

import { groupMapHomes, projectNativeMapPoint } from "../src/components/mapGroups";
import NativeMap from "../src/components/PropertyMap";

function home(id: string, lat: number | null, lon: number | null, status = "active"): Listing {
  return {
    id, lat, lon, status, title: `Fixture home ${id}`, rent_pln: 4500,
  } as Listing;
}

const project = ({ latitude, longitude }: { latitude: number; longitude: number }) =>
  ({ x: longitude, y: latitude });

describe("current-page map groups", () => {
  it("groups five coincident homes, keeping every ID and an unchanged anchor coordinate", () => {
    const homes = ["a", "b", "c", "d", "e"].map(id => home(id, 50.05, 19.93));
    const groups = groupMapHomes(homes, project);
    expect(groups).toEqual([{
      key: "a", coordinate: { latitude: 50.05, longitude: 19.93 }, homes,
    }]);
  });

  it("merges intersecting boxes through a bridge without combining distant homes", () => {
    const homes = [home("west", 0, -65), home("east", 0, 65), home("bridge", 0, 0), home("far", 70, 65)];
    const groups = groupMapHomes(homes, project);
    expect(groups.map(group => group.homes.map(item => item.id))).toEqual([["west", "east", "bridge"], ["far"]]);
    const zoomed = groupMapHomes(homes, coordinate => ({ x: 2 * coordinate.longitude, y: 2 * coordinate.latitude }));
    expect(zoomed.map(group => group.homes.length)).toEqual([1, 1, 1, 1]);
  });

  it("ignores inactive, missing and invalid coordinates and returns an empty group list when appropriate", () => {
    const excluded = [
      home("delisted", 50, 19, "inactive"), home("unknown", 50, 19, "unknown"),
      home("missing", null, 19), home("invalid", 50, Number.NaN), home("invalid-range", 100, 19),
    ];
    expect(groupMapHomes(excluded, project)).toEqual([]);
    const unit = home("valid", 50, 19);
    expect(groupMapHomes([...excluded, unit], project)[0].homes).toEqual([unit]);
  });
});

describe("native adapter", () => {
  it("renders the group count and only the actual group anchor, plus separate homes", () => {
    const homes = [
      ...Array.from({ length: 5 }, (_, index) => home(String(index), 50.06, 19.94)),
      home("separate", 50.10, 19.99), home("delisted", 50.06, 19.94, "inactive"),
    ];
    const markup = renderToStaticMarkup(
      <NativeMap homes={homes} selected="2" city="Kraków" onSelect={() => {}} onPolygonChange={() => {}} />,
    );
    expect(markup).toContain('aria-label="Show 5 homes near this pin" data-anchor="50.06,19.94"');
    expect(markup).toContain('aria-label="Fixture home separate, 4500 zł" data-anchor="50.1,19.99"');
    expect(markup.match(/data-anchor=/g)).toHaveLength(2);
    expect(markup).not.toContain("Fixture home delisted");
  });

  it("projects regional density using the viewport and current zoom", () => {
    const coordinate = { latitude: 50.065, longitude: 19.95 };
    const region = { latitude: 50.06, longitude: 19.94, latitudeDelta: .12, longitudeDelta: .12 };
    const viewport = { width: 360, height: 360 };
    const nearby = projectNativeMapPoint(coordinate, region, viewport);
    expect(nearby.x).toBeCloseTo(30);
    expect(nearby.y).toBeCloseTo(15);
    const zoomed = projectNativeMapPoint(coordinate, { ...region, longitudeDelta: .03 }, viewport);
    expect(zoomed.x).toBeCloseTo(120);
  });
});
