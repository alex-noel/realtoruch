// React Native's URL implementation differs from the browser for custom
// schemes. Parse only the absolute, root-route URLs this app accepts.
const APP_URL =
  /^([a-z][a-z0-9+.-]*):\/\/([^/?#]*)(\/[^?#]*)?(\?[^#]*)?(#.*)?$/i;
const AUTHORITY =
  /^(?:[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?|\[::1\])(?::([1-9]\d{0,4}))?$/i;
const IDENTIFIER = /^[a-zA-Z0-9_-]{1,36}$/;
const ACCOUNT_TOKEN = /^[a-zA-Z0-9_-]{20,128}$/;
const EMAIL_TOKEN = /^[a-zA-Z0-9_-]{32,128}$/;
const RESERVED_SCHEMES = new Set([
  "http",
  "https",
  "javascript",
  "data",
  "file",
  "about",
  "ftp",
  "blob",
  "content",
  "intent",
  "exp",
  "exps",
  "mailto",
  "tel",
  "sms",
]);
const MAX_LINK_LENGTH = 1024;
const REOPEN_DELAY_MS = 500;

export const LINK_SCHEME = process.env.EXPO_PUBLIC_LINK_SCHEME || "realtoruch";
export const PUBLIC_WEB_URL = process.env.EXPO_PUBLIC_WEB_URL;

export type LinkDestination =
  | { type: "listing" | "advert" | "saved-listing"; id: string }
  | { type: "notifications" };
type ProtectedDestination =
  | { type: "saved-listing"; id: string }
  | { type: "notifications" };
export type AutomaticTokenLink = {
  type: "verify-account" | "confirm-email" | "unsubscribe-email";
  token: string;
};
type TokenLink = AutomaticTokenLink | { type: "reset-password"; token: string };
export type IncomingLink =
  | LinkDestination
  | TokenLink
  | { type: "none" }
  | { type: "invalid" };

type LinkOrigins = {
  scheme: string;
  publicWebUrl?: string;
  browserOrigin?: string;
};

function webOrigin(
  protocol: string,
  authority: string,
  allowLoopback: boolean,
) {
  const match = AUTHORITY.exec(authority);
  if (!match || (match[1] && Number(match[1]) > 65_535)) return null;
  const host = authority.toLowerCase().replace(/:\d+$/, "");
  const local =
    host === "localhost" || host === "127.0.0.1" || host === "[::1]";
  if (protocol !== "https" && !(allowLoopback && protocol === "http" && local))
    return null;
  const defaultPort = protocol === "https" ? "443" : "80";
  return `${protocol}://${host}${match[1] && match[1] !== defaultPort ? `:${match[1]}` : ""}`;
}

function configuredOrigin(value: string | undefined, allowLoopback: boolean) {
  const parts = value && APP_URL.exec(value);
  if (!parts || (parts[3] && parts[3] !== "/") || parts[4] || parts[5])
    return null;
  return webOrigin(parts[1].toLowerCase(), parts[2], allowLoopback);
}

function parameter(value: string) {
  const match = /^[?#]([a-z_]+)=([^&=#]+)$/.exec(value);
  if (!match) return null;
  try {
    return { name: match[1], value: decodeURIComponent(match[2]) };
  } catch {
    return null;
  }
}

function destinationFromParameter(
  input: ReturnType<typeof parameter>,
): LinkDestination | null {
  if (!input) return null;
  if (input.name === "notifications" && input.value === "1")
    return { type: "notifications" };
  if (!IDENTIFIER.test(input.value)) return null;
  switch (input.name) {
    case "listing":
      return { type: "listing", id: input.value };
    case "advert":
      return { type: "advert", id: input.value };
    case "saved_listing":
      return { type: "saved-listing", id: input.value };
    default:
      return null;
  }
}

const INVALID = { type: "invalid" } as const;

export function parseIncomingLink(
  url: string,
  origins: LinkOrigins,
): IncomingLink {
  if (url.length > MAX_LINK_LENGTH || /[\s\\\x00-\x1f\x7f]/.test(url))
    return INVALID;
  const match = APP_URL.exec(url);
  if (!match) return INVALID;

  const [, rawProtocol, authority, path = "/", query, fragment] = match;
  const protocol = rawProtocol.toLowerCase();
  if (protocol === "https" || protocol === "http") {
    const origin = webOrigin(protocol, authority, !!origins.browserOrigin);
    if (
      !origin ||
      (origin !== configuredOrigin(origins.publicWebUrl, false) &&
        origin !== configuredOrigin(origins.browserOrigin, true))
    )
      return INVALID;
  } else if (
    protocol !== origins.scheme ||
    RESERVED_SCHEMES.has(protocol) ||
    authority
  ) {
    return INVALID;
  }

  if (path !== "/" || (query && fragment)) return INVALID;
  if (!query && !fragment) return { type: "none" };
  const input = parameter(query ?? fragment);
  if (!input) return INVALID;

  if (query) return destinationFromParameter(input) ?? INVALID;

  switch (input.name) {
    case "verify_account":
      return ACCOUNT_TOKEN.test(input.value)
        ? { type: "verify-account", token: input.value }
        : INVALID;
    case "reset_password":
      return ACCOUNT_TOKEN.test(input.value)
        ? { type: "reset-password", token: input.value }
        : INVALID;
    case "confirm_email":
      return EMAIL_TOKEN.test(input.value)
        ? { type: "confirm-email", token: input.value }
        : INVALID;
    case "unsubscribe_email":
      return EMAIL_TOKEN.test(input.value)
        ? { type: "unsubscribe-email", token: input.value }
        : INVALID;
    default:
      return INVALID;
  }
}

export function listingFromPush(id: string): IncomingLink {
  return IDENTIFIER.test(id) ? { type: "listing", id } : INVALID;
}

// Fragments are never kept in browser history, including rejected fragments.
export function sanitizedWebSearch(
  search: string,
  hash: string,
): string | null {
  // Only safe navigation queries survive. Rejected queries may contain secrets.
  if (
    search &&
    (search.length > MAX_LINK_LENGTH ||
      !destinationFromParameter(parameter(search)))
  )
    return "";
  return hash ? search : null;
}

type LinkSource = {
  getInitialURL: () => Promise<string | null | undefined>;
  addEventListener: (
    event: "url",
    receive: (event: { url: string }) => void,
  ) => { remove: () => void };
};

export function subscribeToLinks(
  source: LinkSource,
  receive: (url: string) => void,
) {
  let active = true;
  let initialPending = true;
  const earlyWarmUrls = new Set<string>();
  const subscription = source.addEventListener("url", ({ url }) => {
    if (!active) return;
    if (initialPending && url.length <= MAX_LINK_LENGTH) earlyWarmUrls.add(url);
    receive(url);
  });
  void source
    .getInitialURL()
    .then((url) => {
      if (active && url && !earlyWarmUrls.has(url)) receive(url);
    })
    .catch(() => {})
    .finally(() => {
      initialPending = false;
      earlyWarmUrls.clear();
    });
  return () => {
    active = false;
    earlyWarmUrls.clear();
    subscription.remove();
  };
}

function protectedDestination(
  destination: LinkDestination,
): destination is ProtectedDestination {
  return (
    destination.type === "notifications" || destination.type === "saved-listing"
  );
}

export type LinkFeedback = { message: string; retry?: () => void };

type LinkHandlers = {
  navigate: (
    destination: LinkDestination,
    isCurrent: () => boolean,
  ) => Promise<void>;
  consume: (action: AutomaticTokenLink) => Promise<string>;
  reset: (token: string | null) => void;
  showLogin: () => void;
  feedback: (value: LinkFeedback | null) => void;
  error: (error: unknown) => { message: string; retryable: boolean };
  now?: () => number;
};

export function createLinkLifecycle(handlers: LinkHandlers) {
  let active = true;
  let generation = 0;
  let pendingDestination: ProtectedDestination | null = null;
  let lastDestination: { key: string; time: number } | null = null;
  let currentToken: string | null = null;
  const inFlightTokens = new Set<string>();
  const completedTokens = new Set<string>();
  const now = handlers.now ?? Date.now;

  function run<T>(
    start: () => Promise<T>,
    success: (result: T) => void,
    isCurrent: () => boolean,
  ) {
    let busy = false;
    let completed = false;
    async function attempt() {
      if (busy || completed || !isCurrent()) return;
      busy = true;
      handlers.feedback(null);
      try {
        const result = await start();
        completed = true;
        if (isCurrent()) success(result);
      } catch (error) {
        if (isCurrent()) {
          const { message, retryable } = handlers.error(error);
          completed = !retryable;
          handlers.feedback({
            message,
            retry: retryable ? () => void attempt() : undefined,
          });
        }
      } finally {
        busy = false;
      }
    }
    void attempt();
  }

  function navigate(destination: LinkDestination, intent: number) {
    const isCurrent = () => active && generation === intent;
    run(
      () => handlers.navigate(destination, isCurrent),
      () => {},
      isCurrent,
    );
  }

  function receive(
    action: IncomingLink,
    auth: "restoring" | "guest" | "authenticated",
  ) {
    if (!active || action.type === "none") return;
    if (action.type === "invalid") {
      ++generation;
      currentToken = null;
      pendingDestination = null;
      lastDestination = null;
      handlers.reset(null);
      handlers.feedback({ message: "This link is invalid or unsupported." });
      return;
    }
    if ("token" in action) {
      const key = `${action.type}:${action.token}`;
      if (
        currentToken === key ||
        inFlightTokens.has(key) ||
        completedTokens.has(key)
      )
        return;
      currentToken = key;
      const intent = ++generation;
      pendingDestination = null;
      handlers.feedback(null);
      handlers.reset(action.type === "reset-password" ? action.token : null);
      if (action.type !== "reset-password") {
        run(
          async () => {
            inFlightTokens.add(key);
            try {
              const message = await handlers.consume(action);
              if (active) completedTokens.add(key);
              return message;
            } finally {
              inFlightTokens.delete(key);
            }
          },
          (message) => handlers.feedback({ message }),
          () => active && intent === generation,
        );
      }
      return;
    }
    const key = "id" in action ? `${action.type}:${action.id}` : action.type;
    const time = now();
    if (
      lastDestination?.key === key &&
      time - lastDestination.time < REOPEN_DELAY_MS
    )
      return;
    lastDestination = { key, time };
    currentToken = null;
    const intent = ++generation;
    handlers.reset(null);
    handlers.feedback(null);
    if (protectedDestination(action) && auth !== "authenticated") {
      pendingDestination = action;
      if (auth === "guest") handlers.showLogin();
      return;
    }
    pendingDestination = null;
    navigate(action, intent);
  }

  function resolveSession(authenticated: boolean) {
    if (!active || !pendingDestination) return;
    if (!authenticated) {
      handlers.showLogin();
      return;
    }
    const destination = pendingDestination;
    pendingDestination = null;
    navigate(destination, ++generation);
  }

  function close() {
    active = false;
    pendingDestination = null;
    currentToken = null;
    inFlightTokens.clear();
    completedTokens.clear();
  }

  function finishReset(token: string, completed: boolean) {
    if (!active) return false;
    const key = `reset-password:${token}`;
    if (completed) completedTokens.add(key);
    if (currentToken !== key) return false;
    currentToken = null;
    handlers.reset(null);
    return true;
  }

  function clearPending() {
    pendingDestination = null;
  }

  return { receive, resolveSession, clearPending, finishReset, close };
}
