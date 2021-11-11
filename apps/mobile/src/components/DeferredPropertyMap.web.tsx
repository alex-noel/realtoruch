import React, { lazy, Suspense } from "react";
import { Text } from "react-native";
import { s } from "../theme";
import type { MapProps } from "./MapDrawing";

const PropertyMap = lazy(() => import("./PropertyMap"));

export default function DeferredPropertyMap(props: MapProps) {
  return (
    <Suspense
      fallback={
        <Text aria-live="polite" style={s.muted}>
          Loading map…
        </Text>
      }
    >
      <PropertyMap {...props} />
    </Suspense>
  );
}
