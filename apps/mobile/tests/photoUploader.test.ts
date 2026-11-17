import { afterEach, describe, expect, it, vi } from "vitest";
import {
  choosePhotos,
  MAX_BYTES,
  observePreview,
  type PhotoSource,
} from "../src/components/photoSelection";
import { PhotoQueue } from "../src/components/photoState";
import type { ImagePickerAsset } from "expo-image-picker";
import type { MediaAsset } from "../src/types";

const native = vi.hoisted(() => {
  const cache = new Map<string, Uint8Array>();
  return {
    cache,
    permission: vi.fn(),
    launch: vi.fn(),
    fetch: vi.fn(),
    File: class {
      uri: string;
      type = "image/png";
      size = 128;
      constructor(path: string, name?: string) {
        this.uri = name ? `${path}/${name}` : path;
      }
      get exists() {
        return cache.has(this.uri);
      }
      create() {
        cache.set(this.uri, new Uint8Array());
      }
      write(data: Uint8Array) {
        cache.set(this.uri, data);
      }
      delete() {
        cache.delete(this.uri);
      }
    },
  };
});
vi.mock("expo-image-picker", () => ({
  requestMediaLibraryPermissionsAsync: native.permission,
  launchImageLibraryAsync: native.launch,
  UIImagePickerPreferredAssetRepresentationMode: { Current: "current" },
}));
vi.mock("expo-file-system", () => ({
  File: native.File,
  Paths: { cache: "file:///test-cache" },
}));
vi.mock("expo/fetch", () => ({ fetch: native.fetch }));

