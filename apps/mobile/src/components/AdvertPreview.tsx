import React from "react";
import { Text, View } from "react-native";
import type { Draft } from "../marketplaceApi";
import { s } from "../theme";
import { money } from "./UI";
import { OwnedPhotoPreview } from "./PhotoUploader";
import type { PhotoRow } from "./photoState";

// A read-only view of the exact normalized draft passed to the next mutation.
export function AdvertPreview({ draft, rows = [] }: { draft: Draft; rows?: PhotoRow[] }) {
  const optional = (value: number | null) => value == null ? "Not stated" : money(value);
  return <View style={[s.card, { padding: 20, gap: 10 }]}>
    <Text accessibilityRole="header" style={s.title}>Review this rental</Text>
    <Text style={s.text}>{draft.title}</Text>
    <Text style={s.text}>{draft.description}</Text>
    <Text style={s.muted}>{draft.property_type} · {draft.area_m2} m² · {draft.rooms} rooms · Floor {draft.floor == null ? "not stated" : draft.floor}</Text>
    <Text style={s.text}>Base rent: {money(draft.rent_pln)} / month</Text>
    <Text style={s.text}>Fees: {optional(draft.fees_pln)}</Text>
    <Text style={s.text}>Monthly rent and fees: {draft.fees_pln == null ? "Not stated; fees are unknown" : money(draft.rent_pln + draft.fees_pln)}</Text>
    <Text style={s.text}>Deposit: {optional(draft.deposit_pln)} · Commission: {optional(draft.commission_pln)}</Text>
    <Text style={s.text}>Location: {[draft.address, draft.district, draft.city, draft.region].filter(Boolean).join(", ")}</Text>
    <Text style={s.muted}>The street address and location coordinates ({draft.lat}, {draft.lon}) are included in the listing.</Text>
    <Text style={s.text}>Amenities: {draft.amenities.length ? draft.amenities.join(", ") : "None listed"}</Text>
    <Text style={s.text}>Photos: {draft.images.length + (draft.media_ids?.length ?? 0)}</Text>
    {draft.images.map((url, index) => <Text key={`${url}-${index}`} style={s.muted}>{index + 1}. {url}{index === 0 ? " · Cover" : ""}</Text>)}
    {(draft.media_ids ?? []).map((id, index) => <View key={id} style={{ gap: 6 }}>
      <Text style={s.muted}>Uploaded photo {index + 1}{index === 0 && !draft.images.length ? " · Cover" : ""}</Text>
      <OwnedPhotoPreview id={id} index={index} row={rows.find(item => item.id === id && item.phase === "ready")} />
    </View>)}
  </View>;
}
