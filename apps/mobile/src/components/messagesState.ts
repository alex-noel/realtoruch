import type {
  market,
  Conversation,
  ConversationPage,
  Message,
  Thread,
} from "../marketplaceApi";

export type InboxApi = Pick<
  typeof market,
  "conversations" | "thread" | "read" | "start" | "reply" | "block"
>;

type Target = { kind: "thread" | "advert"; id: string; title: string };
type Range = Pick<Thread, "items" | "next_cursor">;
type Transcript = Pick<Thread, "id" | "blocked" | "can_unblock"> & {
  ranges: Range[];
};
type Draft = { body: string; clientId?: string };
type Job = "inbox" | "more" | "thread" | "older" | "read" | "send" | "block";
type Jobs = Partial<Record<Job, AbortController>>;
type Snapshot = {
  active: boolean;
  target: Target | null;
  inbox: ConversationPage | null;
  thread: Transcript | null;
  body: string;
  jobs: Jobs;
  errors: Partial<Record<Job, string>>;
  historyCursor?: string;
};

// API times are canonical UTC strings, with no fraction for whole seconds.
function timestampKey(value: string) {
  const [seconds, fraction] = value.slice(0, -1).split(".");
  return seconds + (fraction ?? "").padEnd(6, "0");
}

function compare(a: string, b: string) {
  return a < b ? -1 : a > b ? 1 : 0;
}

function compareMessage(a: Message, b: Message) {
  return (
    compare(timestampKey(a.created_at), timestampKey(b.created_at)) ||
    compare(a.id, b.id)
  );
}

function mergeMessages(older: Message[], newer: Message[]) {
  const byId = new Map(older.map((item) => [item.id, item]));
  newer.forEach((item) => byId.set(item.id, item));
  return [...byId.values()].sort(compareMessage);
}

// Ranges are ordered oldest first. A page fetched with "before" is known to
// be adjacent to its requesting range. A poll is only joined on actual overlap.
function mergeRange(ranges: Range[], page: Range, before?: string): Range[] {
  if (ranges.length === 0) return page.items.length ? [page] : [];
  let combined = page;
  const remaining = ranges.filter((range) => {
    if (before !== undefined && range.next_cursor === before) {
      combined = {
        items: mergeMessages(range.items, page.items),
        next_cursor: page.next_cursor,
      };
      return false;
    }
    return true;
  });
  for (let i = remaining.length - 1; i >= 0 && combined.items.length; i--) {
    const range = remaining[i];
    const ids = new Set(combined.items.map(({ id }) => id));
    if (!range.items.some(({ id }) => ids.has(id))) continue;
    const first = compareMessage(range.items[0], combined.items[0]);
    combined = {
      items: mergeMessages(range.items, combined.items),
      next_cursor:
        first < 0
          ? range.next_cursor
          : first > 0
            ? combined.next_cursor
            : range.next_cursor && combined.next_cursor,
    };
    remaining.splice(i, 1);
  }
  if (combined.items.length) remaining.push(combined);
  return remaining.sort((a, b) => compareMessage(a.items[0], b.items[0]));
}

function mergeConversations(stale: Conversation[], fresh: Conversation[]) {
  const byId = new Map(stale.map((item) => [item.id, item]));
  fresh.forEach((item) => byId.set(item.id, item));
  return [...byId.values()].sort(
    (a, b) =>
      compare(timestampKey(b.updated_at), timestampKey(a.updated_at)) ||
      compare(b.id, a.id),
  );
}

type Rect = { y: number; height: number };
export function highestVisibleIncoming(
  cards: { message: Message; rect: Rect }[],
  viewport: Rect,
) {
  let highest: Message | undefined;
  for (const { message, rect } of cards) {
    const overlap =
      Math.min(viewport.y + viewport.height, rect.y + rect.height) -
      Math.max(viewport.y, rect.y);
    // A few pixels of the card at the viewport edge is not a display.
    if (
      !message.mine &&
      rect.height > 0 &&
      overlap >= Math.min(48, rect.height) &&
      (!highest || compareMessage(message, highest) > 0)
    )
      highest = message;
  }
  return highest;
}

const threadJobs: Job[] = ["thread", "older", "read", "send", "block"];
const pollJobs: Job[] = ["inbox", "more", "thread", "older", "read"];
const messages = {
  inbox: "Could not load conversations.",
  more: "Could not load more conversations.",
  thread: "Could not load messages.",
  older: "Could not load message history.",
  send: "Could not send your message. Your draft is saved.",
  block: "Could not change the block status.",
};
function makeClientId() {
  return (
    globalThis.crypto?.randomUUID?.() ??
    `${Date.now()}_${Math.random().toString(36).slice(2)}`
  );
}

export class InboxModel {
  private state: Snapshot;
  private listeners = new Set<() => void>();
  private drafts = new Map<string, Draft>();
  private attached = false;
  private timer?: ReturnType<typeof setInterval>;
  private paginatedInbox = false;
  private olderInboxCursors = new Map<string, string>();
  private acknowledged?: Message;
  private displayed?: Message;

