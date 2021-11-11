import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const platform = vi.hoisted(() => ({ OS: "ios" }));
vi.mock("react-native", () => ({ Platform: platform }));
vi.mock("expo-secure-store", () => ({
  getItemAsync: vi.fn(),
  setItemAsync: vi.fn(),
  deleteItemAsync: vi.fn(),
}));

import { DEFAULT_FILTERS } from "../src/types";

function barrier<T>() {
  let release!: (value: T) => void;
  const promise = new Promise<T>((resolve) => {
    release = resolve;
  });
  return { promise, release };
}

function response(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status });
}

beforeEach(() => {
  platform.OS = "ios";
  vi.resetModules();
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it("retains inbox cancellation and deadline through the shared transport", async () => {
  vi.useFakeTimers();
  vi.stubGlobal("fetch", vi.fn((_url: string, options: RequestInit) =>
    new Promise((_, reject) => {
      options.signal?.addEventListener("abort", () => reject(new Error("aborted")), { once: true });
    }),
  ));
  const { market } = await import("../src/marketplaceApi");
  const caller = new AbortController();
  const cancelled = expect(market.thread("A", undefined, caller.signal))
    .rejects.toMatchObject({ name: "AbortError" });
  caller.abort();
  await cancelled;
  const timedOut = expect(market.conversations(undefined, new AbortController().signal))
    .rejects.toMatchObject({ name: "SessionError", kind: "transient" });
  await vi.advanceTimersByTimeAsync(12_000);
  await timedOut;
  expect(vi.getTimerCount()).toBe(0);
});

describe("latest normalized listing and city requests", () => {
  it("keeps Warszawa results and status when the aborted Kraków requests resolve later", async () => {
    const { createLatestRequest, normalizeCity } = await import(
      "../src/hooks/useListingSearch"
    );
    expect(normalizeCity("  Krakow ")).toBe("Kraków");
    expect(normalizeCity(" warszawa ")).toBe("Warszawa");
    expect(normalizeCity("Krak-ow")).toBe("Krak-ow");

    const search = createLatestRequest();
    const sources = createLatestRequest();
    const krakowListings = barrier<string>();
    const krakowSources = barrier<string>();
    const warsawListings = barrier<string>();
    const warsawSources = barrier<string>();
    const showHomes = vi.fn();
    const showStatus = vi.fn();
    const showError = vi.fn();
    let searchSignal: AbortSignal | undefined;
    let sourcesSignal: AbortSignal | undefined;
    search.run(
      0,
      (signal) => {
        searchSignal = signal;
        return krakowListings.promise;
      },
      showHomes,
      showError,
    );
    sources.run(
      0,
      (signal) => {
        sourcesSignal = signal;
        return krakowSources.promise;
      },
      showStatus,
      showError,
    );

    search.run(0, () => warsawListings.promise, showHomes, showError);
    expect(searchSignal?.aborted).toBe(true);
    expect(sourcesSignal?.aborted).toBe(false);
    sources.run(0, () => warsawSources.promise, showStatus, showError);
    expect(sourcesSignal?.aborted).toBe(true);

    warsawListings.release("Warszawa listings");
    warsawSources.release("Warszawa status");
    await Promise.all([warsawListings.promise, warsawSources.promise]);
    krakowListings.release("Kraków listings");
    krakowSources.release("Kraków status");
    await Promise.all([krakowListings.promise, krakowSources.promise]);
    expect(showHomes.mock.calls).toEqual([["Warszawa listings"]]);
    expect(showStatus.mock.calls).toEqual([["Warszawa status"]]);
    expect(showError).not.toHaveBeenCalled();
  });

  it("debounces twenty keystrokes and sends one request for fifty canonical IDs", async () => {
    vi.useFakeTimers();
    const { createLatestRequest, loadSeenIds, SEARCH_DEBOUNCE_MS } =
      await import("../src/hooks/useListingSearch");
    const { api } = await import("../src/api");
    const ids = Array.from({ length: 50 }, (_, index) => `canonical-${index}`);
    const fetchSearch = vi.fn(async (_query: string) => ids);
    const seen = vi
      .spyOn(api, "listingState")
      .mockResolvedValue({ seen_ids: [ids[0]] });
    const search = createLatestRequest();
    const show = vi.fn(async (results: string[]) => loadSeenIds(results));
    for (let index = 1; index <= 20; index++) {
      search.run(
        SEARCH_DEBOUNCE_MS,
        () => fetchSearch("a".repeat(index)),
        show,
        vi.fn(),
      );
      if (index < 20) await vi.advanceTimersByTimeAsync(10);
    }
    await vi.advanceTimersByTimeAsync(249);
    expect(fetchSearch).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    expect(fetchSearch.mock.calls).toEqual([["a".repeat(20)]]);
    expect(seen.mock.calls).toEqual([[ids, undefined]]);
    expect(show).toHaveBeenCalledTimes(1);
  });

  it("starts an explicit submit immediately and discards the pending debounce", async () => {
    vi.useFakeTimers();
    const { createLatestRequest, SEARCH_DEBOUNCE_MS } = await import(
      "../src/hooks/useListingSearch"
    );
    const request = createLatestRequest();
    const drafts = vi.fn(async () => 4_000);
    const applied = vi.fn(async () => 5_000);
    const display = vi.fn();
    request.run(SEARCH_DEBOUNCE_MS, drafts, display, vi.fn());
    request.run(0, applied, display, vi.fn());
    expect(applied).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(SEARCH_DEBOUNCE_MS);
    expect(drafts).not.toHaveBeenCalled();
    expect(display.mock.calls).toEqual([[5_000]]);
  });

  it("deduplicates the visible IDs into bounded batches of 100", async () => {
    const { loadSeenIds } = await import("../src/hooks/useListingSearch");
    const { api } = await import("../src/api");
    const spy = vi
      .spyOn(api, "listingState")
      .mockImplementation(async (ids) => ({ seen_ids: ids }));
    const ids = Array.from({ length: 201 }, (_, index) => `canonical-${index}`);
    const controller = new AbortController();
    expect(await loadSeenIds([...ids, ids[0]], controller.signal)).toEqual(ids);
    expect(spy.mock.calls.map(([batch]) => batch.length)).toEqual([
      100, 100, 1,
    ]);
    expect(
      spy.mock.calls.every(([, signal]) => signal === controller.signal),
    ).toBe(true);
  });

  it("does not run queued work or publish a completed request after cleanup", async () => {
    vi.useFakeTimers();
    const { createLatestRequest } = await import(
      "../src/hooks/useListingSearch"
    );
    const request = createLatestRequest();
    const success = vi.fn();
    const failure = vi.fn();
    const fetchQueued = vi.fn();
    const cancel = request.run(250, fetchQueued, success, failure);
    cancel();
    const late = barrier<string>();
    let signal: AbortSignal | undefined;
    request.run(
      0,
      (current) => {
        signal = current;
        return late.promise;
      },
      success,
      failure,
    )();
    expect(signal?.aborted).toBe(true);
    late.release("after unmount");
    await vi.advanceTimersByTimeAsync(250);
    expect(fetchQueued).not.toHaveBeenCalled();
    expect(success).not.toHaveBeenCalled();
    expect(failure).not.toHaveBeenCalled();
  });

  it("keeps a public search in flight across sign-out and fences old private batches", async () => {
    const { api, setToken } = await import("../src/api");
    const listings = barrier<Response>();
    const state = barrier<Response>();
    const headers = new Map<string, Headers>();
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, options: RequestInit) => {
        const path = new URL(url).pathname;
        headers.set(path, new Headers(options.headers));
        if (path === "/v1/listings") return listings.promise;
        if (path === "/v1/me/listing-state") return state.promise;
        return Promise.resolve(response({}));
      }),
    );
    await setToken("account-a");
    const search = api.search(DEFAULT_FILTERS);
    const oldState = api.listingState(["private"]);
    const rejected = expect(oldState).rejects.toMatchObject({
      kind: "superseded",
    });
    await api.signOut();
    state.release(response({ seen_ids: ["private"] }));
    listings.release(response({ items: [], total: 0 }));
    await rejected;
    expect(await search).toEqual({ items: [], total: 0 });
    expect(headers.get("/v1/listings")?.has("Authorization")).toBe(false);
    expect(headers.get("/v1/me/listing-state")?.get("Authorization")).toBe(
      "Bearer account-a",
    );
  });

  it("labels retained result age from the successful response time", async () => {
    const { resultAge } = await import("../src/hooks/useListingSearch");
    expect(resultAge(0, 59_000)).toBe("less than a minute ago");
    expect(resultAge(0, 60_000)).toBe("1 minute ago");
    expect(resultAge(0, 120_000)).toBe("2 minutes ago");
  });
});

