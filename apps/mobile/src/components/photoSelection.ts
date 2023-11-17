import type {
  ImagePickerAsset,
  ImagePickerOptions,
  ImagePickerResult,
} from "expo-image-picker";
import type { MediaMime } from "../types";

export const MAX_PHOTOS = 30;
export const MAX_BYTES = 10 * 1024 * 1024;
const MAX_PIXELS = 20_000_000;
const MAX_SIDE = 32_768;

export type PhotoPreview = { uri: string; dispose: () => void };
export type PhotoSource = {
  name: string;
  mime: MediaMime;
  body: Blob;
  preview: () => PhotoPreview;
};

type Picker = {
  requestMediaLibraryPermissionsAsync: () => Promise<{ granted: boolean }>;
  launchImageLibraryAsync: (
    options: ImagePickerOptions,
  ) => Promise<ImagePickerResult>;
};
type LocalAsset = { body: Blob; preview: PhotoSource["preview"] };

const mimes: readonly MediaMime[] = ["image/jpeg", "image/png", "image/webp"];
const supportedMime = (mime: string): mime is MediaMime =>
  mimes.some((supported) => supported === mime);

export async function choosePhotos(
  web: boolean,
  picker: Picker,
  localAsset: (asset: ImagePickerAsset) => LocalAsset,
  remaining: number,
) {
  const sources: PhotoSource[] = [];
  const errors: string[] = [];
  if (remaining < 1)
    return { sources, errors: ["Your advert can contain up to 30 photos."] };
  if (!web && !(await picker.requestMediaLibraryPermissionsAsync()).granted) {
    return {
      sources,
      errors: [
        "Photo access was denied. You can keep editing or allow access in your device settings and try again.",
      ],
    };
  }
  // Web must enter the picker directly inside the activating button press.
  const result = await picker.launchImageLibraryAsync({
    mediaTypes: ["images"],
    allowsMultipleSelection: true,
    selectionLimit: remaining,
    quality: 1,
  });
  if (result.canceled) return { sources, errors };
  for (const asset of result.assets) {
    const name = asset.fileName || asset.file?.name || "Selected photo";
    if (sources.length >= remaining) {
      errors.push(
        "Your advert can contain up to 30 photos. Extra files were not added.",
      );
      break;
    }
    try {
      const { body, preview } = localAsset(asset);
      const detected = (body.type || asset.mimeType || "").toLowerCase();
      const extension = (asset.fileName || asset.uri)
        .split(".")
        .at(-1)
        ?.toLowerCase();
      const mime =
        !detected || detected === "application/octet-stream"
          ? extension === "jpg" || extension === "jpeg"
            ? "image/jpeg"
            : extension === "png"
              ? "image/png"
              : extension === "webp"
                ? "image/webp"
                : ""
          : detected;
      let issue: string | undefined;
      if (!supportedMime(mime)) issue = "Choose a JPEG, PNG or WebP image.";
      else if (body.size > MAX_BYTES)
        issue = "Choose an image no larger than 10 MiB.";
      else if (!(body.size > 0)) issue = "This file could not be read.";
      else if (Math.max(asset.width, asset.height) > MAX_SIDE)
        issue = "Choose an image with neither side longer than 32,768 pixels.";
      else if (asset.width * asset.height > MAX_PIXELS)
        issue = "Choose an image no larger than 20 megapixels.";
      else sources.push({ name, mime, body, preview });
      if (issue) errors.push(`${name}: ${issue}`);
    } catch {
      errors.push(`${name}: This file could not be read.`);
    }
  }
  return { sources, errors };
}

export function objectPreview(blob: Blob): PhotoPreview {
  const uri = URL.createObjectURL(blob);
  return { uri, dispose: () => URL.revokeObjectURL(uri) };
}

export function observePreview(
  load: (signal: AbortSignal) => PhotoPreview | Promise<PhotoPreview>,
  show: (preview: PhotoPreview) => void,
  failed: () => void,
) {
  const controller = new AbortController();
  let active: PhotoPreview | undefined;
  void (async () => {
    try {
      const preview = await load(controller.signal);
      if (controller.signal.aborted) preview.dispose();
      else {
        active = preview;
        show(preview);
      }
    } catch {
      if (!controller.signal.aborted) failed();
    }
  })();
  return () => {
    controller.abort();
    active?.dispose();
    active = undefined;
  };
}

export function photoIdentity(): string {
  return (
    globalThis.crypto?.randomUUID?.() ??
    `photo-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`
  );
}
