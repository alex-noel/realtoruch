import React, { type ComponentRef, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Linking, Platform, ScrollView, Text, View } from "react-native";
import { getSessionRevision, SessionError } from "../api";
import { market, type Report } from "../marketplaceApi";
import { s } from "../theme";
import type { Listing } from "../types";
import { Button, Chip, Field, money } from "./UI";
import type { RentalDeskWork } from "./MarketplaceDialog";

type Identity = Awaited<ReturnType<typeof market.identity>>;
type Source = Identity["sources"][number];
type VisibilityDecision = "hide" | "restore" | "dismiss";
type Action =
  | { kind: VisibilityDecision }
  | { kind: "merge"; target: Listing; sources: Source[] }
  | { kind: "split"; source: Source };
type Decision = { report: Report; reason: string; action: Action };
type Queue = { state: "loading" | "ready" | "failed" | "denied"; reports: Report[] };
type Notice = { kind: "alert" | "status"; text: string };
type Active = () => boolean;

const actionLabels = {
  hide: "Hide home",
  restore: "Restore visibility",
  dismiss: "Dismiss report",
  merge: "Merge homes",
  split: "Separate source",
};

function reportAge(createdAt: string) {
  const timestamp = Date.parse(createdAt);
  if (!Number.isFinite(timestamp)) return "Report age unavailable";
  const minutes = Math.max(0, Math.floor((Date.now() - timestamp) / 60000));
  if (minutes < 1) return "Reported just now";
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  const [amount, unit] = days ? [days, "day"] : hours ? [hours, "hour"] : [minutes, "minute"];
  return `Reported ${amount} ${unit}${amount === 1 ? "" : "s"} ago`;
}

function describeHome(home: Listing) {
  const location = [home.address, home.city].filter(Boolean).join(", ");
  return `${home.title} · ${location} · Home ID ${home.id}`;
}

function describeSource(source: Source) {
  return `${source.name} · ${source.title} · ${source.address} · Source ID ${source.id}`;
}

