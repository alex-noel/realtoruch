import React, { useEffect, useState } from "react";
import { Text, View } from "react-native";
import { api, Account } from "../api";
import { s } from "../theme";
import { Button, Field, Panel } from "./UI";

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
      <Button disabled={busy} outline onPress={() => setDeleting(!deleting)}>
        Delete account…
      </Button>
      {deleting && (
        <View style={{ gap: 16 }}>
          <Text style={s.text}>
            This permanently removes your account, favorites, saved searches,
            seen history, messages, and alert subscriptions. Published adverts
            will be withdrawn. Enter your password to confirm.
          </Text>
          <Field
            label="CURRENT PASSWORD"
            value={password}
            onChange={setPassword}
            secure
          />
          <Button
            disabled={busy || password.length < 12}
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

export function ResetPasswordDialog({
  token,
  onClose,
  onComplete,
}: {
  token: string;
  onClose: () => void;
  onComplete: (message: string) => void;
}) {
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit() {
    setBusy(true);
    setError("");
    try {
      onComplete((await api.resetPassword(token, password)).message);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Panel title="Choose a new password." onClose={onClose}>
      <Field
        label="NEW PASSWORD"
        value={password}
        onChange={setPassword}
        secure
        placeholder="At least 12 characters"
      />
      <Field
        label="REPEAT NEW PASSWORD"
        value={confirmation}
        onChange={setConfirmation}
        secure
      />
      {!!error && (
        <Text accessibilityRole="alert" style={s.text}>
          {error}
        </Text>
      )}
      <Button
        disabled={busy || password.length < 12 || password !== confirmation}
        onPress={submit}
      >
        {busy ? "Changing password…" : "Change password"}
      </Button>
    </Panel>
  );
}
