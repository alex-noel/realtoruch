import React, { useEffect, useRef, useState } from "react";
import { ScrollView, Text, View } from "react-native";
import MapView, { Marker, Polygon, Polyline, type Region } from "react-native-maps";
import { c, s } from "../theme";
import { Button, Chip, money } from "./UI";
import { MapErrorBoundary, MapRecovery } from "./MapRecovery";
import { groupMapHomes, MAP_MARKER_SIZE, projectNativeMapPoint } from "./mapGroups";
import {
  cityCenter,
  DrawControls,
  MapProps,
  readPoints,
  useMapDrawing,
} from "./MapDrawing";

export default function PropertyMap(props: MapProps) {
  const [attempt, setAttempt] = useState(0);
  const draw = useMapDrawing(props.polygon, props.onPolygonChange);
  const recovery = (
    <MapRecovery
      reason="map"
      onRetry={() => setAttempt((current) => current + 1)}
      onShowList={props.onShowList}
      canEnterPin={!!props.onPinChange}
    />
  );
  return (
    <MapErrorBoundary key={attempt} fallback={recovery}>
      <NativeMap {...props} draw={draw} recovery={recovery} />
    </MapErrorBoundary>
  );
}

function NativeMap(props: MapProps & {
  draw: ReturnType<typeof useMapDrawing>;
  recovery: React.ReactNode;
}) {
  const [ready, setReady] = useState(false);
  const [timedOut, setTimedOut] = useState(false);
  const { homes, selected, onSelect, city, polygon } = props;
  const ref = useRef<MapView>(null);
  const { draw } = props;
  const [latitude, longitude] = cityCenter(city);
  const initialRegion = { latitude, longitude, latitudeDelta: 0.12, longitudeDelta: 0.12 };
  const [region, setRegion] = useState<Region>(initialRegion);
  const [viewport, setViewport] = useState({ width: 360, height: 400 });
  const [openedGroup, setOpenedGroup] = useState<{ key: string; page: typeof homes } | null>(null);
  const groups = draw.drawing ? [] : groupMapHomes(homes, coordinate =>
    projectNativeMapPoint(coordinate, region, viewport));
  const group = openedGroup?.page === homes
    ? groups.find(item => item.key === openedGroup.key && item.homes.length > 1)
    : undefined;
  useEffect(() => {
    if (openedGroup && !group) setOpenedGroup(null);
  }, [openedGroup, group]);
  const shape = (draw.drawing ? draw.points : readPoints(polygon)).map(
    ([lon, lat]) => ({ latitude: lat, longitude: lon }),
  );
  useEffect(() => {
    if (ready) return;
    const timer = setTimeout(() => setTimedOut(true), 12000);
    return () => clearTimeout(timer);
  }, [ready]);
  useEffect(() => {
    if (!ready) return;
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
  }, [ready, city, polygon]);
  return (
    <View style={{ flex: 1, minHeight: 400 }}>
      {!props.onPinChange && (
        <DrawControls draw={draw} hasPolygon={!!polygon} mapAvailable={ready} />
      )}
      {!ready && (timedOut ? props.recovery : <Text style={s.muted}>Loading map…</Text>)}
      <View
        style={{ flex: 1, minHeight: 300 }}
        onLayout={({ nativeEvent: { layout } }) => {
          if (layout.width > 0 && layout.height > 0) {
            setViewport({ width: layout.width, height: layout.height });
          }
        }}
      >
        <MapView
          ref={ref}
          onMapReady={() => setReady(true)}
          style={{ flex: 1, minHeight: 300 }}
          initialRegion={initialRegion}
          onRegionChangeComplete={setRegion}
          onPress={(event) =>
            (props.onPinChange || draw.add)([
              event.nativeEvent.coordinate.longitude,
              event.nativeEvent.coordinate.latitude,
            ])
          }
        >
          {props.pin && (
            <Marker
              coordinate={{ longitude: props.pin[0], latitude: props.pin[1] }}
              pinColor={c.green}
            />
          )}
          {shape.length >= 3 ? (
            <Polygon coordinates={shape} strokeColor={c.green} fillColor="#17382D22" strokeWidth={2} />
          ) : shape.length > 0 ? (
            <Polyline coordinates={shape} strokeColor={c.green} strokeWidth={2} />
          ) : null}
          {draw.drawing
            ? shape.map((point, i) => <Marker key={i} coordinate={point} pinColor={c.green} />)
            : groups.map(item => {
              const first = item.homes[0];
              const count = item.homes.length;
              const current = item.homes.some(home => home.id === selected);
              return (
                <Marker
                  key={item.key}
                  coordinate={item.coordinate}
                  onPress={() => {
                    if (count > 1) setOpenedGroup({ key: item.key, page: homes });
                    else {
                      setOpenedGroup(null);
                      onSelect(first);
                    }
                  }}
                  accessibilityLabel={count > 1 ? `Show ${count} homes near this pin` : `${first.title}, ${first.rent_pln} zł`}
                >
                  <View
                    style={{
                      ...MAP_MARKER_SIZE,
                      overflow: "hidden",
                      alignItems: "center",
                      justifyContent: "center",
                      backgroundColor: current ? c.green : "white",
                      borderWidth: 1,
                      borderColor: c.green,
                    }}
                  >
                    <Text
                      numberOfLines={1}
                      ellipsizeMode="tail"
                      style={[
                        s.text,
                        {
                          fontSize: 11,
                          fontWeight: "700",
                          maxWidth: "100%",
                          color: current ? "white" : c.green,
                        },
                      ]}
                    >
                      {count > 1 ? `${count} homes` : money(first.rent_pln)}
                    </Text>
                  </View>
                </Marker>
              );
            })}
        </MapView>
        {group && (
          <View style={[s.card, { position: "absolute", top: 8, left: 8, right: 8, gap: 8, padding: 10 }]}>
            <View style={[s.row, { justifyContent: "space-between", gap: 8, flexWrap: "wrap" }]}>
              <Text accessibilityRole="header" style={[s.text, { fontWeight: "600" }]}>
                {group.homes.length} homes near this pin
              </Text>
              <Button outline label="Close homes near this pin" onPress={() => setOpenedGroup(null)}>Close</Button>
            </View>
            <Text style={s.muted}>Pins show approximate locations.</Text>
            <ScrollView nestedScrollEnabled style={{ maxHeight: 146 }} contentContainerStyle={{ gap: 6 }}>
              {group.homes.map(home => (
                <Chip
                  key={home.id}
                  label={`${home.title} · ${money(home.rent_pln)}`}
                  selected={home.id === selected}
                  onPress={() => {
                    setOpenedGroup(null);
                    onSelect(home);
                  }}
                />
              ))}
            </ScrollView>
          </View>
        )}
      </View>
    </View>
  );
}
