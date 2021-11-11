import { useEffect, useId, useState } from "react";
import { Platform, Text, View } from "react-native";
import type { Listing } from "../types";
import { Button, Field, Panel } from "./UI";
import { c, s } from "../theme";
import { readCoordinate } from "./coordinates";

export type Point = [number, number]; // longitude, latitude
export type MapProps = {
  homes: Listing[];
  selected: string | null;
  onSelect: (home: Listing) => void;
  city: string;
  polygon?: string;
  pin?: Point;
  onPinChange?: (point: Point) => void;
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
    const points: Point[] = polygon ? JSON.parse(polygon) : [];
    if (
      !Array.isArray(points) ||
      points.some(
        (point) =>
          !Array.isArray(point) ||
          point.length !== 2 ||
          point.some((value) => !Number.isFinite(value)),
      )
    )
      return [];
    return points.length > 1 && points[0].join(",") === points.at(-1)?.join(",")
      ? points.slice(0, -1)
      : points;
  } catch {
    return [];
  }
}
const MAX_VERTICES = 64;
const EPSILON = 1e-9;
// Same order and epsilon as backend/realtoruch/geometry.py. The editor
// closes the ring itself, so users need not repeat the first vertex.
function polygonError(points: Point[]): string {
  if (points.length < 3 || points.length > MAX_VERTICES)
    return "Use between 3 and 64 distinct vertices.";
  if (
    points.some(
      ([lon, lat]) =>
        !Number.isFinite(lon) ||
        !Number.isFinite(lat) ||
        Math.abs(lon) > 180 ||
        Math.abs(lat) > 90,
    )
  )
    return "Latitude must be from −90 to 90, and longitude from −180 to 180.";
  if (new Set(points.map((p) => p.join(","))).size !== points.length)
    return "Each vertex must have a different latitude and longitude pair.";
  const longitudes = points.map(([lon]) => lon);
  if (Math.max(...longitudes) - Math.min(...longitudes) > 180)
    return "Choose an area that spans no more than 180 degrees of longitude.";
  const cross = (a: Point, b: Point, p: Point) =>
    (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]);
  const onSegment = (a: Point, b: Point, p: Point) =>
    Math.abs(cross(a, b, p)) <= EPSILON &&
    p.every(
      (coordinate, i) =>
        coordinate >= Math.min(a[i], b[i]) - EPSILON &&
        coordinate <= Math.max(a[i], b[i]) + EPSILON,
    );
  const edges = points.map((p, i) => [p, points[(i + 1) % points.length]]);
  const area = edges.reduce(
    (sum, [a, b]) => sum + a[0] * b[1] - b[0] * a[1],
    0,
  );
  const crossed = edges.some(([a, b], i) =>
    edges.some(
      ([c, d], j) =>
        j > i + 1 &&
        !(i === 0 && j === edges.length - 1) &&
        ((cross(a, b, c) * cross(a, b, d) < 0 &&
          cross(c, d, a) * cross(c, d, b) < 0) ||
          onSegment(a, b, c) ||
          onSegment(a, b, d) ||
          onSegment(c, d, a) ||
          onSegment(c, d, b)),
    ),
  );
  return crossed || Math.abs(area) < EPSILON
    ? "Draw one area without crossing its edges. The vertices must enclose an area."
    : "";
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
    if (drawing) {
      setPoints((current) =>
        current.length < MAX_VERTICES ? [...current, point] : current,
      );
      setError("");
    }
  }
  function finish() {
    const invalid = polygonError(points);
    if (invalid) {
      setError(invalid);
      return false;
    }
    onChange(JSON.stringify(points));
    setDrawing(false);
    setPoints([]);
    setError("");
    return true;
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
    edit: () => {
      setDrawing(true);
      if (!drawing) setPoints(readPoints(polygon));
      setError("");
    },
    replace: (next: Point[]) => {
      setPoints(next);
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
    clear: () => {
      setDrawing(false);
      setPoints([]);
      setError("");
      onChange(undefined);
    },
  };
}
type Drawing = ReturnType<typeof useMapDrawing>;

