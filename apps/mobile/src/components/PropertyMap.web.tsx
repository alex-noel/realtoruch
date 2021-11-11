import React, { useEffect, useRef } from "react";
import { View } from "react-native";
import type * as Leaflet from "leaflet";
import "leaflet/dist/leaflet.css";
import {
  cityCenter,
  DrawControls,
  MapProps,
  readPoints,
  useMapDrawing,
} from "./MapDrawing";

export default function PropertyMap(props: MapProps) {
  const { homes, selected, city, polygon, onPolygonChange } = props;
  const draw = useMapDrawing(polygon, onPolygonChange);
  const node = useRef<HTMLDivElement>(null);
  const map = useRef<Leaflet.Map | null>(null);
  const markers = useRef<Leaflet.LayerGroup | null>(null);
  const shapes = useRef<Leaflet.LayerGroup | null>(null);
  const library = useRef<typeof Leaflet | null>(null);
  const latest = useRef({ props, draw });
  latest.current = { props, draw };
  function renderMarkers() {
    if (!map.current || !markers.current || !library.current) return;
    const L = library.current;
    markers.current.clearLayers();
    if (latest.current.draw.drawing) return;
    for (const home of latest.current.props.homes) {
      if (home.status !== "active" || home.lat === null || home.lon === null)
        continue;
      const button = document.createElement("button");
      button.className = `price-marker ${home.id === latest.current.props.selected ? "selected" : ""}`;
      button.textContent = `${new Intl.NumberFormat("pl-PL").format(home.rent_pln)} zł`;
      button.setAttribute("aria-label", `${home.title}, ${home.rent_pln} zł`);
      button.onclick = (event) => {
        event.stopPropagation();
        latest.current.props.onSelect(home);
      };
      L.marker([home.lat, home.lon], {
        icon: L.divIcon({
          html: button,
          className: "marker-wrapper",
          iconSize: [78, 32],
          iconAnchor: [39, 16],
        }),
        keyboard: false,
      }).addTo(markers.current);
    }
  }
  function renderShape() {
    if (!shapes.current || !library.current) return;
    shapes.current.clearLayers();
    const { draw, props } = latest.current;
    const points = (draw.drawing ? draw.points : readPoints(props.polygon)).map(
      ([lon, lat]) => [lat, lon] as [number, number],
    );
    if (points.length >= 3)
      library.current
        .polygon(points, {
          color: "#17382D",
          fillOpacity: 0.12,
          weight: 2,
          interactive: false,
        })
        .addTo(shapes.current);
    else if (points.length)
      library.current
        .polyline(points, { color: "#17382D", weight: 2, interactive: false })
        .addTo(shapes.current);
    if (draw.drawing)
      for (const point of points)
        library.current
          .circleMarker(point, {
            radius: 4,
            color: "#17382D",
            fillOpacity: 1,
            interactive: false,
          })
          .addTo(shapes.current);
    if (node.current)
      node.current.style.cursor = draw.drawing ? "crosshair" : "";
  }
  function focusArea() {
    const points = readPoints(latest.current.props.polygon).map(
      ([lon, lat]) => [lat, lon] as [number, number],
    );
    if (points.length)
      map.current?.fitBounds(points, { padding: [24, 24], maxZoom: 16 });
    else map.current?.setView(cityCenter(latest.current.props.city), 12);
  }
  useEffect(() => {
    let disposed = false;
    let observer: ResizeObserver | undefined;
    import("leaflet").then((L) => {
      if (disposed || !node.current) return;
      library.current = L;
      map.current = L.map(node.current, {
        zoomControl: false,
        scrollWheelZoom: false,
      }).setView(cityCenter(latest.current.props.city), 12);
      L.tileLayer(
        process.env.EXPO_PUBLIC_MAP_TILE_URL ||
          "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
          attribution:
            '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
          maxZoom: 19,
        },
      ).addTo(map.current);
      L.control.zoom({ position: "bottomright" }).addTo(map.current);
      markers.current = L.layerGroup().addTo(map.current);
      shapes.current = L.layerGroup().addTo(map.current);
      map.current.on("click", (event) =>
        latest.current.draw.add([event.latlng.lng, event.latlng.lat]),
      );
      renderMarkers();
      renderShape();
      focusArea();
      observer = new ResizeObserver(() => map.current?.invalidateSize());
      observer.observe(node.current);
    });
    return () => {
      disposed = true;
      observer?.disconnect();
      map.current?.remove();
      map.current = null;
    };
  }, []);
  useEffect(renderMarkers, [homes, selected, draw.drawing]);
  useEffect(renderShape, [polygon, draw.drawing, draw.points]);
  useEffect(focusArea, [city, polygon]);
  return (
    <View style={{ flex: 1, minHeight: 400 }}>
      <DrawControls draw={draw} hasPolygon={!!polygon} />
      <div
        ref={node}
        role="region"
        aria-label="Map of rental homes"
        style={{
          width: "100%",
          flex: 1,
          minHeight: 300,
          background: "#e9eee4",
        }}
      />
    </View>
  );
}
