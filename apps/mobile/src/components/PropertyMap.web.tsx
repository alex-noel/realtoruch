import React, { useEffect, useRef } from "react";
import { Listing } from "../types";
import type * as Leaflet from "leaflet";
import "leaflet/dist/leaflet.css";

type Props = {
  homes: Listing[];
  selected: string | null;
  onSelect: (home: Listing) => void;
};
export default function PropertyMap({ homes, selected, onSelect }: Props) {
  const node = useRef<HTMLDivElement>(null);
  const map = useRef<Leaflet.Map | null>(null);
  const markers = useRef<Leaflet.LayerGroup | null>(null);
  const library = useRef<typeof Leaflet | null>(null);
  const latest = useRef({ homes, selected, onSelect });
  latest.current = { homes, selected, onSelect };
  const fitHomes = () => {
    const points = latest.current.homes
      .filter((h) => h.lat !== null && h.lon !== null)
      .map((h) => [h.lat!, h.lon!] as [number, number]);
    if (points.length && map.current)
      map.current.fitBounds(points, { padding: [45, 55], maxZoom: 14 });
  };
  const renderMarkers = () => {
    if (!map.current || !markers.current || !library.current) return;
    const L = library.current;
    markers.current.clearLayers();
    for (const home of latest.current.homes) {
      if (home.lat === null || home.lon === null) continue;
      const button = document.createElement("button");
      button.className = `price-marker ${home.id === latest.current.selected ? "selected" : ""}`;
      button.textContent = `${new Intl.NumberFormat("pl-PL").format(home.rent_pln)} zł`;
      button.setAttribute("aria-label", `${home.title}, ${home.rent_pln} zł`);
      button.onclick = () => latest.current.onSelect(home);
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
  };
  useEffect(() => {
    let disposed = false;
    let observer: ResizeObserver | undefined;
    import("leaflet").then((L) => {
      if (disposed || !node.current) return;
      library.current = L;
      map.current = L.map(node.current, {
        zoomControl: false,
        scrollWheelZoom: false,
      }).setView([52.229, 21.015], 12);
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
      renderMarkers();
      fitHomes();
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
  useEffect(() => {
    renderMarkers();
    fitHomes();
  }, [homes]);
  useEffect(renderMarkers, [selected]);
  return (
    <div
      ref={node}
      role="region"
      aria-label="Map of rental homes"
      style={{
        width: "100%",
        height: "100%",
        minHeight: 400,
        background: "#e9eee4",
      }}
    />
  );
}
