import React, { type ComponentRef, useLayoutEffect, useRef, useState } from "react";
import {
  type KeyDownEvent,
  Linking,
  Platform,
  Pressable,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import ArrowUpRight from "lucide-react-native/icons/arrow-up-right";
import Check from "lucide-react-native/icons/check";
import Flag from "lucide-react-native/icons/flag";
import ShieldAlert from "lucide-react-native/icons/shield-alert";
import { api } from "../api";
import { Filters, Listing } from "../types";
import { c, s } from "../theme";
import { ListingPhoto } from "./ListingCard";
import { Button, Chip, Field, Panel, money } from "./UI";
import { parseFilterNumber } from "../filterNumbers";

const numericFilterKeys = [
  "min_price",
  "max_price",
  "min_area",
  "max_area",
] as const;
type NumericFilterKey = (typeof numericFilterKeys)[number];
type NumericDraft = Record<NumericFilterKey, string>;
type NumericErrors = Partial<
  Record<NumericFilterKey, { message: string; reason: "input" | "range" }>
>;
const numericDraftFrom = (filters: Filters): NumericDraft => ({
  min_price: filters.min_price == null ? "" : String(filters.min_price),
  max_price: filters.max_price == null ? "" : String(filters.max_price),
  min_area: filters.min_area == null ? "" : String(filters.min_area),
  max_area: filters.max_area == null ? "" : String(filters.max_area),
});

export function AuthDialog({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: (token: string, email: string) => Promise<void>;
}) {
  const [register, setRegister] = useState(false);
  const [forgot, setForgot] = useState(false);
  const [message, setMessage] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit() {
    setBusy(true);
    setError("");
    try {
      if (forgot) {
        setMessage((await api.resetRequest(email.trim())).message);
        return;
      }
      const result = await api.signIn(email.trim(), password, register);
      await onSuccess(result.access_token, result.user.email);
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Panel
      title={
        forgot
          ? "Reset your password."
          : register
            ? "Make room for your shortlist."
            : "Welcome back."
      }
      onClose={onClose}
    >
      <Text style={s.muted}>
        Keep your favorite homes and searches together across devices.
      </Text>
      <Field
        label="EMAIL"
        value={email}
        onChange={setEmail}
        placeholder="you@example.com"
      />
      {!forgot && (
        <Field
          label="PASSWORD"
          value={password}
          onChange={setPassword}
          secure
          placeholder="At least 12 characters"
        />
      )}
      {!!message && (
        <Text accessibilityRole="alert" style={s.text}>
          {message}
        </Text>
      )}
      {!!error && (
        <Text accessibilityRole="alert" style={{ color: "#A3422D" }}>
          {error}
        </Text>
      )}
      <Button
        disabled={busy || !email || (!forgot && password.length < 12)}
        onPress={submit}
      >
        {busy
          ? "Please wait…"
          : forgot
            ? "Email reset link"
            : register
              ? "Create account"
              : "Sign in"}
      </Button>
      <Pressable
        accessibilityRole="button"
        onPress={() => {
          setRegister(forgot ? false : !register);
          setForgot(false);
          setMessage("");
          setError("");
        }}
      >
        <Text
          style={[
            s.text,
            { textAlign: "center", textDecorationLine: "underline" },
          ]}
        >
          {register || forgot
            ? "Already have an account? Sign in"
            : "New here? Create a free account"}
        </Text>
      </Pressable>
      {!forgot && !register && (
        <Button
          outline
          onPress={() => {
            setForgot(true);
            setError("");
          }}
        >
          Forgot password?
        </Button>
      )}
      <Text style={[s.muted, { fontSize: 11 }]}>
        Sessions stay signed in for up to 30 days. Manage your devices in
        Account.
      </Text>
    </Panel>
  );
}

export function FilterDialog({
  initial,
  districts,
  onApply,
  onClose,
}: {
  initial: Filters;
  districts: string[];
  onApply: (value: Filters) => void;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState(initial);
  const [numericDraft, setNumericDraft] = useState(() =>
    numericDraftFrom(initial),
  );
  const [fieldErrors, setFieldErrors] = useState<NumericErrors>({});
  const edit = (key: keyof Filters, value: unknown) =>
    setDraft((current) => ({ ...current, [key]: value }));
  function editNumeric(key: NumericFilterKey, value: string) {
    setNumericDraft((current) => ({ ...current, [key]: value }));
    setFieldErrors((current) => {
      const next = { ...current };
      delete next[key];
      const peer: Record<NumericFilterKey, NumericFilterKey> = {
        min_price: "max_price",
        max_price: "min_price",
        min_area: "max_area",
        max_area: "min_area",
      };
      if (next[peer[key]]?.reason === "range") delete next[peer[key]];
      return next;
    });
  }
  function apply() {
    const minPrice = parseFilterNumber(numericDraft.min_price, true);
    const maxPrice = parseFilterNumber(numericDraft.max_price, true);
    const minArea = parseFilterNumber(numericDraft.min_area);
    const maxArea = parseFilterNumber(numericDraft.max_area);
    const errors: NumericErrors = {};
    const invalidMessage = (
      result: ReturnType<typeof parseFilterNumber>,
      rent: boolean,
    ) =>
      result.valid
        ? undefined
        : result.reason === "integer"
          ? "Enter rent as a whole number of PLN."
          : rent
            ? "Enter a non-negative whole number of PLN."
            : "Enter a non-negative area; use a comma or dot for decimals.";
    const results: Record<
      NumericFilterKey,
      ReturnType<typeof parseFilterNumber>
    > = {
      min_price: minPrice,
      max_price: maxPrice,
      min_area: minArea,
      max_area: maxArea,
    };
    for (const key of numericFilterKeys) {
      const message = invalidMessage(results[key], key.endsWith("price"));
      if (message) errors[key] = { message, reason: "input" };
    }
    if (
      minPrice.valid &&
      maxPrice.valid &&
      minPrice.value !== undefined &&
      maxPrice.value !== undefined &&
      minPrice.value >= maxPrice.value
    ) {
      errors.min_price = {
        message: "Minimum rent must be below the exclusive rent maximum.",
        reason: "range",
      };
      errors.max_price = {
        message: "Rent maximum must be above minimum rent.",
        reason: "range",
      };
    }
    if (
      minArea.valid &&
      maxArea.valid &&
      minArea.value !== undefined &&
      maxArea.value !== undefined &&
      minArea.value > maxArea.value
    ) {
      errors.min_area = {
        message: "Minimum area cannot exceed maximum area.",
        reason: "range",
      };
      errors.max_area = {
        message: "Maximum area must be at least the minimum area.",
        reason: "range",
      };
    }
    if (Object.keys(errors).length) {
      setFieldErrors(errors);
      return;
    }
    if (!minPrice.valid || !maxPrice.valid || !minArea.valid || !maxArea.valid)
      return;
    onApply({
      ...draft,
      min_price: minPrice.value,
      max_price: maxPrice.value,
      min_area: minArea.value,
      max_area: maxArea.value,
      max_price_exclusive: true,
    });
    onClose();
  }
  return (
    <Panel title="A home that fits." onClose={onClose}>
      <View style={{ gap: 10 }}>
        <Text style={s.label}>NEIGHBORHOOD</Text>
        <View style={[s.row, { flexWrap: "wrap", gap: 8 }]}>
          {["", ...districts].map((district) => (
            <Chip
              key={district}
              label={district || "All neighborhoods"}
              selected={draft.district === district}
              onPress={() => edit("district", district)}
            />
          ))}
        </View>
      </View>
      <View style={[s.row, { gap: 16 }]}>
        <Field
          label="MIN RENT · PLN"
          value={numericDraft.min_price}
          onChange={(v) => editNumeric("min_price", v)}
          numeric
          placeholder="Any"
          error={fieldErrors.min_price?.message}
        />
        <Field
          label="RENT BELOW · PLN"
          value={numericDraft.max_price}
          onChange={(v) => editNumeric("max_price", v)}
          numeric
          placeholder="Any"
          error={fieldErrors.max_price?.message}
        />
      </View>
      <Text style={[s.muted, { fontSize: 11 }]}>
        Rent filters use base rent, excluding building fees and utilities.
      </Text>
      <View style={[s.row, { gap: 16 }]}>
        <Field
          label="MIN AREA · M²"
          value={numericDraft.min_area}
          onChange={(v) => editNumeric("min_area", v)}
          numeric
          placeholder="Any"
          error={fieldErrors.min_area?.message}
        />
        <Field
          label="MAX AREA · M²"
          value={numericDraft.max_area}
          onChange={(v) => editNumeric("max_area", v)}
          numeric
          placeholder="Any"
          error={fieldErrors.max_area?.message}
        />
      </View>
      <View style={{ gap: 10 }}>
        <Text style={s.label}>ROOMS</Text>
        <View style={[s.row, { flexWrap: "wrap", gap: 8 }]}>
          {[undefined, 1, 2, 3, 4, 5].map((value) => (
            <Chip
              key={value ?? "any"}
              label={value ? `${value} rooms` : "Any"}
              selected={draft.rooms === value}
              onPress={() => edit("rooms", value)}
            />
          ))}
        </View>
      </View>
      <View style={{ gap: 10 }}>
        <Text style={s.label}>PROPERTY TYPE</Text>
        <View style={[s.row, { gap: 8, flexWrap: "wrap" }]}>
          {["all", "apartment", "house", "room"].map((value) => (
            <Chip
              key={value}
              label={
                value === "all"
                  ? "All types"
                  : value[0].toUpperCase() + value.slice(1)
              }
              selected={draft.property_type === value}
              onPress={() => edit("property_type", value)}
            />
          ))}
        </View>
      </View>
      <View style={{ gap: 10 }}>
        <Text style={s.label}>ADVERTISER</Text>
        <View style={[s.row, { gap: 8, flexWrap: "wrap" }]}>
          {["all", "private", "agency"].map((value) => (
            <Chip
              key={value}
              label={
                value === "all"
                  ? "Everyone"
                  : value === "private"
                    ? "Direct offers"
                    : "Agencies"
              }
              selected={draft.advertiser === value}
              onPress={() => edit("advertiser", value)}
            />
          ))}
        </View>
      </View>
      <View style={{ gap: 10 }}>
        <Text style={s.label}>NICE TO HAVE</Text>
        <View style={[s.row, { gap: 8, flexWrap: "wrap" }]}>
          {[
            "balcony",
            "pets",
            "parking",
            "furnished",
            "lift",
            "dishwasher",
          ].map((value) => (
            <Chip
              key={value}
              label={
                value === "pets"
                  ? "Pets welcome"
                  : value[0].toUpperCase() + value.slice(1)
              }
              selected={draft.amenity === value}
              onPress={() =>
                edit("amenity", draft.amenity === value ? "" : value)
              }
            />
          ))}
        </View>
      </View>
      <View style={{ gap: 10 }}>
        <Chip
          label="Only explicitly zero commission"
          selected={draft.no_commission}
          onPress={() => edit("no_commission", !draft.no_commission)}
        />
        <Chip
          label="Hide offers with risk signals"
          selected={draft.hide_suspicious}
          onPress={() => edit("hide_suspicious", !draft.hide_suspicious)}
        />
      </View>
      <Button onPress={apply}>Show matching homes</Button>
    </Panel>
  );
}

export function DetailDialog({
  home,
  onClose,
  onSave,
  saved,
  onReport,
  onContact,
  loadState = "loaded",
  onRetry,
}: {
  home: Listing;
  onClose: () => void;
  onSave: () => void;
  saved: boolean;
  onReport: () => void;
  onContact: (contact: NonNullable<Listing["contact_adverts"]>[number]) => void;
  loadState?: "summary" | "loading" | "loaded" | "failed" | "unavailable";
  onRetry?: () => void;
}) {
  const narrow = useWindowDimensions().width < 700;
  const detailsLoaded = loadState === "loaded";
  const history = home.history ?? [];
  const latestObservations = history.slice(-8).reverse();
  return (
    <Panel title="A closer look" wide onClose={onClose}>
      {!detailsLoaded && <View style={[s.card, { padding: 14, gap: 8, alignItems: "flex-start" }]}>
        {loadState === "loading" || loadState === "summary" ? <Text accessibilityRole="status" style={s.text}>Loading current details, contact options and observations…</Text>
          : <Text accessibilityRole="alert" style={s.text}>{loadState === "unavailable" ? "This home's details are no longer available. The saved summary may be out of date; contact options are unavailable." : "Could not load current details. Showing the listing summary; contact options and observations have not been checked."}</Text>}
        {onRetry && (loadState === "failed" || loadState === "unavailable") && <Button outline onPress={onRetry}>Retry details</Button>}
      </View>}
      {home.status !== "active" ? (
        <Text style={[s.text, { color: c.warning }]}>
          {home.status === "inactive"
            ? "Delisted · Kept in your saved homes. It will not appear on the discovery map."
            : "Availability unconfirmed · This home is hidden from the discovery map until checked."}
        </Text>
      ) : null}
      {home.is_demo && (
        <Text style={[s.muted, { color: c.warning }]}>
          SAMPLE HOME · Fictional listing and illustrative photography
        </Text>
      )}
      <View style={{ gap: 8 }}>
        <Text style={s.label}>
          {[home.district, home.city].filter(Boolean).join(" · ").toUpperCase()}
        </Text>
        <Text style={s.title}>{home.title}</Text>
        <Text style={s.muted}>
          {home.address} · {home.area_m2} m² · {home.rooms} rooms ·{" "}
          {home.status} ·{" "}
          {home.advertiser_type === "private"
            ? "Direct offer"
            : home.advertiser_type === "agency"
              ? "Agency"
              : "Advertiser type unconfirmed"}
        </Text>
      </View>
      <View
        style={[
          s.card,
          {
            padding: 20,
            flexDirection: narrow ? "column" : "row",
            flexWrap: "wrap",
            gap: 24,
            justifyContent: "space-between",
          },
        ]}
      >
        <View>
          <Text style={s.label}>BASE RENT / MONTH</Text>
          <Text style={[s.title, { marginTop: 10 }]}>
            {money(home.rent_pln)}
          </Text>
        </View>
        <View>
          <Text style={s.label}>BUILDING FEES</Text>
          <Text style={[s.text, { marginTop: 10 }]}>
            {money(home.fees_pln)}
          </Text>
        </View>
        <View>
          <Text style={s.label}>{home.fees_pln === null ? "KNOWN COSTS · FEES UNSTATED" : "RENT + BUILDING FEES*"}</Text>
          <Text style={[s.text, { marginTop: 10, fontWeight: "700" }]}>
            {money(home.total_monthly_pln)}
          </Text>
        </View>
      </View>
      <Text style={s.muted}>
        * This is not a complete monthly bill. Utilities may be additional. When building fees are unstated, the displayed known cost excludes them.
        Deposit: {money(home.deposit_pln)}. Commission:{" "}
        {money(home.commission_pln)}. “Not stated” does not mean zero.
      </Text>
      <View style={[s.row, { gap: 12, flexWrap: "wrap" }]}>
        <Button onPress={onSave}>
          {saved ? "Remove from saved homes" : "Save this home"}
        </Button>
        {(detailsLoaded && home.status === "active" ? home.contact_adverts || [] : []).map((contact) => (
          <Button key={contact.id} onPress={() => onContact(contact)}>Message {contact.name}</Button>
        ))}
        {detailsLoaded && home.status === "active" && home.sources.filter(source => source.name !== "realtoruch" && source.status === "active").map((source, index) => (
          <Button key={`${source.name}-${index}`} outline onPress={() => Linking.openURL(source.url)}>View on {source.name}</Button>
        ))}
        <Button variant="quiet" onPress={onReport}>
          Report a concern
        </Button>
      </View>
      <ListingGallery key={home.id} home={home} narrow={narrow} />
      <View style={{ gap: 12 }}>
        <Text style={[s.title, { fontSize: 20 }]}>The space</Text>
        <Text style={s.text}>{home.description}</Text>
        <View style={[s.row, { flexWrap: "wrap", gap: 8 }]}>
          {home.amenities.map((a) => (
            <View
              key={a}
              style={[s.row, { padding: 10, backgroundColor: c.pale, gap: 6 }]}
            >
              <Check size={12} color={c.green} />
              <Text style={[s.text, { fontSize: 12 }]}>
                {a === "pets" ? "Pets welcome" : a}
              </Text>
            </View>
          ))}
        </View>
      </View>
      <View style={{ gap: 12 }}>
        <Text style={[s.title, { fontSize: 20 }]}>One home. Every source.</Text>
        {home.sources.map((source, i) => (
          <View key={source.name + i} style={[s.card, { padding: 16, gap: 6 }]}>
            <View
              style={[
                s.row,
                { justifyContent: "space-between", gap: 12, flexWrap: "wrap" },
              ]}
            >
              <Text style={[s.text, { fontWeight: "700" }]}>
                {source.name === "realtoruch"
                  ? "Realtoruch"
                  : `${source.name}.pl`}
              </Text>
              <Text style={s.text}>{money(source.rent_pln)}</Text>
              <Pressable
                accessibilityRole="link"
                accessibilityLabel={`Visit ${source.name}`}
                disabled={!detailsLoaded || home.status !== "active"}
                accessibilityState={{ disabled: !detailsLoaded || home.status !== "active" }}
                onPress={() => Linking.openURL(source.url)}
              >
                <ArrowUpRight size={20} color={c.green} />
              </Pressable>
            </View>
            <Text style={s.muted}>
              {source.advertiser_type} · {source.status} · commission{" "}
              {money(source.commission_pln)}
            </Text>
            <Text style={[s.muted, { fontSize: 11 }]}>
              Checked {new Date(source.last_checked).toLocaleString()} ·{" "}
              {source.match_reason}
            </Text>
          </View>
        ))}
      </View>
      <View style={{ gap: 12 }}>
        <Text style={[s.title, { fontSize: 20 }]}>What we noticed</Text>
        {home.risk_flags.length ? (
          home.risk_flags.map((flag) => (
            <View
              key={flag.code}
              style={{ padding: 16, backgroundColor: "#F4EBDE", gap: 8 }}
            >
              <View style={[s.row, { gap: 8, flexWrap: "wrap" }]}>
                <ShieldAlert size={17} color={c.warning} />
                <Text style={[s.text, { fontWeight: "600" }]}>
                  {flag.label}
                </Text>
              </View>
              <Text style={s.muted}>{flag.detail}</Text>
            </View>
          ))
        ) : (
          <Text style={s.muted}>
            No automated risk signals in the available observations. This is not
            a verification or a guarantee of the advertiser.
          </Text>
        )}
      </View>
      {detailsLoaded && latestObservations.length > 0 && (
        <View style={{ gap: 10 }}>
          <Text accessibilityRole="header" style={[s.title, { fontSize: 20 }]}>
            Observed rent history
          </Text>
          {history.length > latestObservations.length && (
            <Text style={s.muted}>
              Showing the latest {latestObservations.length} of {history.length} observations.
            </Text>
          )}
          {latestObservations.map((item, i) => (
            <View
              key={i}
              style={[
                s.row,
                {
                  justifyContent: "space-between",
                  flexWrap: "wrap",
                  gap: 6,
                  borderBottomWidth: 1,
                  borderColor: c.line,
                  paddingVertical: 10,
                },
              ]}
            >
              <Text style={s.muted}>
                {new Date(item.at).toLocaleDateString("en-GB", {
                  day: "numeric",
                  month: "short",
                  year: "numeric",
                  timeZone: "Europe/Warsaw",
                })}
              </Text>
              <Text style={s.text}>
                {money(item.rent_pln)} · {item.status}
              </Text>
            </View>
          ))}
        </View>
      )}

    </Panel>
  );
}

const THUMBNAIL_LIMIT = 5;

function ListingGallery({ home, narrow }: { home: Listing; narrow: boolean }) {
  const [photoIndex, setPhotoIndex] = useState(0);
  const selectedThumbnail = useRef<ComponentRef<typeof Pressable>>(null);
  const restoreThumbnailFocus = useRef(false);
  const count = home.images.length;
  const photo = Math.max(0, Math.min(photoIndex, count - 1));
  if (photo !== photoIndex) setPhotoIndex(photo);

  useLayoutEffect(() => {
    if (restoreThumbnailFocus.current) selectedThumbnail.current?.focus();
    restoreThumbnailFocus.current = false;
  }, [photo]);

  if (!count) {
    return (
      <View style={{ alignItems: "center", justifyContent: "center", minHeight: 100, padding: 16, backgroundColor: c.pale }}>
        <Text style={s.muted}>No photos available</Text>
      </View>
    );
  }

  function handleArrow(event: KeyDownEvent, fromThumbnail: boolean) {
    const { key, altKey, ctrlKey, metaKey, shiftKey } = event.nativeEvent;
    if (altKey || ctrlKey || metaKey || shiftKey) return;
    if (key !== "ArrowLeft" && key !== "ArrowRight") return;
    event.preventDefault();
    const step = key === "ArrowLeft" ? -1 : 1;
    const next = Math.max(0, Math.min(photo + step, count - 1));
    if (next !== photo) {
      restoreThumbnailFocus.current = fromThumbnail;
      setPhotoIndex(next);
    }
  }

  const web = Platform.OS === "web";
  // Keep a complete strip of five near the current photo, including at either end.
  const start = Math.max(0, Math.min(photo - 2, count - THUMBNAIL_LIMIT));
  const position = `Photo ${photo + 1} of ${count}`;
  return (
    <View style={{ gap: 12 }}>
      <View testID="gallery-photo-frame">
        <ListingPhoto
          uri={home.images[photo]}
          alt={home.is_demo ? "Illustrative apartment interior" : `${position} for ${home.title}`}
          width={narrow ? 560 : 1000}
          height={narrow ? 230 : 340}
        />
      </View>
      <View
        onKeyDown={web ? (event) => handleArrow(event, false) : undefined}
        style={[s.row, { justifyContent: "space-between", gap: 8, flexWrap: "wrap" }]}
      >
        {count > 1 && (
          <Button outline label="Previous photo" disabled={photo === 0} onPress={() => setPhotoIndex(photo - 1)}>
            Previous
          </Button>
        )}
        <Text aria-live="polite" style={s.muted}>{position}</Text>
        {count > 1 && (
          <Button outline label="Next photo" disabled={photo === count - 1} onPress={() => setPhotoIndex(photo + 1)}>
            Next
          </Button>
        )}
      </View>
      {count > 1 && (
        <View
          onKeyDown={web ? (event) => handleArrow(event, true) : undefined}
          style={[s.row, { gap: 4, flexWrap: "wrap" }]}
        >
          {home.images.slice(start, start + THUMBNAIL_LIMIT).map((uri, offset) => {
            const index = start + offset;
            const selected = photo === index;
            return (
              <Pressable
                key={index}
                ref={selected ? selectedThumbnail : undefined}
                accessibilityRole="button"
                accessibilityLabel={`Photo ${index + 1}`}
                accessibilityState={{ selected }}
                {...(web ? { "aria-pressed": selected, tabIndex: selected ? 0 : -1 } : {})}
                onPress={() => setPhotoIndex(index)}
                style={{
                  width: 44,
                  height: 44,
                  borderWidth: 1,
                  borderColor: selected ? c.green : c.line,
                  backgroundColor: c.pale,
                }}
              >
                <View aria-hidden accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
                  <ListingPhoto uri={uri} alt="" width={42} height={42} thumbnail />
                </View>
              </Pressable>
            );
          })}
        </View>
      )}
    </View>
  );
}

export function CompareDialog({
  homes,
  onClose,
}: {
  homes: Listing[];
  onClose: () => void;
}) {
  const narrow = useWindowDimensions().width < 700;
  const rows: [string, (home: Listing) => string][] = [
    ["Base rent", (h) => money(h.rent_pln)],
    ["Building fees", (h) => money(h.fees_pln)],
    ["Monthly total", (h) => money(h.total_monthly_pln)],
    ["Deposit", (h) => money(h.deposit_pln)],
    ["Commission", (h) => money(h.commission_pln)],
    ["Size", (h) => `${h.area_m2} m² · ${h.rooms} rooms`],
    ["Advertiser", (h) => h.advertiser_type],
    ["Risk signals", (h) => `${h.risk_flags.length}`],
    ["Sources", (h) => h.sources.map((s) => s.name).join(", ")],
  ];
  return (
    <Panel title="Side by side" wide onClose={onClose}>
      <View
        style={{
          flexDirection: narrow ? "column" : "row",
          alignItems: "stretch",
          gap: 22,
        }}
      >
        {homes.map((home) => (
          <View
            key={home.id}
            style={{ flex: narrow ? undefined : 1, minWidth: 0, gap: 12 }}
          >
            {!!home.images[0] && (
              <ListingPhoto
                uri={home.images[0]}
                alt={
                  home.is_demo
                    ? "Illustrative apartment interior"
                    : `Photo of ${home.title}`
                }
                height={140}
                width={300}
              />
            )}
            <Text style={[s.text, { fontWeight: "600", minHeight: 66 }]}>
              {home.title}
            </Text>
            {rows.map(([label, value]) => (
              <View
                key={label}
                style={{
                  borderTopWidth: 1,
                  borderColor: c.line,
                  paddingTop: 12,
                  minHeight: 64,
                }}
              >
                <Text style={[s.label, { fontSize: 9, letterSpacing: 0.5 }]}>
                  {label.toUpperCase()}
                </Text>
                <Text style={[s.text, { marginTop: 4, fontSize: 12 }]}>
                  {value(home)}
                </Text>
              </View>
            ))}
          </View>
        ))}
      </View>
    </Panel>
  );
}
