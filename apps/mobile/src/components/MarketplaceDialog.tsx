import React, { useEffect, useRef, useState } from "react";
import { ScrollView, Text, View } from "react-native";
import { market } from "../marketplaceApi";
import { c, s } from "../theme";
import { Listing } from "../types";
import { Chip, Panel } from "./UI";
import { MessagesPanel } from "./MessagesPanel";
import { InboxModel } from "./messagesState";
import { AdvertDesk } from "./AdvertDesk";
import { ReviewDesk } from "./ReviewDesk";

type Mode = "adverts" | "messages" | "review";
type Contact = NonNullable<Listing["contact_adverts"]>[number];
export default function MarketplaceDialog({
  mode: initialMode,
  contact,
  onClose,
  onOpenHome,
}: {
  mode: Mode;
  contact?: Contact;
  onClose: () => void;
  onOpenHome: (id: string) => void;
}) {
  const [mode, setMode] = useState<Mode>(initialMode);
  const [moderator, setModerator] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [inbox] = useState(
    () =>
      new InboxModel(
        market,
        contact
          ? { kind: "advert", id: contact.id, title: contact.name }
          : null,
      ),
  );
  const messagesScroll = useRef<React.ComponentRef<typeof ScrollView>>(null);
  const onMessagesScroll = useRef<(() => void) | null>(null);
  const stopMessages = useRef<(() => void) | null>(null);
  const changeMode = (next: Mode) => {
    if (mode === "messages" && next !== mode) stopMessages.current?.();
    setMode(next);
  };
  useEffect(() => {
    let active = true;
    market
      .capabilities()
      .then((r) => {
        if (active) setModerator(r.moderator);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, []);
  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Panel
      title="Your rental desk."
      wide
      onClose={() => {
        stopMessages.current?.();
        onClose();
      }}
      inboxViewport={
        mode === "messages"
          ? {
              ref: messagesScroll,
              onChange: () => onMessagesScroll.current?.(),
            }
          : undefined
      }
    >
      <View style={[s.row, { flexWrap: "wrap", gap: 8 }]}>
        <Chip
          label="My adverts"
          selected={mode === "adverts"}
          onPress={() => changeMode("adverts")}
        />
        <Chip
          label="Messages"
          selected={mode === "messages"}
          onPress={() => changeMode("messages")}
        />
        {moderator && (
          <Chip
            label="Review reports"
            selected={mode === "review"}
            onPress={() => changeMode("review")}
          />
        )}
      </View>
      {!!error && (
        <Text accessibilityRole="alert" style={{ color: c.warning }}>
          {error}
        </Text>
      )}
      {mode === "adverts" ? (
        <AdvertDesk run={run} busy={busy} onOpenHome={onOpenHome} />
      ) : mode === "messages" ? (
        <MessagesPanel
          model={inbox}
          contact={contact}
          onOpenHome={onOpenHome}
          scroll={messagesScroll}
          onViewportChange={onMessagesScroll}
          stop={stopMessages}
        />
      ) : (
        <ReviewDesk run={run} busy={busy} />
      )}
    </Panel>
  );
}

export interface RentalDeskWork {
  run: (action: () => Promise<void>) => Promise<void>;
  busy: boolean;
}
