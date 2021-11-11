import React, { useEffect, useRef, useState } from "react";
import { AppState, Linking, Text, View } from "react-native";
import {
  market,
  Advert,
  Conversation,
  Draft,
  Profile,
  Report,
  Thread,
} from "../marketplaceApi";
import { c, s } from "../theme";
import { Listing } from "../types";
import { Button, Chip, Field, Panel, money } from "./UI";
import PropertyMap from "./PropertyMap";

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
    <Panel title="Your rental desk." wide onClose={onClose}>
      <View style={[s.row, { flexWrap: "wrap", gap: 8 }]}>
        <Chip
          label="My adverts"
          selected={mode === "adverts"}
          onPress={() => setMode("adverts")}
        />
        <Chip
          label="Messages"
          selected={mode === "messages"}
          onPress={() => setMode("messages")}
        />
        {moderator && (
          <Chip
            label="Review reports"
            selected={mode === "review"}
            onPress={() => setMode("review")}
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
        <Messages
          contact={contact}
          run={run}
          busy={busy}
          onOpenHome={onOpenHome}
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
        busy={busy}
        onCancel={() => setEditing(null)}
        onSave={(draft) =>
          run(async () => {
            await market.saveAdvert(
              draft,
              editing === "new" ? undefined : editing,
            );
            await reload();
            setEditing(null);
          })
        }
      />
    );
  return (
    <>
      <Text style={s.muted}>
        Publish a rental, keep its history, and speak with interested renters.
        Verify your account email before publishing.
      </Text>
      <Button outline onPress={() => setProfileOpen(!profileOpen)}>
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
          <View style={[s.row, { gap: 8 }]}>
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
          <Text style={s.muted}>
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
  busy,
  onCancel,
  onSave,
}: {
  initial?: Advert;
  busy: boolean;
  onCancel: () => void;
  onSave: (draft: Draft) => void;
}) {
  const [draft, setDraft] = useState<Draft>(
    () => initial?.advert || { ...emptyDraft },
  );
  const [pinned, setPinned] = useState(!!initial);
  const change = <K extends keyof Draft>(key: K, value: Draft[K]) =>
    setDraft((d) => ({ ...d, [key]: value }));
  return (
    <>
      <Text style={[s.title, { fontSize: 23 }]}>
        {initial ? "Edit rental" : "A new place to call home."}
      </Text>
      <Field
        label="TITLE"
        value={draft.title}
        onChange={(v) => change("title", v)}
      />
      <Field
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
          key={key}
          label={label}
          value={draft[key]}
          onChange={(v) => change(key, v)}
        />
      ))}
      <Text style={s.label}>
        TAP THE MAP TO PIN THE HOME{pinned ? " · LOCATION SET" : ""}
      </Text>
      <View style={{ height: 340 }}>
        <PropertyMap
          homes={[]}
          selected={null}
          onSelect={() => {}}
          city={draft.city}
          onPolygonChange={() => {}}
          pin={pinned ? [draft.lon, draft.lat] : undefined}
          onPinChange={([lon, lat]) => {
            setDraft((d) => ({ ...d, lon, lat }));
            setPinned(true);
          }}
        />
      </View>
      <View style={[s.row, { gap: 8, flexWrap: "wrap" }]}>
        {(["apartment", "house", "room"] as const).map((type) => (
          <Chip
            key={type}
            label={type}
            selected={draft.property_type === type}
            onPress={() => change("property_type", type)}
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
        label="PHOTO LINKS (HTTPS; ONE PER LINE)"
        multiline
        value={draft.images.join("\n")}
        onChange={(v) => change("images", v.split("\n"))}
      />
      <Text style={s.muted}>
        Use photos you own or have permission to publish. Empty fees mean
        unknown; zero means no charge.
      </Text>
      <Button
        disabled={
          busy ||
          !pinned ||
          draft.title.trim().length < 5 ||
          draft.description.trim().length < 20 ||
          !draft.rent_pln ||
          !draft.area_m2 ||
          !draft.rooms
        }
        onPress={() =>
          onSave({
            ...draft,
            images: draft.images.map((v) => v.trim()).filter(Boolean),
            amenities: draft.amenities.filter(Boolean),
          })
        }
      >
        {busy
          ? "Saving…"
          : initial?.state === "published"
            ? "Save and update advert"
            : "Save draft"}
      </Button>
      <Button outline disabled={busy} onPress={onCancel}>
        Back to adverts
      </Button>
    </>
  );
}
function Messages({
  contact,
  run,
  busy,
  onOpenHome,
}: Work & { contact?: Contact; onOpenHome: (id: string) => void }) {
  const [list, setList] = useState<Conversation[]>([]);
  const [thread, setThread] = useState<Thread | null>(null);
  const [body, setBody] = useState("");
  const [recipient, setRecipient] = useState(contact);
  const [profile, setProfile] = useState<Profile | null>(null);
  const delivery = useRef<{ body: string; target: string; id: string } | null>(
    null,
  );
  const selected = useRef<string | null>(null);
  async function reload() {
    setList((await market.conversations()).items);
  }
  useEffect(() => {
    run(reload);
  }, []);
  useEffect(() => {
    let active = true;
    if (recipient)
      run(async () => {
        const p = await market.advertiser(recipient.profile_id);
        if (active) setProfile(p.profile);
      });
    return () => {
      active = false;
    };
  }, [recipient?.profile_id]);
  useEffect(() => {
    const timer = setInterval(() => {
      if (
        AppState.currentState !== "active" ||
        (typeof document !== "undefined" &&
          document.visibilityState !== "visible")
      )
        return;
      market
        .conversations()
        .then((r) => setList(r.items))
        .catch(() => {});
      const id = selected.current;
      if (id)
        market
          .thread(id)
          .then((r) => {
            if (selected.current !== id) return;
            setThread((current) => {
              if (!current || current.id !== r.id) return r;
              const freshIds = new Set(r.items.map((item) => item.id));
              // Preserve explicitly loaded history when the polling windows
              // overlap. After a long offline gap, restart from the newest page.
              if (!current.items.some((item) => freshIds.has(item.id)))
                return r;
              const items = new Map(
                current.items.map((item) => [item.id, item]),
              );
              r.items.forEach((item) => items.set(item.id, item));
              return {
                ...r,
                next_cursor: current.next_cursor,
                items: [...items.values()].sort(
                  (a, b) =>
                    a.created_at.localeCompare(b.created_at) ||
                    a.id.localeCompare(b.id),
                ),
              };
            });
          })
          .catch(() => {});
    }, 15000);
    return () => clearInterval(timer);
  }, []);
  async function open(id: string) {
    selected.current = id;
    const r = await market.thread(id);
    if (selected.current !== id) return;
    setThread(r);
    setRecipient(undefined);
    setBody("");
    await market.read(id);
    await reload();
  }
  async function send() {
    const target = thread?.id || recipient?.id;
    if (!target) return;
    if (delivery.current?.body !== body || delivery.current.target !== target)
      delivery.current = {
        body,
        target,
        id: `${Date.now()}_${Math.random().toString(36).slice(2)}`,
      };
    const key = delivery.current.id;
    let id = thread?.id;
    if (id) await market.reply(id, body, key);
    else if (recipient) id = (await market.start(recipient.id, body, key)).id;
    delivery.current = null;
    if (id) await open(id);
  }
  return (
    <>
      {!thread && !recipient && (
        <Text style={s.muted}>
          Messages about homes advertised directly on Realtoruch appear here.
          For imported adverts, contact the advertiser through the original
          source.
        </Text>
      )}
      {recipient && (
        <View style={{ gap: 8 }}>
          <Text style={[s.title, { fontSize: 21 }]}>
            Write to {recipient.name}
          </Text>
          <Text style={s.muted}>
            {profile?.description || recipient.kind} · Advertiser type is
            self-declared.
          </Text>
        </View>
      )}
      {thread && (
        <>
          <Button
            outline
            onPress={() => {
              selected.current = null;
              setThread(null);
            }}
          >
            All conversations
          </Button>
          {thread.next_cursor && (
            <Button
              outline
              disabled={busy}
              onPress={() =>
                run(async () => {
                  const older = await market.thread(
                    thread.id,
                    thread.next_cursor!,
                  );
                  setThread((current) =>
                    current?.id === older.id
                      ? { ...older, items: [...older.items, ...current.items] }
                      : current,
                  );
                })
              }
            >
              Load older messages
            </Button>
          )}
          {thread.items.map((message) => (
            <View
              key={message.id}
              style={[
                s.card,
                {
                  padding: 16,
                  backgroundColor: message.mine ? c.pale : "white",
                  gap: 6,
                },
              ]}
            >
              <Text style={s.label}>
                {message.mine ? "YOU" : "REPLY"} ·{" "}
                {new Date(message.created_at).toLocaleString()}
              </Text>
              <Text style={s.text}>{message.body}</Text>
            </View>
          ))}
          {thread.blocked && (
            <Text style={s.muted}>This conversation is blocked.</Text>
          )}
          {(!thread.blocked || thread.can_unblock) && (
            <Button
              outline
              disabled={busy}
              onPress={() =>
                run(async () => {
                  await market.block(thread.id, !thread.blocked);
                  await open(thread.id);
                })
              }
            >
              {thread.blocked ? "Unblock conversation" : "Block conversation"}
            </Button>
          )}
        </>
      )}
      {(recipient || (thread && !thread.blocked)) && (
        <>
          <Field
            label="YOUR MESSAGE"
            multiline
            value={body}
            onChange={setBody}
          />
          <Button
            disabled={busy || !body.trim() || body.length > 4000}
            onPress={() => run(send)}
          >
            Send message
          </Button>
        </>
      )}
      {!thread &&
        list.map((item) => (
          <View key={item.id} style={[s.card, { padding: 16, gap: 12 }]}>
            <Text style={s.text}>
              {item.title}
              {item.unread_count ? ` · ${item.unread_count} unread` : ""}
            </Text>
            <Button
              outline
              disabled={busy}
              onPress={() => run(() => open(item.id))}
            >
              Open conversation
            </Button>
            <Button outline onPress={() => onOpenHome(item.listing_id)}>
              View home
            </Button>
          </View>
        ))}
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
