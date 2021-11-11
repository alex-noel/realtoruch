import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  createLinkLifecycle,
  listingFromPush,
  parseIncomingLink,
  sanitizedWebSearch,
  subscribeToLinks,
  type AutomaticTokenLink,
  type LinkDestination,
  type LinkFeedback,
} from "../src/linking";

const secureStore = vi.hoisted(() => ({
  setItemAsync: vi.fn(),
  getItemAsync: vi.fn(),
  deleteItemAsync: vi.fn(),
}));
vi.mock("react-native", () => ({ Platform: { OS: "ios" } }));
vi.mock("expo-secure-store", () => secureStore);

const settings = {
  scheme: "realtoruch-test",
  publicWebUrl: "https://homes.example.test",
};
const fixtureToken = "A".repeat(43);

function barrier<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((finish) => {
    resolve = finish;
  });
  return { resolve, promise };
}

function lifecycleFixture() {
  let time = 0;
  const handlers = {
    navigate: vi.fn(
      async (_destination: LinkDestination, _isCurrent: () => boolean) => {},
    ),
    consume: vi.fn(async (_action: AutomaticTokenLink) => "Link applied."),
    reset: vi.fn(),
    showLogin: vi.fn(),
    feedback: vi.fn<(message: LinkFeedback | null) => void>(),
    error: vi.fn(() => ({
      message: "Link unavailable. Try again.",
      retryable: true,
    })),
    now: () => time,
  };
  const lifecycle = createLinkLifecycle(handlers);
  return {
    handlers,
    lifecycle,
    setTime: (value: number) => {
      time = value;
    },
  };
}

function sourceFixture() {
  const initial = barrier<string | null>();
  let listener: ((event: { url: string }) => void) | undefined;
  const remove = vi.fn();
  const source = {
    getInitialURL: vi.fn(() => initial.promise),
    addEventListener: vi.fn(
      (_event: "url", receive: (event: { url: string }) => void) => {
        listener = receive;
        return { remove };
      },
    ),
  };
  return {
    source,
    initial,
    remove,
    emit: (url: string) => listener?.({ url }),
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.resetModules();
});
afterEach(() => vi.unstubAllGlobals());

