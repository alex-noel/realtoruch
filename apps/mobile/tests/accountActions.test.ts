import { beforeEach, expect, it, vi } from "vitest";
const f = vi.hoisted(() => ({ revision: 0, state: "active", disable: vi.fn(), signOut: vi.fn() }));
vi.mock("../src/api", () => ({ getSessionRevision: () => f.revision, getSessionState: () => f.state, api: { signOut: f.signOut } }));
vi.mock("../src/pushClient", () => ({ disablePush: f.disable }));
import { completedAccountAction, signOutWithPush } from "../src/accountActions";
beforeEach(() => { f.revision = 4; f.state = "active"; f.disable.mockReset(); f.signOut.mockReset(); });
it("does not sign out a newer account after delayed push cleanup", async () => {
  let release!: () => void;
  f.disable.mockReturnValue(new Promise<void>(resolve => { release = resolve; }));
  const action = signOutWithPush(); f.revision = 5; release();
  expect(await action).toBeNull(); expect(f.signOut).not.toHaveBeenCalled();
});
it("does not publish old completion after a new login during secure cleanup", async () => {
  let release!: () => void;
  f.signOut.mockImplementation(async () => { f.revision++; f.state = "signed-out"; await new Promise<void>(resolve => { release = resolve; }); });
  const action = signOutWithPush(); await vi.waitFor(() => expect(f.signOut).toHaveBeenCalled());
  f.revision++; f.state = "active"; release();
  expect(await action).toBeNull(); expect(completedAccountAction(4)).toBe(false);
});
it("allows account deletion completion only for its signed-out session", () => {
  f.revision = 5; f.state = "signed-out"; expect(completedAccountAction(4)).toBe(true);
  f.revision = 6; f.state = "active"; expect(completedAccountAction(4)).toBe(false);
});
it("still signs out after provider cleanup failure and includes the recovery message", async () => {
  f.disable.mockRejectedValue(Error("offline")); f.signOut.mockImplementation(async () => { f.revision++; f.state = "signed-out"; });
  expect(await signOutWithPush()).toContain("Device alert removal could not be confirmed.");
});
