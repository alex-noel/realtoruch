import React, { useEffect, useRef, useState } from "react";
import { Platform, Text, TextInput, View } from "react-native";
import { market, Advert, Profile } from "../marketplaceApi";
import { api, getSessionRevision, SessionError } from "../api";
import { AdvertPreview } from "./AdvertPreview";
import { ownerMedia } from "./PhotoUploader";
import { s } from "../theme";
import { Button, Chip, Field, money } from "./UI";
import { AdvertEditor } from "./AdvertEditor";
import type { RegisterExitGuard, RequestExit, RentalDeskWork } from "./MarketplaceDialog";

export interface AdvertDeskProps extends RentalDeskWork {
  onOpenHome: (id: string) => void;
  registerExitGuard: RegisterExitGuard;
  requestExit: RequestExit;
}

const emptyProfile = { name: "", kind: "private" as const, description: "" };
type LoadState = "loading" | "ready" | "failed";

function savedTime(value?: string) {
  const timestamp = value ? Date.parse(value) : NaN;
  return Number.isFinite(timestamp)
    ? new Date(timestamp).toLocaleString("en-GB", { timeZone: "Europe/Warsaw" })
    : "Time unavailable";
}
export function AdvertDesk({
  run,
  busy,
  onOpenHome,
  registerExitGuard,
  requestExit,
}: AdvertDeskProps) {
  const profileName = useRef<React.ComponentRef<typeof TextInput>>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [profileDraft, setProfileDraft] =
    useState<Omit<Profile, "id">>(emptyProfile);
  const [profileOpen, setProfileOpen] = useState(false);
  const [adverts, setAdverts] = useState<Advert[]>([]);
  const [profileState, setProfileState] = useState<LoadState>("loading");
  const [advertsState, setAdvertsState] = useState<LoadState>("loading");
  const loads = useRef({ profile: 0, adverts: 0 });
  const mounted = useRef(true);
  const [editing, setEditing] = useState<Advert | "new" | null>(null);
  const [preview, setPreview] = useState<Advert | null>(null);
  const [verified, setVerified] = useState<boolean | null>(null);
  const [previewError, setPreviewError] = useState("");
  const [notice, setNotice] = useState("");
  const publishing = useRef(false);
  const [mediaReady, setMediaReady] = useState<boolean | null>(null);
  const [mediaRetry, setMediaRetry] = useState(0);
  const previewIds = JSON.stringify(preview?.advert.media_ids ?? []);
  useEffect(() => {
    if (!preview) return;
    const ids: string[] = JSON.parse(previewIds);
    const job = new AbortController();
    if (!ids.length) { setMediaReady(true); return () => job.abort(); }
    setMediaReady(null);
    Promise.all(ids.map(id => ownerMedia.status(id, job.signal)))
      .then(items => { if (!job.signal.aborted) setMediaReady(items.every(item => item.state === "ready")); })
      .catch(() => { if (!job.signal.aborted) setMediaReady(false); });
    return () => job.abort();
  }, [preview?.id, previewIds, mediaRetry]);
  useEffect(() => {
    let active = true;
    api.me().then(account => { if (active) setVerified(account.email_verified); }).catch(() => {});
    return () => { active = false; };
  }, []);
  const [appeal, setAppeal] = useState<Advert | null>(null);
  const [reason, setReason] = useState("");
  const [withdrawing, setWithdrawing] = useState<Advert | null>(null);
  const [actionError, setActionError] = useState("");
  const mutating = useRef(false);
  const actionOpener = useRef<HTMLElement | null>(null);
  const confirmation = useRef<React.ComponentRef<typeof View>>(null);
  useEffect(() => {
    mounted.current = true;
    void loadProfile();
    void reload();
    return () => {
      mounted.current = false;
      loads.current.profile++;
      loads.current.adverts++;
    };
  }, []);

  async function loadProfile() {
    const sequence = ++loads.current.profile, session = getSessionRevision();
    setProfileState("loading");
    try {
      const { profile: next } = await market.profile();
      if (!mounted.current || sequence !== loads.current.profile || session !== getSessionRevision()) return;
      setProfile(next);
      setProfileDraft(next || emptyProfile);
      setProfileOpen(!next);
      setProfileState("ready");
    } catch {
      if (mounted.current && sequence === loads.current.profile && session === getSessionRevision())
        setProfileState("failed");
    }
  }

  async function reload() {
    const sequence = ++loads.current.adverts, session = getSessionRevision();
    setAdvertsState("loading");
    try {
      const { items } = await market.adverts();
      if (!mounted.current || sequence !== loads.current.adverts || session !== getSessionRevision()) return;
      setAdverts(items);
      setAdvertsState("ready");
    } catch {
      if (mounted.current && sequence === loads.current.adverts && session === getSessionRevision())
        setAdvertsState("failed");
    }
  }
  const profileFields = (value: Omit<Profile, "id">) => ({ name: value.name, kind: value.kind, description: value.description });
  const profileDirty = JSON.stringify(profileFields(profileDraft)) !== JSON.stringify(profileFields(profile || emptyProfile));
  const profileValid = profileDraft.name.trim().length >= 2 && profileDraft.name.length <= 100 && profileDraft.description.length <= 2000;
  async function saveProfile() {
    return run(async () => {
      const r = await market.saveProfile(profileFields(profileDraft));
      setProfile(r.profile); setProfileDraft(r.profile); setProfileOpen(false); setProfileState("ready");
    });
  }
  useEffect(() => {
    if (editing || !profileOpen) return;
    registerExitGuard({ dirty: () => profileDirty, canSave: () => profileValid, save: saveProfile,
      focus: () => profileName.current?.focus(),
      discard: () => { setProfileDraft(profile || emptyProfile); setProfileOpen(false); } });
    return () => registerExitGuard(null);
  }, [editing, profileOpen, profileDirty, profileValid, profileDraft, profile, registerExitGuard]);

  useEffect(() => {
    if (withdrawing) confirmation.current?.focus();
  }, [withdrawing]);

  function prepareWithdrawal(advert: Advert) {
    if (busy || mutating.current) return;
    requestExit(() => {
      if (Platform.OS === "web" && document.activeElement instanceof HTMLElement)
        actionOpener.current = document.activeElement;
      setActionError("");
      setWithdrawing(advert);
    });
  }

  function cancelWithdrawal() {
    if (busy || mutating.current) return;
    setWithdrawing(null);
    setActionError("");
    const opener = actionOpener.current;
    if (opener?.isConnected) requestAnimationFrame(() => opener.focus({ preventScroll: true }));
  }

  async function withdraw() {
    if (!withdrawing || busy || mutating.current) return;
    const target = withdrawing, session = getSessionRevision();
    mutating.current = true;
    setActionError("");
    try {
      await run(async () => {
        try {
          const latest = await market.withdraw(target);
          if (!mounted.current || session !== getSessionRevision()) return;
          setAdverts(previous => previous.map(item => item.id === latest.id
            ? { ...item, ...latest } : item));
          setWithdrawing(null);
          setNotice(`Withdrawn ${target.advert.title}.`);
          await reload();
        } catch (error) {
          if (mounted.current && session === getSessionRevision())
            setActionError(error instanceof Error ? error.message : "Could not withdraw this advert.");
        }
      });
    } finally { mutating.current = false; }
  }

  async function submitAppeal() {
    if (!appeal || busy || mutating.current || reason.trim().length < 10) return;
    const target = appeal, session = getSessionRevision();
    mutating.current = true;
    setActionError("");
    try {
      await run(async () => {
        try {
          await market.appeal(target, reason.trim());
          if (!mounted.current || session !== getSessionRevision()) return;
          setAdverts(previous => previous.map(item => item.id === target.id
            ? { ...item, appeal_status: "pending" } : item));
          setAppeal(null);
          setReason("");
          setNotice(`Appeal submitted for ${target.advert.title}.`);
          await reload();
        } catch (error) {
          if (!mounted.current || session !== getSessionRevision()) return;
          if (error instanceof SessionError && error.code === "appeal_pending") {
            setAppeal(null);
            setNotice(`A review is already pending for ${target.advert.title}.`);
            setAdverts(previous => previous.map(item => item.id === target.id
              ? { ...item, appeal_status: "pending" } : item));
            await reload();
          } else {
            setActionError(error instanceof Error ? error.message : "Could not submit the appeal.");
          }
        }
      });
    } finally { mutating.current = false; }
  }
  async function publishPreview() {
    if (!preview || publishing.current || busy || verified === false || preview.hidden || mediaReady !== true) return;
    publishing.current = true; setPreviewError("");
    try {
      const ok = await run(async () => {
        try { await market.publish(preview); }
        catch (error) {
          if (error instanceof SessionError && error.code === "verification_required") setVerified(false);
          setPreviewError(error instanceof Error ? error.message : "Could not publish. Please try again.");
          throw error;
        }
      });
      if (ok) { setPreview(null); setNotice(`Published ${preview.advert.title}.`); void reload(); }
    } finally { publishing.current = false; }
  }
  async function refreshPreview() {
    if (!preview || busy) return;
    setPreviewError("");
    await run(async () => {
      try {
        const latest = (await market.adverts()).items.find(item => item.id === preview.id);
        if (!latest) { setPreviewError("This advert is no longer available."); return; }
        setMediaReady(null); setPreview(latest); setPreviewError("Latest advert loaded. Review it again before publishing.");
      } catch (error) {
        setPreviewError("Could not load the latest advert. Please try again.");
        throw error;
      }
    });
  }
  if (preview) return <View style={{ gap: 12 }}>
    <AdvertPreview draft={preview.advert} />
    <Text style={s.muted}>Status: {preview.state}{preview.hidden ? " · hidden after review" : ""}</Text>
    {verified === false && <Text accessibilityRole="alert" style={s.text}>Verify your email in Account: close this desk, open Account, then choose Send verification email. Your saved draft will be here when you return.</Text>}
    {preview.hidden && <Text accessibilityRole="alert" style={s.text}>This advert is hidden after review. Submit an appeal before publishing.</Text>}
    {mediaReady === null && <Text accessibilityRole="status" style={s.muted}>Checking saved photos…</Text>}
    {mediaReady === false && <><Text accessibilityRole="alert" style={s.text}>Some saved photos are unavailable. Retry or edit the draft to remove them before publishing.</Text><Button outline onPress={() => setMediaRetry(value => value + 1)}>Retry photo check</Button></>}
    {!!previewError && <><Text accessibilityRole="alert" style={s.text}>{previewError}</Text><Button outline disabled={busy} onPress={() => void refreshPreview()}>Refresh latest advert</Button></>}
    <Button busy={busy} busyLabel="Publishing…" disabled={verified === false || !!preview.hidden || mediaReady !== true} onPress={() => void publishPreview()}>Publish advert</Button>
    <Button outline disabled={busy} onPress={() => { setEditing(preview); setPreview(null); }}>Edit draft</Button>
    <Button outline disabled={busy} onPress={() => { setPreview(null); setPreviewError(""); }}>Back to adverts</Button>
  </View>;
  if (editing)
    return (
      <AdvertEditor
        registerExitGuard={registerExitGuard}
        requestExit={requestExit}
        initial={editing === "new" ? undefined : editing}
        busy={busy}
        onCancel={() => setEditing(null)}
        onSave={async (draft, base) => {
          let error: unknown, result: Advert | undefined;
          const saved = await run(async () => {
            try { result = await market.saveAdvert(draft, editing === "new" ? undefined : base || editing); }
            catch (cause) { error = cause; throw cause; }
          });
          return { ok: saved, saved: result, error };
        }}
        onFinished={(saved, keepEditing) => {
          setEditing(keepEditing ? saved : null);
          void reload();
        }}
      />
    );
  return (
    <>
      {!!notice && <Text accessibilityRole="status" style={s.text}>{notice}</Text>}
      <Text style={s.muted}>
        Publish a rental, keep its history, and speak with interested renters.
        Verify your account email before publishing.
      </Text>
      {profileState === "loading" && <Text accessibilityRole="status" style={s.text}>Loading advertiser profile…</Text>}
      {profileState === "failed" && (
        <View style={{ gap: 8, alignItems: "flex-start" }}>
          <Text accessibilityRole="alert" style={s.text}>Could not load advertiser profile.</Text>
          <Button outline disabled={busy} onPress={() => void loadProfile()}>Retry advertiser profile</Button>
        </View>
      )}
      {profileState === "ready" && (
        <>
          <Button
            outline
            expanded={profileOpen}
            onPress={() => profileOpen ? requestExit(() => setProfileOpen(false)) : setProfileOpen(true)}
          >
            {profile
              ? `${profile.name} · Edit profile`
              : "Create advertiser profile"}
          </Button>
          {profileOpen && (
            <View style={{ gap: 16 }}>
              <Field
                label="PUBLIC NAME"
                inputRef={profileName}
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
                disabled={busy || !profileValid}
                onPress={() => { void saveProfile(); }}
              >
                Save profile
              </Button>
            </View>
          )}
          {profile && (
            <Button disabled={busy} onPress={() => requestExit(() => setEditing("new"))}>
              Create rental advert
            </Button>
          )}
        </>
      )}
      {advertsState === "loading" && <Text accessibilityRole="status" style={s.text}>Loading your adverts…</Text>}
      {advertsState === "failed" && <Text accessibilityRole="alert" style={s.text}>Could not load your adverts.{adverts.length ? " Showing the last loaded adverts." : ""}</Text>}
      {advertsState !== "loading" && (
        <View style={{ alignItems: "flex-start" }}>
          <Button outline disabled={busy} onPress={() => void reload()}>
            {advertsState === "failed" ? "Retry adverts" : "Refresh adverts"}
          </Button>
        </View>
      )}
      {advertsState === "ready" && !adverts.length && <Text style={s.text}>No rental adverts yet.</Text>}
      {adverts.map((advert) => (
        <View key={advert.id} style={[s.card, { padding: 20, gap: 12 }]}>
          <Text accessibilityRole="header" style={[s.title, { fontSize: 19 }]}>{advert.advert.title}</Text>
          <Text aria-live="polite" style={s.muted}>
            {advert.state.toUpperCase()}{advert.hidden ? " · HIDDEN AFTER REVIEW" : ""}{" "}
            · {money(advert.advert.rent_pln)} · {advert.advert.city}
          </Text>
          <Text style={s.muted}>Last saved {savedTime(advert.updated_at)} · Europe/Warsaw</Text>
          {advert.appeal_status && (
            <Text style={s.text}>
              {advert.appeal_status === "pending" ? "Review pending" : "Appeal reviewed"}
            </Text>
          )}
          {advert.hidden && <Text style={s.muted}>Hidden after moderation review. Publishing remains unavailable while hidden.</Text>}
          <View style={[s.row, { flexWrap: "wrap", gap: 8 }]}>
            <Button disabled={busy} outline onPress={() => requestExit(() => setEditing(advert))}>
              Edit
            </Button>
            {advert.state === "published" && (
              <Button
                disabled={busy}
                outline
                onPress={() => prepareWithdrawal(advert)}
              >
                Withdraw
              </Button>
            )}
            {advert.state !== "published" && !advert.hidden && (
              <Button
                disabled={busy}
                onPress={() => requestExit(() => { setPreviewError(""); setNotice(""); setMediaReady(null); setPreview(advert); })}
              >
                Review and publish
              </Button>
            )}
            {advert.listing_id && !advert.hidden && (
              <Button outline onPress={() => requestExit(() => onOpenHome(advert.listing_id!))}>
                View home
              </Button>
            )}
            {advert.listing_id && advert.hidden && advert.appeal_status !== "pending" && (
              <Button
                outline
                onPress={() => {
                  setAppeal(advert);
                  setReason("");
                  setActionError("");
                }}
              >
                Appeal a review
              </Button>
            )}
          </View>
        </View>
      ))}
      {withdrawing && (
        <View ref={confirmation} role="region" accessibilityLabel="Confirm withdrawal" focusable tabIndex={-1}
          style={[s.card, { padding: 16, gap: 12 }]}
          onKeyDown={Platform.OS === "web" ? event => {
            if (event.nativeEvent.key === "Escape") {
              event.preventDefault(); event.stopPropagation(); cancelWithdrawal();
            }
          } : undefined}
        >
          <Text accessibilityRole="header" style={s.title}>Withdraw {withdrawing.advert.title}?</Text>
          <Text style={s.text}>{withdrawing.advert.address} · {withdrawing.advert.city}</Text>
          <Text style={s.muted}>The advert will stop appearing in discovery. Its saved history remains available.</Text>
          {actionError && <Text accessibilityRole="alert" style={s.text}>{actionError}</Text>}
          <View style={[s.row, { gap: 8, flexWrap: "wrap" }]}>
            <Button outline disabled={busy} onPress={cancelWithdrawal}>Keep published</Button>
            <Button variant="danger" busy={busy} busyLabel="Withdrawing…" onPress={() => void withdraw()}>Confirm withdrawal</Button>
          </View>
        </View>
      )}
      {appeal && (
        <View style={{ gap: 12 }}>
          <Text accessibilityRole="header" style={s.title}>Appeal for {appeal.advert.title}</Text>
          <Field
            label="WHY SHOULD THIS ADVERT BE RESTORED?"
            multiline
            value={reason}
            onChange={setReason}
          />
          <Button
            busy={busy}
            busyLabel="Submitting appeal…"
            disabled={reason.trim().length < 10 || reason.length > 1000}
            onPress={() => void submitAppeal()}
          >
            Submit appeal
          </Button>
          {actionError && <Text accessibilityRole="alert" style={s.text}>{actionError}</Text>}
          <Button outline disabled={busy} onPress={() => setAppeal(null)}>
            Cancel appeal
          </Button>
        </View>
      )}
    </>
  );
}
