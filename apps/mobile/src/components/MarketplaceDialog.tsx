import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Platform, ScrollView, Text, View } from "react-native";
import { market } from "../marketplaceApi";
import { subscribeSession } from "../api";
import { c, s } from "../theme";
import { Listing } from "../types";
import { Button, Chip, Panel } from "./UI";
import { MessagesPanel } from "./MessagesPanel";
import { InboxModel } from "./messagesState";
import { AdvertDesk } from "./AdvertDesk";
import { ReviewDesk } from "./ReviewDesk";

type Mode = "adverts" | "messages" | "review";
type Contact = NonNullable<Listing["contact_adverts"]>[number];
const sendingWarning = "Wait for the message to finish sending before leaving.";
export type ExitGuard = { dirty: () => boolean; canSave: () => boolean; save: () => Promise<boolean>; focus: () => void; discard?: () => void; isBusy?: () => boolean };
export type RegisterExitGuard = (guard: ExitGuard | null) => void;
export type RequestExit = (action: () => void) => void;
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
  const guard = useRef<ExitGuard | null>(null);
  const savingLeave = useRef(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; pendingRef.current = null; }; }, []);
  const [pendingExit, setPendingExit] = useState<(() => void) | null>(null);
  const pendingRef = useRef<(() => void) | null>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const pendingMessages = useRef(false);
  const promptRef = useRef<React.ComponentRef<typeof View>>(null);
  const registerExitGuard = useCallback<RegisterExitGuard>((value) => { guard.current = value; }, []);
  function beginExit(action: () => void, includeMessages: boolean) {
    if (busy || pendingRef.current || guard.current?.isBusy?.()) return;
    if (includeMessages && inbox.snapshot().jobs.send) { setError(sendingWarning); return; }
    const messagesDirty = includeMessages && inbox.hasDrafts();
    if (!guard.current?.dirty() && !messagesDirty) { action(); return; }
    setError("");
    if (Platform.OS === "web" && document.activeElement instanceof HTMLElement) previousFocus.current = document.activeElement;
    pendingMessages.current = messagesDirty;
    pendingRef.current = action;
    setPendingExit(() => action);
  }
  const requestExit: RequestExit = action => beginExit(action, false);
  function keepEditing() {
    if (savingLeave.current) return;
    pendingRef.current = null; pendingMessages.current = false; setPendingExit(null);
    requestAnimationFrame(() => {
      const prior = previousFocus.current;
      if (Platform.OS === "web" && prior?.isConnected && prior.matches("input, textarea, select")) prior.focus();
      else if (guard.current) guard.current.focus();
      else {
        focusMessages.current?.();
        if (Platform.OS === "web" && prior?.isConnected) prior.focus();
      }
    });
  }
  function discard() {
    if (savingLeave.current) return;
    guard.current?.discard?.();
    if (pendingMessages.current) inbox.discardDrafts();
    pendingMessages.current = false;
    const action = pendingRef.current;
    pendingRef.current = null; setPendingExit(null);
    action?.();
  }
  async function saveAndLeave() {
    const current = guard.current, action = pendingRef.current;
    if (!current || !action || busy || savingLeave.current || pendingMessages.current || !current.canSave()) return;
    savingLeave.current = true;
    try {
      const saved = await current.save();
      savingLeave.current = false;
      if (saved && mounted.current && pendingRef.current === action) {
        pendingRef.current = null; setPendingExit(null); action();
      } else if (!saved && mounted.current && pendingRef.current === action) {
        setError(current => current || "Could not finish saving. Keep editing to review the details.");
      }
    } finally { savingLeave.current = false; }
  }
  useLayoutEffect(() => { if (pendingExit) promptRef.current?.focus?.(); }, [pendingExit]);
  const [inbox] = useState(
    () =>
      new InboxModel(
        market,
        contact
          ? { kind: "advert", id: contact.id, title: contact.name }
          : null,
      ),
  );
  useEffect(() => inbox.subscribe(() => {
    if (!inbox.snapshot().jobs.send) setError(current => current === sendingWarning ? "" : current);
  }), [inbox]);
  useEffect(() => {
    const unsubscribe = subscribeSession(state => {
      if (state === "signed-out" || state === "reauth" || state === "storage-cleanup") inbox.clearPrivate();
    });
    return () => { unsubscribe(); inbox.clearPrivate(); };
  }, [inbox]);
  const focusMessages = useRef<(() => void) | null>(null);
  const messagesScroll = useRef<React.ComponentRef<typeof ScrollView>>(null);
  const onMessagesScroll = useRef<(() => void) | null>(null);
  const stopMessages = useRef<(() => void) | null>(null);
  const changeMode = (next: Mode) => {
    if (next === mode) return;
    requestExit(() => {
      if (mode === "messages") stopMessages.current?.();
      setMode(next);
    });
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
      return true;
    } catch (e) {
      setError((e as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  }
  return (
    <Panel
      title="Your rental desk."
      wide
      onClose={() => {
        if (pendingRef.current) { keepEditing(); return; }
        beginExit(() => { stopMessages.current?.(); onClose(); }, true);
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
      {pendingExit && <View ref={promptRef} focusable tabIndex={-1} accessibilityRole="alert" style={[s.card, { padding: 18, gap: 12, alignItems: "flex-start" }]}>
        <Text style={s.title}>Discard unsaved changes?</Text>
        <Text style={s.muted}>{pendingMessages.current ? "Unsent message drafts stay only while this rental desk is open. Leaving will discard them." : "Your changes have not been saved."}</Text>
        <View style={[s.row, { gap: 8, flexWrap: "wrap" }]}>
          <Button onPress={keepEditing} disabled={busy}>Keep editing</Button>
          <Button outline onPress={discard} disabled={busy}>Discard changes</Button>
          {!pendingMessages.current && guard.current?.canSave() && <Button outline onPress={saveAndLeave} disabled={busy}>Save and leave</Button>}
        </View>
      </View>}
      {!!error && (
        <Text accessibilityRole="alert" style={{ color: c.warning }}>
          {error}
        </Text>
      )}
      <View style={{ display: pendingExit ? "none" : "flex", gap: 20 }}>
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
      {mode === "adverts" ? (
        <AdvertDesk run={run} busy={busy} onOpenHome={id => beginExit(() => { stopMessages.current?.(); onOpenHome(id); }, true)} registerExitGuard={registerExitGuard} requestExit={requestExit} />
      ) : mode === "messages" ? (
        <MessagesPanel
          model={inbox}
          contact={contact}
          onOpenHome={id => beginExit(() => { stopMessages.current?.(); onOpenHome(id); }, true)}
          scroll={messagesScroll}
          onViewportChange={onMessagesScroll}
          stop={stopMessages}
          focusComposer={focusMessages}
        />
      ) : (
        <ReviewDesk run={run} busy={busy} />
      )}
      </View>
    </Panel>
  );
}

export interface RentalDeskWork {
  run: (action: () => Promise<void>) => Promise<boolean>;
  busy: boolean;
}
