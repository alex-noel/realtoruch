import React from "react";
import {
  Image,
  Platform,
  Pressable,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import ArrowUpRight from "lucide-react-native/icons/arrow-up-right";
import Check from "lucide-react-native/icons/check";
import Heart from "lucide-react-native/icons/heart";
import Layers from "lucide-react-native/icons/layers";
import MapPin from "lucide-react-native/icons/map-pin";
import Plus from "lucide-react-native/icons/plus";
import ScanLine from "lucide-react-native/icons/scan-line";
import ShieldAlert from "lucide-react-native/icons/shield-alert";
import { Listing } from "../types";
import { c, s } from "../theme";
import { money } from "./UI";

export function ListingPhoto({
  uri,
  alt,
  width,
  height,
  fill = false,
}: {
  uri: string;
  alt: string;
  width: number;
  height: number;
  fill?: boolean;
}) {
  if (Platform.OS === "web")
    return (
      <img
        data-testid="listing-photo"
        src={uri}
        alt={alt}
        width={width}
        height={height}
        loading="lazy"
        decoding="async"
        style={
          fill ? { position: "absolute", inset: 0, height: "100%" } : undefined
        }
      />
    );
  return (
    <Image
      source={{ uri }}
      accessibilityLabel={alt}
      style={{
        width: "100%",
        height: fill ? "100%" : height,
        position: fill ? "absolute" : "relative",
      }}
      resizeMode="cover"
    />
  );
}

export function ListingCard({
  home,
  selected,
  saved,
  compared,
  seen = false,
  onOpen,
  onSave,
  onCompare,
}: {
  home: Listing;
  selected: boolean;
  saved: boolean;
  compared: boolean;
  seen?: boolean;
  onOpen: () => void;
  onSave: () => void;
  onCompare: () => void;
}) {
  const compact = useWindowDimensions().width < 620;
  return (
    <View
      style={[
        s.card,
        {
          borderColor: selected ? c.green : c.line,
          flexDirection: compact ? "column" : "row",
        },
      ]}
    >
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`View ${home.title}`}
        onPress={onOpen}
        style={{
          width: compact ? "100%" : "34%",
          maxWidth: compact ? "100%" : 196,
          height: compact ? 210 : undefined,
          minHeight: compact ? 210 : 202,
          backgroundColor: c.pale,
        }}
      >
        {home.images[0] ? (
          <ListingPhoto
            uri={home.images[0]}
            alt={
              home.is_demo
                ? "Illustrative apartment interior"
                : `Photo of ${home.title}`
            }
            width={compact ? 400 : 196}
            height={compact ? 210 : 202}
            fill
          />
        ) : (
          <View
            style={{ flex: 1, alignItems: "center", justifyContent: "center" }}
          >
            <ScanLine size={40} color={c.muted} />
            <Text style={s.muted}>No photo available</Text>
          </View>
        )}
        <View
          style={{
            position: "absolute",
            bottom: 12,
            left: 12,
            backgroundColor: "#172D2AD9",
            padding: 6,
            flexDirection: "row",
            gap: 5,
            alignItems: "center",
          }}
        >
          <Layers color="white" size={11} />
          <Text style={{ color: "white", fontSize: 10 }}>
            {home.sources.length}{" "}
            {home.sources.length === 1 ? "source" : "sources"}
          </Text>
        </View>
      </Pressable>
      <View style={{ flex: 1, minWidth: 0, padding: 19, gap: 10 }}>
        <View style={[s.row, { gap: 8, flexWrap: "wrap" }]}>
          <Text style={[s.label, { color: c.green }]}>
            {home.advertiser_type === "private"
              ? "DIRECT OFFER"
              : home.advertiser_type === "agency"
                ? "AGENCY"
                : "TYPE UNCONFIRMED"}
          </Text>
          {home.status !== "active" && (
            <Text style={[s.label, { color: c.warning }]}>
              {home.status === "inactive"
                ? "DELISTED"
                : "AVAILABILITY UNCONFIRMED"}
            </Text>
          )}
          {seen && <Text style={s.label}>SEEN</Text>}
        </View>
        <View
          style={[
            s.row,
            { justifyContent: "space-between", gap: 8, flexWrap: "wrap" },
          ]}
        >
          <View style={[s.row, { gap: 5, minWidth: 0, flexShrink: 1 }]}>
            <MapPin size={11} color={c.muted} />
            <Text style={[s.muted, { fontSize: 11, flexShrink: 1 }]}>
              {[home.district, home.city].filter(Boolean).join(", ")}
            </Text>
          </View>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={
              saved ? `Unsave ${home.title}` : `Save ${home.title}`
            }
            accessibilityState={{ selected: saved }}
            {...(Platform.OS === "web" ? { "aria-pressed": saved } : {})}
            onPress={onSave}
            hitSlop={10}
            style={[s.row, { padding: 4, gap: 4 }]}
          >
            <Heart
              size={18}
              color={saved ? c.orange : c.muted}
              fill={saved ? c.orange : "none"}
            />
            {saved && <Text style={[s.muted, { fontSize: 11 }]}>Saved</Text>}
          </Pressable>
        </View>
        <Pressable onPress={onOpen} accessibilityRole="button">
          <Text
            style={[
              s.text,
              {
                fontSize: 16,
                lineHeight: 21,
                fontWeight: "600",
                letterSpacing: -0.25,
              },
            ]}
          >
            {home.title}
          </Text>
        </Pressable>
        <View style={[s.row, { gap: 8, flexWrap: "wrap" }]}>
          <Text style={[s.text, { fontSize: 12 }]}>{home.area_m2} m²</Text>
          <Text style={[s.text, { fontSize: 12 }]}>
            {home.rooms} {home.rooms === 1 ? "room" : "rooms"}
          </Text>
          <Text style={[s.muted, { fontSize: 11 }]}>
            {home.floor === null ? "Floor n/a" : `Floor ${home.floor}`}
          </Text>
        </View>
        <View
          style={[
            s.row,
            {
              justifyContent: "space-between",
              marginTop: 2,
              gap: 8,
              flexWrap: "wrap",
            },
          ]}
        >
          <View>
            <Text
              style={[
                s.text,
                { fontSize: 21, fontWeight: "700", letterSpacing: -0.7 },
              ]}
            >
              {money(home.rent_pln)}
              <Text style={[s.muted, { fontWeight: "400" }]}> / month</Text>
            </Text>
            <Text style={[s.muted, { fontSize: 10 }]}>
              +{" "}
              {home.fees_pln === null
                ? "fees not stated"
                : `${money(home.fees_pln)} building fees`}
            </Text>
          </View>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`Compare ${home.title}`}
            accessibilityState={{ selected: compared }}
            {...(Platform.OS === "web" ? { "aria-pressed": compared } : {})}
            onPress={onCompare}
            style={{
              padding: 8,
              borderWidth: 1,
              borderColor: compared ? c.green : c.line,
              backgroundColor: compared ? c.pale : "white",
              flexDirection: "row",
              alignItems: "center",
              gap: 4,
            }}
          >
            {compared ? (
              <Check size={14} color={c.green} />
            ) : (
              <Plus size={14} color={c.ink} />
            )}
            {compared && (
              <Text style={[s.muted, { fontSize: 11 }]}>Compared</Text>
            )}
          </Pressable>
        </View>
        <View style={[s.row, { gap: 5, marginTop: 2 }]}>
          {!!home.risk_flags.length && (
            <ShieldAlert color={c.warning} size={12} />
          )}
          <Text
            style={[
              s.muted,
              {
                fontSize: 10,
                color: home.risk_flags.length ? c.warning : c.green,
                flex: 1,
              },
            ]}
          >
            {home.commission_pln === null
              ? "Commission not stated"
              : home.commission_pln === 0
                ? "No commission"
                : `Commission: ${money(home.commission_pln)}`}
            {home.risk_flags.length
              ? " · Advertiser details worth checking"
              : ""}
          </Text>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`Open details for ${home.title}`}
            onPress={onOpen}
          >
            <ArrowUpRight size={15} color={c.ink} />
          </Pressable>
        </View>
      </View>
    </View>
  );
}
