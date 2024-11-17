import React, { lazy, Suspense, useMemo, useState } from "react";
import { Text } from "react-native";
import { s } from "../theme";
import type { MapProps } from "./MapDrawing";
import { MapErrorBoundary, MapRecovery } from "./MapRecovery";

export default function DeferredPropertyMap(props: MapProps) {
  const [attempt, setAttempt] = useState(0);
  const PropertyMap = useMemo(() => lazy(() => import("./PropertyMap")), [attempt]);
  return (
    <MapErrorBoundary
      key={attempt}
      fallback={
        <MapRecovery
          reason="map"
          onRetry={() => setAttempt((current) => current + 1)}
          onShowList={props.onShowList}
          canEnterPin={!!props.onPinChange}
        />
      }
    >
      <Suspense fallback={<Text aria-live="polite" style={s.muted}>Loading map…</Text>}>
        <PropertyMap {...props} />
      </Suspense>
    </MapErrorBoundary>
  );
}
