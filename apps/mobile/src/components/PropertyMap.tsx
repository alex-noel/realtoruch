import React, { useEffect, useRef } from "react";
import { Text, View } from "react-native";
import MapView, { Marker, Polygon, Polyline } from "react-native-maps";
import { c, s } from "../theme";
import {
  cityCenter,
  DrawControls,
  MapProps,
  readPoints,
  useMapDrawing,
} from "./MapDrawing";

export default function PropertyMap(props: MapProps) {
  const { homes, selected, onSelect, city, polygon, onPolygonChange } = props;
  const ref = useRef<MapView>(null);
  const draw = useMapDrawing(polygon, onPolygonChange);
  const [latitude, longitude] = cityCenter(city);
  const shape = (draw.drawing ? draw.points : readPoints(polygon)).map(
    ([lon, lat]) => ({ latitude: lat, longitude: lon }),
  );
  useEffect(() => {
    const points = readPoints(polygon).map(([lon, lat]) => ({
      latitude: lat,
      longitude: lon,
    }));
    if (points.length)
      ref.current?.fitToCoordinates(points, {
        edgePadding: { top: 30, right: 30, bottom: 30, left: 30 },
        animated: true,
      });
    else {
      const [lat, lon] = cityCenter(city);
      ref.current?.animateToRegion({
        latitude: lat,
        longitude: lon,
        latitudeDelta: 0.12,
        longitudeDelta: 0.12,
      });
    }
  }, [city, polygon]);
  return (
    <View style={{ flex: 1, minHeight: 400 }}>
      <DrawControls draw={draw} hasPolygon={!!polygon} />
      <MapView
        ref={ref}
        style={{ flex: 1, minHeight: 300 }}
        initialRegion={{
          latitude,
          longitude,
          latitudeDelta: 0.12,
          longitudeDelta: 0.12,
        }}
        onPress={(event) =>
          draw.add([
            event.nativeEvent.coordinate.longitude,
            event.nativeEvent.coordinate.latitude,
          ])
        }
      >
        {shape.length >= 3 ? (
          <Polygon
            coordinates={shape}
            strokeColor={c.green}
            fillColor="#17382D22"
            strokeWidth={2}
          />
        ) : shape.length > 0 ? (
          <Polyline coordinates={shape} strokeColor={c.green} strokeWidth={2} />
        ) : null}
        {!draw.drawing
          ? homes
              .filter(
                (h) =>
                  h.status === "active" && h.lat !== null && h.lon !== null,
              )
              .map((home) => (
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
              ))
          : shape.map((point, i) => (
              <Marker key={i} coordinate={point} pinColor={c.green} />
            ))}
      </MapView>
    </View>
  );
}
