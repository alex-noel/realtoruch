import React, { useState } from "react";
import { Pressable, Text, View } from "react-native";
import { c, s } from "../theme";
import type { SourceHealth, Sources } from "../types";
import { Button } from "./UI";

const MAX_VISIBLE_PROVIDERS = 6;
const UTC_TIMESTAMP = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
const PROVIDER_NAMES = new Map([
  ["olx", "OLX"],
  ["otodom", "Otodom"],
  ["gratka", "Gratka"],
  ["morizon", "Morizon"],
]);

function timestamp(value: string | null | undefined) {
  if (!value || !UTC_TIMESTAMP.test(value) || value.startsWith("0000"))
    return null;
  const milliseconds = Date.parse(value);
  if (!Number.isFinite(milliseconds)) return null;
  // Date.parse can roll an invalid calendar day forward into the next month.
  return new Date(milliseconds).toISOString().slice(0, 19) ===
    value.slice(0, 19)
    ? milliseconds
    : null;
}

const LABELS = {
  "never-collected": "No collection yet",
  collecting: "Collecting",
  fresh: "Fresh collection",
  delayed: "Collection delayed",
  partial: "Partial collection",
  failed: "Collection failed",
  "access-blocked": "Collection access blocked",
  disabled: "Automatic collection unavailable",
  unknown: "Collection status unknown",
};

export function describeSource(source: SourceHealth, now = Date.now()) {
  const { health, cadence_minutes: cadence } = source;
  const completed = timestamp(health?.last_success_at);
  const lastSuccess =
    completed !== null && completed <= now ? health?.last_success_at : null;
  const freshness =
    completed === null ||
    completed > now ||
    cadence === null ||
    !Number.isInteger(cadence) ||
    cadence < 1 ||
    cadence > 10_080
      ? "unknown"
      : now - completed <= 2 * cadence * 60_000
        ? "fresh"
        : "delayed";
  let state: keyof typeof LABELS = freshness;
  if (!source.enabled) state = "disabled";
  else if (!health) state = "never-collected";
  else if (health.status === "running") state = "collecting";
  else if (
    health.errors.some(
      (error) =>
        error.http_status === 401 ||
        error.http_status === 403 ||
        error.http_status === 429 ||
        (error.kind === "SourceAccessError" && error.http_status === null),
    )
  )
    state = "access-blocked";
  else if (health.status === "failed" || health.status === "interrupted")
    state = "failed";
  else if (health.status === "partial" || health.limited) state = "partial";
  else if (health.status !== "succeeded") state = "unknown";

  const attempt = health?.finished_at ?? health?.started_at;
  const observation = source.last_observed_at;
  const provider = /^[a-z0-9_-]{2,40}$/.test(source.name)
    ? source.name
    : "Source";
  return {
    state,
    freshness,
    provider: PROVIDER_NAMES.get(provider) ?? provider,
    label: LABELS[state],
    lastSuccess,
    latestAttempt: timestamp(attempt) !== null ? attempt : null,
    latestObservation: timestamp(observation) !== null ? observation : null,
    storedAdverts:
      source.stored_adverts > 0 && !source.enabled
        ? `${source.stored_adverts} stored ${source.stored_adverts === 1 ? "advert" : "adverts"}. Stored adverts can include imports.`
        : null,
  };
}

export default function SourceStatus({
  city,
  data,
  loading,
  failed,
  onRetry,
}: {
  city: string;
  data: Sources | null;
  loading: boolean;
  failed: boolean;
  onRetry: () => void;
}) {
  const [showDetails, setShowDetails] = useState(false);
  const now = Date.now();
  const sources = data?.sources ?? [];
  return (
    <View style={[s.card, { padding: 14, gap: 10 }]}>
      <Text accessibilityRole="header" style={[s.text, { fontWeight: "600" }]}>
        Source collection · {city || "All cities"}
      </Text>
      {failed ? (
        <View style={{ gap: 8, alignItems: "flex-start" }}>
          <Text accessibilityRole="alert" style={s.muted}>
            Source status unavailable.
          </Text>
          <Button outline onPress={onRetry}>
            Retry source status
          </Button>
        </View>
      ) : sources.length ? (
        <>
          <Text style={s.muted}>
            Collection status reflects configured runs. Individual adverts can
            be older.
          </Text>
          {sources.slice(0, MAX_VISIBLE_PROVIDERS).map((source) => {
            const status = describeSource(source, now);
            return (
              <View
                key={source.name}
                style={{
                  gap: 4,
                  paddingTop: 8,
                  borderTopWidth: 1,
                  borderColor: c.line,
                }}
              >
                <Text style={s.text}>
                  <Text style={{ fontWeight: "600" }}>{status.provider}</Text> ·{" "}
                  {status.label}
                </Text>
                {status.state !== status.freshness && (
                  <Text style={s.muted}>
                    {status.freshness === "unknown"
                      ? "Freshness unknown"
                      : status.freshness === "delayed"
                        ? "Last complete collection is delayed"
                        : "Last complete collection is within cadence"}
                  </Text>
                )}
                {!!status.storedAdverts && (
                  <Text style={s.muted}>{status.storedAdverts}</Text>
                )}
                {showDetails && (
                  <View style={{ gap: 4 }}>
                    <Text style={s.muted}>
                      Last complete collection ·{" "}
                      {status.lastSuccess ?? "Unknown"}
                    </Text>
                    <Text style={s.muted}>
                      Latest attempt · {status.latestAttempt ?? "Unknown"}
                    </Text>
                    <Text style={s.muted}>
                      Latest stored observation ·{" "}
                      {status.latestObservation ?? "Unknown"}
                    </Text>
                  </View>
                )}
              </View>
            );
          })}
          {sources.length > MAX_VISIBLE_PROVIDERS && (
            <Text style={s.muted}>
              Showing {MAX_VISIBLE_PROVIDERS} of {sources.length} configured
              sources.
            </Text>
          )}
          <View style={{ alignItems: "flex-start" }}>
            <Pressable
              accessibilityRole="button"
              aria-expanded={showDetails}
              onPress={() => setShowDetails((open) => !open)}
              style={s.outline}
            >
              <Text style={[s.text, { fontSize: 13, fontWeight: "600" }]}>
                {showDetails
                  ? "Hide collection timestamps"
                  : "Show collection timestamps"}
              </Text>
            </Pressable>
          </View>
        </>
      ) : (
        <Text accessibilityLiveRegion="polite" style={s.muted}>
          {loading ? "Checking source status…" : "No configured sources."}
        </Text>
      )}
    </View>
  );
}