export function ReviewDesk({ run, busy }: RentalDeskWork) {
  const [queue, setQueue] = useState<Queue>({ state: "loading", reports: [] });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [identityError, setIdentityError] = useState(false);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const revision = useRef(0);
  const inFlight = useRef(false);
  const confirmation = useRef<ComponentRef<typeof View>>(null);
  const opener = useRef<HTMLElement | null>(null);
  const report = queue.reports.find(item => item.id === selectedId);
  const draft = report ? reasons[report.id] ?? "" : "";
  const canDecide = !busy && draft.trim().length >= 10;

  async function work(operation: (active: Active) => Promise<void>) {
    if (inFlight.current) return;
    const expected = ++revision.current;
    const session = getSessionRevision();
    const active = () => revision.current === expected && getSessionRevision() === session;
    inFlight.current = true;
    try {
      await run(() => operation(active));
    } finally {
      if (revision.current === expected) inFlight.current = false;
    }
  }

  function clearRestrictedQueue(error: unknown) {
    if (!(error instanceof SessionError) || (error.status !== 401 && error.status !== 403)) return false;
    setQueue({ state: "denied", reports: [] });
    setSelectedId(null);
    setReasons({});
    setIdentity(null);
    setIdentityError(false);
    setDecision(null);
    setNotice({
      kind: "alert",
      text: error.status === 401
        ? "Your session ended. Sign in again to review reports."
        : "Moderator access is required to review reports.",
    });
    return true;
  }

  async function loadQueue(active: Active) {
    setQueue({ state: "loading", reports: [] });
    setIdentity(null);
    setIdentityError(false);
    try {
      const { items } = await market.reports();
      if (!active()) return;
      setQueue({ state: "ready", reports: items });
      setSelectedId(previous => items.some(item => item.id === previous) ? previous : items[0]?.id ?? null);
    } catch (error) {
      if (active() && !clearRestrictedQueue(error)) setQueue({ state: "failed", reports: [] });
    }
  }

  function reload() {
    void work(async active => {
      setNotice(null);
      await loadQueue(active);
    });
  }

  useEffect(() => {
    reload();
    return () => { revision.current++; inFlight.current = false; };
  }, []);

  function selectReport(id: string) {
    if (inFlight.current || decision) return;
    setSelectedId(id);
    setIdentity(null);
    setIdentityError(false);
    setNotice(null);
  }

  function loadIdentity(item: Report) {
    void work(async active => {
      setIdentityError(false);
      try {
        const data = await market.identity(item.listing.id);
        if (active()) setIdentity(data);
      } catch (error) {
        if (active() && !clearRestrictedQueue(error)) setIdentityError(true);
      }
    });
  }

  function prepare(item: Report, action: Action) {
    if (!canDecide || inFlight.current) return;
    if (Platform.OS === "web" && document.activeElement instanceof HTMLElement)
      opener.current = document.activeElement;
    setNotice(null);
    setDecision({ report: item, action, reason: draft.trim() });
  }

  function cancel() {
    if (inFlight.current) return;
    setDecision(null);
    setNotice(null);
    const previous = opener.current;
    opener.current = null;
    if (previous?.isConnected) requestAnimationFrame(() => previous.focus({ preventScroll: true }));
  }

  useLayoutEffect(() => {
    if (decision) confirmation.current?.focus();
  }, [decision]);

  function confirm() {
    if (!decision || inFlight.current) return;
    const { report: item, action, reason } = decision;
    void work(async active => {
      setSubmitting(true);
      setNotice(null);
      try {
        if (action.kind === "merge") await market.merge(item.listing.id, action.target.id, reason);
        else if (action.kind === "split") await market.split(item.listing.id, action.source.id, reason);
        else await market.review(item.id, action.kind, reason);
        if (!active()) return;
        setDecision(null);
        setReasons(previous => {
          const next = { ...previous };
          delete next[item.id];
          return next;
        });
        setNotice({ kind: "status", text: "Decision saved." });
        await loadQueue(active);
      } catch (error) {
        if (!active() || clearRestrictedQueue(error)) return;
        if (error instanceof SessionError && error.status === 409) {
          setDecision(null);
          setNotice({
            kind: "alert",
            text: error.code === "already_reviewed"
              ? "This report has already been reviewed."
              : "The decision could not be applied. Review the current evidence before trying again.",
          });
          await loadQueue(active);
        } else {
          setNotice({ kind: "alert", text: "Could not save the decision. Try again or cancel." });
        }
      } finally {
        if (active()) setSubmitting(false);
      }
    });
  }

  return (
    <>
      <Text style={s.muted}>Review source evidence before acting. Every decision is recorded.</Text>
      {!decision && notice && <Text accessibilityRole={notice.kind} style={s.text}>{notice.text}</Text>}
      {queue.state === "loading" && <Text accessibilityRole="status" style={s.text}>Loading reports…</Text>}
      {queue.state === "failed" && <Text accessibilityRole="alert" style={s.text}>Could not load reports.</Text>}
      {queue.state !== "loading" && !decision && (
        <View style={{ alignItems: "flex-start" }}>
          <Button outline disabled={busy} onPress={reload}>
            {queue.state === "ready" ? "Refresh queue" : "Retry queue"}
          </Button>
        </View>
      )}
      {queue.state === "ready" && queue.reports.length === 0 && <Text style={s.text}>No pending reports.</Text>}
      {decision && (
        <View
          ref={confirmation}
          role="region"
          accessibilityLabel="Confirm moderation decision"
          focusable
          tabIndex={-1}
          onKeyDown={Platform.OS === "web" ? event => {
            if (event.nativeEvent.key === "Escape") {
              event.preventDefault();
              event.stopPropagation();
              cancel();
            }
          } : undefined}
          style={[s.card, { padding: 16, gap: 10 }]}
        >
          <Text accessibilityRole="header" style={s.title}>{actionLabels[decision.action.kind]}</Text>
          <Text style={s.text}>{describeHome(decision.report.listing)}</Text>
          {decision.action.kind === "merge" ? (
            <>
              <Text style={s.text}>Merge into {describeHome(decision.action.target)}.</Text>
              <Text style={s.label}>SOURCES MOVING TO THE TARGET HOME</Text>
              {decision.action.sources.map(source => <Text key={source.id} style={s.text}>{describeSource(source)}</Text>)}
            </>
          ) : decision.action.kind === "split" ? (
            <Text style={s.text}>Move {describeSource(decision.action.source)} into a separate home.</Text>
          ) : (
            <Text style={s.text}>
              {decision.action.kind === "hide" ? "Hide this home and close this report."
                : decision.action.kind === "restore" ? "Remove the moderation hide from this home and close this report."
                : "Close this report and keep the home's current visibility."}
            </Text>
          )}
          <Text style={s.label}>DECISION REASON</Text>
          <Text style={s.text}>{decision.reason}</Text>
          {notice && <Text accessibilityRole={notice.kind} style={s.text}>{notice.text}</Text>}
          <View style={[s.row, { gap: 8, flexWrap: "wrap" }]}>
            <Button outline disabled={busy} onPress={cancel}>Cancel decision</Button>
            <Button
              variant={decision.action.kind === "hide" ? "danger" : "primary"}
              disabled={busy}
              busy={submitting}
              busyLabel="Saving decision…"
              onPress={confirm}
            >
              Confirm {actionLabels[decision.action.kind].toLowerCase()}
            </Button>
          </View>
        </View>
      )}
      {report && (
        <View style={{ display: decision ? "none" : "flex", gap: 12 }}>
          <ScrollView
            accessibilityLabel="Pending reports"
            nestedScrollEnabled
            keyboardShouldPersistTaps="handled"
            style={{ maxHeight: 144 }}
            contentContainerStyle={[s.row, { gap: 8, flexWrap: "wrap" }]}
          >
            {queue.reports.map((item, index) => (
              <Chip key={item.id} label={`Report ${index + 1} · ${item.listing.title}`} selected={item.id === report.id} onPress={() => selectReport(item.id)} />
            ))}
          </ScrollView>
          <View role="region" accessibilityLabel="Selected report" style={[s.card, { padding: 16, gap: 12 }]}>
            <Text accessibilityRole="header" style={[s.title, { fontSize: 19 }]}>{report.listing.title}</Text>
            <Text style={s.muted}>{reportAge(report.created_at)} · {report.hidden ? "Hidden" : "Visible"}</Text>
            <Text style={s.muted}>{report.listing.address} · {report.listing.city} · Report ID {report.id}</Text>
            <Text style={s.text}>{report.reason}</Text>
            <Text style={s.text}>{report.listing.description}</Text>
            {report.listing.risk_flags.map(flag => <Text key={flag.code} style={s.muted}>{flag.detail}</Text>)}
            <Field
              key={report.id}
              label="Review reason"
              multiline
              value={draft}
              onChange={reason => setReasons(previous => ({ ...previous, [report.id]: reason.slice(0, 1000) }))}
              helperText="Use 10–1000 characters. The reason is recorded with the decision."
            />
            <View style={[s.row, { gap: 8, flexWrap: "wrap" }]}>
              {(["hide", "restore", "dismiss"] as const).map(kind => (
                <Button key={kind} outline disabled={!canDecide} onPress={() => prepare(report, { kind })}>
                  {actionLabels[kind]}
                </Button>
              ))}
            </View>
            <View style={{ alignItems: "flex-start" }}>
              <Button outline disabled={busy} onPress={() => loadIdentity(report)}>
                {identityError ? "Retry duplicate identity" : "Review duplicate identity"}
              </Button>
            </View>
            {identityError && <Text accessibilityRole="alert" style={s.text}>Could not load duplicate identity evidence.</Text>}
            {identity && (
              <View style={{ gap: 12 }}>
                <Text style={s.muted}>Compare the original sources before changing identity.</Text>
                {identity.sources.map(source => (
                  <View key={source.id} style={{ gap: 8, alignItems: "flex-start" }}>
                    <Text style={s.text}>{source.name} · {source.title} · {source.address} · {money(source.rent_pln)}</Text>
                    <Button outline onPress={() => Linking.openURL(source.url)}>Open source</Button>
                    {identity.sources.length > 1 && (
                      <Button outline disabled={!canDecide} label={`Separate ${source.name} source`}
                        onPress={() => prepare(report, { kind: "split", source })}>
                        Separate this source
                      </Button>
                    )}
                  </View>
                ))}
                <Text style={s.label}>OTHER HOMES WITH SIMILAR SIZE AND ROOM COUNT</Text>
                <Text style={s.muted}>Similarity alone does not prove these are the same home.</Text>
                {identity.candidates.map(candidate => (
                  <View key={candidate.id} style={[s.card, { padding: 12, gap: 8, alignItems: "flex-start" }]}>
                    <Text style={s.text}>{candidate.title} · {candidate.address} · {money(candidate.rent_pln)}</Text>
                    <Text style={s.muted}>{candidate.sources.map(source => source.name).join(", ")}</Text>
                    <Button outline disabled={!canDecide} label={`Merge into ${candidate.title}`}
                      onPress={() => prepare(report, { kind: "merge", target: candidate, sources: identity.sources })}>
                      Merge into this home
                    </Button>
                  </View>
                ))}
              </View>
            )}
          </View>
        </View>
      )}
    </>
  );
}
