import React, { useEffect, useRef, useState } from "react";
import { Image, Platform, Text, TextInput, View } from "react-native";
import { makeOwnerMedia } from "../marketplaceApi";
import { c, s } from "../theme";
import { Button } from "./UI";
import { photoFetch, pickPhotos, storedPhotoPreview } from "./photoFiles";
import {
  MAX_PHOTOS,
  observePreview,
  type PhotoPreview,
} from "./photoSelection";
import type { PhotoQueue, PhotoRow } from "./photoState";

export const ownerMedia = makeOwnerMedia(photoFetch);

type PreviewProps = {
  row: PhotoRow;
  label: string;
  expanded: boolean;
};
function PhotoPreviewImage({ row, label, expanded }: PreviewProps) {
  const [preview, setPreview] = useState<PhotoPreview>();
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const source = row.upload?.source;
  const readyId = row.phase === "ready" ? row.id : undefined;
  const rendition = expanded ? "display" : "thumbnail";
  useEffect(
    () =>
      observePreview(
        async (signal) => {
          if (readyId) {
            const bytes = await ownerMedia.preview(readyId, rendition, signal);
            return storedPhotoPreview(bytes);
          }
          if (source) return source.preview();
          throw new Error("No preview is available.");
        },
        setPreview,
        () => setFailed(true),
      ),
    [readyId, source, rendition, attempt],
  );

  if (failed) {
    return (
      <View style={{ alignItems: "flex-start", gap: 6 }}>
        <Text style={s.muted}>Preview unavailable.</Text>
        <Button
          outline
          label={`Retry preview for ${label}`}
          onPress={() => {
            setFailed(false);
            setPreview(undefined);
            setAttempt((value) => value + 1);
          }}
        >
          Retry preview
        </Button>
      </View>
    );
  }
  if (!preview) return <Text style={s.muted}>Loading preview…</Text>;
  return (
    <Image
      source={{ uri: preview.uri }}
      accessibilityRole="image"
      accessibilityLabel={row.description.trim() || `Rental photo: ${label}`}
      resizeMode={expanded ? "contain" : "cover"}
      resizeMethod="resize"
      onError={() => setFailed(true)}
      style={[
        { backgroundColor: c.pale, maxWidth: "100%" },
        expanded ? { width: "100%", height: 260 } : { width: 112, height: 80 },
      ]}
    />
  );
}

const phases = {
  queued: "Queued",
  uploading: "Uploading…",
  checking: "Checking saved photo…",
  ready: "Ready",
  failed: "Failed",
};
function PhotoControls({
  row,
  index,
  total,
  expanded,
  onExpand,
  queue,
  disabled,
}: {
  row: PhotoRow;
  index: number;
  total: number;
  expanded: boolean;
  onExpand: () => void;
  queue: PhotoQueue;
  disabled: boolean;
}) {
  const label = `photo ${index + 1}${row.name ? `, ${row.name}` : ""}`;
  const pending = row.phase === "queued" || row.phase === "uploading";
  return (
    <View style={[s.card, { padding: 12, gap: 8, minWidth: 0 }]}>
      <Text
        style={s.text}
        numberOfLines={2}
      >{`Photo ${index + 1}${row.name ? ` · ${row.name}` : ""}`}</Text>
      <Text aria-live="polite" style={s.muted}>
        {phases[row.phase]}
      </Text>
      {!!row.error && (
        <Text accessibilityRole="alert" style={{ color: c.warning }}>
          {row.error}
        </Text>
      )}
      {(row.upload?.source || row.phase === "ready") && (
        <PhotoPreviewImage
          key={`${row.phase === "ready" ? "stored" : "local"}:${expanded ? "large" : "small"}`}
          row={row}
          label={label}
          expanded={expanded}
        />
      )}
      {row.phase === "ready" && (
        <Button
          outline
          disabled={disabled}
          expanded={expanded}
          label={`${expanded ? "Hide" : "View"} larger preview for ${label}`}
          onPress={onExpand}
        >
          {expanded ? "Hide larger preview" : "View larger preview"}
        </Button>
      )}
      <TextInput
        value={row.description}
        accessibilityLabel={`Description for ${label}`}
        placeholder="Describe what the photo shows"
        placeholderTextColor={c.muted}
        onChangeText={(value) => queue.describe(row.key, value)}
        editable={!disabled && (row.phase === "ready" || !!row.upload)}
        maxLength={500}
        style={[s.input, { minWidth: 0 }]}
      />
      <View style={[s.row, { gap: 8, flexWrap: "wrap" }]}>
        <Button
          outline
          disabled={disabled || index === 0}
          label={`Move ${label} earlier`}
          onPress={() => queue.move(row.key, -1)}
        >
          Move earlier
        </Button>
        <Button
          outline
          disabled={disabled || index === total - 1}
          label={`Move ${label} later`}
          onPress={() => queue.move(row.key, 1)}
        >
          Move later
        </Button>
        {row.phase === "failed" && row.retryable && (
          <Button
            outline
            disabled={disabled}
            label={`Retry ${label}`}
            onPress={() => queue.retry(row.key)}
          >
            Retry
          </Button>
        )}
        <Button
          outline
          disabled={disabled}
          label={`${pending ? "Cancel upload for" : "Remove"} ${label}`}
          onPress={() => queue.remove(row.key)}
        >
          {pending ? "Cancel upload" : "Remove"}
        </Button>
      </View>
    </View>
  );
}

