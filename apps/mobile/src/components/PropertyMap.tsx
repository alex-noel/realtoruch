import React, { useEffect, useRef } from "react";
import { Text, View } from "react-native";
import MapView, { Marker } from "react-native-maps";
import { Listing } from "../types";
import { c, s } from "../theme";
export default function PropertyMap({
  homes,
  selected,
  onSelect,
}: {
  homes: Listing[];
  selected: string | null;
  onSelect: (home: Listing) => void;
}) {
  const ref = useRef<MapView>(null);
  const points = homes.filter((h) => h.lat !== null && h.lon !== null);
  useEffect(() => {
    if (points.length)
      ref.current?.fitToCoordinates(
        points.map((h) => ({ latitude: h.lat!, longitude: h.lon! })),
        {
          edgePadding: { top: 50, right: 40, bottom: 50, left: 40 },
          animated: true,
        },
      );
  }, [homes]);
  return (
    <MapView
      ref={ref}
      style={{ flex: 1, minHeight: 400 }}
      initialRegion={{
        latitude: 52.229,
        longitude: 21.015,
        latitudeDelta: 0.13,
        longitudeDelta: 0.13,
      }}
    >
      {points.map((home) => (
        <Marker
          key={home.id}
          coordinate={{ latitude: home.lat!, longitude: home.lon! }}
          onPress={() => onSelect(home)}
          accessibilityLabel={`${home.title}, ${home.rent_pln} zł`}
        >
          <View
            style={{
              padding: 8,
              backgroundColor: home.id === selected ? c.green : "white",
              borderWidth: 1,
              borderColor: c.green,
            }}
          >
            <Text
              style={[
                s.text,
                {
                  fontSize: 11,
                  fontWeight: "700",
                  color: home.id === selected ? "white" : c.green,
                },
              ]}
            >
              {home.rent_pln} zł
            </Text>
          </View>
        </Marker>
      ))}
    </MapView>
  );
}
