import type { makeOwnerMedia } from "../marketplaceApi";
import type { MediaAsset } from "../types";
import { MAX_PHOTOS, photoIdentity, type PhotoSource } from "./photoSelection";

type MediaApi = Omit<
  ReturnType<typeof makeOwnerMedia>,
  "preview" | "statusByKey"
>;
type Cleanup = { kind: "key" | "id"; target: string };
type Phase = "queued" | "uploading" | "checking" | "ready" | "failed";
export type PhotoRow = {
  key: string;
  name?: string;
  upload?: { identity: string; source?: PhotoSource };
  id?: string;
  phase: Phase;
  description: string;
  storedDescription: string;
  error?: string;
  retryable?: boolean;
};
export type PhotoSave = {
  ids: string[];
  descriptions: { id: string; value: string }[];
  unresolved: boolean;
};
type Snapshot = { rows: PhotoRow[]; cleanupFailed: boolean };

const LIMIT = 3;
const fromStored = (id: string): PhotoRow => ({
  key: `saved:${id}`,
  id,
  phase: "checking",
  description: "",
  storedDescription: "",
});
const statusCode = (error: unknown) =>
  (error as { status?: number } | null)?.status;
function explain(error: unknown, restoring: boolean) {
  switch (statusCode(error)) {
    case 401:
      return "Sign in again before working with photos.";
    case 403:
      return restoring
        ? "This photo is unavailable."
        : "Verify your account email before uploading photos.";
    case 404:
      return "This photo is unavailable.";
    case 409:
      return "This upload can no longer be retried. Remove it and choose the file again.";
    case 413:
      return "Choose an image no larger than 10 MiB.";
    case 415:
      return "Choose a JPEG, PNG or WebP image.";
    case 422:
      return "Choose a valid still image no larger than 20 megapixels.";
    default:
      return restoring
        ? "Could not check this photo. Try again."
        : "Upload could not finish. Try again.";
  }
}

function waitForPoll(signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const cancel = () => {
      clearTimeout(timer);
      signal.removeEventListener("abort", cancel);
      reject(new Error("Photo check cancelled."));
    };
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", cancel);
      resolve();
    }, 500);
    signal.addEventListener("abort", cancel, { once: true });
    if (signal.aborted) cancel();
  });
}

export class PhotoQueue {
  private view: Snapshot;
  private saved: Set<string>;
  private listening = new Set<() => void>();
  private working = new Map<string, AbortController>();
  private deleting = new Map<
    string,
    { controller: AbortController; done: Promise<void> }
  >();
  private cleanup = new Map<string, Cleanup>();
  private lifecycle = new AbortController();
  private mounted = false;

  constructor(
    private api: MediaApi,
    ids: readonly string[] = [],
    private isCurrent = () => true,
    private nextIdentity = photoIdentity,
    private poll = waitForPoll,
  ) {
    this.saved = new Set(ids);
    this.view = { rows: [...this.saved].map(fromStored), cleanupFailed: false };
  }

  snapshot = () => this.view;
  subscribe = (onChange: () => void) => {
    this.listening.add(onChange);
    return () => {
      this.listening.delete(onChange);
    };
  };

  activate() {
    this.mounted = true;
    this.lifecycle = new AbortController();
    this.pump();
  }
  deactivate() {
    this.mounted = false;
    this.lifecycle.abort();
    for (const job of this.working.values()) job.abort();
    for (const { controller } of this.deleting.values()) controller.abort();
    // An upload interrupted by an effect teardown can be resumed with the same key.
    this.update(
      this.view.rows.map((row) =>
        row.phase === "uploading" ? { ...row, phase: "queued" } : row,
      ),
    );
  }

  add(sources: PhotoSource[], externalCount: number) {
    const remaining = Math.max(
      0,
      MAX_PHOTOS - externalCount - this.view.rows.length,
    );
    const newRows = sources.slice(0, remaining).map((source) => {
      const identity = this.nextIdentity();
      return {
        key: `upload:${identity}`,
        name: source.name,
        upload: { identity, source },
        phase: "queued" as const,
        description: "",
        storedDescription: "",
      };
    });
    this.update([...this.view.rows, ...newRows]);
    this.pump();
    return sources.length - newRows.length;
  }

  move(key: string, distance: -1 | 1) {
    const from = this.view.rows.findIndex((row) => row.key === key);
    if (from < 0) return;
    const to = from + distance;
    if (to < 0 || to >= this.view.rows.length) return;
    const rows = [...this.view.rows];
    [rows[from], rows[to]] = [rows[to], rows[from]];
    this.update(rows);
  }

