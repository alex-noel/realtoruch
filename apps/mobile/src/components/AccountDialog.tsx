import React, { type ComponentRef, useCallback, useEffect, useRef, useState } from "react";
import { AppState, Platform, Text, TextInput, View } from "react-native";
import { api } from "../api";
import { s } from "../theme";
import { Button, PasswordField, Panel } from "./UI";

const loadDevices = async () => (await api.sessions()).items;
function useAccountSection<T>(load: () => Promise<T>, initial: T, revision = 0) {
  const [data, setData] = useState(initial);
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  const alive = useRef(false), sequence = useRef(0);
  const refresh = useCallback(async () => {
    const request = ++sequence.current;
    setLoading(true); setFailed(false);
    try {
      const next = await load();
      if (alive.current && sequence.current === request) { setData(next); setLoaded(true); }
    } catch { if (alive.current && sequence.current === request) setFailed(true); }
    finally { if (alive.current && sequence.current === request) setLoading(false); }
  }, [load]);
  useEffect(() => {
    alive.current = true; void refresh();
    return () => { alive.current = false; sequence.current++; };
  }, [refresh, revision]);
  function update(change: (previous: T) => T) {
    if (!alive.current) return;
    sequence.current++; setData(change); setLoading(false);
  }
  return { data, loaded, loading, failed, refresh, update };
}

export function AccountDialog({ onClose, onSignOut, onDeleted, onMarketplace, verificationRevision = 0 }: {
  onMarketplace: (mode: "adverts" | "messages") => void;
  onClose: () => void;
  onSignOut: () => Promise<void>;
  onDeleted: (message: string) => void;
  verificationRevision?: number;
}) {
  const identity = useAccountSection<Awaited<ReturnType<typeof api.me>> | null>(api.me, null, verificationRevision);
  const devices = useAccountSection(loadDevices, []);
  const [pending, setPending] = useState<string[]>([]);
  const pendingRef = useRef(new Set<string>());
  const [feedback, setFeedback] = useState<Record<string, { message: string; failed: boolean }>>({});
  const [deleting, setDeleting] = useState(false);
  const [password, setPassword] = useState("");
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    const active = AppState.addEventListener("change", state => { if (state === "active") void identity.refresh(); });
    const focus = () => { void identity.refresh(); };
    if (Platform.OS === "web") window.addEventListener("focus", focus);
    return () => { alive.current = false; active.remove(); if (Platform.OS === "web") window.removeEventListener("focus", focus); };
  }, [identity.refresh]);
  const terminal = pending.includes("signout") || pending.includes("delete");
  async function run(key: string, action: () => Promise<string | void>) {
    if (pendingRef.current.has(key)) return;
    pendingRef.current.add(key); setPending([...pendingRef.current]);
    setFeedback(current => { const next = { ...current }; delete next[key]; return next; });
    try {
      const message = await action();
      if (message && alive.current) setFeedback(current => ({ ...current, [key]: { message, failed: false } }));
    } catch (error) {
      if (alive.current) setFeedback(current => ({ ...current, [key]: { message: (error as Error).message, failed: true } }));
    } finally {
      pendingRef.current.delete(key);
      if (alive.current) setPending([...pendingRef.current]);
    }
  }
  function notice(key: string) {
    const item = feedback[key];
    return item ? <Text accessibilityRole={item.failed ? "alert" : "status"} style={s.text}>{item.message}</Text> : null;
  }
  return <Panel title="Your account." onClose={onClose}>
    <View style={[s.card, { padding: 16, gap: 12 }]}>
      <Text accessibilityRole="header" style={[s.text, { fontWeight: "700" }]}>Account details</Text>
      {identity.loading && <Text accessibilityRole="status" style={s.muted}>Loading account details…</Text>}
      {identity.failed && <><Text accessibilityRole="alert" style={s.text}>Could not load account details.{identity.loaded ? " Previously loaded details may be out of date." : ""}</Text><Button outline disabled={identity.loading} onPress={() => void identity.refresh()}>Retry account details</Button></>}
      {identity.data && <>
        <Text style={s.text}>{identity.data.email}</Text>
        <Text style={s.muted}>{identity.data.email_verified ? "Email verified" : "Email not yet verified"}</Text>
        <Button outline disabled={terminal || identity.loading} onPress={() => void identity.refresh()}>Refresh verification status</Button>
        {!identity.data.email_verified && <Button outline disabled={terminal} busy={pending.includes("verification")} busyLabel="Requesting verification…" onPress={() => void run("verification", async () => (await api.requestVerification()).message)}>Send verification email</Button>}
        {notice("verification")}
        <Button outline disabled={terminal} busy={pending.includes("password")} busyLabel="Requesting reset…" onPress={() => void run("password", async () => (await api.resetRequest(identity.data!.email)).message)}>Change password by email</Button>
        {notice("password")}
      </>}
    </View>
    <View style={{ gap: 12 }}>
      <Button outline disabled={terminal} onPress={() => onMarketplace("adverts")}>My rental adverts</Button>
      <Button outline disabled={terminal} onPress={() => onMarketplace("messages")}>Messages</Button>
    </View>
    <View style={[s.card, { padding: 16, gap: 12 }]}>
      <Text accessibilityRole="header" style={[s.text, { fontWeight: "700" }]}>Signed-in devices</Text>
      {devices.loading && <Text accessibilityRole="status" style={s.muted}>Loading signed-in devices…</Text>}
      {devices.failed && <><Text accessibilityRole="alert" style={s.text}>Could not load signed-in devices.{devices.loaded ? " Previously loaded devices may be out of date." : ""}</Text><Button outline disabled={devices.loading} onPress={() => void devices.refresh()}>Retry signed-in devices</Button></>}
      {devices.loaded && !devices.data.length && <Text style={s.muted}>No signed-in devices returned. Refresh to check again.</Text>}
      {devices.data.map(device => <View key={device.id} style={{ gap: 8 }}>
        <Text style={s.text}>{device.label}{device.current ? " · This device" : ""}</Text>
        <Text style={s.muted}>Last active {new Date(device.last_used_at).toLocaleString()}</Text>
        {!device.current && <Button outline disabled={terminal} busy={pending.includes(device.id)} busyLabel="Signing out device…" onPress={() => void run(device.id, async () => {
          await api.revokeSession(device.id); devices.update(current => current.filter(item => item.id !== device.id)); return "Device signed out.";
        })}>Sign out this device</Button>}
        {notice(device.id)}
      </View>)}
      {devices.loaded && <Button outline disabled={devices.loading || terminal} onPress={() => void devices.refresh()}>Refresh devices</Button>}
      {Object.entries(feedback).filter(([key, value]) => value.message === "Device signed out." && !devices.data.some(device => device.id === key)).map(([key, value]) => <Text key={key} accessibilityRole="status" style={s.text}>{value.message}</Text>)}
    </View>
    <Button busy={pending.includes("signout")} busyLabel="Signing out…" disabled={pending.includes("delete")} onPress={() => void run("signout", onSignOut)}>{feedback.signout?.failed ? "Retry sign out" : "Sign out"}</Button>
    {notice("signout")}
    <View style={[s.card, { padding: 16, gap: 12 }]}>
      <Text accessibilityRole="header" style={[s.text, { fontWeight: "700" }]}>Delete account</Text>
      <Button disabled={terminal} outline onPress={() => { setDeleting(!deleting); setPassword(""); setFeedback(current => { const next = { ...current }; delete next.delete; return next; }); }}>Delete account…</Button>
      {deleting && <>
        <Text style={s.text}>This permanently removes your account, favorites, saved searches, seen history, messages, and alert subscriptions. Published adverts will be withdrawn. Enter your password to confirm.</Text>
        <PasswordField label="CURRENT PASSWORD" value={password} onChange={setPassword} inputPurpose="current-password" helperText="Enter your current password (12–128 characters) to enable permanent deletion." />
        <Button variant="danger" busy={pending.includes("delete")} busyLabel="Deleting account…" disabled={pending.includes("signout") || password.length < 12 || password.length > 128} onPress={() => void run("delete", async () => {
          const entered = password; setPassword(""); const result = await api.deleteAccount(entered); onDeleted(result.message);
        })}>Permanently delete my account</Button>
        {notice("delete")}
      </>}
    </View>
  </Panel>;
}

