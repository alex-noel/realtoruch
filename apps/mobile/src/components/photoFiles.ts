import * as ImagePicker from "expo-image-picker";
import { File, Paths } from "expo-file-system";
import { fetch as expoFetch } from "expo/fetch";
import {
  choosePhotos,
  photoIdentity,
  type PhotoPreview,
} from "./photoSelection";

export const photoFetch = expoFetch;
export const pickPhotos = (remaining: number, signal: AbortSignal) =>
  choosePhotos(
    false,
    {
      requestMediaLibraryPermissionsAsync:
        ImagePicker.requestMediaLibraryPermissionsAsync,
      launchImageLibraryAsync: (options) =>
        signal.aborted
          ? Promise.resolve({ canceled: true, assets: null })
          : ImagePicker.launchImageLibraryAsync({
              ...options,
              preferredAssetRepresentationMode:
                ImagePicker.UIImagePickerPreferredAssetRepresentationMode
                  .Current,
            }),
    },
    (asset) => {
      const body = new File(asset.uri);
      return { body, preview: () => ({ uri: body.uri, dispose() {} }) };
    },
    remaining,
  );

export async function storedPhotoPreview(blob: Blob): Promise<PhotoPreview> {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  const preview = new File(Paths.cache, `owner-preview-${photoIdentity()}.jpg`);
  const dispose = () => {
    try {
      if (preview.exists) preview.delete();
    } catch {
      /* The OS may already have cleaned its cache. */
    }
  };
  try {
    preview.create();
    preview.write(bytes);
    return { uri: preview.uri, dispose };
  } catch (error) {
    dispose();
    throw error;
  }
}