  describe(key: string, description: string) {
    this.change(key, (row) => ({
      ...row,
      description: Array.from(description).slice(0, 500).join(""),
    }));
  }

  retry(key: string) {
    this.change(key, (row) =>
      row.phase === "failed" && row.retryable
        ? {
            ...row,
            phase: row.upload ? "queued" : "checking",
            error: undefined,
          }
        : row,
    );
    this.pump();
  }

  remove(key: string) {
    const row = this.view.rows.find((item) => item.key === key);
    if (!row) return;
    this.working.get(key)?.abort();
    this.update(this.view.rows.filter((item) => item.key !== key));
    if (row.upload && (!row.id || !this.saved.has(row.id))) {
      const removal: Cleanup = { kind: "key", target: row.upload.identity };
      this.enqueueCleanup(removal);
      void this.deleteItem(removal);
    }
  }

  hasUnverifiedSaved() {
    return this.view.rows.some(
      (row) => row.id && this.saved.has(row.id) && row.phase !== "ready",
    );
  }

  prepareSave(): PhotoSave {
    const ready = this.view.rows.flatMap((row) =>
      row.id && row.phase === "ready" ? [{ ...row, id: row.id }] : [],
    );
    return {
      ids: ready.map((row) => row.id),
      descriptions: ready
        .filter((row) => row.description.trim() !== row.storedDescription)
        .map((row) => ({ id: row.id, value: row.description.trim() })),
      unresolved: ready.length !== this.view.rows.length,
    };
  }

  // This method runs only after the optimistic advert write succeeded.
  async finalizeSave(save: PhotoSave) {
    const nextSaved = new Set(save.ids);
    for (const id of this.saved)
      if (!nextSaved.has(id)) {
        this.enqueueCleanup({ kind: "id", target: id });
      }
    this.saved = nextSaved;
    const signal = this.lifecycle.signal;
    const results = await Promise.all([
      ...save.descriptions.map(async ({ id, value }) => {
        if (!this.mounted || !this.isCurrent()) return false;
        try {
          const asset = await this.api.describe(id, value, signal);
          if (signal.aborted || !this.isCurrent()) return false;
          const row = this.view.rows.find((item) => item.id === id);
          if (row)
            this.change(row.key, (current) => ({
              ...current,
              description: asset.description,
              storedDescription: asset.description,
            }));
          return true;
        } catch {
          return false;
        }
      }),
      this.retryCleanup(),
    ]);
    return {
      descriptionsSaved: results.slice(0, -1).every(Boolean),
      removalsSaved: results.at(-1) === true,
    };
  }

  // Keep local additions (including unsent originals) and latest saved additions.
  // For saved photos, respect either editor's removals without resurrecting them.
  applyLatest(ids: readonly string[], merge: boolean) {
    const previous = this.saved;
    const latest = new Set(ids);
    const rows = this.view.rows;
    if (!merge) {
      for (const row of rows) {
        if (row.upload && (!row.id || !previous.has(row.id)))
          this.remove(row.key);
        else this.working.get(row.key)?.abort();
      }
      this.saved = latest;
      this.update([...latest].map(fromStored));
      this.pump();
      return;
    }

    const currentById = new Map(
      rows.flatMap((row) => (row.id ? [[row.id, row] as const] : [])),
    );
    const remoteRows = [...latest].flatMap((id) => {
      const current = currentById.get(id);
      return current ? [current] : previous.has(id) ? [] : [fromStored(id)];
    });
    const surviving = new Set(remoteRows.map((row) => row.id));
    const newLocal = (row: PhotoRow) =>
      row.upload && (!row.id || !previous.has(row.id));
    const localSurvivors = rows.filter(
      (row) => newLocal(row) || surviving.has(row.id),
    );
    const localExisting = localSurvivors.flatMap((row) =>
      row.id && previous.has(row.id) ? [row.id] : [],
    );
    const baseExisting = [...previous].filter((id) =>
      localExisting.includes(id),
    );
    const reordered = localExisting.some((id, i) => id !== baseExisting[i]);
    // Preserve a local insertion before an existing photo as well as explicit
    // reordering; when the local order is unchanged use the latest saved order.
    const positioned = localSurvivors.some(
      (row, i) =>
        newLocal(row) &&
        localSurvivors
          .slice(i + 1)
          .some((item) => item.id && previous.has(item.id)),
    );
    const merged =
      reordered || positioned
        ? [
            ...localSurvivors,
            ...remoteRows.filter((row) => !currentById.has(row.id!)),
          ]
        : [
            ...remoteRows,
            ...localSurvivors.filter(
              (row) => newLocal(row) && !latest.has(row.id!),
            ),
          ];
    for (const row of rows) {
      if (!merged.includes(row)) this.working.get(row.key)?.abort();
    }
    this.saved = latest;
    this.update(merged);
    this.pump();
  }

