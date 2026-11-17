import type { ImagePickerResult } from "expo-image-picker";
import { choosePhotos, objectPreview } from "./photoSelection";

export const photoFetch = (url: string, init: RequestInit) => fetch(url, init);
export const storedPhotoPreview = objectPreview;

// The Expo web adapter decodes every file before returning, including rejected
// excess files, and does not release the object URLs it creates. Own the input
// and let the server verify decoded dimensions and still-image content.
function launchWebPicker(signal: AbortSignal): Promise<ImagePickerResult> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      resolve({ canceled: true, assets: null });
      return;
    }
    const input = document.createElement("input");
    input.type = "file";
    input.multiple = true;
    input.accept = ".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp";
    input.hidden = true;
    function cleanup() {
      input.removeEventListener("change", change);
      input.removeEventListener("cancel", cancel);
      signal.removeEventListener("abort", cancel);
      input.remove();
    }
    function cancel() {
      cleanup();
      resolve({ canceled: true, assets: null });
    }
    function change() {
      const assets = Array.from(input.files ?? [], (file) => ({
        file,
        fileName: file.name,
        width: 0,
        height: 0,
        uri: "",
        mimeType: file.type,
      }));
      cleanup();
      resolve(
        assets.length
          ? { canceled: false, assets }
          : { canceled: true, assets: null },
      );
    }
    input.addEventListener("change", change);
    input.addEventListener("cancel", cancel);
    signal.addEventListener("abort", cancel, { once: true });
    document.body.append(input);
    try {
      input.click();
    } catch (error) {
      cleanup();
      reject(error);
    }
  });
}

export const pickPhotos = (remaining: number, signal: AbortSignal) =>
  choosePhotos(
    true,
    {
      launchImageLibraryAsync: () => launchWebPicker(signal),
      requestMediaLibraryPermissionsAsync: () =>
        Promise.resolve({ granted: true }),
    },
    (asset) => {
      if (!asset.file) throw new Error("The selected file is unavailable.");
      const body = asset.file;
      return { body, preview: () => objectPreview(body) };
    },
    remaining,
  );
