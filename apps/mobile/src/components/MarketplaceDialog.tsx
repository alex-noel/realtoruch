import React, { useEffect, useId, useRef, useState, useSyncExternalStore } from "react";
import { Linking, ScrollView, Text, View } from "react-native";
import { market, Advert, Draft, Profile, Report } from "../marketplaceApi";
import { captureSession, SessionError } from "../api";
import { c, s } from "../theme";
import { Listing } from "../types";
import { Button, Chip, Field, Panel, money } from "./UI";
import PropertyMap from "./DeferredPropertyMap";
import { readCoordinate } from "./coordinates";
import { MessagesPanel } from "./MessagesPanel";
import { InboxModel } from "./messagesState";
import { PhotoUploader, ownerMedia } from "./PhotoUploader";
import { PhotoQueue } from "./photoState";
import { MAX_PHOTOS } from "./photoSelection";
import { mergeAdvertEdits, photoLinks } from "./advertEdits";

type Mode = "adverts" | "messages" | "review";
type Contact = NonNullable<Listing["contact_adverts"]>[number];
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
const emptyProfile = { name: "", kind: "private" as const, description: "" };
export default function MarketplaceDialog({
  mode: initialMode,
  contact,
  onClose,
  onOpenHome,
}: {
  mode: Mode;
  contact?: Contact;
  onClose: () => void;
  onOpenHome: (id: string) => void;
}) {
  const [mode, setMode] = useState<Mode>(initialMode);
  const [moderator, setModerator] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [inbox] = useState(
    () =>
      new InboxModel(
        market,
        contact
          ? { kind: "advert", id: contact.id, title: contact.name }
          : null,
      ),
  );
  const messagesScroll = useRef<React.ComponentRef<typeof ScrollView>>(null);
  const onMessagesScroll = useRef<(() => void) | null>(null);
  const stopMessages = useRef<(() => void) | null>(null);
  const changeMode = (next: Mode) => {
    if (mode === "messages" && next !== mode) stopMessages.current?.();
    setMode(next);
  };
  useEffect(() => {
    let active = true;
    market
      .capabilities()
      .then((r) => {
        if (active) setModerator(r.moderator);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, []);
  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Panel
      title="Your rental desk."
      wide
      onClose={() => {
        stopMessages.current?.();
        onClose();
      }}
      inboxViewport={
        mode === "messages"
          ? {
              ref: messagesScroll,
              onChange: () => onMessagesScroll.current?.(),
            }
          : undefined
      }
    >
      <View style={[s.row, { flexWrap: "wrap", gap: 8 }]}>
        <Chip
          label="My adverts"
          selected={mode === "adverts"}
          onPress={() => changeMode("adverts")}
        />
        <Chip
          label="Messages"
          selected={mode === "messages"}
          onPress={() => changeMode("messages")}
        />
        {moderator && (
          <Chip
            label="Review reports"
            selected={mode === "review"}
            onPress={() => changeMode("review")}
          />
        )}
      </View>
      {!!error && (
        <Text accessibilityRole="alert" style={{ color: c.warning }}>
          {error}
        </Text>
      )}
      {mode === "adverts" ? (
        <AdvertDesk run={run} busy={busy} onOpenHome={onOpenHome} />
      ) : mode === "messages" ? (
        <MessagesPanel
          model={inbox}
          contact={contact}
          onOpenHome={onOpenHome}
          scroll={messagesScroll}
          onViewportChange={onMessagesScroll}
          stop={stopMessages}
        />
      ) : (
        <ReviewDesk run={run} busy={busy} />
      )}
    </Panel>
  );
}
type Work = {
  run: (action: () => Promise<void>) => Promise<void>;
  busy: boolean;
};
function AdvertDesk({
  run,
  busy,
  onOpenHome,
}: Work & { onOpenHome: (id: string) => void }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [profileDraft, setProfileDraft] =
    useState<Omit<Profile, "id">>(emptyProfile);
  const [profileOpen, setProfileOpen] = useState(false);
  const [adverts, setAdverts] = useState<Advert[]>([]);
  const [editing, setEditing] = useState<Advert | "new" | null>(null);
  const [appeal, setAppeal] = useState<Advert | null>(null);
  const [reason, setReason] = useState("");
  useEffect(() => {
    let active = true;
    run(async () => {
      const [p, a] = await Promise.all([market.profile(), market.adverts()]);
      if (active) {
        setProfile(p.profile);
        setProfileDraft(p.profile || emptyProfile);
        setProfileOpen(!p.profile);
        setAdverts(a.items);
      }
    });
    return () => {
      active = false;
    };
  }, []);
  async function reload() {
    setAdverts((await market.adverts()).items);
  }
  if (editing)
    return (
      <AdvertEditor
        initial={editing === "new" ? undefined : editing}
        onCancel={() => setEditing(null)}
        onSaved={(saved, keepEditing) => {
          setAdverts(current => [
            { ...saved, hidden: saved.hidden ?? current.find(advert => advert.id === saved.id)?.hidden },
            ...current.filter(advert => advert.id !== saved.id),
          ]);
          if (!keepEditing) setEditing(null);
        }}
      />
    );
  return (
    <>
      <Text style={s.muted}>
        Publish a rental, keep its history, and speak with interested renters.
        Verify your account email before publishing.
      </Text>
      <Button
        outline
        expanded={profileOpen}
        onPress={() => setProfileOpen(!profileOpen)}
      >
        {profile
          ? `${profile.name} · Edit profile`
          : "Create advertiser profile"}
      </Button>
      {profileOpen && (
        <View style={{ gap: 16 }}>
          <Field
            label="PUBLIC NAME"
            value={profileDraft.name}
            onChange={(name) => setProfileDraft((p) => ({ ...p, name }))}
          />
          <View style={[s.row, { gap: 8, flexWrap: "wrap" }]}>
            <Chip
              label="Private owner"
              selected={profileDraft.kind === "private"}
              onPress={() =>
                setProfileDraft((p) => ({ ...p, kind: "private" }))
              }
            />
            <Chip
              label="Agency"
              selected={profileDraft.kind === "agency"}
              onPress={() => setProfileDraft((p) => ({ ...p, kind: "agency" }))}
            />
          </View>
          <Field
            label="ABOUT YOU / YOUR AGENCY"
            value={profileDraft.description}
            multiline
            onChange={(description) =>
              setProfileDraft((p) => ({ ...p, description }))
            }
          />
          <Button
            disabled={busy || profileDraft.name.trim().length < 2}
            onPress={() =>
              run(async () => {
                const r = await market.saveProfile(profileDraft);
                setProfile(r.profile);
                setProfileOpen(false);
              })
            }
          >
            Save profile
          </Button>
        </View>
      )}
      {profile && (
        <Button disabled={busy} onPress={() => setEditing("new")}>
          Create rental advert
        </Button>
      )}
      {adverts.map((advert) => (
        <View key={advert.id} style={[s.card, { padding: 20, gap: 12 }]}>
          <Text style={[s.title, { fontSize: 19 }]}>{advert.advert.title}</Text>
          <Text aria-live="polite" style={s.muted}>
            {advert.hidden ? "HIDDEN AFTER REVIEW" : advert.state.toUpperCase()}{" "}
            · {money(advert.advert.rent_pln)} · {advert.advert.city}
          </Text>
          <View style={[s.row, { flexWrap: "wrap", gap: 8 }]}>
            <Button disabled={busy} outline onPress={() => setEditing(advert)}>
              Edit
            </Button>
            {advert.state === "published" ? (
              <Button
                disabled={busy}
                outline
                onPress={() =>
                  run(async () => {
                    await market.withdraw(advert);
                    await reload();
                  })
                }
              >
                Withdraw
              </Button>
            ) : (
              <Button
                disabled={busy}
                onPress={() =>
                  run(async () => {
                    await market.publish(advert);
                    await reload();
                  })
                }
              >
                Publish
              </Button>
            )}
            {advert.listing_id && !advert.hidden && (
              <Button outline onPress={() => onOpenHome(advert.listing_id!)}>
                View home
              </Button>
            )}
            {advert.listing_id && advert.hidden && (
              <Button
                outline
                onPress={() => {
                  setAppeal(advert);
                  setReason("");
                }}
              >
                Appeal a review
              </Button>
            )}
          </View>
        </View>
      ))}
      {appeal && (
        <View style={{ gap: 12 }}>
          <Field
            label="WHY SHOULD THIS ADVERT BE RESTORED?"
            multiline
            value={reason}
            onChange={setReason}
          />
          <Button
            disabled={busy || reason.trim().length < 10}
            onPress={() =>
              run(async () => {
                await market.appeal(appeal, reason);
                setAppeal(null);
              })
            }
          >
            Submit appeal
          </Button>
          <Button outline onPress={() => setAppeal(null)}>
            Cancel appeal
          </Button>
        </View>
      )}
    </>
  );
}
function AdvertEditor({
  initial,
  onCancel,
  onSaved,
}: {
  initial?: Advert;
  onCancel: () => void;
  onSaved: (saved: Advert, keepEditing: boolean) => void;
}) {
  const [base, setBase] = useState(initial);
  const [draft, setDraft] = useState<Draft>(() => initial?.advert || { ...emptyDraft });
  const [latitude, setLatitude] = useState(initial ? String(draft.lat) : "");
  const [longitude, setLongitude] = useState(initial ? String(draft.lon) : "");
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [notice, setNotice] = useState("");
  const [conflict, setConflict] = useState<{ latest?: Advert; loading: boolean } | null>(null);
  const [isCurrent] = useState(captureSession);
  const [queue] = useState(() => new PhotoQueue(ownerMedia, initial?.advert.media_ids, isCurrent));
  const photos = useSyncExternalStore(queue.subscribe, queue.snapshot);
  const controller = useRef<AbortController>(null);
  const saveInFlight = useRef(false);
  useEffect(() => {
    const job = new AbortController();
    controller.current = job;
    queue.activate();
    return () => {
      job.abort();
      queue.deactivate();
    };
  }, [queue]);

  const lat = readCoordinate(latitude, 90);
  const lon = readCoordinate(longitude, 180);
  const pinned = lat !== null && lon !== null;
  const invalidLat = !!latitude.trim() && lat === null;
  const invalidLon = !!longitude.trim() && lon === null;
  const locationErrorId = useId();
  const change = <K extends keyof Draft>(key: K, value: Draft[K]) =>
    setDraft((d) => ({ ...d, [key]: value }));
  const external = photoLinks(draft.images);
  const unresolved = photos.rows.some(row => row.phase !== "ready");
  const unverified = queue.hasUnverifiedSaved();
  const isPublished = base?.state === "published";

  async function loadLatest(id: string, signal: AbortSignal) {
    setConflict({ loading: true });
    setFeedback("");
    try {
      const response = await market.adverts(signal);
      if (signal.aborted || !isCurrent()) return;
      const latest = response.items.find(advert => advert.id === id);
      setConflict({ latest, loading: false });
      if (!latest) setFeedback("The latest version is unavailable. Your edits are still here.");
    } catch {
      if (signal.aborted || !isCurrent()) return;
      setConflict({ loading: false });
      setFeedback("Could not load the latest version. Your edits are still here.");
    }
  }

  function applyLatest(latest: Advert, merge: boolean) {
    if (!base) return;
    setDraft(merge ? mergeAdvertEdits(base.advert, draft, latest.advert) : latest.advert);
    if (!merge || lat === base.advert.lat) setLatitude(String(latest.advert.lat));
    if (!merge || lon === base.advert.lon) setLongitude(String(latest.advert.lon));
    queue.applyLatest(latest.advert.media_ids ?? [], merge);
    setBase(latest);
    onSaved(latest, true);
    setConflict(null);
    setFeedback("");
    setNotice(merge ? "Edits merged. Review the advert and photos before saving." : "Latest advert loaded.");
  }

  async function save() {
    const signal = controller.current?.signal;
    if (!signal || signal.aborted || !isCurrent() || !pinned || saveInFlight.current || conflict || queue.hasUnverifiedSaved()) return;
    const photoSave = queue.prepareSave();
    if ((isPublished && photoSave.unresolved) || external.length + queue.snapshot().rows.length > MAX_PHOTOS) return;
    saveInFlight.current = true;
    setSaving(true);
    setFeedback("");
    setNotice("");
    try {
      const saved = await market.saveAdvert({
        ...draft, lat, lon, images: external,
        amenities: draft.amenities.filter(Boolean), media_ids: photoSave.ids,
      }, base, signal);
      if (signal.aborted || !isCurrent()) return;
      setBase(saved);
      const done = await queue.finalizeSave(photoSave);
      if (signal.aborted || !isCurrent()) return;
      const keepEditing = photoSave.unresolved || !done.descriptionsSaved || !done.removalsSaved;
      if (photoSave.unresolved) setNotice("Draft saved with ready photos. Retry or remove the other uploads before publishing. Save again if more photos become ready.");
      if (!done.descriptionsSaved) setFeedback("The advert was saved, but some photo descriptions could not be saved. Save again to retry.");
      if (!done.removalsSaved && done.descriptionsSaved) setNotice("The advert was saved. Retry any unconfirmed photo removals here.");
      onSaved(saved, keepEditing);
    } catch (error) {
      if (signal.aborted || !isCurrent()) return;
      if (base && error instanceof SessionError && error.status === 409) {
        await loadLatest(base.id, signal);
      } else {
        setFeedback(error instanceof Error ? error.message : "Could not save your advert.");
      }
    } finally {
      saveInFlight.current = false;
      if (!signal.aborted && isCurrent()) setSaving(false);
    }
  }
  return (
    <>
      <Text style={[s.title, { fontSize: 23 }]}>
        {base ? "Edit rental" : "A new place to call home."}
      </Text>
      {conflict && (
        <View style={[s.card, { gap: 8, padding: 12 }]}>
          <Text accessibilityRole="alert" style={{ color: c.warning }}>
            This advert changed elsewhere. Review the latest version before saving.
          </Text>
          {conflict.loading ? <Text style={s.muted}>Loading latest advert…</Text> : conflict.latest ? (
            <>
              <Text style={s.muted}>
                Merge keeps the latest values where you did not edit them, prefers your edits where
                both versions changed, keeps new photos from both versions, and respects removals.
                Review the result before saving.
              </Text>
              <Button outline onPress={() => applyLatest(conflict.latest!, true)}>Merge my edits with latest</Button>
              <Button outline onPress={() => applyLatest(conflict.latest!, false)}>Reload latest and discard my edits</Button>
            </>
          ) : (
            <Button outline onPress={() => {
              if (base && controller.current) void loadLatest(base.id, controller.current.signal);
            }}>Try loading latest again</Button>
          )}
        </View>
      )}
      {!!feedback && <Text accessibilityRole="alert" style={{ color: c.warning }}>{feedback}</Text>}
      {!!notice && <Text aria-live="polite" style={s.muted}>{notice}</Text>}
      <Field
        disabled={saving}
        label="TITLE"
        value={draft.title}
        onChange={(v) => change("title", v)}
      />
      <Field
        disabled={saving}
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
          disabled={saving}
          key={key}
          label={label}
          value={draft[key]}
          onChange={(v) => change(key, v)}
        />
      ))}
      <Text style={s.label}>ENTER COORDINATES OR PIN THE HOME ON THE MAP</Text>
      <Field
        disabled={saving}
        label="Location latitude"
        value={latitude}
        onChange={setLatitude}
        numeric
        errorId={invalidLat ? locationErrorId : undefined}
      />
      <Field
        disabled={saving}
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
            if (saving) return;
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
            onPress={() => { if (!saving) change("property_type", type); }}
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
          disabled={saving}
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
        disabled={saving}
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
        disabled={saving}
        label="PHOTO LINKS (HTTPS; ONE PER LINE)"
        multiline
        value={draft.images.join("\n")}
        onChange={(v) => change("images", v.split("\n"))}
      />
      <PhotoUploader queue={queue} photos={photos} externalCount={external.length} disabled={saving} />
      {unverified ? (
        <Text aria-live="polite" style={s.muted}>Check or remove unavailable saved photos before saving.</Text>
      ) : unresolved ? (
        <Text aria-live="polite" style={s.muted}>
          Finish or remove unfinished uploads before publishing. Save draft keeps ready photos only;
          leaving this editor discards unfinished uploads.
        </Text>
      ) : null}
      <Text style={s.muted}>
        Use photos you own or have permission to publish. Empty fees mean
        unknown; zero means no charge.
      </Text>
      <Button
        disabled={
          saving || !!conflict || unverified || (isPublished && unresolved) ||
          external.length + photos.rows.length > MAX_PHOTOS ||
          !pinned ||
          draft.title.trim().length < 5 ||
          draft.description.trim().length < 20 ||
          !draft.rent_pln ||
          !draft.area_m2 ||
          !draft.rooms
        }
        onPress={() => void save()}
      >
        {saving ? "Saving…" : isPublished ? "Save and update advert" : "Save draft"}
      </Button>
      <Button outline disabled={saving} onPress={onCancel}>
        Back to adverts
      </Button>
    </>
  );
}
function ReviewDesk({ run, busy }: Work) {
  const [reports, setReports] = useState<Report[]>([]);
  const [reason, setReason] = useState("");
  const [identity, setIdentity] = useState<{
    id: string;
    data: Awaited<ReturnType<typeof market.identity>>;
  } | null>(null);
  async function reload() {
    setReports((await market.reports()).items);
  }
  useEffect(() => {
    run(reload);
  }, []);
  return (
    <>
      <Text style={s.muted}>
        Review source evidence before acting. Every decision is recorded. Hidden
        homes stay hidden when sources are collected again.
      </Text>
      <Field
        label="REVIEW REASON (REQUIRED FOR EACH DECISION)"
        multiline
        value={reason}
        onChange={setReason}
      />
      {reports.length === 0 && <Text style={s.text}>No pending reports.</Text>}
      {reports.map((report) => (
        <View key={report.id} style={[s.card, { padding: 20, gap: 12 }]}>
          <Text style={[s.title, { fontSize: 19 }]}>
            {report.listing.title}
          </Text>
          <Text style={s.text}>{report.reason}</Text>
          <Text style={s.muted}>
            {report.listing.address} · {report.listing.city} ·{" "}
            {report.hidden ? "Hidden" : "Visible"}
          </Text>
          <Text style={s.text}>{report.listing.description}</Text>
          <Button
            outline
            disabled={busy}
            onPress={() =>
              run(async () => {
                setIdentity({
                  id: report.listing.id,
                  data: await market.identity(report.listing.id),
                });
              })
            }
          >
            Review duplicate identity
          </Button>
          {identity?.id === report.listing.id && (
            <View style={{ gap: 12 }}>
              <Text style={s.muted}>
                Compare the original sources before changing identity. A merge
                retains favorites and seen prices. Separating a source retains
                both homes on existing shortlists.
              </Text>
              {identity.data.sources.map((source) => (
                <View key={source.id} style={{ gap: 8 }}>
                  <Text style={s.text}>
                    {source.name} · {source.address} · {money(source.rent_pln)}
                  </Text>
                  <Button outline onPress={() => Linking.openURL(source.url)}>
                    Open source
                  </Button>
                  {identity.data.sources.length > 1 && (
                    <Button
                      outline
                      disabled={busy || reason.trim().length < 10}
                      onPress={() =>
                        run(async () => {
                          await market.split(
                            report.listing.id,
                            source.id,
                            reason,
                          );
                          setIdentity(null);
                          setReason("");
                          await reload();
                        })
                      }
                    >
                      Separate this source into another home
                    </Button>
                  )}
                </View>
              ))}
              <Text style={s.label}>
                OTHER HOMES WITH SIMILAR SIZE AND ROOM COUNT
              </Text>
              {identity.data.candidates.map((candidate) => (
                <View
                  key={candidate.id}
                  style={[s.card, { padding: 16, gap: 8 }]}
                >
                  <Text style={s.text}>
                    {candidate.title} · {candidate.address} ·{" "}
                    {money(candidate.rent_pln)}
                  </Text>
                  <Text style={s.muted}>
                    {candidate.sources.map((source) => source.name).join(", ")}{" "}
                    · Similarity alone does not prove these are the same home.
                  </Text>
                  <Button
                    outline
                    disabled={busy || reason.trim().length < 10}
                    onPress={() =>
                      run(async () => {
                        await market.merge(
                          report.listing.id,
                          candidate.id,
                          reason,
                        );
                        setIdentity(null);
                        setReason("");
                        await reload();
                      })
                    }
                  >
                    Merge into this home
                  </Button>
                </View>
              ))}
            </View>
          )}
          {report.listing.risk_flags.map((flag) => (
            <Text key={flag.code} style={s.muted}>
              {flag.detail}
            </Text>
          ))}
          <View style={[s.row, { gap: 8, flexWrap: "wrap" }]}>
            {(["hide", "restore", "dismiss"] as const).map((action) => (
              <Button
                key={action}
                outline
                disabled={busy || reason.trim().length < 10}
                onPress={() =>
                  run(async () => {
                    await market.review(report.id, action, reason);
                    setReason("");
                    await reload();
                  })
                }
              >
                {action}
              </Button>
            ))}
          </View>
        </View>
      ))}
    </>
  );
}
