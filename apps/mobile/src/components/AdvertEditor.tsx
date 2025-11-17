import React, { useId, useState } from "react";
import { Text, View } from "react-native";
import { Advert, Draft } from "../marketplaceApi";
import { c, s } from "../theme";
import { Button, Chip, Field } from "./UI";
import PropertyMap from "./DeferredPropertyMap";
import { readCoordinate } from "./coordinates";

// Reserved for the unified parent-close/dirty-state contract; currently unused.
export type AdvertEditorExitGuardRegistration = (guard: (() => boolean) | null) => void;
export interface AdvertEditorProps {
  initial?: Advert;
  busy: boolean;
  onCancel: () => void;
  onSave: (draft: Draft) => void;
  registerExitGuard?: AdvertEditorExitGuardRegistration;
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
export function AdvertEditor({
  initial,
  busy,
  onCancel,
  onSave,
}: AdvertEditorProps) {
  const [draft, setDraft] = useState<Draft>(
    () => initial?.advert || { ...emptyDraft },
  );
  const [latitude, setLatitude] = useState(initial ? String(draft.lat) : "");
  const [longitude, setLongitude] = useState(initial ? String(draft.lon) : "");
  const lat = readCoordinate(latitude, 90);
  const lon = readCoordinate(longitude, 180);
  const pinned = lat !== null && lon !== null;
  const invalidLat = !!latitude.trim() && lat === null;
  const invalidLon = !!longitude.trim() && lon === null;
  const locationErrorId = useId();
  const change = <K extends keyof Draft>(key: K, value: Draft[K]) =>
    setDraft((d) => ({ ...d, [key]: value }));
  return (
    <>
      <Text style={[s.title, { fontSize: 23 }]}>
        {initial ? "Edit rental" : "A new place to call home."}
      </Text>
      <Field
        label="TITLE"
        value={draft.title}
        onChange={(v) => change("title", v)}
      />
      <Field
        label="DESCRIPTION"
        multiline
        value={draft.description}
        onChange={(v) => change("description", v)}
      />
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
          onChange={(v) => change(key, v)}
        />
      ))}
      <Text style={s.label}>ENTER COORDINATES OR PIN THE HOME ON THE MAP</Text>
      <Field
        label="Location latitude"
        value={latitude}
        onChange={setLatitude}
        numeric
        errorId={invalidLat ? locationErrorId : undefined}
      />
      <Field
        label="Location longitude"
        value={longitude}
        onChange={setLongitude}
        numeric
        errorId={invalidLon ? locationErrorId : undefined}
      />
      {(invalidLat || invalidLon) && (
        <Text
          nativeID={locationErrorId}
          accessibilityRole="alert"
          style={{ color: c.warning }}
        >
          Enter a latitude from −90 to 90 and a longitude from −180 to 180.
        </Text>
      )}
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
          pin={pinned ? [lon, lat] : undefined}
          onPinChange={([lon, lat]) => {
            setLongitude(String(lon));
            setLatitude(String(lat));
          }}
        />
      </View>
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
      {(
        [
          ["MONTHLY BASE RENT (PLN)", "rent_pln"],
          ["FEES (PLN; LEAVE BLANK IF UNKNOWN)", "fees_pln"],
          ["DEPOSIT (PLN)", "deposit_pln"],
          ["COMMISSION (PLN; 0 IF NONE)", "commission_pln"],
          ["AREA (M²)", "area_m2"],
          ["ROOMS", "rooms"],
          ["FLOOR", "floor"],
        ] as const
      ).map(([label, key]) => (
        <Field
          key={key}
          label={label}
          numeric
          value={draft[key] === null ? "" : String(draft[key])}
          onChange={(v) =>
            change(
              key,
              (v.trim() ? Number(v.replace(",", ".")) : null) as never,
            )
          }
        />
      ))}
      <Field
        label="AMENITIES (COMMA SEPARATED)"
        value={draft.amenities.join(", ")}
        onChange={(v) =>
          change(
            "amenities",
            v.split(",").map((a) => a.trim()),
          )
        }
      />
      <Field
        label="PHOTO LINKS (HTTPS; ONE PER LINE)"
        multiline
        value={draft.images.join("\n")}
        onChange={(v) => change("images", v.split("\n"))}
      />
      <Text style={s.muted}>
        Use photos you own or have permission to publish. Empty fees mean
        unknown; zero means no charge.
      </Text>
      <Button
        disabled={
          busy ||
          !pinned ||
          draft.title.trim().length < 5 ||
          draft.description.trim().length < 20 ||
          !draft.rent_pln ||
          !draft.area_m2 ||
          !draft.rooms
        }
        onPress={() =>
          pinned &&
          onSave({
            ...draft,
            lat,
            lon,
            images: draft.images.map((v) => v.trim()).filter(Boolean),
            amenities: draft.amenities.filter(Boolean),
          })
        }
      >
        {busy
          ? "Saving…"
          : initial?.state === "published"
            ? "Save and update advert"
            : "Save draft"}
      </Button>
      <Button outline disabled={busy} onPress={onCancel}>
        Back to adverts
      </Button>
    </>
  );
}
