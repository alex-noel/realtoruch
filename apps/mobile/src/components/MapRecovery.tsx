import { Component, type ReactNode } from "react";
import { Text, View } from "react-native";
import { c, s } from "../theme";
import { Button } from "./UI";

export class MapErrorBoundary extends Component<
  { children: ReactNode; fallback: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

export function MapRecovery({
  reason,
  onRetry,
  onShowList,
  canEnterPin,
}: {
  reason: "map" | "tiles";
  onRetry: () => void;
  onShowList?: () => void;
  canEnterPin: boolean;
}) {
  return (
    <View style={{ padding: 12, gap: 8, backgroundColor: c.cream }}>
      <Text accessibilityRole="alert" style={[s.text, { fontWeight: "600" }]}>
        {reason === "tiles" ? "Map tiles couldn't load." : "The map couldn't load."}
      </Text>
      {canEnterPin && (
        <Text style={s.text}>Enter latitude and longitude in the location fields.</Text>
      )}
      <View style={[s.row, { gap: 8, flexWrap: "wrap" }]}>
        <Button outline onPress={onRetry}>Retry map</Button>
        {onShowList && <Button outline onPress={onShowList}>Show homes as a list</Button>}
      </View>
    </View>
  );
}
