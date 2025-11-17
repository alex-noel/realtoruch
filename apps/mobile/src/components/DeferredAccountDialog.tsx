import React, { Component, lazy, Suspense, useMemo, useState, type ReactNode } from "react";
import { Text } from "react-native";
import { Button, Panel } from "./UI";
import { s } from "../theme";
import type { AccountDialog as Account, ResetPasswordDialog as Reset } from "./AccountDialog";
class Boundary extends Component<{ children: ReactNode; fallback: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? this.props.fallback : this.props.children; }
}
function Deferred({ name, props }: { name: "AccountDialog" | "ResetPasswordDialog"; props: Record<string, unknown> & { onClose: () => void } }) {
  const [attempt, setAttempt] = useState(0);
  const Dialog = useMemo(() => lazy(() => import("./AccountDialog").then(module => ({ default: module[name] as React.ComponentType<any> }))), [attempt, name]);
  const frame = (content: ReactNode) => <Panel title={name === "AccountDialog" ? "Your account." : "Choose a new password."} onClose={props.onClose}>{content}</Panel>;
  return <Boundary key={attempt} fallback={frame(<><Text accessibilityRole="alert" style={s.text}>Could not load this screen. Check your connection and retry.</Text><Button onPress={() => setAttempt(value => value + 1)}>Retry account screen</Button></>)}>
    <Suspense fallback={frame(<Text accessibilityRole="status" style={s.muted}>Loading account screen…</Text>)}><Dialog {...props} /></Suspense>
  </Boundary>;
}
export function AccountDialog(props: React.ComponentProps<typeof Account>) { return <Deferred name="AccountDialog" props={props} />; }
export function ResetPasswordDialog(props: React.ComponentProps<typeof Reset>) { return <Deferred name="ResetPasswordDialog" props={props} />; }
