import { useEffect, useState } from "react";
import { Text, View } from "react-native";
import type { Listing } from "../types";
import { Button } from "./UI";
import { c, s } from "../theme";

export type Point = [number, number]; // longitude, latitude
export type MapProps = {
  homes: Listing[];
  selected: string | null;
  onSelect: (home: Listing) => void;
  city: string;
  polygon?: string;
  onPolygonChange: (polygon?: string) => void;
};
export function cityCenter(city: string): [number, number] {
  return city
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase() === "krakow"
    ? [50.0647, 19.945]
    : [52.229, 21.015];
}
export function readPoints(polygon?: string): Point[] {
  try {
    return polygon ? JSON.parse(polygon) : [];
  } catch {
    return [];
  }
}
export function useMapDrawing(
  polygon: string | undefined,
  onChange: MapProps["onPolygonChange"],
) {
  const [drawing, setDrawing] = useState(false);
  const [points, setPoints] = useState<Point[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    setDrawing(false);
    setPoints([]);
    setError("");
  }, [polygon]);
  function add(point: Point) {
    if (drawing)
      setPoints((current) =>
        current.length < 64 ? [...current, point] : current,
      );
  }
  function finish() {
    if (points.length < 3) return;
    const cross = (a: Point, b: Point, p: Point) =>
      (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]);
    const edges = points.map((p, i) => [p, points[(i + 1) % points.length]]);
    const area = edges.reduce(
      (sum, [a, b]) => sum + a[0] * b[1] - b[0] * a[1],
      0,
    );
    const duplicate =
      new Set(points.map((p) => p.join(","))).size !== points.length;
    const crossed = edges.some(([a, b], i) =>
      edges.some(
        ([c, d], j) =>
          j > i + 1 &&
          !(i === 0 && j === edges.length - 1) &&
          cross(a, b, c) * cross(a, b, d) <= 0 &&
          cross(c, d, a) * cross(c, d, b) <= 0 &&
          Math.max(Math.min(a[0], b[0]), Math.min(c[0], d[0])) <=
            Math.min(Math.max(a[0], b[0]), Math.max(c[0], d[0])) &&
          Math.max(Math.min(a[1], b[1]), Math.min(c[1], d[1])) <=
            Math.min(Math.max(a[1], b[1]), Math.max(c[1], d[1])),
      ),
    );
    if (duplicate || crossed || Math.abs(area) < 1e-9) {
      setError("Draw one area without crossing its edges.");
      return;
    }
    onChange(JSON.stringify(points));
    setDrawing(false);
    setPoints([]);
    setError("");
  }
  return {
    drawing,
    points,
    error,
    add,
    finish,
    start: () => {
      setDrawing(true);
      setPoints([]);
      setError("");
    },
    undo: () => {
      setPoints((p) => p.slice(0, -1));
      setError("");
    },
    cancel: () => {
      setDrawing(false);
      setPoints([]);
      setError("");
    },
    clear: () => onChange(undefined),
  };
}
export function DrawControls({
  draw,
  hasPolygon,
}: {
  draw: ReturnType<typeof useMapDrawing>;
  hasPolygon: boolean;
}) {
  return (
    <View
      style={{
        padding: 10,
        gap: 8,
        backgroundColor: "white",
        borderBottomWidth: 1,
        borderColor: c.line,
      }}
    >
      <View style={[s.row, { gap: 8, flexWrap: "wrap" }]}>
        {draw.drawing ? (
          <>
            <Button onPress={draw.finish} disabled={draw.points.length < 3}>
              Use this area
            </Button>
            <Button outline onPress={draw.undo} disabled={!draw.points.length}>
              Undo point
            </Button>
            <Button outline onPress={draw.cancel}>
              Cancel drawing
            </Button>
          </>
        ) : (
          <>
            <Button outline onPress={draw.start}>
              {hasPolygon ? "Redraw area" : "Draw area"}
            </Button>
            {hasPolygon ? (
              <Button outline onPress={draw.clear}>
                Clear area
              </Button>
            ) : null}
          </>
        )}
      </View>
      {draw.drawing ? (
        <Text style={[s.muted, { fontSize: 11 }]}>
          Tap the map to add corners · {draw.points.length}/64 points · pan or
          zoom to adjust the map.
        </Text>
      ) : null}
      {draw.error ? (
        <Text accessibilityRole="alert" style={{ color: c.warning }}>
          {draw.error}
        </Text>
      ) : null}
    </View>
  );
}