describe("transport deadlines and shared refresh cancellation", () => {
  it.each(["deadline", "caller", "simultaneous", "success"])(
    "cleans up both sources after %s",
    async (outcome) => {
      vi.useFakeTimers();
      const { request } = await import("../src/api");
      const caller = new AbortController();
      const add = vi.spyOn(caller.signal, "addEventListener");
      const remove = vi.spyOn(caller.signal, "removeEventListener");
      const late = barrier<Response>();
      let signal: AbortSignal | null | undefined;
      vi.stubGlobal(
        "fetch",
        vi.fn((_url: string, options: RequestInit) => {
          signal = options.signal;
          return new Promise<Response>((resolve, reject) => {
            signal?.addEventListener("abort", () => reject(Error("aborted")), {
              once: true,
            });
            void late.promise.then(resolve);
          });
        }),
      );
      const pending = request("/probe", { signal: caller.signal });
      const callerAborted = outcome === "caller" || outcome === "simultaneous";
      const settled =
        outcome === "success"
          ? expect(pending).resolves.toEqual({ ok: true })
          : expect(pending).rejects.toMatchObject(
              callerAborted ? { name: "AbortError" } : { kind: "transient" },
            );
      expect(signal).not.toBe(caller.signal);
      await vi.advanceTimersByTimeAsync(11_999);
      expect(signal?.aborted).toBe(false);
      if (outcome === "caller") caller.abort();
      else if (outcome === "deadline") await vi.advanceTimersByTimeAsync(1);
      else if (outcome === "simultaneous") {
        vi.advanceTimersByTime(1);
        caller.abort();
      } else late.release(response({ ok: true }));
      await settled;
      expect(signal?.aborted).toBe(outcome !== "success");
      expect(caller.signal.aborted).toBe(callerAborted);
      expect(remove).toHaveBeenCalledWith("abort", add.mock.calls[0][1]);
      expect(vi.getTimerCount()).toBe(0);
    },
  );

  it("does not fetch when the caller has already cancelled", async () => {
    const { request } = await import("../src/api");
    const caller = new AbortController();
    caller.abort();
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    await expect(
      request("/probe", { signal: caller.signal }),
    ).rejects.toMatchObject({ name: "AbortError" });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("cancels only the waiting caller and retries the sibling with the rotated account token", async () => {
    const { api, request } = await import("../src/api");
    const refresh = barrier<Response>();
    const reachedRefresh = barrier<void>();
    const reachedSibling = barrier<void>();
    const seen: string[] = [];
    const result = (access_token: string) =>
      response({
        access_token,
        refresh_token: `refresh-${access_token}`,
        user: {
          id: "account-a",
          email: "test@example.test",
          email_verified: true,
        },
      });
    let refreshSignal: AbortSignal | null | undefined;
    let abandonedSignal: AbortSignal | null | undefined;
    const add = vi.spyOn(AbortSignal.prototype, "addEventListener");
    const remove = vi.spyOn(AbortSignal.prototype, "removeEventListener");
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, options: RequestInit) => {
        const path = new URL(url).pathname;
        if (path.endsWith("/login")) return Promise.resolve(result("initial"));
        if (path.endsWith("/refresh")) {
          refreshSignal = options.signal;
          reachedRefresh.release();
          return refresh.promise;
        }
        const token = new Headers(options.headers).get("Authorization");
        seen.push(`${path} ${token}`);
        if (path === "/sibling") reachedSibling.release();
        if (path === "/abandoned") abandonedSignal = options.signal;
        return Promise.resolve(
          response({}, token === "Bearer rotated" ? 200 : 401),
        );
      }),
    );
    await api.signIn("test@example.test", "synthetic-password", false);
    const caller = new AbortController();
    const abandoned = request("/abandoned", { signal: caller.signal });
    const cancelled = expect(abandoned).rejects.toMatchObject({
      name: "AbortError",
    });
    await reachedRefresh.promise;
    const sibling = request("/sibling");
    await reachedSibling.promise;
    caller.abort();
    await cancelled;
    expect(refreshSignal?.aborted).toBe(false);
    for (const signal of [caller.signal, abandonedSignal]) {
      const listener = add.mock.calls[add.mock.contexts.indexOf(signal)][1];
      expect(remove).toHaveBeenCalledWith("abort", listener);
    }
    refresh.release(result("rotated"));
    expect(await sibling).toEqual({});
    expect(seen).toEqual([
      "/abandoned Bearer initial",
      "/sibling Bearer initial",
      "/sibling Bearer rotated",
    ]);
    expect(
      vi
        .mocked(fetch)
        .mock.calls.filter(([url]) => String(url).endsWith("/refresh")),
    ).toHaveLength(1);
  });

  it.each(["success", "timeout"])(
    "times out a lock wait and keeps the sibling's shared refresh and original deadline (%s)",
    async (outcome) => {
      platform.OS = "web";
      vi.useFakeTimers();
      const { api, request } = await import("../src/api");
      const waiting = barrier<void>();
      const releaseLock = barrier<void>();
      const retryResponse = barrier<Response>();
      const result = (access_token: string) =>
        response({
          access_token,
          user: { id: "a", email: "test@example.test", email_verified: true },
        });
      let lockRequests = 0;
      vi.stubGlobal("navigator", {
        locks: {
          request: async (_name: string, run: () => Promise<unknown>) => {
            if (++lockRequests === 2) {
              waiting.release();
              await releaseLock.promise;
            }
            return run();
          },
        },
      });
      const fetch = vi.fn((url: string, options: RequestInit) => {
        const path = new URL(url).pathname;
        if (path.endsWith("/login")) return Promise.resolve(result("initial"));
        if (path.endsWith("/refresh"))
          return Promise.resolve(result("rotated"));
        if (
          new Headers(options.headers).get("Authorization") === "Bearer initial"
        )
          return Promise.resolve(response({}, 401));
        return new Promise<Response>((resolve, reject) => {
          options.signal?.addEventListener(
            "abort",
            () => reject(Error("timed out")),
            { once: true },
          );
          void retryResponse.promise.then(resolve);
        });
      });
      vi.stubGlobal("fetch", fetch);
      await api.signIn("test@example.test", "synthetic-password", false);
      const first = expect(request("/first")).rejects.toMatchObject({
        kind: "transient",
      });
      await waiting.promise;
      await vi.advanceTimersByTimeAsync(11_000);
      const sibling =
        outcome === "success"
          ? expect(request("/sibling")).resolves.toEqual({ ok: true })
          : expect(request("/sibling")).rejects.toMatchObject({
              kind: "transient",
            });
      await vi.advanceTimersByTimeAsync(1_000);
      await first;
      expect(
        fetch.mock.calls.filter(([url]) => url.endsWith("/refresh")),
      ).toHaveLength(0);
      await vi.advanceTimersByTimeAsync(10_999);
      releaseLock.release();
      await vi.advanceTimersByTimeAsync(0);
      expect(
        fetch.mock.calls.filter(([url]) => url.endsWith("/refresh")),
      ).toHaveLength(1);
      expect(
        fetch.mock.calls.filter(([url]) => url.endsWith("/first")),
      ).toHaveLength(1);
      expect(
        fetch.mock.calls.filter(([url]) => url.endsWith("/sibling")),
      ).toHaveLength(2);
      if (outcome === "success") retryResponse.release(response({ ok: true }));
      else await vi.advanceTimersByTimeAsync(1);
      await sibling;
      expect(vi.getTimerCount()).toBe(0);
    },
  );

  it("holds the logout lock through a started rotation and skips retry after the original deadline", async () => {
    platform.OS = "web";
    vi.useFakeTimers();
    const { api, getSessionState } = await import("../src/api");
    const logoutResponse = barrier<Response>();
    const refreshResponse = barrier<Response>();
    const enteredLogout = barrier<void>();
    const enteredRefresh = barrier<void>();
    const result = (access_token: string) =>
      response({
        access_token,
        user: { id: "a", email: "test@example.test", email_verified: true },
      });
    let lockHeld = false;
    vi.stubGlobal("navigator", {
      locks: {
        request: async (_name: string, run: () => Promise<unknown>) => {
          expect(lockHeld).toBe(false);
          lockHeld = true;
          try {
            return await run();
          } finally {
            lockHeld = false;
          }
        },
      },
    });
    const fetch = vi.fn((url: string) => {
      if (url.endsWith("/login")) return Promise.resolve(result("initial"));
      if (url.endsWith("/refresh")) {
        expect(lockHeld).toBe(true);
        enteredRefresh.release();
        return refreshResponse.promise;
      }
      enteredLogout.release();
      return logoutResponse.promise;
    });
    vi.stubGlobal("fetch", fetch);
    await api.signIn("test@example.test", "synthetic-password", false);
    const logout = expect(api.signOut()).rejects.toMatchObject({
      kind: "transient",
    });
    await enteredLogout.promise;
    await vi.advanceTimersByTimeAsync(11_000);
    logoutResponse.release(response({}, 401));
    await enteredRefresh.promise;
    await vi.advanceTimersByTimeAsync(1_001);
    expect(lockHeld).toBe(true);
    expect(
      fetch.mock.calls.filter(([url]) => url.endsWith("/logout")),
    ).toHaveLength(1);
    refreshResponse.release(result("rotated"));
    await logout;
    expect(lockHeld).toBe(false);
    expect(
      fetch.mock.calls.filter(([url]) => url.endsWith("/logout")),
    ).toHaveLength(1);
    expect(getSessionState()).toBe("logout-retry");
    expect(vi.getTimerCount()).toBe(0);
  });
});