  constructor(
    private api: InboxApi,
    target: Target | null = null,
  ) {
    this.state = {
      active: false,
      target,
      inbox: null,
      thread: null,
      body: "",
      jobs: {},
      errors: {},
    };
  }

  snapshot = () => this.state;
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  private update(change: Partial<Snapshot>) {
    this.state = { ...this.state, ...change };
    this.listeners.forEach((listener) => listener());
  }

  attach() {
    this.attached = true;
  }

  stop = () => {
    this.attached = false;
    this.setForeground(false);
    this.cancel(threadJobs);
  };

  setForeground(active: boolean) {
    if (active === this.state.active || (active && !this.attached)) return;
    this.update({ active });
    if (active) {
      this.refresh();
      this.timer = setInterval(() => this.refresh(), 15000);
    } else {
      clearInterval(this.timer);
      this.timer = undefined;
      this.displayed = undefined;
      this.cancel(pollJobs);
    }
  }

  private refresh() {
    void this.refreshInbox();
    void this.refreshThread();
  }

  private cancel(keys: Job[]) {
    const jobs = { ...this.state.jobs };
    let changed = false;
    for (const key of keys) {
      if (!jobs[key]) continue;
      jobs[key]?.abort();
      delete jobs[key];
      changed = true;
    }
    if (changed) this.update({ jobs });
  }

  private begin(key: Job) {
    if (!this.attached || !this.state.active || this.state.jobs[key]) return;
    const job = new AbortController();
    this.update({
      jobs: { ...this.state.jobs, [key]: job },
      errors: { ...this.state.errors, [key]: undefined },
    });
    return job;
  }

  private current(key: Job, job: AbortController) {
    return this.attached && this.state.jobs[key] === job && !job.signal.aborted;
  }

  private finish(key: Job, job: AbortController, error?: string) {
    if (!this.current(key, job)) return;
    const jobs = { ...this.state.jobs };
    delete jobs[key];
    this.update({
      jobs,
      ...(error ? { errors: { ...this.state.errors, [key]: error } } : {}),
    });
  }

  refreshInbox = async (replace = false, refreshId?: string) => {
    if (replace) this.cancel(["inbox"]);
    const job = this.begin("inbox");
    if (!job) return;
    try {
      const page = await this.api.conversations(undefined, job.signal);
      if (!this.current("inbox", job)) return;
      if (!page.next_cursor) {
        this.paginatedInbox = false;
        this.olderInboxCursors.clear();
        this.cancel(["more"]);
      }
      page.items.forEach((item) => this.olderInboxCursors.delete(item.id));
      const prev = this.state.inbox;
      this.update({
        inbox:
          this.paginatedInbox && prev
            ? {
                items: mergeConversations(prev.items, page.items),
                next_cursor: prev.next_cursor,
              }
            : page,
      });
      // A read does not move the conversation to the first page. Refresh its
      // known older page as well, keeping the server's unread count (a new
      // arrival may have raced with the displayed read boundary).
      if (
        refreshId &&
        page.next_cursor &&
        prev?.items.some((item) => item.id === refreshId) &&
        !page.items.some((item) => item.id === refreshId)
      ) {
        const cursor =
          this.olderInboxCursors.get(refreshId) ?? page.next_cursor;
        const older = await this.api.conversations(cursor, job.signal);
        const current = this.state.inbox;
        const refreshed = older.items.find((item) => item.id === refreshId);
        if (this.current("inbox", job) && current && refreshed) {
          this.olderInboxCursors.set(refreshId, cursor);
          this.update({
            inbox: {
              ...current,
              items: mergeConversations(current.items, [refreshed]),
            },
          });
        }
      }
      this.finish("inbox", job);
    } catch {
      this.finish("inbox", job, messages.inbox);
    }
  };

  loadMore = async () => {
    const cursor = this.state.inbox?.next_cursor;
    if (!cursor) return;
    const job = this.begin("more");
    if (!job) return;
    // The next page starts after this window's old boundary. Retain the
    // window now, before a refresh can replace it with a moved first page.
    this.paginatedInbox = true;
    try {
      const page = await this.api.conversations(cursor, job.signal);
      if (!this.current("more", job)) return;
      const previous = this.state.inbox?.items ?? [];
      const loaded = new Set(previous.map((item) => item.id));
      for (const item of page.items) {
        if (!loaded.has(item.id)) this.olderInboxCursors.set(item.id, cursor);
      }
      this.update({
        inbox: {
          items: mergeConversations(page.items, previous),
          next_cursor: page.next_cursor,
        },
      });
      this.finish("more", job);
    } catch {
      this.finish("more", job, messages.more);
    }
  };

  private key(target: Target) {
    return `${target.kind}:${target.id}`;
  }

  select = (target: Target | null) => {
    if (!this.attached) return;
    const previousThread = this.state.thread?.id;
    this.cancel(threadJobs);
    this.acknowledged = undefined;
    this.displayed = undefined;
    this.update({
      target,
      thread: null,
      body: target ? (this.drafts.get(this.key(target))?.body ?? "") : "",
      errors: { inbox: this.state.errors.inbox, more: this.state.errors.more },
      historyCursor: undefined,
    });
    if (target?.kind === "thread") void this.refreshThread();
    else if (!target) void this.refreshInbox(true, previousThread);
  };