const deferred = <T>() => {
  let resolve!: (result: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((ok, fail) => {
    resolve = ok;
    reject = fail;
  });
  return { promise, resolve, reject };
};
const transferResult = (
  id: string,
  state: MediaAsset["state"] = "ready",
  description = "",
): MediaAsset => ({
  id,
  state,
  description,
  display_url: null,
  thumbnail_url: null,
});
function asset(
  name: string,
  size = 8,
  mimeType = "image/png",
  width = 8,
  height = 8,
): ImagePickerAsset {
  return {
    uri: `file:///picker/${name}`,
    fileName: name,
    mimeType,
    fileSize: size,
    width,
    height,
  };
}
function photo(name: string): PhotoSource {
  return {
    name,
    mime: "image/png",
    body: new Blob([name], { type: "image/png" }),
    preview: () => ({ uri: `file:///test/${name}`, dispose() {} }),
  };
}
const api = () => ({
  upload:
    vi.fn<
      (
        key: string,
        file: Blob,
        mime: string,
        signal: AbortSignal,
      ) => Promise<MediaAsset>
    >(),
  status: vi
    .fn<(id: string, signal: AbortSignal) => Promise<MediaAsset>>()
    .mockImplementation(async (id) => transferResult(id)),
  cancel: vi
    .fn<(key: string, signal: AbortSignal) => Promise<MediaAsset>>()
    .mockImplementation(async (key) => transferResult(key, "deleted")),
  remove: vi
    .fn<(id: string, signal: AbortSignal) => Promise<MediaAsset>>()
    .mockImplementation(async (id) => transferResult(id, "deleted")),
  describe: vi
    .fn<
      (id: string, text: string, signal: AbortSignal) => Promise<MediaAsset>
    >()
    .mockImplementation(async (id, text) => transferResult(id, "ready", text)),
});
const queues: PhotoQueue[] = [];
function start(
  transport: ReturnType<typeof api>,
  ids: string[] = [],
  stillCurrent?: () => boolean,
  poll?: (signal: AbortSignal) => Promise<void>,
) {
  let key = 0;
  const queue = new PhotoQueue(
    transport,
    ids,
    stillCurrent,
    () => `key-${++key}`,
    poll,
  );
  queues.push(queue);
  queue.activate();
  return queue;
}
async function settle() {
  for (let i = 0; i < 10; i++) await Promise.resolve();
}
afterEach(() => {
  queues.splice(0).forEach((queue) => queue.deactivate());
  native.cache.clear();
  vi.clearAllMocks();
});

describe("owner picker adapters", () => {
  it("uses native read permission only on choice, leaves denial recoverable, and returns the original native file", async () => {
    const { pickPhotos, photoFetch } = await import(
      "../src/components/photoFiles"
    );
    expect(native.permission).not.toHaveBeenCalled();
    const signal = new AbortController().signal;
    native.permission
      .mockResolvedValueOnce({ granted: false })
      .mockResolvedValueOnce({ granted: true });
    native.launch.mockResolvedValueOnce({
      canceled: false,
      assets: [
        asset("kitchen.png", 128, "image/png", 32_768, 1),
        asset("wide.png", 128, "image/png", 32_769, 0),
        asset("tall.png", 128, "image/png", 1, 32_769),
      ],
    });
    expect((await pickPhotos(3, signal)).errors.join()).toContain("denied");
    expect(native.launch).not.toHaveBeenCalled();
    const picked = await pickPhotos(3, signal);
    expect(native.launch).toHaveBeenCalledWith(
      expect.objectContaining({
        mediaTypes: ["images"],
        selectionLimit: 3,
        preferredAssetRepresentationMode: "current",
        quality: 1,
      }),
    );
    expect(picked.sources.map((source) => source.name)).toEqual(["kitchen.png"]);
    expect(picked.errors).toEqual([
      "wide.png: Choose an image with neither side longer than 32,768 pixels.",
      "tall.png: Choose an image with neither side longer than 32,768 pixels.",
    ]);
    expect(picked.sources[0].body).toBeInstanceOf(native.File);
    expect(picked.sources[0].preview().uri).toBe("file:///picker/kitchen.png");
    expect(photoFetch).toBe(native.fetch);
  });

  it("opens web synchronously without permission and separates valid, oversized and unsupported files", async () => {
    const selected = {
      canceled: false as const,
      assets: [
        asset("valid.png"),
        asset("bad.txt", 8, "text/plain"),
        asset("big.jpg", MAX_BYTES + 1, "image/jpeg"),
        asset("wide.png", 1000, "image/png", 6000, 4000),
        asset("valid-limit.png", MAX_BYTES),
        asset("too-many.png"),
      ],
    };
    const picker = {
      requestMediaLibraryPermissionsAsync: vi.fn(),
      launchImageLibraryAsync: vi.fn(async () => selected),
    };
    const promise = choosePhotos(
      true,
      picker,
      (input) => ({
        body: { type: input.mimeType, size: input.fileSize } as Blob,
        preview: () => ({ uri: input.uri, dispose() {} }),
      }),
      2,
    );
    expect(picker.launchImageLibraryAsync).toHaveBeenCalledTimes(1);
    expect(picker.requestMediaLibraryPermissionsAsync).not.toHaveBeenCalled();
    const result = await promise;
    expect(result.sources.map((source) => source.name)).toEqual([
      "valid.png",
      "valid-limit.png",
    ]);
    expect(result.errors).toEqual([
      expect.stringContaining("JPEG, PNG or WebP"),
      expect.stringContaining("10 MiB"),
      expect.stringContaining("20 megapixels"),
      expect.stringContaining("Extra files were not added"),
    ]);
  });

  it("writes private native preview bytes to a temporary file and deletes it on disposal", async () => {
    const { storedPhotoPreview } = await import("../src/components/photoFiles");
    const preview = await storedPhotoPreview(
      new Blob([new Uint8Array([1, 2, 3])], { type: "image/jpeg" }),
    );
    expect(preview.uri).toMatch(
      /^file:\/\/\/test-cache\/owner-preview-.*\.jpg$/,
    );
    expect(native.cache.get(preview.uri)).toEqual(new Uint8Array([1, 2, 3]));
    preview.dispose();
    expect(native.cache.has(preview.uri)).toBe(false);
  });

  it("aborts a private preview load and disposes a late resource without publishing it", async () => {
    const pending = deferred<{ uri: string; dispose: () => void }>();
    const shown = vi.fn();
    const failed = vi.fn();
    const release = vi.fn();
    let signal: AbortSignal | undefined;
    const cleanup = observePreview(
      (s) => ((signal = s), pending.promise),
      shown,
      failed,
    );
    cleanup();
    expect(signal?.aborted).toBe(true);
    pending.resolve({ uri: "blob:late", dispose: release });
    await settle();
    expect(release).toHaveBeenCalledTimes(1);
    expect(shown).not.toHaveBeenCalled();
    expect(failed).not.toHaveBeenCalled();
  });
});

describe("owner upload queue", () => {
  it("runs at most three of six, cancels before the ID and retries the same bytes and key after a timeout", async () => {
    const transport = api();
    const requests: {
      key: string;
      result: ReturnType<typeof deferred<MediaAsset>>;
    }[] = [];
    let active = 0;
    let peak = 0;
    transport.upload.mockImplementation((key) => {
      active++;
      peak = Math.max(peak, active);
      const result = deferred<MediaAsset>();
      requests.push({ key, result });
      return result.promise.finally(() => active--);
    });
    const queue = start(transport);
    const selection = ["one", "two", "three", "four", "five", "six"].map(photo);
    queue.add(selection, 0);
    expect(requests.map((r) => r.key)).toEqual(["key-1", "key-2", "key-3"]);
    queue.remove("upload:key-1");
    await settle();
    expect(transport.cancel).toHaveBeenCalledWith(
      "key-1",
      expect.any(AbortSignal),
    );
    expect(transport.upload.mock.calls[0][3].aborted).toBe(true);
    expect(requests).toHaveLength(3); // A transport ignoring AbortSignal has not settled yet.
    requests[0].result.resolve(transferResult("late"));
    requests[1].result.reject(new Error("Timed out"));
    await settle();
    expect(requests.map((r) => r.key)).toEqual([
      "key-1",
      "key-2",
      "key-3",
      "key-4",
      "key-5",
    ]);
    queue.retry("upload:key-2");
    requests[2].result.resolve(transferResult("three"));
    await settle();
    expect(transport.upload.mock.calls[5].slice(0, 3)).toEqual([
      "key-2",
      selection[1].body,
      "image/png",
    ]);
    expect(transport.upload.mock.calls[5][1]).toBe(
      transport.upload.mock.calls[1][1],
    );
    for (const item of requests.slice(3))
      item.result.resolve(transferResult(item.key));
    await settle();
    requests[6].result.resolve(transferResult("six"));
    await settle();
    expect(peak).toBe(3);
    expect(queue.prepareSave()).toEqual({
      ids: ["key-2", "three", "key-4", "key-5", "six"],
      descriptions: [],
      unresolved: false,
    });
  });

  it("polls pending server assets, saves only ordered ready IDs, and detaches before deleting and describing", async () => {
    const transport = api();
    const polling = deferred<void>();
    transport.upload.mockImplementation(async (key) =>
      key === "key-1"
        ? transferResult("pending", "pending")
        : transferResult("ready"),
    );
    transport.status.mockImplementation(async (id) =>
      transferResult(id, "ready", "Saved photo"),
    );
    const queue = start(
      transport,
      ["saved-a", "saved-b"],
      undefined,
      () => polling.promise,
    );
    queue.add([photo("pending"), photo("ready")], 0);
    await settle();
    queue.describe("upload:key-2", "  View from the living room  ");
    queue.move("upload:key-2", -1);
    queue.move("upload:key-2", -1);
    queue.remove("saved:saved-a");
    expect(queue.prepareSave()).toEqual({
      ids: ["ready", "saved-b"],
      descriptions: [{ id: "ready", value: "View from the living room" }],
      unresolved: true,
    });
    expect(transport.remove).not.toHaveBeenCalled();
    expect(transport.describe).not.toHaveBeenCalled();
    await queue.finalizeSave(queue.prepareSave());
    expect(transport.remove).toHaveBeenCalledWith(
      "saved-a",
      expect.any(AbortSignal),
    );
    expect(transport.describe).toHaveBeenCalledWith(
      "ready",
      "View from the living room",
      expect.any(AbortSignal),
    );
    polling.resolve();
    await settle();
    expect(queue.prepareSave().ids).toEqual(["ready", "saved-b", "pending"]);
  });

  it("includes links in the photo cap and retains unavailable saved IDs until an owner's explicit removal", async () => {
    const transport = api();
    transport.status.mockRejectedValue(
      Object.assign(new Error("Network"), { status: 503 }),
    );
    transport.upload.mockResolvedValue(transferResult("new"));
    const queue = start(transport, ["stored"]);
    expect(queue.add([photo("one"), photo("two")], 28)).toBe(1);
    await settle();
    expect(queue.hasUnverifiedSaved()).toBe(true);
    expect(queue.prepareSave()).toMatchObject({
      ids: ["new"],
      unresolved: true,
    });
    queue.remove("saved:stored");
    expect(queue.hasUnverifiedSaved()).toBe(false);
    expect(transport.remove).not.toHaveBeenCalled();
  });

  it("tracks unsaved photo changes and preserves selected descriptions after a confirmed save", async () => {
    const transport = api(); transport.status.mockImplementation(async id => transferResult(id, "ready", "Existing"));
    transport.upload.mockResolvedValue(transferResult("new"));
    const queue = start(transport, ["stored"]); await settle();
    expect(queue.isDirty()).toBe(false);
    queue.add([photo("new")], 0); await settle(); expect(queue.isDirty()).toBe(true);
    queue.describe("upload:key-1", "Private caption");
    transport.describe.mockRejectedValueOnce(new Error("offline"));
    const save = queue.prepareSave();
    expect(await queue.finalizeSave(save)).toMatchObject({ descriptionsSaved: false });
    queue.retainSaved(save.ids);
    expect(queue.snapshot().rows.find(row => row.id === "new")?.description).toBe("Private caption");
    expect(queue.isDirty()).toBe(true);
    expect((await queue.finalizeSave(queue.prepareSave())).descriptionsSaved).toBe(true);
    expect(queue.isDirty()).toBe(false);
  });

  it("starts explicit discard cancellation before teardown and ignores a late upload", async () => {
    const transport = api(), upload = deferred<MediaAsset>(), cancel = deferred<MediaAsset>();
    transport.upload.mockReturnValue(upload.promise); transport.cancel.mockReturnValue(cancel.promise);
    const queue = start(transport); queue.add([photo("unfinished")], 0);
    queue.discardNew(); queue.deactivate();
    expect(transport.cancel).toHaveBeenCalledOnce();
    expect(transport.cancel.mock.calls[0][0]).toBe("key-1");
    expect(transport.cancel.mock.calls[0][1].aborted).toBe(false);
    upload.resolve(transferResult("late")); cancel.resolve(transferResult("cancelled", "deleted")); await settle();
    expect(queue.snapshot().rows).toEqual([]);
  });

  it("retains explicitly selected remote IDs and cancels unselected local additions only after save", async () => {
    const transport = api(); transport.upload.mockResolvedValue(transferResult("local"));
    const queue = start(transport, ["stored"]); await settle();
    queue.add([photo("new")], 0); await settle();
    expect(transport.cancel).not.toHaveBeenCalled();
    const save = { ids: ["remote", "stored"], descriptions: [], unresolved: false };
    await queue.finalizeSave(save); queue.retainSaved(save.ids); await settle();
    expect(queue.snapshot().rows.map(row => row.id)).toEqual(["remote", "stored"]);
    expect(transport.cancel).toHaveBeenCalledWith("key-1", expect.any(AbortSignal));
  });

  it("merges local and latest photo additions without restoring removals or starting mutations after session changes", async () => {
    const transport = api();
    transport.upload.mockResolvedValue(transferResult("local"));
    let current = true;
    const queue = start(transport, ["a", "b", "c"], () => current);
    await settle();
    queue.add([photo("local")], 0);
    await settle();
    queue.remove("saved:b");
    queue.move("upload:key-1", -1);
    queue.applyLatest(["latest", "a", "b"], true);
    await settle();
    expect(queue.prepareSave().ids).toEqual(["latest", "a", "local"]);
    expect(transport.remove).not.toHaveBeenCalled();
    current = false;
    queue.add([photo("different account")], 0);
    await settle();
    expect(transport.upload).toHaveBeenCalledTimes(1);
    expect(await queue.finalizeSave(queue.prepareSave())).toMatchObject({
      removalsSaved: false,
    });
    expect(transport.remove).not.toHaveBeenCalled();
  });
});

