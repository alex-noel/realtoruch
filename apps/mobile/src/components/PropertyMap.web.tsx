import React, { useEffect, useRef, useState } from "react";
import { Text, View } from "react-native";
import type * as Leaflet from "leaflet";
import "leaflet/dist/leaflet.css";
import { s } from "../theme";
import { Chip, Panel, money } from "./UI";
import { MapRecovery } from "./MapRecovery";
import { groupMapHomes, MAP_MARKER_SIZE, type MapGroup } from "./mapGroups";
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
  const [openedGroup, setOpenedGroup] = useState<{ group: MapGroup; page: typeof homes } | null>(null);
  const node = useRef<HTMLDivElement>(null);
  const map = useRef<Leaflet.Map | null>(null);
  const markers = useRef<Leaflet.LayerGroup | null>(null);
  const shapes = useRef<Leaflet.LayerGroup | null>(null);
  const library = useRef<typeof Leaflet | null>(null);
  const markerByHome = useRef(new Map<string, HTMLButtonElement>());
  const latest = useRef({ props, draw });
  latest.current = { props, draw };
  function renderMarkers() {
    const instance = map.current;
    if (!instance || !markers.current || !library.current) return;
    const L = library.current;
    markers.current.clearLayers();
    markerByHome.current.clear();
    setOpenedGroup(null);
    if (latest.current.draw.drawing) return;
    const page = latest.current.props.homes;
    const groups = groupMapHomes(page, ({ latitude, longitude }) =>
      instance.latLngToLayerPoint([latitude, longitude]));
    for (const group of groups) {
      const first = group.homes[0];
      const count = group.homes.length;
      const current = group.homes.some(home => home.id === latest.current.props.selected);
      const button = document.createElement("button");
      button.className = current ? "price-marker selected" : "price-marker";
      button.style.width = `${MAP_MARKER_SIZE.width}px`;
      button.style.height = `${MAP_MARKER_SIZE.height}px`;
      button.style.padding = "4px";
      button.style.overflow = "hidden";
      button.style.textOverflow = "ellipsis";
      button.dataset.listingIds = group.homes.map(home => home.id).join(" ");
      if (count === 1) {
        button.dataset.listingId = first.id;
        button.textContent = money(first.rent_pln);
        button.setAttribute("aria-label", `${first.title}, ${first.rent_pln} zł`);
      } else {
        button.style.display = "flex";
        button.style.flexWrap = "wrap";
        button.style.alignItems = "center";
        button.style.alignContent = "center";
        button.style.justifyContent = "center";
        button.style.columnGap = "3px";
        button.style.lineHeight = "1";
        button.style.padding = "1px";
        const number = document.createElement("span");
        number.textContent = String(count);
        const noun = document.createElement("span");
        noun.textContent = "homes";
        noun.style.fontSize = "clamp(11px, .72em, 100%)";
        button.append(number, " ", noun);
        button.setAttribute("aria-label", `Show ${count} homes near this pin`);
        button.setAttribute("aria-haspopup", "dialog");
      }
      for (const home of group.homes) markerByHome.current.set(home.id, button);
      L.DomEvent.disableClickPropagation(button);
      button.onclick = (event) => {
        event.stopPropagation();
        if (count === 1) latest.current.props.onSelect(first);
        else setOpenedGroup({ group, page });
      };
      L.marker([group.coordinate.latitude, group.coordinate.longitude], {
        icon: L.divIcon({
          html: button,
          className: "marker-wrapper",
          iconSize: [MAP_MARKER_SIZE.width, MAP_MARKER_SIZE.height],
          iconAnchor: [MAP_MARKER_SIZE.width / 2, MAP_MARKER_SIZE.height / 2],
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
      map.current?.off("zoomend", renderMarkers);
      map.current?.remove();
      markerByHome.current.clear();
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
      instance.on("zoomend", renderMarkers);
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
    node.current?.querySelector(".price-marker.selected")?.classList.remove("selected");
    if (selected) markerByHome.current.get(selected)?.classList.add("selected");
  }, [selected]);
  useEffect(renderShape, [polygon, draw.drawing, draw.points, props.pin]);
  useEffect(focusArea, [city, polygon]);
  const mapAvailable = status === "ready" || status === "tiles";
  const group = !draw.drawing && openedGroup?.page === homes ? openedGroup.group : null;
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
      {group && (
        <Panel title={`${group.homes.length} homes near this pin`} onClose={() => setOpenedGroup(null)}>
          <Text style={s.muted}>Pins show approximate locations.</Text>
          <View style={{ gap: 8, alignItems: "flex-start" }}>
            {group.homes.map(home => (
              <Chip
                key={home.id}
                label={`${home.title} · ${money(home.rent_pln)}`}
                selected={home.id === selected}
                onPress={() => {
                  setOpenedGroup(null);
                  props.onSelect(home);
                }}
              />
            ))}
          </View>
        </Panel>
      )}
    </View>
  );
}
