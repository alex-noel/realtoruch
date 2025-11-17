import React, { useEffect, useState } from "react";
import { Text, View } from "react-native";
import { NotificationInbox as Inbox, RentalNotification } from "../types";
import { disablePush, enablePush, pushEnabled } from "../pushClient";
import { Button, money } from "./UI";
import { c, s } from "../theme";
import { request } from "../api";
export default function NotificationInbox({
  user,
  message,
  inbox,
  onOpen,
  onRead,
  onMore,
  onSignIn,
  morePending, moreFailed, reading, readFailed,
}: {
  user: string | null;
  message?: string;
  inbox: Inbox;
  onOpen: (item: RentalNotification) => void;
  onRead: (id: string) => void;
  onMore: () => void;
  onSignIn: () => void;
  morePending: boolean;
  moreFailed: boolean;
  reading: string[];
  readFailed: string[];
}) {
  const [enabled, setEnabled] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    pushEnabled()
      .then((value) => {
        if (active) setEnabled(value);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [user]);
  async function toggle() {
    setBusy(true);
    setError("");
    try {
      if (enabled) await disablePush();
      else await enablePush();
      setEnabled(!enabled);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <View style={{ gap: 20 }}>
      <Text style={s.label}>YOUR RENTAL UPDATES</Text>
      <Text style={s.title}>Notifications.</Text>
      {message ? (
        <Text accessibilityRole="alert" style={s.text}>
          {message}
        </Text>
      ) : null}
      <Text style={s.muted}>
        New matches for your saved areas and lower prices on homes you like.
        Repeated adverts at the same price stay quiet.
      </Text>
      {!user ? (
        <Button onPress={onSignIn}>Sign in for notifications</Button>
      ) : (
        <>
          <View style={[s.row, { gap: 12, flexWrap: "wrap" }]}>
            <Text style={s.text}>{inbox.unread_count} unread</Text>
            <EmailPreference key={user} user={user} />
            <Button outline disabled={busy} onPress={toggle}>
              {busy
                ? "Please wait…"
                : enabled
                  ? "Disable device alerts"
                  : "Enable device alerts"}
            </Button>
          </View>
          {error ? (
            <Text accessibilityRole="alert" style={{ color: c.warning }}>
              {error}
            </Text>
          ) : null}
          {!inbox.items.length ? (
            <View style={[s.card, { padding: 24, gap: 10 }]}>
              <Text style={s.text}>You're all caught up.</Text>
              <Text style={s.muted}>
                Save a search to watch an area, or like a home to follow its
                price.
              </Text>
            </View>
          ) : null}
          {inbox.items.map((item) => (
            <View
              key={item.id}
              style={[
                s.card,
                {
                  padding: 22,
                  gap: 12,
                  borderLeftWidth: item.read_at ? 1 : 3,
                  borderLeftColor: item.read_at ? c.line : c.green,
                },
              ]}
            >
              <Text style={[s.label, { color: c.green }]}>
                {item.kind === "price_drop"
                  ? "PRICE DROP ON A SAVED HOME"
                  : "NEW MATCH"}
                {item.read_at ? " · READ" : ""}
              </Text>
              <Text style={[s.title, { fontSize: 20 }]}>{item.title}</Text>
              <Text style={s.text}>
                {item.previous_rent_pln
                  ? `${money(item.previous_rent_pln)} → `
                  : ""}
                {money(item.rent_pln)} / month
              </Text>
              <Text style={s.muted}>
                {new Date(item.created_at).toLocaleString()}
                {item.listing_status !== "active"
                  ? ` · ${item.listing_status === "inactive" ? "Now delisted" : "Availability unconfirmed"}`
                  : ""}
              </Text>
              <View style={[s.row, { gap: 10, flexWrap: "wrap" }]}>
                <Button onPress={() => onOpen(item)}>View home</Button>
                {!item.read_at ? (
                  <Button outline disabled={reading.includes(item.id)} onPress={() => onRead(item.id)}>
                    {reading.includes(item.id) ? "Marking as read…" : "Mark as read"}
                  </Button>
                ) : null}
              </View>
              {readFailed.includes(item.id) && <Text accessibilityRole="alert" style={{ color: c.warning }}>Could not mark this notification as read. Please try again.</Text>}
            </View>
          ))}
          {moreFailed && <Text accessibilityRole="alert" style={{ color: c.warning }}>Could not load older notifications. Please try again.</Text>}
          {inbox.has_more ? (
            <Button outline disabled={morePending} onPress={onMore}>
              {morePending ? "Loading older notifications…" : moreFailed ? "Retry older notifications" : "Older notifications"}
            </Button>
          ) : null}
        </>
      )}
    </View>
  );
}


type EmailValue = {
  configured?: boolean;
  enabled: boolean;
  verified: boolean;
  confirmation_pending?: boolean;
};
export type EmailPreferenceState = {
  value: EmailValue | null;
  loading: boolean;
  busy: boolean;
  loadFailed: boolean;
  updateFailed: boolean;
};
const emptyEmail = (): EmailPreferenceState => ({
  value: null,
  loading: false,
  busy: false,
  loadFailed: false,
  updateFailed: false,
});

// The controller belongs to one mounted account; disposal fences every result.
export function createEmailPreference(
  load: () => Promise<EmailValue>,
  save: (enabled: boolean) => Promise<EmailValue>,
  changed: (state: EmailPreferenceState) => void,
) {
  let state = emptyEmail();
  let epoch = 0;
  const publish = (next: EmailPreferenceState) => {
    state = next;
    changed(state);
  };
  async function refresh() {
    if (state.loading || state.busy) return;
    const intent = ++epoch;
    publish({ ...state, loading: true, loadFailed: false });
    try {
      const value = await load();
      if (epoch === intent)
        publish({
          value,
          loading: false,
          busy: false,
          loadFailed: false,
          updateFailed: false,
        });
    } catch {
      if (epoch === intent) publish({ ...state, loading: false, loadFailed: true });
    }
  }
  async function toggle() {
    if (
      !state.value ||
      state.value.configured === false ||
      state.busy ||
      state.loading ||
      state.loadFailed
    ) return;
    const intent = epoch;
    publish({ ...state, busy: true, updateFailed: false });
    try {
      const value = await save(!state.value.enabled);
      if (epoch === intent) publish({ ...state, value, busy: false, updateFailed: false });
    } catch {
      if (epoch === intent) publish({ ...state, busy: false, updateFailed: true });
    }
  }
  return {
    refresh,
    toggle,
    dispose: () => {
      epoch++;
    },
  };
}

function EmailPreference({ user }: { user: string }) {
  const [email, setEmail] = useState<EmailPreferenceState>(emptyEmail);
  const [controller] = useState(() =>
    createEmailPreference(
      () => request<EmailValue>("/v1/me/email-notifications"),
      (enabled) =>
        request<EmailValue>("/v1/me/email-notifications", {
          method: "PUT",
          body: JSON.stringify({ enabled }),
        }),
      setEmail,
    ),
  );
  useEffect(() => {
    void controller.refresh();
    return controller.dispose;
  }, [controller]);
  return (
    <View style={{ gap: 8, alignItems: "flex-start" }}>
      {email.loading && (
        <Text accessibilityRole="status" style={s.muted}>
          {email.value
            ? "Refreshing email alert settings…"
            : "Loading email alert settings…"}
        </Text>
      )}
      {email.loadFailed && (
        <>
          <Text accessibilityRole="alert" style={{ color: c.warning }}>
            Could not load email alert settings.
          </Text>
          <Button outline disabled={email.loading} onPress={controller.refresh}>
            Retry email settings
          </Button>
        </>
      )}
      {email.value && email.value.configured !== false && (
        <Button
          disabled={email.busy || email.loading || email.loadFailed}
          onPress={controller.toggle}
        >
          {email.busy
            ? "Please wait…"
            : email.value.enabled
              ? "Disable email alerts"
              : email.value.confirmation_pending
                ? "Resend confirmation email"
                : "Enable email alerts"}
        </Button>
      )}
      {email.value?.configured === false ? (
        <Text style={s.muted}>
          Email alerts are unavailable right now. In-app notifications remain available.
        </Text>
      ) : email.value?.enabled ? (
        <Text style={s.muted}>
          {email.loadFailed
            ? `Email alerts were last confirmed on for ${user}.`
            : `Email alerts are on for ${user}.`}
        </Text>
      ) : email.value?.confirmation_pending ? (
        <Text accessibilityRole="status" style={s.muted}>
          Check {user} for a confirmation link. It expires in one hour.
        </Text>
      ) : email.value ? (
        <Text style={s.muted}>
          {email.loadFailed
            ? "Email alerts were last confirmed off."
            : "Email alerts are off."}
        </Text>
      ) : null}
      {email.updateFailed && (
        <Text accessibilityRole="alert" style={{ color: c.warning }}>
          Could not update email alerts. Please try again.
        </Text>
      )}
    </View>
  );
}
