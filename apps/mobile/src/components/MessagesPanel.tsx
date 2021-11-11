import React, {
  Fragment,
  useCallback,
  useLayoutEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type ComponentRef,
  type RefObject,
} from "react";
import {
  AppState,
  Platform,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import { subscribeSession } from "../api";
import { market, type Message } from "../marketplaceApi";
import type { Listing } from "../types";
import { c, s } from "../theme";
import { InboxModel, highestVisibleIncoming } from "./messagesState";
import { Button } from "./UI";

type Contact = NonNullable<Listing["contact_adverts"]>[number];
type Call = RefObject<(() => void) | null>;
type Scroll = RefObject<ComponentRef<typeof ScrollView> | null>;
type Card = ComponentRef<typeof View>;

function measureView(
  view: Pick<Card, "measureInWindow">,
  report: (rect: { y: number; height: number }) => void,
) {
  view.measureInWindow((_x, y, width, height) => {
    report({ y, height: width > 0 ? height : 0 });
  });
}

function useDisplayedMessages(
  model: InboxModel,
  scroll: Scroll,
  onViewportChange: Call,
  { active, thread }: ReturnType<InboxModel["snapshot"]>,
) {
  const cards = useRef(new Map<string, Card>());
  const epoch = useRef(0);
  const frame = useRef<number | null>(null);
  const measure = useCallback(() => {
    epoch.current++;
    if (frame.current !== null) return;
    frame.current = requestAnimationFrame(() => {
      frame.current = null;
      const generation = epoch.current;
      const { active, thread } = model.snapshot();
      const viewport = scroll.current?.getNativeScrollRef();
      if (!active || !thread || !viewport) return;
      const candidates = (thread.ranges[0]?.items ?? []).flatMap((message) => {
        const card = cards.current.get(message.id);
        return card && !message.mine ? [{ card, message }] : [];
      });
      if (!candidates.length) return;
      measureView(viewport, (bounds) => {
        if (epoch.current !== generation || !bounds.height) return;
        const measured: Parameters<typeof highestVisibleIncoming>[0] = [];
        for (const { card, message } of candidates) {
          measureView(card, (rect) => {
            if (epoch.current !== generation) return;
            measured.push({ message, rect });
            if (measured.length !== candidates.length) return;
            const visible = highestVisibleIncoming(measured, bounds);
            if (visible) model.acknowledgeDisplayed(thread, visible);
          });
        }
      });
    });
  }, [model, scroll]);
  useLayoutEffect(() => {
    onViewportChange.current = measure;
    if (active) measure();
    return () => {
      onViewportChange.current = null;
      epoch.current++;
      if (frame.current !== null) cancelAnimationFrame(frame.current);
      frame.current = null;
    };
  }, [active, thread, measure, onViewportChange]);

  const register = useCallback((id: string, view: Card | null) => {
    if (view) cards.current.set(id, view);
    else cards.current.delete(id);
  }, []);
  const jumpToLatest = () => {
    const viewport = scroll.current;
    const content = viewport?.getInnerViewRef();
    const latest = thread?.ranges.at(-1)?.items.at(-1);
    const card = latest && cards.current.get(latest.id);
    if (viewport && content && card) {
      card.measureLayout(content, (_x, y) => {
        if (model.snapshot().thread === thread && model.snapshot().active) {
          viewport.scrollTo({ y: Math.max(0, y - 12), animated: true });
        }
      });
    }
  };
  return { register, measure, jumpToLatest };
}

function MessageCard({
  message,
  register,
  measure,
}: {
  message: Message;
  register: (id: string, card: Card | null) => void;
  measure: () => void;
}) {
  const ref = useCallback(
    (card: Card | null) => register(message.id, card),
    [message.id, register],
  );
  return (
    <View
      ref={ref}
      collapsable={false}
      onLayout={measure}
      style={[
        s.card,
        {
          padding: 16,
          backgroundColor: message.mine ? c.pale : c.paper,
          gap: 6,
        },
      ]}
    >
      <Text style={[s.label, { color: c.ink }]}>
        {message.mine ? "YOU" : "REPLY"} ·{" "}
        {new Date(message.created_at).toLocaleString()}
      </Text>
      <Text style={s.text}>{message.body}</Text>
    </View>
  );
}

function Status({ children }: { children: React.ReactNode }) {
  return (
    <Text accessibilityLiveRegion="polite" style={s.text}>
      {children}
    </Text>
  );
}

function Retry({
  error,
  label,
  action,
}: {
  error?: string;
  label: string;
  action: () => void;
}) {
  if (!error) return null;
  return (
    <View style={{ gap: 8 }}>
      <Text accessibilityRole="alert" style={[s.text, { color: c.warning }]}>
        {error}
      </Text>
      <Button outline onPress={action}>
        {label}
      </Button>
    </View>
  );
}

export function MessagesPanel({
  model,
  contact,
  onOpenHome,
  scroll,
  onViewportChange,
  stop,
}: {
  model: InboxModel;
  contact?: Contact;
  onOpenHome: (id: string) => void;
  scroll: Scroll;
  onViewportChange: Call;
  stop: Call;
}) {
  const [description, setDescription] = useState("");
  const state = useSyncExternalStore(model.subscribe, model.snapshot);
  const { active, target, inbox, thread, body, jobs, errors, historyCursor } =
    state;
  const { register, measure, jumpToLatest } = useDisplayedMessages(
    model,
    scroll,
    onViewportChange,
    state,
  );
  const selected = target?.kind === "thread";
  const recipient = target?.kind === "advert" ? contact : undefined;

  useLayoutEffect(() => {
    model.attach();
    stop.current = model.stop;
    let appState = AppState.currentState;
    const sync = () => {
      const web = Platform.OS === "web" && typeof document !== "undefined";
      model.setForeground(
        (appState === "active" || (web && appState === null)) &&
          (!web || document.visibilityState === "visible"),
      );
    };
    const app = AppState.addEventListener("change", (state) => {
      appState = state;
      sync();
    });
    const web = Platform.OS === "web" && typeof document !== "undefined";
    if (web) document.addEventListener("visibilitychange", sync);
    const unsubscribe = subscribeSession((state) => {
      if (
        state === "signed-out" ||
        state === "reauth" ||
        state === "storage-cleanup"
      )
        model.stop();
    });
    sync();
    return () => {
      unsubscribe();
      model.stop();
      stop.current = null;
      app.remove();
      if (web) document.removeEventListener("visibilitychange", sync);
    };
  }, [model, stop]);

  useLayoutEffect(() => {
    scroll.current?.scrollTo({ y: 0, animated: false });
  }, [scroll, target]);

  useLayoutEffect(() => {
    if (!active || !recipient) return;
    const job = new AbortController();
    market
      .advertiser(recipient.profile_id, job.signal)
      .then(({ profile }) => {
        if (!job.signal.aborted) setDescription(profile.description);
      })
      .catch(() => {});
    return () => job.abort();
  }, [active, recipient]);

  const loadHistory = (cursor: string) => void model.loadHistory(cursor);
  const canSend =
    active && !jobs.send && !jobs.block && !!body.trim() && body.length <= 4000;
  const showComposer = !!recipient || !!(thread && !thread.blocked);
  return (
    <View style={{ gap: 16, minWidth: 0 }}>
      {recipient && (
        <View style={{ gap: 8 }}>
          <Text accessibilityRole="header" style={[s.title, { fontSize: 21 }]}>
            Write to {recipient.name}
          </Text>
          <Text style={s.text}>
            {description || recipient.kind} · Advertiser type is self-declared.
          </Text>
        </View>
      )}
      {selected && (
        <>
          <Button outline onPress={() => model.select(null)}>
            All conversations
          </Button>
          <Text accessibilityRole="header" style={[s.title, { fontSize: 21 }]}>
            {target.title}
          </Text>
          {!thread && !errors.thread && <Status>Loading messages…</Status>}
          <Retry
            error={errors.thread}
            label="Retry loading messages"
            action={() => void model.refreshThread()}
          />
        </>
      )}
      {thread && (
        <>
          {!thread.ranges.length && (
            <Status>No messages in this conversation yet.</Status>
          )}
          {thread.ranges.length > 1 && (
            <Status>
              Some messages are missing between these pages. Load missing
              messages to recover that part of the conversation.
            </Status>
          )}
          {thread.ranges.length === 1 && thread.ranges[0].items.length > 1 && (
            <Button outline onPress={jumpToLatest}>
              Jump to latest messages
            </Button>
          )}
          {thread.ranges.map((range, index) => (
            <Fragment key={range.items[0].id}>
              {range.next_cursor && (
                <Button
                  outline
                  disabled={!!jobs.older}
                  onPress={() => loadHistory(range.next_cursor!)}
                >
                  {jobs.older && historyCursor === range.next_cursor
                    ? "Loading messages…"
                    : index
                      ? "Load missing messages"
                      : "Load older messages"}
                </Button>
              )}
              {range.items.map((message) => (
                <MessageCard
                  key={message.id}
                  message={message}
                  register={register}
                  measure={measure}
                />
              ))}
            </Fragment>
          ))}
          <Retry
            error={errors.older}
            label="Retry loading history"
            action={() => historyCursor && loadHistory(historyCursor)}
          />
          {thread.blocked && <Status>This conversation is blocked.</Status>}
          {thread.blocked && !!body && (
            <Status>
              Your unsent draft is saved while this conversation is blocked.
            </Status>
          )}
          {(!thread.blocked || thread.can_unblock) && (
            <Button
              outline
              disabled={!!jobs.block || !!jobs.send || !active}
              onPress={() => void model.toggleBlock()}
            >
              {jobs.block
                ? "Updating block status…"
                : thread.blocked
                  ? "Unblock conversation"
                  : "Block conversation"}
            </Button>
          )}
          {errors.block && (
            <Text
              accessibilityRole="alert"
              style={[s.text, { color: c.warning }]}
            >
              {errors.block}
            </Text>
          )}
        </>
      )}
      {showComposer && (
        <>
          <View style={{ gap: 8 }}>
            <Text style={[s.label, { color: c.ink }]}>YOUR MESSAGE</Text>
            <TextInput
              accessibilityLabel="YOUR MESSAGE"
              multiline
              editable={!jobs.send}
              value={body}
              onChangeText={model.edit}
              autoCapitalize="sentences"
              style={[s.input, { minHeight: 100, textAlignVertical: "top" }]}
            />
          </View>
          {body.length > 4000 && (
            <Status>Use no more than 4,000 characters.</Status>
          )}
          {errors.send && (
            <Text
              accessibilityRole="alert"
              style={[s.text, { color: c.warning }]}
            >
              {errors.send}
            </Text>
          )}
          <Button disabled={!canSend} onPress={() => void model.send()}>
            {jobs.send
              ? "Sending message…"
              : errors.send
                ? "Retry send"
                : "Send message"}
          </Button>
        </>
      )}
      {!selected && (
        <>
          <Text style={s.text}>
            Messages about homes advertised directly on Realtoruch appear here.
            For imported adverts, contact the advertiser through the original
            source.
          </Text>
          {jobs.inbox && !inbox && <Status>Loading conversations…</Status>}
          <Retry
            error={errors.inbox}
            label="Retry loading conversations"
            action={() => void model.refreshInbox()}
          />
          {inbox && !inbox.items.length && !errors.inbox && (
            <Status>No conversations yet.</Status>
          )}
          {inbox && !errors.inbox && (
            <Button
              outline
              disabled={!!jobs.inbox || !active}
              onPress={() => void model.refreshInbox()}
            >
              Refresh conversations
            </Button>
          )}
          {inbox?.items.map((item) => (
            <View key={item.id} style={[s.card, { padding: 16, gap: 12 }]}>
              <Text style={s.text}>
                {item.title}
                {item.unread_count ? ` · ${item.unread_count} unread` : ""}
              </Text>
              <Button
                outline
                label={`Open conversation: ${item.title}`}
                onPress={() =>
                  model.select({
                    kind: "thread",
                    id: item.id,
                    title: item.title,
                  })
                }
              >
                Open conversation
              </Button>
              {!!item.listing_id && (
                <Button
                  outline
                  onPress={() => {
                    model.stop();
                    onOpenHome(item.listing_id!);
                  }}
                >
                  View home
                </Button>
              )}
            </View>
          ))}
          {inbox?.next_cursor &&
            (errors.more ? (
              <Retry
                error={errors.more}
                label="Retry loading more conversations"
                action={() => void model.loadMore()}
              />
            ) : (
              <Button
                outline
                disabled={!!jobs.more || !active}
                onPress={() => void model.loadMore()}
              >
                {jobs.more
                  ? "Loading more conversations…"
                  : "Load more conversations"}
              </Button>
            ))}
        </>
      )}
    </View>
  );
}
