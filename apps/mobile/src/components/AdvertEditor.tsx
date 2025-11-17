import React, { type ComponentRef, useEffect, useRef, useState } from "react";
import { Text, TextInput, View } from "react-native";
import { Advert, Draft } from "../marketplaceApi";
import { c, s } from "../theme";
import { Button, Chip, Field } from "./UI";
import type { RegisterExitGuard, RequestExit } from "./MarketplaceDialog";
import PropertyMap from "./DeferredPropertyMap";
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
  onSave: (draft: Draft) => Promise<boolean>;
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
  const [baseline] = useState(snapshot);
  useEffect(() => {
    registerExitGuard({ dirty: () => snapshot !== baseline, canSave: () => !!validation.value,
      save: () => validation.value ? onSave(validation.value) : Promise.resolve(false),
      focus: () => refs.current.title?.focus() });
    return () => registerExitGuard(null);
  }, [registerExitGuard, snapshot, baseline, validation.value, onSave]);
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
  function submit() {
    setSubmitted(true);
    if (validation.value) void onSave(validation.value);
  }
  return (
    <>
      <Text style={[s.title, { fontSize: 23 }]}>
        {initial ? "Edit rental" : "A new place to call home."}
      </Text>
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
      <Button busy={busy} busyLabel="Saving…" onPress={submit}>
        {initial?.state === "published"
          ? "Save and update advert"
          : "Save draft"}
      </Button>
      <Button outline disabled={busy} onPress={() => requestExit(onCancel)}>
        Back to adverts
      </Button>
    </>
  );
}
