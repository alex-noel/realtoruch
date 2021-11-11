import { afterEach, describe, expect, it, vi } from "vitest";
import {
  InboxModel,
  highestVisibleIncoming,
  type InboxApi,
} from "../src/components/messagesState";
import {
  market,
  type Conversation,
  type Message,
  type Thread,
} from "../src/marketplaceApi";
import { request } from "../src/api";

vi.mock("../src/api", () => ({ request: vi.fn() }));

const deferred = <T,>() => {
  let resolve!: (result: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((ok, fail) => {
    resolve = ok;
    reject = fail;
  });
  return { promise, resolve, reject };
};
const date = "2026-11-11T20:00:00";
const message = (id: string, fraction: string, mine = false): Message => ({
  id,
  body: `Synthetic message ${id}`,
  created_at: date + fraction + "Z",
  mine,
});
const numbered = (id: number) =>
  message(`M${id}`, `.${String(id).padStart(6, "0")}`);
const page = (
  id: string,
  items: Message[],
  next_cursor: string | null = null,
  blocked = false,
  can_unblock = false,
): Thread => ({ id, items, next_cursor, blocked, can_unblock });
const conversation = (
  id: string,
  stamp: string,
  unread_count = 0,
): Conversation => ({
  id,
  updated_at: date + stamp + "Z",
  title: `Synthetic home ${id}`,
  unread_count,
  listing_id: null,
  blocked: false,
  can_unblock: false,
});
const fixture = () => ({
  conversations: vi
    .fn<InboxApi["conversations"]>()
    .mockResolvedValue({ items: [], next_cursor: null }),
  thread: vi.fn<InboxApi["thread"]>().mockResolvedValue(page("A", [])),
  read: vi.fn<InboxApi["read"]>().mockResolvedValue({ read: true }),
  reply: vi.fn<InboxApi["reply"]>(),
  start: vi.fn<InboxApi["start"]>(),
  block: vi.fn<InboxApi["block"]>(),
});
const target = (id: string) => ({
  kind: "thread" as const,
  id,
  title: `Synthetic home ${id}`,
});
const models: InboxModel[] = [];
function mount(api: InboxApi, selected?: Parameters<InboxModel["select"]>[0]) {
  const model = new InboxModel(api, selected);
  models.push(model);
  model.attach();
  model.setForeground(true);
  return model;
}
async function settle() {
  for (let i = 0; i < 6; i++) await Promise.resolve();
}
function display(
  model: InboxModel,
  cards: { message: Message; rect: { y: number; height: number } }[],
  y = 0,
) {
  const visible = highestVisibleIncoming(cards, { y, height: 200 });
  const { thread } = model.snapshot();
  if (visible && thread) model.acknowledgeDisplayed(thread, visible);
}

afterEach(() => {
  models.splice(0).forEach((model) => model.stop());
  vi.useRealTimers();
  vi.mocked(request).mockReset();
});

describe("messages inbox behavior", () => {
  it("acknowledges only displayed incoming messages, including sub-millisecond arrivals and tied IDs", async () => {
    const m1 = message("z", "");
    const m2 = message("b", ".000001");
    const m3 = message("c", ".000001");
    const outgoing = message("outgoing", ".000999", true);
    const api = fixture();
    let server = [m1];
    let unread = new Set([m1.id]);
    const firstRead = deferred<{ read: true }>();
    api.thread.mockImplementation(async () => page("A", server));
    api.read.mockImplementation(async (_id, boundary) => {
      if (boundary === m1.id) await firstRead.promise;
      server
        .slice(0, server.findIndex((item) => item.id === boundary) + 1)
        .forEach((item) => unread.delete(item.id));
      return { read: true };
    });
    const model = mount(api, target("A"));
    await settle();

    display(model, [{ message: m1, rect: { y: 0, height: 100 } }]);
    server = [m1, m2, m3, outgoing];
    unread = new Set([m1.id, m2.id, m3.id]);
    firstRead.resolve({ read: true });
    await model.refreshThread();
    expect([...unread]).toEqual([m2.id, m3.id]);
    const cards = server.map((message, i) => ({
      message,
      rect: { y: i * 170, height: 100 },
    }));
    display(model, cards); // M2 is only 30px visible; M3 is below the viewport.
    expect(api.read.mock.calls.map(([, id]) => id)).toEqual([m1.id]);
    display(model, cards, 340); // M3 and the outgoing message are now on screen.
    await settle();
    expect(api.read.mock.calls.map(([, id]) => id)).toEqual([m1.id, m3.id]);
    expect([...unread]).toEqual([]);
    expect(
      highestVisibleIncoming(
        [
          { message: m1, rect: { y: 0, height: 70 } },
          { message: m2, rect: { y: 80, height: 70 } },
        ],
        { y: 0, height: 200 },
      )?.id,
    ).toBe(m2.id); // Date would lose the microseconds and prefer m1's larger ID.
    expect(
      highestVisibleIncoming(
        [
          { message: m3, rect: { y: 0, height: 70 } },
          { message: m2, rect: { y: 80, height: 70 } },
        ],
        { y: 0, height: 200 },
      )?.id,
    ).toBe(m3.id);
  });

  it("ignores A, including an earlier selection of the same ID, after selecting B and returning to A", async () => {
    const api = fixture();
    const firstA = deferred<Thread>();
    const secondA = deferred<Thread>();
    const b = numbered(2);
    api.thread
      .mockReturnValueOnce(firstA.promise)
      .mockResolvedValueOnce(page("B", [b]))
      .mockReturnValueOnce(secondA.promise);
    const model = mount(api, target("A"));
    const aSignal = api.thread.mock.calls[0][2];
    model.select(target("B"));
    await settle();
    expect(aSignal?.aborted).toBe(true);
    const bTranscript = model.snapshot().thread!;
    display(model, [{ message: b, rect: { y: 0, height: 100 } }]);
    await settle();
    expect(api.read.mock.calls.map(([id, boundary]) => [id, boundary])).toEqual(
      [["B", b.id]],
    );

    model.select(target("A"));
    firstA.resolve(page("A", [numbered(1)]));
    await settle();
    expect(model.snapshot().thread).toBeNull();
    model.acknowledgeDisplayed(bTranscript, b);
    expect(api.read).toHaveBeenCalledTimes(1);
    secondA.resolve(page("A", [numbered(3)]));
    await settle();
    expect(
      model.snapshot().thread?.ranges[0].items.map(({ id }) => id),
    ).toEqual(["M3"]);
  });

  it("ignores a slow response for a closed panel and aborts an acknowledgement already in flight", async () => {
    const api = fixture();
    const late = deferred<Thread>();
    const read = deferred<{ read: true }>();
    const item = numbered(1);
    api.thread
      .mockResolvedValueOnce(page("A", [item]))
      .mockReturnValueOnce(late.promise);
    api.read.mockReturnValueOnce(read.promise);
    const model = mount(api, target("A"));
    await settle();
    display(model, [{ message: item, rect: { y: 0, height: 100 } }]);
    void model.refreshThread();
    const old = model.snapshot().thread!;
    const inboxRequests = api.conversations.mock.calls.length;
    model.stop();
    expect(api.thread.mock.calls.at(-1)?.[2]?.aborted).toBe(true);
    expect(api.read.mock.calls[0][2]?.aborted).toBe(true);
    late.resolve(page("A", [numbered(2)]));
    read.resolve({ read: true });
    await settle();
    expect(model.snapshot().thread).toBe(old);
    expect(api.read).toHaveBeenCalledTimes(1);
    expect(api.conversations).toHaveBeenCalledTimes(inboxRequests);
  });

  it("retains two older pages, deduplicates polls, and fills a gap before acknowledging across it", async () => {
    const api = fixture();
    const get = (first: number, last: number, cursor: string | null) =>
      page(
        "A",
        Array.from({ length: last - first + 1 }, (_, i) => numbered(first + i)),
        cursor,
      );
    api.thread
      .mockResolvedValueOnce(get(5, 7, "M5"))
      .mockResolvedValueOnce(get(3, 4, "M3"))
      .mockResolvedValueOnce(get(1, 2, null))
      .mockResolvedValueOnce(get(7, 9, "M7"))
      .mockResolvedValueOnce(get(14, 16, "M14"))
      .mockResolvedValueOnce(get(11, 13, "M11"))
      .mockResolvedValueOnce(get(8, 10, "M8"));
    const model = mount(api, target("A"));
    await settle();
    await model.loadHistory("M5");
    await model.loadHistory("M3");
    await model.refreshThread();
    const ranges = () =>
      model
        .snapshot()
        .thread!.ranges.map(({ items }) => items.map(({ id }) => id));
    expect(ranges()).toEqual([
      Array.from({ length: 9 }, (_, i) => `M${i + 1}`),
    ]);

    await model.refreshThread();
    expect(ranges()).toEqual([
      Array.from({ length: 9 }, (_, i) => `M${i + 1}`),
      ["M14", "M15", "M16"],
    ]);
    model.acknowledgeDisplayed(model.snapshot().thread!, numbered(16));
    expect(api.read).not.toHaveBeenCalled();
    await model.loadHistory("M14");
    expect(ranges()[1]).toEqual(["M11", "M12", "M13", "M14", "M15", "M16"]);
    await model.loadHistory("M11");
    expect(ranges()).toEqual([
      Array.from({ length: 16 }, (_, i) => `M${i + 1}`),
    ]);
    expect(model.snapshot().thread?.ranges[0].next_cursor).toBeNull();
    model.acknowledgeDisplayed(model.snapshot().thread!, numbered(16));
    expect(api.read).toHaveBeenCalledWith("A", "M16", expect.any(AbortSignal));
  });

  it("retries a lost send with the same client ID and prevents parallel taps", async () => {
    const api = fixture();
    const lost = deferred<Message>();
    const committed = new Map<string, Message>();
    api.reply.mockImplementation(async (_id, body, clientId) => {
      const prior = committed.get(clientId);
      if (prior) return prior;
      committed.set(clientId, { ...numbered(2), body, mine: true });
      return lost.promise;
    });
    const model = mount(api, target("A"));
    await settle();
    model.edit("Synthetic reply");
    const first = model.send();
    await model.send();
    expect(api.reply).toHaveBeenCalledTimes(1);
    expect(model.snapshot().body).toBe("Synthetic reply");
    lost.reject(Error("Response lost after commit"));
    await first;
    expect(model.snapshot().errors.send).toMatch(/draft is saved/);
    expect(model.snapshot().body).toBe("Synthetic reply");
    await model.send();
    expect(api.reply.mock.calls.map(([, , clientId]) => clientId)).toEqual([
      expect.any(String),
      api.reply.mock.calls[0][2],
    ]);
    expect(committed.size).toBe(1);
    expect(model.snapshot().body).toBe("");
    expect(model.snapshot().errors.send).toBeUndefined();

    model.edit("Synthetic reply");
    await model.send();
    expect(api.reply.mock.calls[2][2]).not.toBe(api.reply.mock.calls[0][2]);
  });

  it("retains drafts per recipient and ignores a late send from a previous selection", async () => {
    const api = fixture();
    const late = deferred<Message>();
    api.reply
      .mockReturnValueOnce(late.promise)
      .mockRejectedValue(Error("Offline"));
    api.thread.mockImplementation(async (id) => page(id, []));
    const model = mount(api, target("A"));
    await settle();
    model.edit("Draft A");
    const send = model.send();
    model.select(target("B"));
    await settle();
    model.edit("Draft B");
    late.resolve(numbered(1));
    await send;
    expect(api.reply.mock.calls[0][3]?.aborted).toBe(true);
    expect(model.snapshot().body).toBe("Draft B");
    await model.send();
    model.select(target("A"));
    await settle();
    expect(model.snapshot().body).toBe("Draft A");
    await model.send();
    expect(api.reply.mock.calls[0][2]).toBe(api.reply.mock.calls[2][2]);
    expect(api.reply.mock.calls[1][2]).not.toBe(api.reply.mock.calls[2][2]);
    model.edit("Edited draft A");
    await model.send();
    expect(api.reply.mock.calls[2][2]).not.toBe(api.reply.mock.calls[3][2]);
  });

  it("pauses and resumes one poll timer across five duplicate visibility notifications", async () => {
    vi.useFakeTimers();
    const api = fixture();
    const model = mount(api, target("A"));
    await settle();
    for (let i = 0; i < 5; i++) {
      model.setForeground(false);
      model.setForeground(false);
      const count = api.thread.mock.calls.length;
      const inboxCount = api.conversations.mock.calls.length;
      expect(vi.getTimerCount()).toBe(0);
      await vi.advanceTimersByTimeAsync(45000);
      expect(api.thread).toHaveBeenCalledTimes(count);
      expect(api.conversations).toHaveBeenCalledTimes(inboxCount);
      model.setForeground(true);
      model.setForeground(true);
      expect(vi.getTimerCount()).toBe(1);
      await vi.advanceTimersByTimeAsync(15000);
      expect(api.thread).toHaveBeenCalledTimes(count + 2);
      expect(api.conversations).toHaveBeenCalledTimes(inboxCount + 2);
    }
    model.stop();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("recovers from load errors, paginates opaque inbox cursors, and keeps rows during refresh", async () => {
    const api = fixture();
    const initial = deferred<{
      items: Conversation[];
      next_cursor: string | null;
    }>();
    const cursor = "opaque-first";
    const a = conversation("A", ".000003");
    const b = conversation("B", ".000002");
    const c = conversation("C", ".000001");
    api.conversations
      .mockReturnValueOnce(initial.promise)
      .mockResolvedValueOnce({ items: [a, b], next_cursor: cursor })
      .mockRejectedValueOnce(Error("Offline"))
      .mockResolvedValueOnce({ items: [b, c], next_cursor: null })
      .mockResolvedValueOnce({
        items: [{ ...c, updated_at: date + ".000004Z", unread_count: 2 }, a],
        next_cursor: "opaque-new",
      });
    const model = mount(api);
    expect(model.snapshot().jobs.inbox).toBeTruthy();
    initial.reject(Error("Offline"));
    await settle();
    expect(model.snapshot().errors.inbox).toMatch(/Could not load/);
    await model.refreshInbox();
    await model.loadMore();
    expect(model.snapshot().errors.more).toMatch(/Could not load more/);
    expect(model.snapshot().inbox?.next_cursor).toBe(cursor);
    await model.loadMore();
    expect(api.conversations.mock.calls.map(([cursor]) => cursor)).toEqual([
      undefined,
      undefined,
      cursor,
      cursor,
    ]);
    expect(model.snapshot().inbox?.items.map(({ id }) => id)).toEqual([
      "A",
      "B",
      "C",
    ]);
    await model.refreshInbox();
    expect(model.snapshot().inbox?.items.map(({ id }) => id)).toEqual([
      "C",
      "A",
      "B",
    ]);
    expect(model.snapshot().inbox?.items[0].unread_count).toBe(2);
  });

  it("retains the original inbox boundary when a top refresh wins a race with pagination", async () => {
    const api = fixture();
    const older = deferred<{
      items: Conversation[];
      next_cursor: string | null;
    }>();
    const a = conversation("A", ".000003");
    const b = conversation("B", ".000002");
    const c = conversation("C", ".000001");
    const newest = conversation("new", ".000004");
    api.conversations
      .mockResolvedValueOnce({ items: [a, b], next_cursor: "after-B" })
      .mockReturnValueOnce(older.promise)
      .mockResolvedValueOnce({ items: [newest, a], next_cursor: "after-A" });
    const model = mount(api);
    await settle();
    const load = model.loadMore();
    await model.refreshInbox();
    expect(model.snapshot().inbox?.items.map(({ id }) => id)).toEqual([
      "new",
      "A",
      "B",
    ]);
    older.resolve({ items: [c], next_cursor: null });
    await load;
    expect(api.conversations.mock.calls[1][0]).toBe("after-B");
    expect(model.snapshot().inbox?.items.map(({ id }) => id)).toEqual([
      "new",
      "A",
      "B",
      "C",
    ]);
  });

  it("refreshes an older conversation's unread badge from the server after a read", async () => {
    const api = fixture();
    const a = conversation("A", ".000002");
    const b = conversation("B", ".000001", 2);
    const m1 = numbered(1);
    api.thread.mockResolvedValue(page("B", [m1]));
    api.conversations
      .mockResolvedValueOnce({ items: [a], next_cursor: "first-cursor" })
      .mockResolvedValueOnce({ items: [b], next_cursor: null })
      .mockResolvedValueOnce({ items: [a], next_cursor: "first-cursor" })
      .mockResolvedValueOnce({
        items: [{ ...b, unread_count: 1 }],
        next_cursor: null,
      });
    const model = mount(api);
    await settle();
    await model.loadMore();
    model.select(target("B"));
    await settle();
    display(model, [{ message: m1, rect: { y: 0, height: 100 } }]);
    await settle();
    expect(api.conversations.mock.calls.map(([cursor]) => cursor)).toEqual([
      undefined,
      "first-cursor",
      undefined,
      "first-cursor",
    ]);
    expect(model.snapshot().inbox?.items[1].unread_count).toBe(1);
  });

  it("prevents sending when blocked and keeps an existing draft through unblock", async () => {
    const api = fixture();
    api.thread
      .mockResolvedValueOnce(page("A", []))
      .mockResolvedValueOnce(page("A", [], null, true, true))
      .mockResolvedValueOnce(page("A", []));
    api.block.mockResolvedValue({ blocked: false });
    const model = mount(api, target("A"));
    await settle();
    model.edit("Saved during block");
    await model.refreshThread();
    await model.send();
    expect(api.reply).not.toHaveBeenCalled();
    expect(model.snapshot().thread?.blocked).toBe(true);
    await model.toggleBlock();
    expect(api.block).toHaveBeenCalledWith("A", false, expect.any(AbortSignal));
    expect(model.snapshot().thread?.blocked).toBe(false);
    expect(model.snapshot().body).toBe("Saved during block");
  });
});

describe("messages API transport", () => {
  it("uses an explicit displayed cursor and passes opaque cursors without rewriting them", async () => {
    await market.read("thread", "message");
    await market.conversations("opaque=+/");
    await market.thread("thread", "before");
    expect(request).toHaveBeenNthCalledWith(
      1,
      "/v1/me/conversations/thread/read",
      {
        method: "PUT",
        body: '{"last_message_id":"message"}',
      },
    );
    expect(request).toHaveBeenNthCalledWith(
      2,
      "/v1/me/conversations?cursor=opaque%3D%2B%2F",
      undefined,
    );
    expect(request).toHaveBeenNthCalledWith(
      3,
      "/v1/me/conversations/thread?before=before",
      undefined,
    );
  });

  it("aborts cancelled calls and retains a deadline with a caller signal", async () => {
    vi.useFakeTimers();
    vi.mocked(request).mockImplementation(
      (_path, options) =>
        new Promise((_, reject) => {
          options?.signal?.addEventListener(
            "abort",
            () => reject(Error("Aborted")),
            { once: true },
          );
        }),
    );
    const caller = new AbortController();
    const cancelled = expect(
      market.thread("A", undefined, caller.signal),
    ).rejects.toThrow("Aborted");
    caller.abort();
    await cancelled;
    const timeout = expect(
      market.conversations(undefined, new AbortController().signal),
    ).rejects.toThrow("Aborted");
    await vi.advanceTimersByTimeAsync(12000);
    await timeout;
    expect(vi.getTimerCount()).toBe(0);
  });
});
