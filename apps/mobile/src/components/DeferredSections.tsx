import React, { Component, lazy, Suspense, useMemo, useState, type ReactNode } from "react";
import { Text, View } from "react-native";
import { Button } from "./UI";
import { s } from "../theme";
import type InsightsScreen from "./Insights";
import type InboxScreen from "./NotificationInbox";

class Boundary extends Component<{ children: ReactNode; fallback: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? this.props.fallback : this.props.children; }
}
const insights = () => import("./Insights");
const notifications = () => import("./NotificationInbox");

function Section({ loader, label, screenProps }: {
  loader: () => Promise<{ default: React.ComponentType<any> }>;
  label: string;
  screenProps: object;
}) {
  const [attempt, setAttempt] = useState(0);
  const Screen = useMemo(() => lazy(loader), [loader, attempt]);
  return <Boundary key={attempt} fallback={<View style={{ gap: 12, alignItems: "flex-start" }}>
    <Text accessibilityRole="alert" style={s.text}>Could not load {label.toLowerCase()}. Check your connection and retry.</Text>
    <Button onPress={() => setAttempt(value => value + 1)}>Retry {label.toLowerCase()} screen</Button>
  </View>}>
    <Suspense fallback={<Text accessibilityRole="status" style={s.muted}>Loading {label.toLowerCase()} screen…</Text>}>
      <Screen {...screenProps} />
    </Suspense>
  </Boundary>;
}

export function Insights(props: React.ComponentProps<typeof InsightsScreen>) {
  return <Section loader={insights} label="Insights" screenProps={props} />;
}
export function NotificationInbox(props: React.ComponentProps<typeof InboxScreen>) {
  return <Section loader={notifications} label="Notifications" screenProps={props} />;
}
