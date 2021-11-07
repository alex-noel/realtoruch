import React from "react";
import {
  Image,
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

export function ListingCard({
  home,
  selected,
  saved,
  compared,
  onOpen,
  onSave,
  onCompare,
}: {
  home: Listing;
  selected: boolean;
  saved: boolean;
  compared: boolean;
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
          overflow: "hidden",
        },
      ]}
    >
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`View ${home.title}`}
        onPress={onOpen}
        style={{
          width: compact ? "100%" : 196,
          height: compact ? 210 : undefined,
          minHeight: compact ? 210 : 202,
          backgroundColor: c.pale,
        }}
      >
        {home.images[0] ? (
          <Image
            source={{ uri: home.images[0] }}
            accessibilityLabel="Illustrative apartment interior"
            style={{ width: "100%", height: "100%", position: "absolute" }}
            resizeMode="cover"
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
            top: 12,
            left: 12,
            backgroundColor: "#FFFFFFED",
            paddingHorizontal: 8,
            paddingVertical: 5,
          }}
        >
          <Text
            style={[s.label, { color: c.ink, fontSize: 9, letterSpacing: 0.5 }]}
          >
            {home.advertiser_type === "private"
              ? "DIRECT OFFER"
              : home.advertiser_type === "agency"
                ? "AGENCY"
                : "TYPE UNCONFIRMED"}
          </Text>
        </View>
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
      <View style={{ flex: 1, padding: 19, gap: 10 }}>
        <View style={[s.row, { justifyContent: "space-between", gap: 8 }]}>
          <View style={[s.row, { gap: 5, flex: 1 }]}>
            <MapPin size={11} color={c.muted} />
            <Text numberOfLines={1} style={[s.muted, { fontSize: 11 }]}>
              {home.district}, {home.city}
            </Text>
          </View>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={
              saved ? `Unsave ${home.title}` : `Save ${home.title}`
            }
            onPress={onSave}
            hitSlop={10}
          >
            <Heart
              size={18}
              color={saved ? c.orange : c.muted}
              fill={saved ? c.orange : "none"}
            />
          </Pressable>
        </View>
        <Pressable onPress={onOpen} accessibilityRole="button">
          <Text
            numberOfLines={2}
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
        <View style={[s.row, { gap: 12 }]}>
          <Text style={[s.text, { fontSize: 12 }]}>{home.area_m2} m²</Text>
          <Text style={{ color: c.line }}>│</Text>
          <Text style={[s.text, { fontSize: 12 }]}>
            {home.rooms} {home.rooms === 1 ? "room" : "rooms"}
          </Text>
          <Text style={{ color: c.line }}>│</Text>
          <Text style={[s.muted, { fontSize: 11 }]}>
            {home.floor === null ? "Floor n/a" : `Floor ${home.floor}`}
          </Text>
        </View>
        <View
          style={[
            s.row,
            { justifyContent: "space-between", marginTop: 2, gap: 8 },
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
            onPress={onCompare}
            style={{
              padding: 8,
              borderWidth: 1,
              borderColor: compared ? c.green : c.line,
              backgroundColor: compared ? c.pale : "white",
            }}
          >
            {compared ? (
              <Check size={14} color={c.green} />
            ) : (
              <Plus size={14} color={c.ink} />
            )}
          </Pressable>
        </View>
        <View style={[s.row, { gap: 5, marginTop: 2 }]}>
          {home.risk_flags.length ? (
            <ShieldAlert color={c.warning} size={12} />
          ) : (
            <Check color={c.green} size={12} />
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
            {home.risk_flags.length
              ? "Advertiser details worth checking"
              : home.commission_pln === 0
                ? "No commission stated"
                : "See source fees"}
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