function CoordinateEditor({
  draw,
  onClose,
  onFinish,
}: {
  draw: Drawing;
  onClose: () => void;
  onFinish: () => void;
}) {
  const [longitude, setLongitude] = useState("");
  const [latitude, setLatitude] = useState("");
  const [editing, setEditing] = useState<number | null>(null);
  const [checked, setChecked] = useState(false);
  const errorId = useId();
  const lon = readCoordinate(longitude, 180);
  const lat = readCoordinate(latitude, 90);
  const invalid = checked && (lon === null || lat === null);
  const reset = () => {
    setLongitude("");
    setLatitude("");
    setEditing(null);
    setChecked(false);
  };
  function saveVertex() {
    setChecked(true);
    if (lon === null || lat === null) return;
    if (editing === null) draw.add([lon, lat]);
    else
      draw.replace(
        draw.points.map((point, i) => (i === editing ? [lon, lat] : point)),
      );
    reset();
  }
  return (
    <Panel title="Search area coordinates" onClose={onClose}>
      <Text style={s.text}>
        Enter the corners in order using decimal degrees. Connect the last
        corner to the first by choosing Use this area.
      </Text>
      <Text aria-live="polite" style={s.muted}>
        {draw.points.length} of {MAX_VERTICES} vertices
      </Text>
      {draw.points.map(([x, y], i) => (
        <View key={i} style={{ gap: 6 }}>
          <Text style={s.text}>
            Vertex {i + 1}: latitude {y}, longitude {x}
          </Text>
          <View style={[s.row, { flexWrap: "wrap", gap: 8 }]}>
            <Button
              outline
              onPress={() => {
                setEditing(i);
                setLongitude(String(x));
                setLatitude(String(y));
                setChecked(false);
              }}
            >
              Edit vertex {i + 1}
            </Button>
            <Button
              outline
              onPress={() => {
                draw.replace(draw.points.filter((_, n) => n !== i));
                reset();
              }}
            >
              Remove vertex {i + 1}
            </Button>
          </View>
        </View>
      ))}
      <Text accessibilityRole="header" style={s.text}>
        {editing === null ? "New vertex" : `Editing vertex ${editing + 1}`}
      </Text>
      <Field
        label="Latitude"
        value={latitude}
        onChange={setLatitude}
        numeric
        errorId={invalid && lat === null ? errorId : undefined}
      />
      <Field
        label="Longitude"
        value={longitude}
        onChange={setLongitude}
        numeric
        errorId={invalid && lon === null ? errorId : undefined}
      />
      {invalid && (
        <Text
          nativeID={errorId}
          accessibilityRole="alert"
          style={{ color: c.warning }}
        >
          Enter a latitude from −90 to 90 and a longitude from −180 to 180.
        </Text>
      )}
      <View style={[s.row, { flexWrap: "wrap", gap: 8 }]}>
        <Button
          outline
          disabled={editing === null && draw.points.length === MAX_VERTICES}
          onPress={saveVertex}
        >
          {editing === null ? "Add vertex" : "Save vertex"}
        </Button>
        {editing !== null && (
          <Button outline onPress={reset}>
            Cancel vertex edit
          </Button>
        )}
      </View>
      {!!draw.error && (
        <Text accessibilityRole="alert" style={{ color: c.warning }}>
          {draw.error}
        </Text>
      )}
      <Button onPress={onFinish}>Use this area</Button>
    </Panel>
  );
}

export function DrawControls({
  draw,
  hasPolygon,
}: {
  draw: Drawing;
  hasPolygon: boolean;
}) {
  const [previous, setPrevious] = useState<{
    drawing: boolean;
    points: Point[];
  } | null>(null);
  const openEditor = () => {
    setPrevious({ drawing: draw.drawing, points: draw.points });
    draw.edit();
  };
  const closeEditor = () => {
    if (previous?.drawing) draw.replace(previous.points);
    else draw.cancel();
    setPrevious(null);
  };
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
        {Platform.OS === "web" && (
          <Button outline onPress={openEditor}>
            {hasPolygon ? "Edit area coordinates" : "Enter area coordinates"}
          </Button>
        )}
      </View>
      {draw.drawing ? (
        <Text aria-live="polite" style={[s.muted, { fontSize: 11 }]}>
          Tap the map to add corners · {draw.points.length}/64 points · pan or
          zoom to adjust the map.
        </Text>
      ) : null}
      {draw.error && !previous ? (
        <Text accessibilityRole="alert" style={{ color: c.warning }}>
          {draw.error}
        </Text>
      ) : null}
      {previous && (
        <CoordinateEditor
          draw={draw}
          onClose={closeEditor}
          onFinish={() => {
            if (draw.finish()) setPrevious(null);
          }}
        />
      )}
    </View>
  );
}
