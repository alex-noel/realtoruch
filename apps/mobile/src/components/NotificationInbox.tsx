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
}: {
  user: string | null;
  message?: string;
  inbox: Inbox;
  onOpen: (item: RentalNotification) => void;
  onRead: (id: string) => void;
  onMore: () => void;
  onSignIn: () => void;
}) {
  const [enabled, setEnabled] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [email, setEmail] = useState<{
    enabled: boolean;
    verified: boolean;
    confirmation_pending?: boolean;
  }>({ enabled: false, verified: false });
  const [emailBusy, setEmailBusy] = useState(false);
  useEffect(() => {
    let active = true;
    pushEnabled()
      .then((value) => {
        if (active) setEnabled(value);
      })
      .catch(() => {});
    if (user)
      request<typeof email>("/v1/me/email-notifications")
        .then((value) => {
          if (active) setEmail(value);
        })
        .catch(() => {});
    return () => {
      active = false;
    };
  }, [user]);
  async function toggleEmail() {
    setEmailBusy(true);
    setError("");
    try {
      const result = await request<typeof email>("/v1/me/email-notifications", {
        method: "PUT",
        body: JSON.stringify({ enabled: !email.enabled }),
      });
      setEmail(result);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setEmailBusy(false);
    }
  }
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
            <Button disabled={emailBusy} onPress={toggleEmail}>
              {emailBusy
                ? "Please wait…"
                : email.enabled
                  ? "Disable email alerts"
                  : email.confirmation_pending
                    ? "Resend confirmation email"
                    : "Enable email alerts"}
            </Button>
            <Button outline disabled={busy} onPress={toggle}>
              {busy
                ? "Please wait…"
                : enabled
                  ? "Disable device alerts"
                  : "Enable device alerts"}
            </Button>
          </View>
          {email.enabled ? (
            <Text style={s.muted}>Email alerts are on for {user}.</Text>
          ) : email.confirmation_pending ? (
            <Text accessibilityRole="status" style={s.muted}>
              Check {user} for a confirmation link. It expires in one hour.
            </Text>
          ) : null}
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
                  <Button outline onPress={() => onRead(item.id)}>
                    Mark as read
                  </Button>
                ) : null}
              </View>
            </View>
          ))}
          {inbox.items.length >= inbox.page * inbox.page_size ? (
            <Button outline onPress={onMore}>
              Older notifications
            </Button>
          ) : null}
        </>
      )}
    </View>
  );
}