  refreshThread = async (replace = false) => {
    const target = this.state.target;
    if (target?.kind !== "thread" || this.state.jobs.block) return;
    if (replace) this.cancel(["thread"]);
    const job = this.begin("thread");
    if (!job) return;
    try {
      const page = await this.api.thread(target.id, undefined, job.signal);
      if (!this.current("thread", job)) return;
      const ranges = mergeRange(this.state.thread?.ranges ?? [], page);
      this.update({
        thread: {
          id: page.id,
          blocked: page.blocked,
          can_unblock: page.can_unblock,
          ranges,
        },
      });
      this.finish("thread", job);
    } catch {
      this.finish("thread", job, messages.thread);
    }
  };

  loadHistory = async (cursor: string) => {
    const { thread } = this.state;
    if (!thread) return;
    const job = this.begin("older");
    if (!job) return;
    this.update({ historyCursor: cursor });
    try {
      const older = await this.api.thread(thread.id, cursor, job.signal);
      const current = this.state.thread;
      if (!this.current("older", job) || !current) return;
      this.update({
        thread: {
          ...current,
          ranges: mergeRange(current.ranges, older, cursor),
        },
        historyCursor: undefined,
      });
      this.finish("older", job);
    } catch {
      this.finish("older", job, messages.older);
    }
  };

  acknowledgeDisplayed = (transcript: Transcript, message: Message) => {
    // This must be called with a measured, committed transcript. Only the
    // oldest continuous range may advance the watermark while a gap is known.
    if (
      !this.state.active ||
      this.state.thread !== transcript ||
      message.mine ||
      !transcript.ranges[0]?.items.some((item) => item.id === message.id)
    )
      return;
    if (!this.displayed || compareMessage(message, this.displayed) > 0)
      this.displayed = message;
    void this.acknowledge();
  };

  private async acknowledge() {
    const { thread } = this.state;
    const message = this.displayed;
    if (
      !thread ||
      !message ||
      (this.acknowledged && compareMessage(message, this.acknowledged) <= 0)
    )
      return;
    const job = this.begin("read");
    if (!job) return;
    try {
      await this.api.read(thread.id, message.id, job.signal);
      if (!this.current("read", job)) return;
      this.acknowledged = message;
      this.finish("read", job);
      void this.refreshInbox(true, thread.id);
      // A newer message may have been displayed while this request was in flight.
      void this.acknowledge();
    } catch {
      // Retry on a later measurement/poll, with the same displayed boundary.
      this.finish("read", job);
    }
  }

  edit = (body: string) => {
    const { target } = this.state;
    if (!target || this.state.jobs.send || this.state.body === body) return;
    this.drafts.set(this.key(target), { body });
    this.update({ body, errors: { ...this.state.errors, send: undefined } });
  };

  send = async () => {
    const { target, thread, body } = this.state;
    if (
      !target ||
      this.state.jobs.block ||
      (target.kind === "thread" && (!thread || thread.blocked)) ||
      !body.trim() ||
      body.length > 4000
    )
      return;
    const job = this.begin("send");
    if (!job) return;
    const key = this.key(target);
    const clientId = this.drafts.get(key)?.clientId ?? makeClientId();
    this.drafts.set(key, { body, clientId });
    try {
      let id = target.id;
      if (target.kind === "thread")
        await this.api.reply(target.id, body, clientId, job.signal);
      else
        id = (await this.api.start(target.id, body, clientId, job.signal)).id;
      if (!this.current("send", job)) return;
      this.drafts.delete(key);
      this.finish("send", job);
      this.update({ body: "" });
      if (target.kind === "advert")
        this.select({ kind: "thread", id, title: target.title });
      else void this.refreshThread(true);
      void this.refreshInbox(true);
    } catch (error) {
      if (!this.current("send", job)) return;
      const status = (error as { status?: number } | null)?.status;
      const reason =
        status === 429
          ? " Too many messages. Wait a minute and try again."
          : "";
      this.finish("send", job, messages.send + reason);
      if (status === 403) void this.refreshThread(true);
    }
  };

  toggleBlock = async () => {
    const { thread } = this.state;
    if (
      !thread ||
      (thread.blocked && !thread.can_unblock) ||
      this.state.jobs.send
    )
      return;
    const job = this.begin("block");
    if (!job) return;
    this.cancel(["thread"]);
    try {
      const result = await this.api.block(
        thread.id,
        !thread.blocked,
        job.signal,
      );
      if (!this.current("block", job)) return;
      if (this.state.thread) {
        this.update({
          thread: {
            ...this.state.thread,
            blocked: result.blocked,
            can_unblock: false,
          },
        });
      }
      this.finish("block", job);
      void this.refreshThread(true);
      void this.refreshInbox(true);
    } catch {
      if (!this.current("block", job)) return;
      this.finish("block", job, messages.block);
      void this.refreshThread(true);
    }
  };
}
