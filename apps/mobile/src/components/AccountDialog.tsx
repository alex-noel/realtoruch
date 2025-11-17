import React, { type ComponentRef, useEffect, useRef, useState } from "react";
import { Text, TextInput, View } from "react-native";
import { api, Account } from "../api";
import { s } from "../theme";
import { Button, Field, PasswordField, Panel } from "./UI";

type Sessions = Awaited<ReturnType<typeof api.sessions>>["items"];
export function AccountDialog({
  onClose,
  onSignOut,
  onDeleted,
  onMarketplace,
}: {
  onMarketplace: (mode: "adverts" | "messages") => void;
  onClose: () => void;
  onSignOut: () => Promise<void>;
  onDeleted: (message: string) => void;
}) {
  const [account, setAccount] = useState<Account | null>(null);
  const [sessions, setSessions] = useState<Sessions>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [password, setPassword] = useState("");
  useEffect(() => {
    let active = true;
    Promise.all([api.me(), api.sessions()])
      .then(([me, list]) => {
        if (active) {
          setAccount(me);
          setSessions(list.items);
        }
      })
      .catch((e) => {
        if (active) setMessage(e.message);
      });
    return () => {
      active = false;
    };
  }, []);
  async function run(action: () => Promise<void>) {
    setBusy(true);
    setMessage("");
    try {
      await action();
    } catch (e) {
      setMessage((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Panel title="Your account." onClose={onClose}>
      {account && (
        <>
          <Text style={s.text}>{account.email}</Text>
          <Text style={s.muted}>
            {account.email_verified
              ? "Email verified"
              : "Email not yet verified"}
          </Text>
          {!account.email_verified && (
            <Button
              disabled={busy}
              outline
              onPress={() =>
                run(async () => {
                  setMessage((await api.requestVerification()).message);
                })
              }
            >
              Send verification email
            </Button>
          )}
          <Button
            disabled={busy}
            outline
            onPress={() =>
              run(async () => {
                setMessage((await api.resetRequest(account.email)).message);
              })
            }
          >
            Change password by email
          </Button>
        </>
      )}
      <Button outline onPress={() => onMarketplace("adverts")}>
        My rental adverts
      </Button>
      <Button outline onPress={() => onMarketplace("messages")}>
        Messages
      </Button>
      <Text style={s.label}>SIGNED-IN DEVICES</Text>
      {sessions.map((device) => (
        <View key={device.id} style={{ gap: 8 }}>
          <Text numberOfLines={2} style={s.text}>
            {device.label}
            {device.current ? " · This device" : ""}
          </Text>
          <Text style={s.muted}>
            Last active {new Date(device.last_used_at).toLocaleString()}
          </Text>
          {!device.current && (
            <Button
              disabled={busy}
              outline
              onPress={() =>
                run(async () => {
                  await api.revokeSession(device.id);
                  setSessions((current) =>
                    current.filter((item) => item.id !== device.id),
                  );
                  setMessage("Device signed out.");
                })
              }
            >
              Sign out this device
            </Button>
          )}
        </View>
      ))}
      <Button disabled={busy} onPress={() => run(onSignOut)}>
        Sign out
      </Button>
      <Button disabled={busy} outline onPress={() => { setDeleting(!deleting); setPassword(""); setMessage(""); }}>
        Delete account…
      </Button>
      {deleting && (
        <View style={{ gap: 16 }}>
          <Text style={s.text}>
            This permanently removes your account, favorites, saved searches,
            seen history, messages, and alert subscriptions. Published adverts
            will be withdrawn. Enter your password to confirm.
          </Text>
          <PasswordField
            label="CURRENT PASSWORD"
            value={password}
            onChange={setPassword}
            inputPurpose="current-password"
            helperText="Enter your current password (12–128 characters) to enable permanent deletion."
          />
          <Button
            disabled={busy || password.length < 12 || password.length > 128}
            onPress={() =>
              run(async () => {
                const result = await api.deleteAccount(password);
                onDeleted(result.message);
              })
            }
          >
            Permanently delete my account
          </Button>
        </View>
      )}
      {!!message && (
        <Text accessibilityRole="alert" style={s.text}>
          {message}
        </Text>
      )}
    </Panel>
  );
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