  async retryCleanup() {
    if (!this.mounted || !this.isCurrent()) return false;
    await Promise.all(
      [...this.cleanup.values()].map((item) => this.deleteItem(item)),
    );
    return this.cleanup.size === 0;
  }

  private cleanupKey = ({ kind, target }: Cleanup) => `${kind}:${target}`;
  private enqueueCleanup(item: Cleanup) {
    this.cleanup.set(this.cleanupKey(item), item);
  }
  private deleteItem(item: Cleanup) {
    const key = this.cleanupKey(item);
    if (!this.mounted || !this.isCurrent()) return;
    const existing = this.deleting.get(key);
    if (existing) return existing.done;
    const controller = new AbortController();
    const { signal } = controller;
    const done = Promise.resolve().then(async () => {
      let failed = false;
      try {
        if (signal.aborted || !this.isCurrent()) return;
        await (item.kind === "key"
          ? this.api.cancel(item.target, signal)
          : this.api.remove(item.target, signal));
        if (!signal.aborted && this.isCurrent()) this.cleanup.delete(key);
      } catch (error) {
        if (!signal.aborted && this.isCurrent()) {
          // A detached photo may still be used by another advert. Keep its bytes.
          if (item.kind === "id" && [404, 409].includes(statusCode(error) ?? 0))
            this.cleanup.delete(key);
          else failed = true;
        }
      } finally {
        this.deleting.delete(key);
        if (!signal.aborted && this.isCurrent())
          this.update(
            this.view.rows,
            failed || this.cleanup.size > this.deleting.size,
          );
      }
    });
    this.deleting.set(key, { controller, done });
    return done;
  }

  private update(rows: PhotoRow[], cleanupFailed = this.view.cleanupFailed) {
    this.view = { rows, cleanupFailed };
    for (const onChange of this.listening) onChange();
  }
  private change(key: string, update: (row: PhotoRow) => PhotoRow) {
    this.update(
      this.view.rows.map((row) => (row.key === key ? update(row) : row)),
    );
  }
  private pump() {
    if (!this.mounted || !this.isCurrent()) return;
    while (this.working.size < LIMIT) {
      const row = this.view.rows.find(
        (item) =>
          !this.working.has(item.key) &&
          (item.phase === "queued" || item.phase === "checking"),
      );
      if (!row) break;
      const job = new AbortController();
      this.working.set(row.key, job);
      void this.transfer(row, job);
    }
  }
  private async transfer(row: PhotoRow, job: AbortController) {
    const { signal } = job;
    const isActive = () =>
      !signal.aborted &&
      this.mounted &&
      this.isCurrent() &&
      this.view.rows.some((item) => item.key === row.key);

    try {
      let asset: MediaAsset;
      const source = row.upload?.source;
      if (source && row.upload) {
        this.change(row.key, (current) => ({ ...current, phase: "uploading" }));
        asset = await this.api.upload(
          row.upload.identity,
          source.body,
          source.mime,
          signal,
        );
      } else if (row.id) {
        asset = await this.api.status(row.id, signal);
      } else {
        throw new Error("No photo to upload.");
      }
      const id = asset.id;
      for (
        let attempt = 0;
        isActive() && asset.state === "pending" && attempt < 20;
        attempt++
      ) {
        await this.poll(signal);
        if (!isActive()) return;
        asset = await this.api.status(id, signal);
      }
      if (!isActive()) return;
      if (asset.id !== id || (row.id && asset.id !== row.id))
        throw new Error("Unexpected photo response.");
      if (asset.state === "ready") {
        this.change(row.key, (current) => ({
          ...current,
          id: asset.id,
          phase: "ready",
          error: undefined,
          retryable: undefined,
          upload: current.upload && { identity: current.upload.identity },
          description: current.description || asset.description,
          storedDescription: asset.description,
        }));
      } else {
        this.change(row.key, (current) => ({
          ...current,
          phase: "failed",
          retryable: asset.state === "pending",
          error:
            asset.state === "pending"
              ? "This photo is still processing. Try again."
              : "This photo is unavailable. Remove it or choose another file.",
        }));
      }
    } catch (error) {
      if (!isActive()) return;
      this.change(row.key, (current) => ({
        ...current,
        phase: "failed",
        error: explain(error, !row.upload),
        retryable: ![409, 413, 415, 422].includes(statusCode(error) ?? 0),
      }));
    } finally {
      this.working.delete(row.key);
      this.pump();
    }
  }
}
