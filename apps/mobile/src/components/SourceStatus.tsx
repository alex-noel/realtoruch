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

export function summarizeSources(sources: SourceHealth[], now = Date.now()) {
  const providers = sources
    .slice(0, MAX_VISIBLE_PROVIDERS)
    .map((source) => ({ source, status: describeSource(source, now) }));
  return {
    providers,
    warnings: providers.filter(
      ({ status }) =>
        status.state !== "fresh" ||
        status.freshness !== "fresh" ||
        !!status.storedAdverts,
    ),
    omittedCount: Math.max(0, sources.length - MAX_VISIBLE_PROVIDERS),
  };
}

function freshnessNote(status: ReturnType<typeof describeSource>) {
  if (status.state === status.freshness) return null;
  return status.freshness === "unknown"
    ? "Freshness unknown"
    : status.freshness === "delayed"
      ? "Last complete collection is delayed"
      : "Last complete collection is within cadence";
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
  const { providers, warnings, omittedCount } = summarizeSources(sources, now);
  const warningGroups = warnings.reduce<
    { providers: string[]; status: ReturnType<typeof describeSource> }[]
  >((groups, entry) => {
    const existing = groups.find(
      ({ status }) =>
        status.label === entry.status.label &&
        freshnessNote(status) === freshnessNote(entry.status) &&
        status.storedAdverts === entry.status.storedAdverts,
    );
    if (existing) existing.providers.push(entry.status.provider);
    else
      groups.push({ providers: [entry.status.provider], status: entry.status });
    return groups;
  }, []);
  const toggleDetails = (
    <View style={{ alignItems: "flex-start" }}>
      <Pressable
        accessibilityRole="button"
        aria-expanded={showDetails}
        onPress={() => setShowDetails((open) => !open)}
        style={s.outline}
      >
        <Text style={[s.text, { fontSize: 13, fontWeight: "600" }]}>
          {showDetails ? "Hide provider details" : "Show provider details"}
        </Text>
      </Pressable>
    </View>
  );
  return (
    <View style={[s.card, { padding: 14, gap: 10 }]}>
      <Text accessibilityRole="header" style={[s.text, { fontWeight: "600" }]}>
        Source collection · {city || "All cities"}
      </Text>
      {failed ? (
        <View style={{ gap: 8 }}>
          <Text accessibilityRole="alert" style={s.muted}>
            Source status unavailable.
          </Text>
          {toggleDetails}
          {showDetails && (
            <View style={{ alignItems: "flex-start" }}>
              <Button outline onPress={onRetry}>
                Retry source status
              </Button>
            </View>
          )}
        </View>
      ) : sources.length ? (
        <>
          <Text style={s.muted}>
            Run health reflects configured sources; adverts may be older.
          </Text>
          {warningGroups.length ? (
            warningGroups.map(({ providers: names, status }) => (
              <Text key={`${status.label}:${names.join(",")}`} style={s.text}>
                <Text style={{ fontWeight: "600" }}>{names.join(", ")}</Text> ·{" "}
                {status.label}
                {freshnessNote(status) ? ` · ${freshnessNote(status)}` : ""}
                {status.storedAdverts ? ` · ${status.storedAdverts}` : ""}
              </Text>
            ))
          ) : (
            <Text style={s.muted}>
              All listed sources report fresh collection status.
            </Text>
          )}
          {omittedCount > 0 && (
            <Text style={s.muted}>
              Showing {MAX_VISIBLE_PROVIDERS} of {sources.length} configured
              sources.
            </Text>
          )}
          {toggleDetails}
          {showDetails && (
            <View style={{ gap: 10 }}>
              {providers.map(({ source, status }) => (
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
                    <Text style={{ fontWeight: "600" }}>{status.provider}</Text>{" "}
                    · {status.label}
                  </Text>
                  {freshnessNote(status) && (
                    <Text style={s.muted}>{freshnessNote(status)}</Text>
                  )}
                  {!!status.storedAdverts && (
                    <Text style={s.muted}>{status.storedAdverts}</Text>
                  )}
                  <Text style={s.muted}>
                    Last complete collection · {status.lastSuccess ?? "Unknown"}
                  </Text>
                  <Text style={s.muted}>
                    Latest attempt · {status.latestAttempt ?? "Unknown"}
                  </Text>
                  <Text style={s.muted}>
                    Latest stored observation ·{" "}
                    {status.latestObservation ?? "Unknown"}
                  </Text>
                </View>
              ))}
            </View>
          )}
        </>
      ) : (
        <Text accessibilityLiveRegion="polite" style={s.muted}>
          {loading ? "Checking source status…" : "No configured sources."}
        </Text>
      )}
    </View>
  );
}
