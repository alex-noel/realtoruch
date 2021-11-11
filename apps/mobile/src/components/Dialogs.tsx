import React, { useState } from "react";
import {
  Image,
  Linking,
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
import { Button, Chip, Field, Panel, money } from "./UI";

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
  const [error, setError] = useState("");
  const edit = (key: keyof Filters, value: unknown) =>
    setDraft((current) => ({ ...current, [key]: value }));
  const numeric = (key: keyof Filters, value: string) =>
    edit(key, value ? Number(value.replace(/[^0-9.]/g, "")) : undefined);
  function apply() {
    if (
      (draft.min_price ?? 0) > (draft.max_price ?? Infinity) ||
      (draft.min_area ?? 0) > (draft.max_area ?? Infinity)
    ) {
      setError("Minimum values must be lower than maximum values.");
      return;
    }
    onApply({ ...draft, max_price_exclusive: true });
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
          value={String(draft.min_price ?? "")}
          onChange={(v) => numeric("min_price", v)}
          numeric
          placeholder="Any"
        />
        <Field
          label="RENT BELOW · PLN"
          value={String(draft.max_price ?? "")}
          onChange={(v) => numeric("max_price", v)}
          numeric
          placeholder="Any"
        />
      </View>
      <Text style={[s.muted, { fontSize: 11 }]}>
        Rent filters use base rent, excluding building fees and utilities.
      </Text>
      <View style={[s.row, { gap: 16 }]}>
        <Field
          label="MIN AREA · M²"
          value={String(draft.min_area ?? "")}
          onChange={(v) => numeric("min_area", v)}
          numeric
          placeholder="Any"
        />
        <Field
          label="MAX AREA · M²"
          value={String(draft.max_area ?? "")}
          onChange={(v) => numeric("max_area", v)}
          numeric
          placeholder="Any"
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
      {!!error && (
        <Text accessibilityRole="alert" style={{ color: "#A3422D" }}>
          {error}
        </Text>
      )}
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
}: {
  home: Listing;
  onClose: () => void;
  onSave: () => void;
  saved: boolean;
  onReport: () => void;
  onContact: (contact: NonNullable<Listing["contact_adverts"]>[number]) => void;
}) {
  const [photo, setPhoto] = useState(0);
  const narrow = useWindowDimensions().width < 700;
  return (
    <Panel title="A closer look" wide onClose={onClose}>
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
      {home.images[photo] && (
        <Image
          source={{ uri: home.images[photo] }}
          accessibilityLabel={
            home.is_demo
              ? "Illustrative apartment interior"
              : `Photo ${photo + 1} of ${home.title}`
          }
          style={{ width: "100%", height: narrow ? 230 : 340 }}
          resizeMode="cover"
        />
      )}
      {home.images.length > 1 && (
        <View style={[s.row, { gap: 8, flexWrap: "wrap" }]}>
          {home.images.map((_, i) => (
            <Chip
              key={i}
              label={`Photo ${i + 1}`}
              selected={photo === i}
              onPress={() => setPhoto(i)}
            />
          ))}
        </View>
      )}
      <View style={{ gap: 8 }}>
        <Text style={s.label}>
          {[home.district, home.city].filter(Boolean).join(" · ").toUpperCase()}
        </Text>
        <Text style={s.title}>{home.title}</Text>
        <Text style={s.muted}>
          {home.address} · {home.area_m2} m² · {home.rooms} rooms ·{" "}
          {home.status}
        </Text>
      </View>
      <View
        style={[
          s.card,
          {
            padding: 20,
            flexDirection: narrow ? "column" : "row",
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
          <Text style={s.label}>MONTHLY TOTAL*</Text>
          <Text style={[s.text, { marginTop: 10, fontWeight: "700" }]}>
            {money(home.total_monthly_pln)}
          </Text>
        </View>
      </View>
      <Text style={s.muted}>
        * Base rent + stated building fees. Utilities may be additional.
        Deposit: {money(home.deposit_pln)}. Commission:{" "}
        {money(home.commission_pln)}. “Not stated” does not mean zero.
      </Text>
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
        {(home.contact_adverts || []).map((contact) => (
          <Button key={contact.id} onPress={() => onContact(contact)}>
            Message {contact.name}
          </Button>
        ))}
        <Text style={[s.title, { fontSize: 20 }]}>One home. Every source.</Text>
        {home.sources.map((source, i) => (
          <View key={source.name + i} style={[s.card, { padding: 16, gap: 6 }]}>
            <View style={[s.row, { justifyContent: "space-between", gap: 12 }]}>
              <Text style={[s.text, { fontWeight: "700" }]}>
                {source.name === "realtoruch"
                  ? "Realtoruch"
                  : `${source.name}.pl`}
              </Text>
              <Text style={s.text}>{money(source.rent_pln)}</Text>
              <Pressable
                accessibilityRole="link"
                accessibilityLabel={`Visit ${source.name}`}
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
              <View style={[s.row, { gap: 8 }]}>
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
      {home.history && home.history.length > 0 && (
        <View style={{ gap: 10 }}>
          <Text style={[s.title, { fontSize: 20 }]}>
            Observed price changes
          </Text>
          {home.history
            .slice(-8)
            .reverse()
            .map((item, i) => (
              <View
                key={i}
                style={[
                  s.row,
                  {
                    justifyContent: "space-between",
                    borderBottomWidth: 1,
                    borderColor: c.line,
                    paddingVertical: 10,
                  },
                ]}
              >
                <Text style={s.muted}>
                  {new Date(item.at).toLocaleDateString()}
                </Text>
                <Text style={s.text}>
                  {money(item.rent_pln)} · {item.status}
                </Text>
              </View>
            ))}
        </View>
      )}
      <View style={[s.row, { gap: 12, flexWrap: "wrap" }]}>
        <Button onPress={onSave}>
          {saved ? "Remove from saved homes" : "Save this home"}
        </Button>
        <Button outline onPress={onReport}>
          Report a concern
        </Button>
      </View>
    </Panel>
  );
}

export function CompareDialog({
  homes,
  onClose,
}: {
  homes: Listing[];
  onClose: () => void;
}) {
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
      <View style={[s.row, { alignItems: "flex-start", gap: 12 }]}>
        {homes.map((home) => (
          <View key={home.id} style={{ flex: 1, gap: 12 }}>
            <Image
              source={{ uri: home.images[0] }}
              style={{ height: 140, width: "100%" }}
            />
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