export function ResetPasswordDialog(props: { token: string; onClose: () => void; onComplete: (message: string) => void }) {
  return <ResetPasswordForm key={props.token} {...props} />;
}
function ResetPasswordForm({ token, onClose, onComplete }: { token: string; onClose: () => void; onComplete: (message: string) => void }) {
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const passwordRef = useRef<ComponentRef<typeof TextInput>>(null);
  const confirmationRef = useRef<ComponentRef<typeof TextInput>>(null);
  const passwordError = password.length >= 12 && password.length <= 128 ? undefined : "Use 12–128 characters.";
  const confirmationError = confirmation === password && !!confirmation ? undefined : "Repeat the same new password.";
  async function submit() {
    if (busy) return;
    setSubmitted(true);
    if (passwordError) { passwordRef.current?.focus(); return; }
    if (confirmationError) { confirmationRef.current?.focus(); return; }
    setBusy(true); setError("");
    try {
      const result = await api.resetPassword(token, password);
      setPassword(""); setConfirmation("");
      onComplete(result.message);
    } catch (e) { setError((e as Error).message); passwordRef.current?.focus(); }
    finally { setBusy(false); }
  }
  return <Panel title="Choose a new password." onClose={onClose}>
    <PasswordField label="NEW PASSWORD" value={password} onChange={value => { setPassword(value); setError(""); }} inputPurpose="new-password" inputRef={passwordRef} placeholder="At least 12 characters" helperText="Choose 12–128 characters." error={submitted ? passwordError : undefined} onSubmitEditing={() => confirmationRef.current?.focus()} />
    <PasswordField label="REPEAT NEW PASSWORD" value={confirmation} onChange={value => { setConfirmation(value); setError(""); }} inputPurpose="new-password" inputRef={confirmationRef} error={submitted ? confirmationError : undefined} onSubmitEditing={() => void submit()} />
    {!!error && <Text accessibilityRole="alert" style={s.text}>{error}</Text>}
    <Button busy={busy} busyLabel="Changing password…" onPress={() => void submit()}>Change password</Button>
  </Panel>;
}
