import { beforeEach, expect, it, vi } from "vitest";
const f = vi.hoisted(() => ({ available: vi.fn(), share: vi.fn(), write: vi.fn(), remove: vi.fn(), exists: false, path: "", contents: "" }));
vi.mock("expo-sharing", () => ({ isAvailableAsync: f.available, shareAsync: f.share }));
vi.mock("expo-file-system", () => ({ Paths: { cache: "file:///private-cache" },
  Directory: class { uri = "file:///private-cache/realtoruch-account-export"; get exists() { return f.exists; } create() { f.exists = true; } delete() { f.remove(); f.exists = false; } },
  File: class { uri: string; constructor(_: unknown, name: string) { this.uri = `file:///private-cache/realtoruch-account-export/${name}`; f.path = this.uri; } create() {} async write(value: string) { f.contents = value; await f.write(); } },
}));
import { deliverAccountExport } from "../src/accountExport";
import { deliverAccountExport as deliverWeb } from "../src/accountExport.web";
beforeEach(() => { f.available.mockReset().mockResolvedValue(true); f.share.mockReset().mockResolvedValue(undefined); f.write.mockReset().mockResolvedValue(undefined); f.remove.mockReset(); f.exists = false; f.path = ""; f.contents = ""; vi.unstubAllGlobals(); });
it("shares named JSON and cleans the temporary file after success or user cancellation", async () => {
  await deliverAccountExport({ account: { email: "synthetic@example.test" } }, () => true);
  expect(f.path).toMatch(/realtoruch-account-\d{4}-\d{2}-\d{2}\.json$/);
  expect(JSON.parse(f.contents)).toEqual({ account: { email: "synthetic@example.test" } });
  expect(f.share).toHaveBeenCalledWith(f.path, expect.objectContaining({ mimeType: "application/json" }));
  expect(f.remove).toHaveBeenCalledTimes(1); expect(f.exists).toBe(false);
});
it("cleans after native share failure without exposing native error details", async () => {
  f.share.mockRejectedValue(Error("secret path"));
  await expect(deliverAccountExport({}, () => true)).rejects.toThrow("Could not save or share your export. Try again.");
  expect(f.exists).toBe(false);
});
it("cleans partial writes and a stale file left by a stopped app process", async () => {
  f.exists = true; f.write.mockRejectedValue(Error("disk full"));
  await expect(deliverAccountExport({}, () => true)).rejects.toThrow("Could not save");
  expect(f.remove).toHaveBeenCalledTimes(2); expect(f.exists).toBe(false);
});
it("does not share after account switch while writing", async () => {
  let current = true; f.write.mockImplementation(async () => { current = false; });
  await deliverAccountExport({}, () => current); expect(f.share).not.toHaveBeenCalled(); expect(f.exists).toBe(false);
});
it("does not create a file if sharing is unavailable", async () => {
  f.available.mockResolvedValue(false); await expect(deliverAccountExport({}, () => true)).rejects.toThrow("Use the web app");
  expect(f.write).not.toHaveBeenCalled(); expect(f.exists).toBe(false);
});
it("keeps the web download private and revokes its transient object URL", async () => {
  vi.useFakeTimers();
  const anchor = { href: "", download: "", style: { display: "" }, click: vi.fn(), remove: vi.fn() };
  const create = vi.fn((_blob: Blob) => "blob:ephemeral"), revoke = vi.fn();
  vi.stubGlobal("document", { createElement: () => anchor, body: { appendChild: vi.fn() } });
  vi.stubGlobal("URL", { createObjectURL: create, revokeObjectURL: revoke });
  await deliverWeb({ synthetic: 1 }, () => true);
  expect(await (create.mock.calls[0][0] as Blob).text()).toBe('{"synthetic":1}');
  expect(anchor.download).toMatch(/^realtoruch-account-.*\.json$/); expect(anchor.click).toHaveBeenCalled(); expect(anchor.remove).toHaveBeenCalled();
  vi.runAllTimers(); expect(revoke).toHaveBeenCalledWith("blob:ephemeral"); vi.useRealTimers();
});
