import { describe, expect, it, vi } from "vitest";
vi.mock("react-native", async () => vi.importActual("react-native-web"));
vi.mock("react-native-safe-area-context", () => ({ SafeAreaView: "div" }));
vi.mock("../src/components/UI", () => ({
  Button: () => null,
  money: (value: number) => String(value),
}));
vi.mock("../src/pushClient", () => ({
  disablePush: vi.fn(),
  enablePush: vi.fn(),
  pushEnabled: vi.fn(async () => false),
}));
vi.mock("../src/api", () => ({ request: vi.fn() }));
import {
  createEmailPreference,
  type EmailPreferenceState,
} from "../src/components/NotificationInbox";

type EmailValue = {
  enabled: boolean;
  verified: boolean;
  confirmation_pending?: boolean;
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}

function setup(
  load: () => Promise<EmailValue>,
  save: (enabled: boolean) => Promise<EmailValue> = async (enabled) => ({
    enabled,
    verified: true,
  }),
) {
  const states: EmailPreferenceState[] = [];
  const controller = createEmailPreference(load, save, (state) => {
    states.push(state);
  });
  return { controller, states };
}

describe("email alert preference recovery", () => {
  it("keeps a failed lookup unknown, then retries to the authoritative enabled state", async () => {
    const load = vi
      .fn<() => Promise<EmailValue>>()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({ enabled: true, verified: true });
    const { controller, states } = setup(load);

    await controller.refresh();
    expect(states.at(-1)).toMatchObject({
      value: null,
      loading: false,
      loadFailed: true,
    });

    await controller.refresh();
    expect(states.at(-1)).toMatchObject({
      value: { enabled: true, verified: true },
      loading: false,
      loadFailed: false,
    });
  });

  it("keeps the confirmed value on update failure and distinguishes pending confirmation", async () => {
    const load = vi.fn(async () => ({ enabled: false, verified: false }));
    const save = vi
      .fn<(enabled: boolean) => Promise<EmailValue>>()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({
        enabled: false,
        verified: false,
        confirmation_pending: true,
      });
    const { controller, states } = setup(load, save);

    await controller.refresh();
    await controller.toggle();
    expect(states.at(-1)).toMatchObject({
      value: { enabled: false, verified: false },
      busy: false,
      updateFailed: true,
    });
    await controller.toggle();
    expect(save).toHaveBeenLastCalledWith(true);
    expect(states.at(-1)).toMatchObject({
      value: {
        enabled: false,
        verified: false,
        confirmation_pending: true,
      },
      updateFailed: false,
    });
  });

  it("keeps an unconfigured channel unavailable after a successful lookup", async () => {
    const save = vi.fn(async (enabled: boolean) => ({ enabled, verified: true }));
    const { controller, states } = setup(
      async () => ({ configured: false, enabled: false, verified: false }),
      save,
    );

    await controller.refresh();
    await controller.toggle();

    expect(states.at(-1)?.value).toEqual({
      configured: false,
      enabled: false,
      verified: false,
    });
    expect(save).not.toHaveBeenCalled();
  });

  it("does not apply delayed load results after disposal for an account switch", async () => {
    const oldLoad = deferred<EmailValue>();
    const old = setup(() => oldLoad.promise);
    const pending = old.controller.refresh();
    old.controller.dispose();

    const next = setup(async () => ({ enabled: true, verified: true }));
    await next.controller.refresh();
    const previousCallbacks = old.states.length;
    oldLoad.resolve({ enabled: false, verified: false });
    await pending;

    expect(old.states).toHaveLength(previousCallbacks);
    expect(next.states.at(-1)?.value).toEqual({ enabled: true, verified: true });
  });

  it("does not apply a delayed update after account disposal", async () => {
    const saveResult = deferred<EmailValue>();
    const old = setup(
      async () => ({ enabled: false, verified: false }),
      () => saveResult.promise,
    );
    await old.controller.refresh();
    const pending = old.controller.toggle();
    const previousCallbacks = old.states.length;
    old.controller.dispose();
    saveResult.resolve({ enabled: true, verified: true });
    await pending;

    expect(old.states).toHaveLength(previousCallbacks);
    expect(old.states.at(-1)).toMatchObject({
      value: { enabled: false, verified: false },
      busy: true,
    });
  });
});
