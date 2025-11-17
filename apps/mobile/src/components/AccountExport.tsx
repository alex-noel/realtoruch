import React, { useEffect, useRef, useState } from "react";
import { Platform, Text, View } from "react-native";
import { api, getSessionRevision } from "../api";
import { deliverAccountExport } from "../accountExport";
import { s } from "../theme";
import { Button, PasswordField } from "./UI";

export function AccountExport({ disabled }: { disabled: boolean }) {
  const [open, setOpen] = useState(false), [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false), [message, setMessage] = useState("");
  const [failed, setFailed] = useState(false);
  const alive = useRef(true), controller = useRef<AbortController | null>(null);
  useEffect(() => { alive.current = true; return () => { alive.current = false; controller.current?.abort(); }; }, []);
  async function exportData() {
    if (disabled || busy || controller.current || password.length < 12 || password.length > 128) return;
    const request = new AbortController(); controller.current = request;
    const revision = getSessionRevision();
    const current = () => alive.current && !request.signal.aborted && getSessionRevision() === revision;
    let entered = password, token = ""; setPassword(""); setBusy(true); setMessage(""); setFailed(false);
    try {
      const auth = await api.authorizeExport(entered, request.signal); entered = ""; token = auth.export_token;
      if (!current()) return;
      const data = await api.exportAccount(token, request.signal); token = "";
      if (!current()) return;
      await deliverAccountExport(data, current);
      if (current()) { setOpen(false); setMessage(Platform.OS === "web" ? "Your JSON download has started." : "Share sheet closed. Any copy you saved or shared is managed by the app you selected."); }
    } catch (error) {
      if (current()) { setFailed(true); setMessage((error as Error).message); }
    } finally {
      entered = ""; token = ""; controller.current = null;
      if (alive.current) setBusy(false);
    }
  }
  return <View style={[s.card, { padding: 16, gap: 12 }]}>
    <Text accessibilityRole="header" style={[s.text, { fontWeight: "700" }]}>Your data</Text>
    <Text style={s.muted}>Export your account, saved homes, searches, adverts and sent messages as JSON. This file contains private information.</Text>
    {!open ? <Button outline disabled={disabled} onPress={() => { setOpen(true); setMessage(""); }}>Export my data</Button> : <>
      <PasswordField label="EXPORT PASSWORD" value={password} onChange={setPassword} inputPurpose="current-password" helperText="Re-enter your current password. Export authorization lasts five minutes and is used only for this download." onSubmitEditing={() => void exportData()} />
      <Button disabled={disabled || password.length < 12 || password.length > 128} busy={busy} busyLabel="Preparing export…" onPress={() => void exportData()}>{Platform.OS === "web" ? "Download my JSON data" : "Save or share my JSON data"}</Button>
      <Button outline onPress={() => { controller.current?.abort(); setOpen(false); setPassword(""); setMessage(""); }}>Cancel export</Button>
    </>}
    {!!message && <Text accessibilityRole={failed ? "alert" : "status"} style={s.text}>{message}</Text>}
  </View>;
}