describe("incoming URL allowlist", () => {
  it.each([
    [
      "https://homes.example.test/?listing=old-canonical-id",
      { type: "listing", id: "old-canonical-id" },
    ],
    [
      "https://HOMES.EXAMPLE.TEST:443/?advert=owner_12",
      { type: "advert", id: "owner_12" },
    ],
    [
      "realtoruch-test:///?listing=old%2Dcanonical",
      { type: "listing", id: "old-canonical" },
    ],
    [
      "realtoruch-test:///?saved_listing=delisted-home",
      { type: "saved-listing", id: "delisted-home" },
    ],
    [
      "https://homes.example.test/?saved_listing=old-alias",
      { type: "saved-listing", id: "old-alias" },
    ],
    ["https://homes.example.test/?notifications=1", { type: "notifications" }],
    ["realtoruch-test:///?notifications=1", { type: "notifications" }],
    ["https://homes.example.test/", { type: "none" }],
  ])("accepts the documented destination %s", (url, action) => {
    expect(parseIncomingLink(url, settings)).toEqual(action);
  });

  it.each([
    ["verify_account", "verify-account"],
    ["reset_password", "reset-password"],
    ["confirm_email", "confirm-email"],
    ["unsubscribe_email", "unsubscribe-email"],
  ])("accepts %s only as a URL fragment", (parameter, type) => {
    for (const base of ["https://homes.example.test/", "realtoruch-test:///"]) {
      const action = parseIncomingLink(
        `${base}#${parameter}=${fixtureToken}`,
        settings,
      );
      expect(action.type).toBe(type);
      expect("token" in action && action.token === fixtureToken).toBe(true);
      expect(
        parseIncomingLink(`${base}?${parameter}=${fixtureToken}`, settings)
          .type,
      ).toBe("invalid");
    }
  });

  it.each([
    "//homes.example.test/?listing=valid",
    "http://homes.example.test/?listing=valid",
    "https://elsewhere.example.test/?listing=valid",
    "https://homes.example.test.example.test/?listing=valid",
    "https://homes.example.test:444/?listing=valid",
    "https://homes.example.test@elsewhere.example.test/?listing=valid",
    "https://elsewhere@homes.example.test/?listing=valid",
    "https://homes.example.test\\@elsewhere.example.test/?listing=valid",
    "https://%68omes.example.test/?listing=valid",
    "https://homes.example.test//?listing=valid",
    "https://homes.example.test/other?listing=valid",
    "https://homes.example.test/other/../?listing=valid",
    "https://homes.example.test/?listing=first&listing=second",
    "https://homes.example.test/?listing=valid&redirect=https%3A%2F%2Felsewhere.example.test",
    "https://homes.example.test/?listing=../valid",
    "https://homes.example.test/?listing=invalid%2Fid",
    "https://homes.example.test/?listing=invalid%00id",
    "https://homes.example.test/?listing=invalid%ZZ",
    "https://homes.example.test/?listing=%C0%AF",
    "https://homes.example.test/?notifications=https%3A%2F%2Felsewhere.example.test",
    "https://homes.example.test/?account=other",
    "javascript:///?listing=valid",
    "data:text/plain,realtoruch-test:///?listing=valid",
    "exp://127.0.0.1:8081/--/?listing=valid",
    "realtoruch:///?listing=valid",
    "realtoruch-test://external.example.test/?listing=valid",
  ])("rejects unsupported URL %s", (url) => {
    expect(parseIncomingLink(url, settings)).toEqual({ type: "invalid" });
  });

  it("rejects malformed and oversized tokens, identifiers and mixed actions", () => {
    const base = "https://homes.example.test/";
    const invalid = [
      `#confirm_email=${"A".repeat(31)}`,
      `#reset_password=${"A".repeat(129)}`,
      `#reset_password=${"A".repeat(1024)}`,
      `?listing=${"A".repeat(37)}`,
      `#verify_account=${fixtureToken}%ZZ`,
      `#verify_account=${fixtureToken}&reset_password=${fixtureToken}`,
      `?listing=alias#verify_account=${fixtureToken}`,
    ];
    for (const candidate of invalid)
      expect(parseIncomingLink(base + candidate, settings).type).toBe(
        "invalid",
      );
    expect(listingFromPush("alias_2")).toEqual({
      type: "listing",
      id: "alias_2",
    });
    expect(listingFromPush("https://elsewhere.example.test/")).toEqual({
      type: "invalid",
    });
    expect(
      parseIncomingLink("javascript:///?listing=valid", {
        scheme: "javascript",
      }).type,
    ).toBe("invalid");
  });

  it("accepts the actual web origin and restricts HTTP development to web loopback", () => {
    const loopback = "http://127.0.0.1:55000";
    const url = loopback + "/?listing=local";
    expect(
      parseIncomingLink(url, { ...settings, browserOrigin: loopback }),
    ).toEqual({
      type: "listing",
      id: "local",
    });
    expect(
      parseIncomingLink(url, { ...settings, publicWebUrl: loopback }).type,
    ).toBe("invalid");
    expect(
      parseIncomingLink("https://own-web.example.test/?listing=local", {
        ...settings,
        browserOrigin: "https://own-web.example.test",
      }).type,
    ).toBe("listing");
  });

  it("scrubs a fragment even if it cannot be decoded or exceeds the link size", () => {
    const safeSearch = "?listing=alias";
    expect(sanitizedWebSearch(safeSearch, "")).toBeNull();
    expect(sanitizedWebSearch(safeSearch, "#verify_account=%ZZ")).toBe(
      safeSearch,
    );
    expect(sanitizedWebSearch("", "#reset_password=" + "x".repeat(2048))).toBe(
      "",
    );
    expect(sanitizedWebSearch("?verify_account=%ZZ", "")).toBe("");
    expect(sanitizedWebSearch("?%72eset_password=" + fixtureToken, "")).toBe(
      "",
    );
  });
});

