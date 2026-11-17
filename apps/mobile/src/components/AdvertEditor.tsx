import React, { type ComponentRef, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { Text, TextInput, View } from "react-native";
import { Advert, Draft, market } from "../marketplaceApi";
import { captureSession, SessionError } from "../api";
import { c, s } from "../theme";
import { Button, Chip, Field } from "./UI";
import type { RegisterExitGuard, RequestExit } from "./MarketplaceDialog";
import PropertyMap from "./DeferredPropertyMap";
import { AdvertPreview } from "./AdvertPreview";
import { OwnedPhotoPreview, PhotoUploader, ownerMedia } from "./PhotoUploader";
import { PhotoQueue } from "./photoState";
import { MAX_PHOTOS } from "./photoSelection";
import {
  ownerNumbersFrom,
  ownerNumberRules,
  validateOwner,
  type OwnerField,
  type OwnerNumberKey,
} from "../ownerValidation";

export interface AdvertEditorProps {
  initial?: Advert;
  busy: boolean;
  onCancel: () => void;
  onSave: (draft: Draft, base?: Advert) => Promise<{ ok: boolean; saved?: Advert; error?: unknown }>;
  onFinished: (saved: Advert, keepEditing: boolean) => void;
  registerExitGuard: RegisterExitGuard;
  requestExit: RequestExit;
}

const emptyDraft: Draft = {
  title: "",
  description: "",
  city: "Kraków",
  district: "",
  region: "małopolskie",
  address: "",
  lat: 50.0647,
  lon: 19.945,
  area_m2: 50,
  rooms: 2,
  floor: null,
  rent_pln: 4000,
  fees_pln: null,
  deposit_pln: null,
  commission_pln: 0,
  property_type: "apartment",
  amenities: [],
  images: [],
};
const knownAmenities = [
  "balcony",
  "pets",
  "parking",
  "furnished",
  "lift",
  "dishwasher",
];
export function AdvertEditor({
  initial,
  busy,
  onCancel,
  onSave,
  onFinished,
  registerExitGuard,
  requestExit,
}: AdvertEditorProps) {
  const [draft, setDraft] = useState<Draft>(
    () => initial?.advert || { ...emptyDraft },
  );
  const [numbers, setNumbers] = useState(() => ownerNumbersFrom(draft));
  const [latitude, setLatitude] = useState(initial ? String(draft.lat) : "");
  const [longitude, setLongitude] = useState(initial ? String(draft.lon) : "");
  const [photoLinks, setPhotoLinks] = useState(draft.images.join("\n"));
  const [submitted, setSubmitted] = useState(false);
  const [isCurrent] = useState(captureSession);
  const [queue] = useState(() => new PhotoQueue(ownerMedia, initial?.advert.media_ids, isCurrent));
  const photos = useSyncExternalStore(queue.subscribe, queue.snapshot);
  const [photoMessage, setPhotoMessage] = useState("");
  const saving = useRef(false);
  const [finalizing, setFinalizing] = useState(false);
  useEffect(() => { queue.activate(); return () => queue.deactivate(); }, [queue]);
  const [base, setBase] = useState(initial);
  const [preview, setPreview] = useState<{ draft: Draft; base?: Advert } | null>(null);
  const [previewReady, setPreviewReady] = useState<boolean | null>(null);
  const [previewRetry, setPreviewRetry] = useState(0);
  const previewIds = JSON.stringify(preview?.draft.media_ids ?? []);
  useEffect(() => {
    if (!preview) return;
    const ids: string[] = JSON.parse(previewIds), job = new AbortController();
    if (!ids.length) { setPreviewReady(true); return () => job.abort(); }
    setPreviewReady(null);
    Promise.all(ids.map(id => ownerMedia.status(id, job.signal)))
      .then(items => { if (!job.signal.aborted) setPreviewReady(items.every(item => item.state === "ready")); })
      .catch(() => { if (!job.signal.aborted) setPreviewReady(false); });
    return () => job.abort();
  }, [preview, previewIds, previewRetry]);
  const saveController = useRef<AbortController | null>(null);
  useEffect(() => () => saveController.current?.abort(), []);
  const [conflict, setConflict] = useState<{ local: Draft; latest: Advert | null; failed: boolean; loading: boolean; confirmReload: boolean; choices: Partial<Record<keyof Draft, "local" | "latest">> } | null>(null);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const refs = useRef<
    Partial<Record<OwnerField, { focus: () => void } | null>>
  >({});
  const validation = validateOwner(
    draft,
    numbers,
    latitude,
    longitude,
    photoLinks,
  );
  const snapshot = JSON.stringify({ draft, numbers, latitude, longitude, photoLinks });
  const [baseline, setBaseline] = useState(snapshot);
  const snapshotRef = useRef(snapshot); snapshotRef.current = snapshot;
  const externalCount = photoLinks.split("\n").filter(line => line.trim()).length;
  const unresolved = photos.rows.some(row => row.phase !== "ready");
  const photoBlocked = unresolved || queue.hasUnverifiedSaved() || externalCount + photos.rows.length > MAX_PHOTOS;
  function candidate() { return validation.value ? { ...validation.value, media_ids: queue.prepareSave().ids } : undefined; }
  useEffect(() => {
    registerExitGuard({ dirty: () => snapshot !== baseline || queue.isDirty(), canSave: () => !!candidate() && !photoBlocked && !conflict && !preview && base?.state !== "published",
      save: async () => candidate() ? (await save(candidate()!)).ok : false,
      focus: () => refs.current.title?.focus(), discard: () => queue.discardNew(), isBusy: () => saving.current });
    return () => registerExitGuard(null);
  }, [registerExitGuard, snapshot, baseline, validation.value, onSave, conflict, base, preview, photos, photoBlocked]);
  const errors = validation.errors;
  const invalid = Object.keys(errors) as OwnerField[];
  const pinned = !errors.lat && !errors.lon;
  const coordinate = (value: string) => Number(value.trim().replace(",", "."));
  const change = <K extends keyof Draft>(key: K, value: Draft[K]) =>
    setDraft((current) => ({ ...current, [key]: value }));
  const fieldProps = (key: OwnerField) => ({
    inputRef: (ref: ComponentRef<typeof TextInput> | null) => {
      refs.current[key] = ref;
    },
    error: submitted ? errors[key] : undefined,
  });
  const heading = (title: string) => (
    <Text accessibilityRole="header" style={[s.title, { fontSize: 20 }]}>
      {title}
    </Text>
  );
  async function fetchLatest(local: Draft) {
    setConflict({ local, latest: null, loading: true, failed: false, confirmReload: false, choices: {} });
    try {
      const result = await market.adverts();
      if (!alive.current) return;
      const latest = result.items.find(item => item.id === base?.id) || null;
      setConflict({ local, latest, loading: false, failed: !latest, confirmReload: false, choices: {} });
    } catch {
      if (alive.current) setConflict({ local, latest: null, loading: false, failed: true, confirmReload: false, choices: {} });
    }
  }
  async function save(value: Draft, against = base) {
    if (saving.current || photoBlocked || !isCurrent()) return { ok: false };
    saving.current = true; setFinalizing(true); setPhotoMessage("");
    const job = new AbortController(); saveController.current = job;
    const started = snapshot;
    const ids = value.media_ids ?? [];
    const prepared = queue.prepareSave();
    const savePhotos = { ...prepared, ids, descriptions: prepared.descriptions.filter(item => ids.includes(item.id)) };
    try {
      try {
        const assets = await Promise.all(ids.map(id => ownerMedia.status(id, job.signal)));
        if (!alive.current || !isCurrent() || job.signal.aborted) return { ok: false };
        if (assets.some(item => item.state !== "ready")) throw new Error("Photo unavailable");
      } catch {
        if (alive.current && isCurrent() && !job.signal.aborted) setPhotoMessage("Some selected photos are unavailable. Retry or remove them before saving.");
        return { ok: false };
      }
      const result = await onSave(value, against);
      if (!alive.current || !isCurrent()) return { ok: false };
      if (!result.ok && result.error instanceof SessionError && result.error.code === "version_conflict" && against) {
        setPreview(null); await fetchLatest(value); return result;
      }
      if (result.ok && result.saved) {
        setBase(result.saved);
        const finalized = await queue.finalizeSave(savePhotos);
        if (!alive.current || !isCurrent()) return { ok: false };
        queue.retainSaved(ids);
        const removedNew = await queue.retryCleanup();
        if (!alive.current || !isCurrent()) return { ok: false };
        const changedDuringSave = snapshotRef.current !== started;
        const keepEditing = changedDuringSave || !finalized.descriptionsSaved || !finalized.removalsSaved || !removedNew;
        if (keepEditing && !changedDuringSave) {
          // A reconciled save may have chosen server fields. Show exactly what
          // was saved while retaining any retryable photo-description edits.
          const savedDraft = result.saved.advert;
          const nextNumbers = ownerNumbersFrom(savedDraft), nextLatitude = String(savedDraft.lat), nextLongitude = String(savedDraft.lon), nextLinks = savedDraft.images.join("\n");
          setDraft(savedDraft); setNumbers(nextNumbers); setLatitude(nextLatitude); setLongitude(nextLongitude); setPhotoLinks(nextLinks);
          setBaseline(JSON.stringify({ draft: savedDraft, numbers: nextNumbers, latitude: nextLatitude, longitude: nextLongitude, photoLinks: nextLinks }));
        } else setBaseline(started);
        if (keepEditing) {
          setPreview(null); setConflict(null);
          setPhotoMessage(changedDuringSave ? "Earlier changes were saved. Review and save the newer edits." : "Advert saved, but some photo details or removals need retry. Save again or retry removal.");
        }
        onFinished(result.saved, keepEditing);
        return { ...result, ok: !keepEditing };
      }
      return result;
    } finally { saving.current = false; if (saveController.current === job) saveController.current = null; if (alive.current) setFinalizing(false); }
  }
  function submit() {
    setSubmitted(true);
    const value = candidate();
    if (photoBlocked) setPhotoMessage("Finish or remove unfinished uploads and keep the total at 30 photos before saving.");
    if (value && !conflict && !photoBlocked) {
      if (base?.state === "published") { setPreviewReady(null); setPreview({ draft: value, base }); }
      else void save(value);
    }
  }
  function reloadLatest() {
    if (!conflict?.latest) return;
    const latest = conflict.latest;
    queue.applyLatest(latest.advert.media_ids ?? [], false);
    const nextNumbers = ownerNumbersFrom(latest.advert);
    const nextLatitude = String(latest.advert.lat), nextLongitude = String(latest.advert.lon);
    const nextLinks = latest.advert.images.join("\n");
    setDraft(latest.advert); setNumbers(nextNumbers);
    setLatitude(nextLatitude); setLongitude(nextLongitude); setPhotoLinks(nextLinks);
    setBaseline(JSON.stringify({ draft: latest.advert, numbers: nextNumbers, latitude: nextLatitude, longitude: nextLongitude, photoLinks: nextLinks }));
    setBase(latest); setSubmitted(false); setConflict(null);
  }
  const different = conflict?.latest ? (Object.keys(conflict.local) as (keyof Draft)[]).filter(key =>
    JSON.stringify(key === "media_ids" ? conflict.local.media_ids ?? [] : conflict.local[key]) !== JSON.stringify(key === "media_ids" ? conflict.latest!.advert.media_ids ?? [] : conflict.latest!.advert[key])) : [];
  function selectConflict(key: keyof Draft, choice: "local" | "latest") {
    setConflict(current => current ? { ...current, choices: { ...current.choices, [key]: choice } } : current);
  }
  function reconcile() {
    if (!conflict?.latest || different.some(key => !conflict.choices[key])) return;
    const merged = { ...conflict.local };
    for (const key of different) if (conflict.choices[key] === "latest")
      Object.assign(merged, { [key]: conflict.latest.advert[key] });
    if (conflict.latest.state === "published") { setPreviewReady(null); setPreview({ draft: merged, base: conflict.latest }); }
    else void save(merged, conflict.latest);
  }

  return (
    <>
      <Text style={[s.title, { fontSize: 23 }]}>
        {initial ? "Edit rental" : "A new place to call home."}
      </Text>
      {!!photoMessage && <Text accessibilityRole="alert" style={s.text}>{photoMessage}</Text>}
      {preview && <View style={{ gap: 12 }}>
        <AdvertPreview draft={preview.draft} rows={photos.rows} />
        <Text style={s.muted}>These changes will update the published advert only after you confirm.</Text>
        {previewReady === null && <Text accessibilityRole="status" style={s.muted}>Checking selected photos…</Text>}
        {previewReady === false && <><Text accessibilityRole="alert" style={s.text}>Some selected photos are unavailable. Retry or return to editing.</Text><Button outline onPress={() => setPreviewRetry(value => value + 1)}>Retry photo check</Button></>}
        <Button busy={busy || finalizing} disabled={previewReady !== true} busyLabel="Applying changes…" onPress={() => void save(preview.draft, preview.base)}>Apply published changes</Button>
        <Button outline disabled={busy || finalizing} onPress={() => setPreview(null)}>Back to editing</Button>
      </View>}
      {conflict && !preview && <View style={[s.card, { padding: 16, gap: 12 }]}>
        <Text accessibilityRole="alert" style={s.text}>This advert changed on another device. Your edits are still here.</Text>
        {conflict.loading && <Text accessibilityRole="status" style={s.muted}>Loading the latest version…</Text>}
        {conflict.failed && <><Text style={s.text}>The latest advert is unavailable. It may have been removed or could not be loaded.</Text><Button outline onPress={() => fetchLatest(conflict.local)}>Retry latest version</Button></>}
        <Button outline disabled={busy || conflict.loading} onPress={() => setConflict(null)}>Return to editing</Button>
        {conflict.latest && <>
          <Text style={s.muted}>Latest status: {conflict.latest.state}{conflict.latest.hidden ? " · hidden after review" : ""}. Server changes will not be overwritten until you explicitly save.</Text>
          {different.map(key => <View key={key} style={{ gap: 6 }}>
            <Text style={s.label}>{key === "media_ids" ? "UPLOADED PHOTOS" : key.replace(/_/g, " ").toUpperCase()}</Text>
            <Text style={s.muted}>Yours: {key === "media_ids" ? `${(conflict.local.media_ids ?? []).length} uploaded photos` : String(JSON.stringify(conflict.local[key]))}</Text>
            <Text style={s.muted}>Latest: {key === "media_ids" ? `${(conflict.latest!.advert.media_ids ?? []).length} uploaded photos` : String(JSON.stringify(conflict.latest!.advert[key]))}</Text>
            {key === "media_ids" && <View style={{ gap: 8 }}>
              <Text style={s.text}>Your uploaded photos, in order</Text>
              {(conflict.local.media_ids ?? []).map((id, index) => <OwnedPhotoPreview key={`local-${id}`} id={id} index={index} row={photos.rows.find(item => item.id === id && item.phase === "ready")} />)}
              <Text style={s.text}>Latest uploaded photos, in order</Text>
              {(conflict.latest!.advert.media_ids ?? []).map((id, index) => <OwnedPhotoPreview key={`latest-${id}`} id={id} index={index} />)}
            </View>}
            <View style={[s.row, { gap: 8, flexWrap: "wrap" }]}>
              <Chip label={`Use mine for ${key}`} selected={conflict.choices[key] === "local"} onPress={() => selectConflict(key, "local")} />
              <Chip label={`Use latest for ${key}`} selected={conflict.choices[key] === "latest"} onPress={() => selectConflict(key, "latest")} />
            </View>
          </View>)}
          <Button disabled={busy || different.some(key => !conflict.choices[key])} onPress={reconcile}>Save selected values</Button>
          {!conflict.confirmReload ? <Button outline disabled={busy} onPress={() => setConflict({ ...conflict, confirmReload: true })}>Reload latest version</Button> :
            <View style={{ gap: 8 }}><Text style={s.text}>Discard your edits and load the latest version?</Text><Button outline onPress={reloadLatest}>Discard edits and reload</Button><Button outline onPress={() => setConflict({ ...conflict, confirmReload: false })}>Keep my edits</Button></View>}
        </>}
      </View>}
      <View style={{ display: conflict || preview ? "none" : "flex", gap: 16 }}>
      {submitted && invalid.length > 0 && (
        <View
          style={[s.card, { padding: 14, gap: 8, alignItems: "flex-start" }]}
        >
          <Text accessibilityRole="alert" style={s.text}>
            Check {invalid.length} {invalid.length === 1 ? "field" : "fields"}{" "}
            before saving.
          </Text>
          <Button outline onPress={() => refs.current[invalid[0]]?.focus()}>
            Go to first invalid field
          </Button>
        </View>
      )}
      {heading("Basics")}
      <Field
        label="TITLE"
        value={draft.title}
        onChange={(value) => change("title", value)}
        {...fieldProps("title")}
        helperText="5–240 characters"
      />
      <Field
        label="DESCRIPTION"
        multiline
        value={draft.description}
        onChange={(value) => change("description", value)}
        {...fieldProps("description")}
        helperText="20–20,000 characters"
      />
      <View style={[s.row, { gap: 8, flexWrap: "wrap" }]}>
        {(["apartment", "house", "room"] as const).map((type) => (
          <Chip
            key={type}
            label={type}
            selected={draft.property_type === type}
            onPress={() => change("property_type", type)}
          />
        ))}
      </View>
      {(["area_m2", "rooms", "floor"] as OwnerNumberKey[]).map((key) => (
        <Field
          key={key}
          label={ownerNumberRules[key].label}
          numeric
          value={numbers[key]}
          onChange={(value) =>
            setNumbers((current) => ({ ...current, [key]: value }))
          }
          {...fieldProps(key)}
        />
      ))}
      <View
        ref={(ref) => {
          refs.current.amenities = ref;
        }}
        focusable
        tabIndex={-1}
        style={{ gap: 8 }}
      >
        <Text style={s.label}>AMENITIES</Text>
        <View style={[s.row, { gap: 8, flexWrap: "wrap" }]}>
          {knownAmenities.map((amenity) => (
            <Chip
              key={amenity}
              label={amenity === "pets" ? "Pets welcome" : amenity}
              selected={draft.amenities.includes(amenity)}
              onPress={() =>
                change(
                  "amenities",
                  draft.amenities.includes(amenity)
                    ? draft.amenities.filter((value) => value !== amenity)
                    : [...draft.amenities, amenity],
                )
              }
            />
          ))}
        </View>
        {draft.amenities
          .filter((value) => !knownAmenities.includes(value))
          .map((value, index) => (
            <Text key={`${value}-${index}`} style={s.muted}>
              Other saved amenity: {value}
            </Text>
          ))}
        {submitted && errors.amenities && (
          <Text accessibilityRole="alert" style={s.text}>
            {errors.amenities}
          </Text>
        )}
      </View>
      {heading("Location")}
      {(
        [
          ["CITY", "city"],
          ["DISTRICT", "district"],
          ["REGION", "region"],
          ["STREET AND BUILDING", "address"],
        ] as const
      ).map(([label, key]) => (
        <Field
          key={key}
          label={label}
          value={draft[key]}
          onChange={(value) => change(key, value)}
          {...fieldProps(key)}
        />
      ))}
      <Text style={s.muted}>
        Enter coordinates or pin the home on the map. Rentals must be in Poland.
      </Text>
      <Field
        label="Location latitude"
        value={latitude}
        onChange={setLatitude}
        numeric
        {...fieldProps("lat")}
        error={submitted || latitude.trim() ? errors.lat : undefined}
      />
      <Field
        label="Location longitude"
        value={longitude}
        onChange={setLongitude}
        numeric
        {...fieldProps("lon")}
        error={submitted || longitude.trim() ? errors.lon : undefined}
      />
      <Text aria-live="polite" style={s.muted}>
        {pinned ? "Location set" : "Location required to save the advert"}
      </Text>
      <View style={{ height: 340 }}>
        <PropertyMap
          homes={[]}
          selected={null}
          onSelect={() => {}}
          city={draft.city}
          onPolygonChange={() => {}}
          pin={
            pinned ? [coordinate(longitude), coordinate(latitude)] : undefined
          }
          onPinChange={([lon, lat]) => {
            setLongitude(String(lon));
            setLatitude(String(lat));
          }}
        />
      </View>
      {heading("Costs")}
      <Text style={s.muted}>
        Base rent is required. Leave optional costs blank if unknown; zero means
        no charge. Enter whole PLN amounts.
      </Text>
      {(
        [
          "rent_pln",
          "fees_pln",
          "deposit_pln",
          "commission_pln",
        ] as OwnerNumberKey[]
      ).map((key) => (
        <Field
          key={key}
          label={ownerNumberRules[key].label}
          numeric
          value={numbers[key]}
          onChange={(value) =>
            setNumbers((current) => ({ ...current, [key]: value }))
          }
          {...fieldProps(key)}
        />
      ))}
      {heading("Photos")}
      <PhotoUploader queue={queue} photos={photos} externalCount={externalCount} disabled={busy || finalizing} />
      {photoBlocked && <Text accessibilityRole="status" style={s.muted}>Finish or remove unfinished uploads before saving or publishing.</Text>}
      <Field
        label="PHOTO LINKS (HTTPS; ONE PER LINE)"
        multiline
        value={photoLinks}
        onChange={setPhotoLinks}
        {...fieldProps("images")}
      />
      <Text style={s.muted}>
        Use up to 30 photos you own or have permission to publish.
      </Text>
      <Button busy={busy || finalizing} disabled={!!conflict || photoBlocked} busyLabel="Saving…" onPress={submit}>
        {base?.state === "published"
          ? "Review published changes"
          : "Save draft"}
      </Button>
      </View>
      {!preview && <Button outline disabled={busy || finalizing} onPress={() => requestExit(onCancel)}>
        Back to adverts
      </Button>}
    </>
  );
}
