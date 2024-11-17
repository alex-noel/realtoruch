import React, { useEffect, useRef, useState } from "react";
import { Text, View } from "react-native";
import type * as Leaflet from "leaflet";
import "leaflet/dist/leaflet.css";
import { s } from "../theme";
import { MapRecovery } from "./MapRecovery";
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
  const [status, setStatus] = useState<"loading" | "ready" | "map" | "tiles">("loading");
  const [attempt, setAttempt] = useState(0);
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
      button.dataset.listingId = home.id;
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
    if (props.pin)
      library.current
        .circleMarker([props.pin[1], props.pin[0]], {
          radius: 9,
          color: "#17382D",
          fillOpacity: 1,
        })
        .addTo(shapes.current);
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
    let tileLayer: Leaflet.TileLayer | undefined;
    let failedTiles = 0;
    let loadedTiles = 0;
    const tileEvents = {
      loading: () => { failedTiles = 0; loadedTiles = 0; },
      tileerror: () => { failedTiles++; },
      tileload: () => { loadedTiles++; },
      load: () => {
        if (disposed) return;
        if (failedTiles > 1 || (failedTiles && !loadedTiles)) setStatus("tiles");
        else if (loadedTiles) setStatus("ready");
      },
    };
    const onMapClick = (event: Leaflet.LeafletMouseEvent) => {
      const point: [number, number] = [event.latlng.lng, event.latlng.lat];
      (latest.current.props.onPinChange || latest.current.draw.add)(point);
    };
    const cleanup = () => {
      observer?.disconnect();
      tileLayer?.off(tileEvents);
      map.current?.off("click", onMapClick);
      map.current?.remove();
      map.current = null;
      library.current = null;
      markers.current = null;
      shapes.current = null;
    };
    import("leaflet").then((L) => {
      if (disposed || !node.current) return;
      library.current = L;
      const instance = L.map(node.current, {
        zoomControl: false,
        scrollWheelZoom: false,
      });
      map.current = instance;
      instance.setView(cityCenter(latest.current.props.city), 12);
      tileLayer = L.tileLayer(
        process.env.EXPO_PUBLIC_MAP_TILE_URL ||
          "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
          attribution:
            '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
          maxZoom: 19,
        },
      );
      tileLayer.on(tileEvents).addTo(instance);
      L.control.zoom({ position: "bottomright" }).addTo(instance);
      markers.current = L.layerGroup().addTo(instance);
      shapes.current = L.layerGroup().addTo(instance);
      instance.on("click", onMapClick);
      renderMarkers();
      renderShape();
      focusArea();
      observer = new ResizeObserver(() => instance.invalidateSize());
      observer.observe(node.current);
      setStatus("ready");
    }).catch(() => {
      if (disposed) return;
      cleanup();
      setStatus("map");
    });
    return () => {
      disposed = true;
      cleanup();
    };
  }, [attempt]);
  useEffect(renderMarkers, [homes, draw.drawing]);
  useEffect(() => {
    // Keep the opener in the DOM so the detail dialog can restore focus.
    node.current?.querySelectorAll<HTMLButtonElement>(".price-marker").forEach((button) => {
      button.classList.toggle("selected", button.dataset.listingId === selected);
    });
  }, [selected]);
  useEffect(renderShape, [polygon, draw.drawing, draw.points, props.pin]);
  useEffect(focusArea, [city, polygon]);
  const mapAvailable = status === "ready" || status === "tiles";
  return (
    <View style={{ flex: 1, minHeight: 400 }}>
      {!props.onPinChange && (
        <DrawControls draw={draw} hasPolygon={!!polygon} mapAvailable={mapAvailable} />
      )}
      <View style={{ flex: 1, minHeight: 300 }}>
        <div
          ref={node}
          role={mapAvailable ? "region" : undefined}
          aria-label={mapAvailable ? "Map of rental homes" : undefined}
          style={{ width: "100%", flex: 1, background: "#e9eee4" }}
        />
        {status !== "ready" && (
          // Keep the map viewport stable when tile requests fail.
          <View style={{ position: "absolute", top: 0, left: 0, right: 0, zIndex: 1 }}>
            {status === "loading" ? (
              <Text aria-live="polite" style={s.muted}>Loading map…</Text>
            ) : (
              <MapRecovery
                reason={status}
                onRetry={() => {
                  setStatus("loading");
                  setAttempt((current) => current + 1);
                }}
                onShowList={props.onShowList}
                canEnterPin={!!props.onPinChange}
              />
            )}
          </View>
        )}
      </View>
    </View>
  );
}