describe("incoming link delivery lifecycle", () => {
  it("subscribes once and consumes one token across cold and warm delivery", async () => {
    const { lifecycle, handlers, setTime } = lifecycleFixture();
    const source = sourceFixture();
    const stop = subscribeToLinks(source.source, (url) =>
      lifecycle.receive(parseIncomingLink(url, settings), "guest"),
    );
    const coldUrl = `https://homes.example.test/#verify_account=${fixtureToken}`;
    source.initial.resolve(coldUrl);
    await source.initial.promise;
    source.emit(`realtoruch-test:///#verify_account=${fixtureToken}`);
    setTime(60_000);
    source.emit(coldUrl);
    expect(handlers.consume).toHaveBeenCalledTimes(1);
    expect(source.source.getInitialURL).toHaveBeenCalledTimes(1);
    expect(source.source.addEventListener).toHaveBeenCalledTimes(1);
    stop();
    lifecycle.close();
    source.emit("realtoruch-test:///?listing=after-teardown");
    expect(source.remove).toHaveBeenCalledTimes(1);
    expect(handlers.navigate).not.toHaveBeenCalled();
  });

  it("does not navigate twice when warm delivery wins the initial URL race", async () => {
    const { lifecycle, handlers } = lifecycleFixture();
    const source = sourceFixture();
    subscribeToLinks(source.source, (url) =>
      lifecycle.receive(parseIncomingLink(url, settings), "guest"),
    );
    const url = "realtoruch-test:///?listing=old-alias";
    source.emit(url);
    source.initial.resolve(url);
    await source.initial.promise;
    expect(handlers.navigate).toHaveBeenCalledTimes(1);
  });

  it("delivers a distinct initial URL even when a warm event arrives first", async () => {
    const { lifecycle, handlers } = lifecycleFixture();
    const source = sourceFixture();
    const stop = subscribeToLinks(source.source, (url) =>
      lifecycle.receive(parseIncomingLink(url, settings), "guest"),
    );
    source.emit("realtoruch-test:///?listing=warm");
    source.initial.resolve("realtoruch-test:///?listing=cold");
    await source.initial.promise;
    expect(
      handlers.navigate.mock.calls.map(([destination]) => destination),
    ).toEqual([
      { type: "listing", id: "warm" },
      { type: "listing", id: "cold" },
    ]);
    stop();
    lifecycle.close();
  });

  it("drops a pending initial link and late request completion at teardown", async () => {
    const { lifecycle, handlers } = lifecycleFixture();
    const source = sourceFixture();
    const late = barrier<string>();
    handlers.consume.mockReturnValue(late.promise);
    const stop = subscribeToLinks(source.source, (url) =>
      lifecycle.receive(parseIncomingLink(url, settings), "guest"),
    );
    source.emit(`realtoruch-test:///#confirm_email=${fixtureToken}`);
    stop();
    lifecycle.close();
    source.initial.resolve("realtoruch-test:///?listing=after-teardown");
    late.resolve("late success");
    await Promise.all([source.initial.promise, late.promise]);
    expect(source.remove).toHaveBeenCalledTimes(1);
    expect(handlers.navigate).not.toHaveBeenCalled();
    expect(handlers.feedback).not.toHaveBeenCalledWith({
      message: "late success",
    });
  });

  it("retains only the protected destination across restore and sign-in", () => {
    const { lifecycle, handlers } = lifecycleFixture();
    const destination = { type: "saved-listing", id: "old-alias" } as const;
    lifecycle.receive(destination, "restoring");
    expect(handlers.showLogin).not.toHaveBeenCalled();
    expect(handlers.navigate).not.toHaveBeenCalled();
    lifecycle.resolveSession(false);
    expect(handlers.showLogin).toHaveBeenCalledTimes(1);
    lifecycle.resolveSession(true);
    lifecycle.resolveSession(true);
    expect(handlers.navigate).toHaveBeenCalledExactlyOnceWith(
      destination,
      expect.any(Function),
    );
    expect(handlers.consume).not.toHaveBeenCalled();
    expect(handlers.reset).not.toHaveBeenCalledWith(expect.any(String));
  });

  it("drops a protected destination when sign-in is dismissed", () => {
    const { lifecycle, handlers } = lifecycleFixture();
    lifecycle.receive({ type: "notifications" }, "guest");
    expect(handlers.showLogin).toHaveBeenCalledTimes(1);
    lifecycle.clearPending();
    lifecycle.resolveSession(true);
    expect(handlers.navigate).not.toHaveBeenCalled();
  });

  it("coalesces a duplicate cold/warm listing while allowing later intentional reopening", () => {
    const { lifecycle, handlers, setTime } = lifecycleFixture();
    lifecycle.receive(
      parseIncomingLink(
        "https://homes.example.test/?listing=old-alias",
        settings,
      ),
      "authenticated",
    );
    lifecycle.receive(
      parseIncomingLink("realtoruch-test:///?listing=old-alias", settings),
      "authenticated",
    );
    expect(handlers.navigate).toHaveBeenCalledTimes(1);
    setTime(2_000);
    lifecycle.receive(listingFromPush("old-alias"), "authenticated");
    expect(handlers.navigate).toHaveBeenCalledTimes(2);
    expect(
      handlers.navigate.mock.calls.map(([destination]) => destination),
    ).toEqual([
      { type: "listing", id: "old-alias" },
      { type: "listing", id: "old-alias" },
    ]);
  });

  it("offers explicit retry once, never replays a successful token", async () => {
    const { lifecycle, handlers } = lifecycleFixture();
    handlers.consume.mockRejectedValueOnce(new Error("transient"));
    const action = { type: "confirm-email", token: fixtureToken } as const;
    lifecycle.receive(action, "authenticated");
    await vi.waitFor(() =>
      expect(typeof handlers.feedback.mock.lastCall?.[0]?.retry).toBe(
        "function",
      ),
    );
    const retry = handlers.feedback.mock.lastCall?.[0]?.retry;
    expect(typeof retry).toBe("function");
    retry?.();
    retry?.();
    await vi.waitFor(() =>
      expect(handlers.feedback).toHaveBeenLastCalledWith({
        message: "Link applied.",
      }),
    );
    lifecycle.receive(action, "authenticated");
    retry?.();
    expect(handlers.consume).toHaveBeenCalledTimes(2);
  });
  it("allows reopening a transient token after another destination replaces its retry", async () => {
    const { lifecycle, handlers } = lifecycleFixture();
    handlers.consume.mockRejectedValueOnce(new Error("transient"));
    const action = { type: "verify-account", token: fixtureToken } as const;
    lifecycle.receive(action, "authenticated");
    await vi.waitFor(() =>
      expect(typeof handlers.feedback.mock.lastCall?.[0]?.retry).toBe(
        "function",
      ),
    );
    const staleRetry = handlers.feedback.mock.lastCall?.[0]?.retry;
    lifecycle.receive({ type: "listing", id: "another-home" }, "authenticated");
    staleRetry?.();
    expect(handlers.consume).toHaveBeenCalledTimes(1);

    lifecycle.receive(action, "authenticated");
    await vi.waitFor(() =>
      expect(handlers.feedback).toHaveBeenLastCalledWith({
        message: "Link applied.",
      }),
    );
    lifecycle.receive(action, "authenticated");
    expect(handlers.consume).toHaveBeenCalledTimes(2);
  });

  it("fences an earlier navigation when a newer invalid link arrives", async () => {
    const { lifecycle, handlers } = lifecycleFixture();
    const pending = barrier<void>();
    const showDestination = vi.fn();
    handlers.navigate.mockImplementation(async (_destination, isCurrent) => {
      await pending.promise;
      if (isCurrent()) showDestination();
    });
    lifecycle.receive({ type: "listing", id: "slow-home" }, "guest");
    lifecycle.receive({ type: "invalid" }, "guest");
    pending.resolve();
    await pending.promise;
    expect(showDestination).not.toHaveBeenCalled();
    expect(handlers.feedback).toHaveBeenLastCalledWith({
      message: "This link is invalid or unsupported.",
    });
  });

  it("allows a dismissed reset to reopen and retains completed resets for the lifecycle", () => {
    const { lifecycle, handlers } = lifecycleFixture();
    const action = { type: "reset-password", token: fixtureToken } as const;
    lifecycle.receive(action, "guest");
    lifecycle.receive(action, "guest");
    expect(handlers.reset).toHaveBeenCalledTimes(1);
    expect(lifecycle.finishReset(fixtureToken, false)).toBe(true);
    lifecycle.receive(action, "guest");
    expect(handlers.reset).toHaveBeenCalledTimes(3);
    expect(lifecycle.finishReset(fixtureToken, true)).toBe(true);
    lifecycle.receive(action, "guest");
    expect(handlers.reset).toHaveBeenCalledTimes(4);
  });
});

