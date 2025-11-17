import React, { useEffect, useRef, useState } from "react";
import { Text, TextInput, View } from "react-native";
import { market, Advert, Profile } from "../marketplaceApi";
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
  const profileFields = (value: Omit<Profile, "id">) => ({ name: value.name, kind: value.kind, description: value.description });
  const profileDirty = JSON.stringify(profileFields(profileDraft)) !== JSON.stringify(profileFields(profile || emptyProfile));
  const profileValid = profileDraft.name.trim().length >= 2 && profileDraft.name.length <= 100 && profileDraft.description.length <= 2000;
  async function saveProfile() {
    return run(async () => {
      const r = await market.saveProfile(profileFields(profileDraft));
      setProfile(r.profile); setProfileDraft(r.profile); setProfileOpen(false);
    });
  }
  useEffect(() => {
    if (editing || !profileOpen) return;
    registerExitGuard({ dirty: () => profileDirty, canSave: () => profileValid, save: saveProfile,
      focus: () => profileName.current?.focus(),
      discard: () => { setProfileDraft(profile || emptyProfile); setProfileOpen(false); } });
    return () => registerExitGuard(null);
  }, [editing, profileOpen, profileDirty, profileValid, profileDraft, profile, registerExitGuard]);
  if (editing)
    return (
      <AdvertEditor
        registerExitGuard={registerExitGuard}
        requestExit={requestExit}
        initial={editing === "new" ? undefined : editing}
        busy={busy}
        onCancel={() => setEditing(null)}
        onSave={async (draft, base) => {
          let error: unknown;
          const saved = await run(async () => {
            try { await market.saveAdvert(draft, editing === "new" ? undefined : base || editing); }
            catch (cause) { error = cause; throw cause; }
            setEditing(null);
          });
          if (saved) void run(reload);
          return { ok: saved, error };
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
      {adverts.map((advert) => (
        <View key={advert.id} style={[s.card, { padding: 20, gap: 12 }]}>
          <Text style={[s.title, { fontSize: 19 }]}>{advert.advert.title}</Text>
          <Text aria-live="polite" style={s.muted}>
            {advert.hidden ? "HIDDEN AFTER REVIEW" : advert.state.toUpperCase()}{" "}
            · {money(advert.advert.rent_pln)} · {advert.advert.city}
          </Text>
          <View style={[s.row, { flexWrap: "wrap", gap: 8 }]}>
            <Button disabled={busy} outline onPress={() => requestExit(() => setEditing(advert))}>
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
              <Button outline onPress={() => requestExit(() => onOpenHome(advert.listing_id!))}>
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