export function PhotoUploader({
  queue,
  photos,
  externalCount,
  disabled,
}: {
  queue: PhotoQueue;
  photos: ReturnType<PhotoQueue["snapshot"]>;
  externalCount: number;
  disabled: boolean;
}) {
  const picker = useRef<AbortController>(null);
  const [choosing, setChoosing] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  useEffect(() => () => picker.current?.abort(), []);
  const count = externalCount + photos.rows.length;
  async function choose() {
    picker.current?.abort();
    const controller = new AbortController();
    picker.current = controller;
    setErrors([]);
    setChoosing(true);
    try {
      const result = await pickPhotos(MAX_PHOTOS - count, controller.signal);
      if (controller.signal.aborted) return;
      const skipped = queue.add(result.sources, externalCount);
      setErrors(
        skipped
          ? [
              ...result.errors,
              "Your advert can contain up to 30 photos. Extra files were not added.",
            ]
          : result.errors,
      );
    } catch {
      if (!controller.signal.aborted)
        setErrors([
          "Could not open the photo picker. You can keep editing and try again.",
        ]);
    } finally {
      if (!controller.signal.aborted) {
        picker.current = null;
        setChoosing(false);
      }
    }
  }
  return (
    <View style={{ gap: 10 }}>
      <Text style={s.label}>UPLOADED PHOTOS</Text>
      <Text style={s.muted}>
        JPEG, PNG or WebP · Up to 10 MiB and 20 megapixels each. Linked photos
        appear first.
      </Text>
      <Text aria-live="polite" style={s.muted}>
        {count} of {MAX_PHOTOS} photos, including links
      </Text>
      {count > MAX_PHOTOS && (
        <Text accessibilityRole="alert" style={{ color: c.warning }}>
          Remove photos or links to keep no more than 30.
        </Text>
      )}
      <Button
        outline
        disabled={
          disabled || count >= MAX_PHOTOS || (Platform.OS !== "web" && choosing)
        }
        onPress={() => void choose()}
      >
        {Platform.OS !== "web" && choosing
          ? "Opening photo library…"
          : "Choose photos"}
      </Button>
      {errors.map((text, i) => (
        <Text key={i} accessibilityRole="alert" style={{ color: c.warning }}>
          {text}
        </Text>
      ))}
      {photos.rows.map((row, index) => (
        <PhotoControls
          key={row.key}
          row={row}
          index={index}
          total={photos.rows.length}
          expanded={expanded === row.key}
          onExpand={() => setExpanded(expanded === row.key ? null : row.key)}
          queue={queue}
          disabled={disabled}
        />
      ))}
      {photos.cleanupFailed && (
        <>
          <Text accessibilityRole="alert" style={{ color: c.warning }}>
            Removal could not be confirmed. Try again.
          </Text>
          <Button
            outline
            disabled={disabled}
            onPress={() => void queue.retryCleanup()}
          >
            Retry photo removal
          </Button>
        </>
      )}
    </View>
  );
}