describe("link token requests", () => {
  function response(data: unknown, status = 200) {
    return new Response(JSON.stringify(data), { status });
  }

  it("renders fixed expired/used reset errors and leaves the unrelated session active after failures", async () => {
    const { api, getSessionState } = await import("../src/api");
    const next = [
      response({ detail: "This link is invalid or has expired" }, 400),
      response({ detail: "This link has already been used" }, 400),
      response({ detail: fixtureToken }, 503),
      response({ message: "Password changed." }),
    ];
    const paths: string[] = [];
    const fetch = vi.fn(async (url: string) => {
      const path = new URL(url).pathname;
      paths.push(path);
      if (path === "/v1/auth/login")
        return response({
          access_token: "active-account",
          refresh_token: "active-refresh",
          user: {
            id: "account",
            email: "fixture@example.test",
            email_verified: true,
          },
        });
      return next.shift() ?? response({}, 500);
    });
    vi.stubGlobal("fetch", fetch);
    await api.signIn("fixture@example.test", "fixture-login-password", false);
    const attempt = () =>
      api.resetPassword(fixtureToken, "fixture-new-password");
    await expect(attempt()).rejects.toMatchObject({
      message: "This link is invalid or has expired.",
      status: 400,
    });
    await expect(attempt()).rejects.toMatchObject({
      message: "This link has already been used.",
      status: 400,
    });
    await expect(attempt()).rejects.toMatchObject({
      kind: "transient",
      message: "Cannot reach the service. Try again.",
    });
    expect(getSessionState()).toBe("active");
    expect(secureStore.deleteItemAsync).toHaveBeenCalledTimes(2);
    expect(await attempt()).toEqual({ message: "Password changed." });
    expect(paths.filter((path) => path.endsWith("/refresh"))).toHaveLength(0);
    expect(
      secureStore.setItemAsync.mock.calls.some((args) =>
        args.includes(fixtureToken),
      ),
    ).toBe(false);
  });

  it("does not refresh a valid session on an invalid verify or confirmation token", async () => {
    const { api, request, getSessionState } = await import("../src/api");
    let count = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        if (++count === 1)
          return response({
            access_token: "signed-in",
            refresh_token: "refresh-fixture",
            user: {
              id: "account",
              email: "fixture@example.test",
              email_verified: true,
            },
          });
        return response({ detail: fixtureToken }, 401);
      }),
    );
    await api.signIn("fixture@example.test", "fixture-login-password", false);
    await expect(api.verifyAccount(fixtureToken)).rejects.toMatchObject({
      message: "This link is invalid or has expired.",
    });
    await expect(
      request(
        "/v1/notifications/email/confirm",
        {
          method: "POST",
          body: JSON.stringify({ token: fixtureToken }),
        },
        false,
        false,
      ),
    ).rejects.toMatchObject({
      message: "This confirmation link expired or was already used.",
    });
    expect(count).toBe(3);
    expect(getSessionState()).toBe("active");
  });
});
