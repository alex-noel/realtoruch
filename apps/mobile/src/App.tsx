import React, { Suspense, lazy, useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  AppState,
  Linking,
  Platform,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
  useWindowDimensions,
} from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import NotificationInbox from "./components/NotificationInbox";
import { disablePush, listenForPush } from "./pushClient";
import type { NotificationInbox as Inbox, RentalNotification } from "./types";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";
import ArrowDownUp from "lucide-react-native/icons/arrow-down-up";
import ArrowRight from "lucide-react-native/icons/arrow-right";
import ArrowUpRight from "lucide-react-native/icons/arrow-up-right";
import Bell from "lucide-react-native/icons/bell";
import Bookmark from "lucide-react-native/icons/bookmark";
import ChevronDown from "lucide-react-native/icons/chevron-down";
import Code2 from "lucide-react-native/icons/code-xml";
import Compass from "lucide-react-native/icons/compass";
import Heart from "lucide-react-native/icons/heart";
import House from "lucide-react-native/icons/house";
import LayoutList from "lucide-react-native/icons/layout-list";
import MapIcon from "lucide-react-native/icons/map";
import MapPin from "lucide-react-native/icons/map-pin";
import Search from "lucide-react-native/icons/search";
import ShieldCheck from "lucide-react-native/icons/shield-check";
import SlidersHorizontal from "lucide-react-native/icons/sliders-horizontal";
import Sprout from "lucide-react-native/icons/sprout";
import TrendingUp from "lucide-react-native/icons/trending-up";
import User from "lucide-react-native/icons/user";
import X from "lucide-react-native/icons/x";
import { api, API_URL, request, restoreToken, setToken, subscribeSession, SessionState, SessionError, getSessionState, isCurrentAccessToken } from "./api";
import { AccountDialog, ResetPasswordDialog } from "./components/AccountDialog";
import { market } from "./marketplaceApi";
import {
  DEFAULT_FILTERS,
  Listing,
  SavedSearch,
} from "./types";
import { c, font, s } from "./theme";
import { Button, Chip, Field, Panel, money } from "./components/UI";
import { ListingCard } from "./components/ListingCard";
import PropertyMap from "./components/DeferredPropertyMap";
import {
  AuthDialog,
  CompareDialog,
  DetailDialog,
  FilterDialog,
} from "./components/Dialogs";
import Insights from "./components/Insights";
import SourceStatus from "./components/SourceStatus";
import { loadSeenIds, normalizeCity, resultAge, useListingSearch } from "./hooks/useListingSearch";
import {
  createLinkLifecycle,
  LINK_SCHEME,
  listingFromPush,
  parseIncomingLink,
  PUBLIC_WEB_URL,
  sanitizedWebSearch,
  subscribeToLinks,
  type LinkFeedback,
} from "./linking";

if (Platform.OS === "web") require("./web.css");
const MarketplaceDialog = lazy(() => import("./components/MarketplaceDialog"));

type Tab = "discover" | "saved" | "insights" | "searches" | "notifications";
const tabs = [
  { id: "discover", title: "Discover homes", icon: Compass },
  { id: "saved", title: "Saved homes", icon: Heart },
  { id: "insights", title: "Rent insights", icon: TrendingUp },
  { id: "searches", title: "Saved searches", icon: Bookmark },
  { id: "notifications", title: "Notifications", icon: Bell },
] as const;

export default function App() {
  return (
    <SafeAreaProvider>
      <SafeAreaView
        style={{ flex: 1, backgroundColor: c.bg }}
        edges={["top", "bottom"]}
      >
        <RentalApp />
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

function RentalApp() {
  const { width } = useWindowDimensions();
  const desktop = width >= 1100;
  const mobile = width < 680;
  const [tab, setTab] = useState<Tab>("discover");
  const [query, setQuery] = useState("");
  const [city, setCity] = useState(DEFAULT_FILTERS.city);
  const {
    filters, page, result, currentPage, loading, failed, sourceData,
    sourceLoading, sourceFailed, summary, changeFilters, goToPage,
    retrySearch, retrySources, refresh,
  } = useListingSearch(DEFAULT_FILTERS);
  const homes = result?.data.items ?? [];
  const total = result?.data.total ?? 0;
  const pageSize = result?.data.page_size ?? 24;
  const [view, setView] = useState<"split" | "list" | "map">("split");
  const [dialog, setDialog] = useState<
    | "auth"
    | "account"
    | "marketplace"
    | "filters"
    | "about"
    | "compare"
    | "save-search"
    | "report"
    | null
  >(null);
  const [detail, setDetail] = useState<Listing | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [favorites, setFavorites] = useState<Listing[]>([]);
  const favoriteIds = new Set(favorites.map((home) => home.id));
  const [searches, setSearches] = useState<SavedSearch[]>([]);
  const [comparison, setComparison] = useState<Listing[]>([]);
  const [user, setUser] = useState<string | null>(null);
  const [sessionState, setSessionState] = useState<SessionState>("signed-out");
  const [linkFeedback, setLinkFeedback] = useState<LinkFeedback | null>(null);
  const links = useRef<ReturnType<typeof createLinkLifecycle> | null>(null);
  const restoringLinkSession = useRef(true);
  const [marketMode, setMarketMode] = useState<"adverts" | "messages">(
    "adverts",
  );
  const [contact, setContact] = useState<
    NonNullable<Listing["contact_adverts"]>[number] | undefined
  >();
  const [resetToken, setResetToken] = useState<string | null>(null);
  const [toast, setToast] = useState("");
  const [searchName, setSearchName] = useState("My Kraków shortlist");
  const [reportReason, setReportReason] = useState("");
  const [formError, setFormError] = useState("");
  const [formBusy, setFormBusy] = useState(false);
  const [seenIds, setSeenIds] = useState<Set<string>>(new Set());
  const [guestSeenIds, setGuestSeenIds] = useState<Set<string>>(new Set());
  const [inbox, setInbox] = useState<Inbox>({
    items: [],
    unread_count: 0,
    page: 1,
    page_size: 30,
  });
  const sessionGeneration = useRef(0);
  const currentUser = useRef(user);
  currentUser.current = user;
  const detailRequest = useRef(0);
  const pendingFavorite = useRef<Listing | null>(null);
  const favoriteBusy = useRef(new Set<string>());

  async function retrySession() {
    const generation = sessionGeneration.current;
    try {
      const token = await restoreToken();
      if (token) {
        const me = await api.me();
        if (generation === sessionGeneration.current) { currentUser.current = me.email; setUser(me.email); }
      }
    } catch (error) {
      if (
        generation === sessionGeneration.current &&
        error instanceof SessionError &&
        (error.kind === "transient" || error.kind === "storage") &&
        getSessionState() !== "reauth"
      ) setSessionState("offline");
    }
  }
  useEffect(() => {
    const unsubscribe = subscribeSession((state) => {
      setSessionState(state);
      if (state === "reauth" || state === "signed-out" || state === "storage-cleanup") {
        sessionGeneration.current++;
        if (currentUser.current) {
          detailRequest.current++;
          setDetail(null);
          setSelected(null);
          setComparison([]);
          setContact(undefined);
          pendingFavorite.current = null;
        }
        favoriteBusy.current.clear();
        currentUser.current = null;
        setUser(null);
        setFavorites([]);
        setSearches([]);
        setInbox({ items: [], unread_count: 0, page: 1, page_size: 30 });
        setSeenIds(new Set());
        setDialog(current =>
          current === "account" || current === "marketplace" || current === "save-search" || current === "report"
            ? null
            : current,
        );
      }
    });
    let active = true;
    void retrySession().finally(() => {
      if (!active) return;
      restoringLinkSession.current = false;
      links.current?.resolveSession(!!currentUser.current);
    });
    return () => {
      active = false;
      sessionGeneration.current++;
      detailRequest.current++;
      unsubscribe();
    };
  }, []);
  useEffect(() => {
    if (Platform.OS === "web")
      document.title = "Realtoruch · A clearer way to rent";
  }, []);
  useEffect(() => {
    if (user) refreshAccount();
  }, [user]);
  useEffect(() => {
    let active = true;
    AsyncStorage.getItem("realtoruch.guest-seen.v1")
      .then((value) => {
        if (!active || !value) return;
        const ids: unknown = JSON.parse(value);
        if (Array.isArray(ids)) {
          const saved = ids.filter((id): id is string => typeof id === "string");
          setGuestSeenIds((current) => new Set([...saved, ...current].slice(-1000)));
        }
      })
      .catch(() => {});
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 4500);
    return () => clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    const timer = setInterval(() => {
      if (
        AppState.currentState === "active" &&
        (Platform.OS !== "web" || document.visibilityState === "visible")
      ) {
        refresh();
        if (currentUser.current) refreshAccount();
      }
    }, 15000);
    return () => clearInterval(timer);
  }, []);
  const stateIds = JSON.stringify(
    [...new Set((tab === "saved" ? favorites : homes).map((home) => home.id))].sort(),
  );
  useLayoutEffect(() => {
    if (!user || (tab !== "discover" && tab !== "saved") || stateIds === "[]") return;
    const controller = new AbortController();
    const generation = sessionGeneration.current;
    const requested = new Set<string>(JSON.parse(stateIds));
    loadSeenIds([...requested], controller.signal)
      .then((ids) => {
        if (!controller.signal.aborted && isCurrentAccount(generation, user)) {
          setSeenIds((current) => new Set([
            ...ids,
            ...[...current].filter((id) => requested.has(id)),
          ]));
        }
      })
      .catch(() => {});
    return () => controller.abort();
  }, [user, stateIds, tab]);
  useEffect(() => {
    if (!detail) return;
    const id = detail.id;
    if (user) {
      const controller = new AbortController();
      const generation = sessionGeneration.current;
      api
        .seen(id, controller.signal)
        .then(() => {
          if (controller.signal.aborted || !isCurrentAccount(generation, user)) return;
          setSeenIds((current) => new Set([...current, id]));
          refreshAccount();
        })
        .catch((e) => {
          if (!controller.signal.aborted && isCurrentAccount(generation, user)) setToast(e.message);
        });
      return () => controller.abort();
    }
    setGuestSeenIds((current) => new Set([...current, id]));
    AsyncStorage.getItem("realtoruch.guest-seen.v1")
      .then((value) => {
        const previous: string[] = value ? JSON.parse(value) : [];
        return AsyncStorage.setItem(
          "realtoruch.guest-seen.v1",
          JSON.stringify([...new Set([...previous, id])].slice(-1000)),
        );
      })
      .catch(() => {});
  }, [detail?.id, detail?.rent_pln, user]);
  useEffect(() => {
    const lifecycle = createLinkLifecycle({
      async navigate(destination, isCurrent) {
        if (destination.type === "notifications") {
          ++detailRequest.current;
          setDetail(null);
          setDialog(null);
          setTab("notifications");
          return;
        }
        const owner = currentUser.current;
        const accountGeneration = sessionGeneration.current;
        const stillCurrent = () =>
          isCurrent() &&
          (destination.type !== "saved-listing" ||
            (!!owner && currentUser.current === owner && sessionGeneration.current === accountGeneration));
        const listingId = destination.type === "advert"
          ? (await market.publicAdvert(destination.id)).listing_id
          : destination.id;
        if (!stillCurrent()) return;
        if (listingFromPush(listingId).type !== "listing")
          throw new SessionError("http", "This home is unavailable.", 404);
        const home = await api.detail(listingId);
        if (!stillCurrent()) return;
        if (destination.type === "saved-listing") {
          const saved = await api.favorites();
          if (!stillCurrent()) return;
          if (!saved.items.some((favorite) => favorite.id === home.id))
            throw new SessionError("http", "This home is unavailable in your saved homes.", 404);
          setTab("saved");
        }
        setDialog(null);
        openHome(home, false);
      },
      async consume(action) {
        if (action.type === "verify-account") {
          await api.verifyAccount(action.token);
          return "Email verified. You can return to your account.";
        }
        setTab("notifications");
        const endpoint = action.type === "confirm-email" ? "confirm" : "unsubscribe";
        await request(
          `/v1/notifications/email/${endpoint}`,
          { method: "POST", body: JSON.stringify({ token: action.token }) },
          false,
          false,
        );
        return endpoint === "confirm"
          ? "Email alerts are enabled. New matches and lower prices on liked homes will arrive by email."
          : "Email alerts are disabled. Your saved homes and in-app notifications are still available.";
      },
      reset(token) {
        if (token) {
          ++detailRequest.current;
          setDetail(null);
          setDialog(null);
        }
        setResetToken(token);
      },
      showLogin: () => setDialog("auth"),
      feedback: setLinkFeedback,
      error(error) {
        if (error instanceof SessionError && error.kind !== "superseded" && error.kind !== "transient") {
          return { message: error.message, retryable: false };
        }
        return { message: "Could not open this link. Check your connection and try again.", retryable: true };
      },
    });
    links.current = lifecycle;

    const web = Platform.OS === "web";
    const origins = {
      scheme: LINK_SCHEME,
      publicWebUrl: PUBLIC_WEB_URL,
      browserOrigin: web ? window.location.origin : undefined,
    };
    const auth = () =>
      currentUser.current ? "authenticated" : restoringLinkSession.current ? "restoring" : "guest";
    const receive = (url: string) =>
      lifecycle.receive(parseIncomingLink(url, origins), auth());
    let stopLinks: (() => void) | undefined;
    if (web) {
      const { href, origin, pathname, search, hash } = window.location;
      const cleaned = sanitizedWebSearch(search, hash);
      if (cleaned !== null) window.history.replaceState(null, "", origin + pathname + cleaned);
      receive(href);
    } else {
      stopLinks = subscribeToLinks(Linking, receive);
    }
    const stopPush = listenForPush((id) => {
      lifecycle.receive(listingFromPush(id), auth());
    }, () => {
      if (currentUser.current) refreshAccount();
      refresh();
    });
    return () => {
      lifecycle.close();
      links.current = null;
      stopLinks?.();
      stopPush();
    };
  }, []);
  useEffect(() => {
    if (user) links.current?.resolveSession(true);
  }, [user]);

  function applyText(nextCity: string, nextQuery: string, debounce = false) {
    const cityChanged = normalizeCity(nextCity) !== filters.city;
    changeFilters({
      ...filters,
      city: nextCity,
      q: nextQuery,
      district: cityChanged ? "" : filters.district,
      polygon: cityChanged ? undefined : filters.polygon,
    }, debounce);
  }
  function isCurrentAccount(generation: number, email: string | null) {
    return generation === sessionGeneration.current && currentUser.current === email;
  }
  async function refreshAccount() {
    const expected = currentUser.current;
    const generation = sessionGeneration.current;
    if (!expected) return;
    try {
      const [saved, searches, notifications] = await Promise.all([
        api.favorites(),
        api.searches(),
        api.notifications(),
      ]);
      if (!isCurrentAccount(generation, expected)) return;
      setFavorites(saved.items);
      setSearches(searches.items);
      setInbox((previous) => ({
        ...notifications,
        page: previous.page,
        items: [
          ...notifications.items,
          ...previous.items.filter(
            (item) =>
              !notifications.items.some((newer) => newer.id === item.id),
          ),
        ],
      }));
    } catch (e) {
      if (isCurrentAccount(generation, expected)) setToast((e as Error).message);
    }
  }
  async function toggleFavorite(home: Listing) {
    if (!user) {
      pendingFavorite.current = home;
      setDialog("auth");
      return;
    }
    if (favoriteBusy.current.has(home.id)) return;
    favoriteBusy.current.add(home.id);
    const generation = sessionGeneration.current;
    const saved = favoriteIds.has(home.id);
    try {
      await api.favorite(home.id, !saved);
      if (!isCurrentAccount(generation, user)) return;
      setFavorites((prev) =>
        saved ? prev.filter((item) => item.id !== home.id) : [...prev, home],
      );
      setToast(
        saved
          ? "Removed from your shortlist."
          : "A good find. Saved to your shortlist.",
      );
    } catch (e) {
      if (isCurrentAccount(generation, user)) setToast((e as Error).message);
    } finally {
      if (isCurrentAccount(generation, user)) favoriteBusy.current.delete(home.id);
    }
  }
  async function signedIn(token: string, email: string) {
    if (!isCurrentAccessToken(token)) return;
    if (pendingFavorite.current) {
      const home = pendingFavorite.current;
      pendingFavorite.current = null;
      await api.favorite(home.id, true);
    }
    if (!isCurrentAccessToken(token)) return;
    sessionGeneration.current++;
    currentUser.current = email;
    setSeenIds(new Set());
    setUser(email);
  }
  function openHome(home: Listing, hydrate = true) {
    const request = ++detailRequest.current;
    setSelected(home.id);
    setDetail(home);
    if (!hydrate) return;
    api
      .detail(home.id)
      .then((value) => {
        if (request === detailRequest.current) setDetail(value);
      })
      .catch((e) => {
        if (request === detailRequest.current) setToast(e.message);
      });
  }
  function toggleCompare(home: Listing) {
    if (comparison.some((item) => item.id === home.id))
      setComparison((prev) => prev.filter((item) => item.id !== home.id));
    else if (comparison.length < 3) setComparison((prev) => [...prev, home]);
    else setToast("Compare up to three homes at a time.");
  }
  function openDialog(value: typeof dialog) {
    setFormError("");
    setDialog(value);
  }
  async function submitSearch() {
    setFormBusy(true);
    setFormError("");
    try {
      await api.saveSearch(searchName.trim(), filters);
      await refreshAccount();
      setDialog(null);
      setToast("Search saved. New matches will appear in Notifications.");
    } catch (e) {
      setFormError((e as Error).message);
    } finally {
      setFormBusy(false);
    }
  }
  async function submitReport() {
    if (!detail) return;
    setFormBusy(true);
    setFormError("");
    try {
      await api.report(detail.id, reportReason.trim());
      setDialog(null);
      setReportReason("");
      setToast("Your report was saved for review.");
    } catch (e) {
      setFormError((e as Error).message);
    } finally {
      setFormBusy(false);
    }
  }
  const showMap =
    tab === "discover" && view !== "list" && (desktop || view === "map");
  const showList = tab === "saved" || view !== "map";
  const visibleHomes = tab === "saved" ? favorites : homes;
  const activeFilterCount =
    Number(!!filters.polygon) +
    Number(!!filters.max_price) +
    Number(!!filters.min_price) +
    Number(!!filters.rooms) +
    Number(!!filters.district) +
    Number(!!filters.amenity) +
    Number(!!filters.min_area) +
    Number(!!filters.max_area) +
    Number(filters.property_type !== "all");
  const nav = (compact = false) =>
    tabs.map(({ id, title, icon: Icon }) => (
      <Pressable
        key={id}
        accessibilityRole="button"
        accessibilityLabel={title}
        accessibilityState={{ selected: tab === id }}
        {...(Platform.OS === "web"
          ? { "aria-current": tab === id ? "page" : undefined }
          : {})}
        onPress={() => setTab(id)}
        style={[
          s.row,
          {
            gap: 13,
            padding: compact ? 12 : 15,
            maxWidth: "100%",
            borderLeftWidth: compact ? 0 : 2,
            borderLeftColor: tab === id ? "#BCCDA4" : "transparent",
            backgroundColor:
              tab === id ? (compact ? c.pale : "#29483B") : "transparent",
          },
        ]}
      >
        <Icon
          size={18}
          color={compact ? c.green : tab === id ? "#E5EBD8" : "#90A599"}
        />
        {(!compact || !mobile) && (
          <Text
            style={{
              color: compact ? c.ink : tab === id ? "#F4F6EA" : "#AABBB0",
              fontSize: 12,
              fontWeight: tab === id ? "600" : "400",
              fontFamily: font,
              flexShrink: 1,
            }}
          >
            {title}
          </Text>
        )}
        {id === "notifications" && inbox.unread_count > 0 ? (
          <Text style={{ color: compact ? c.green : "#B6C7A7", fontSize: 11 }}>
            {inbox.unread_count}
          </Text>
        ) : null}
        {id === "saved" && favorites.length > 0 && (
          <Text style={{ color: compact ? c.green : "#B6C7A7", fontSize: 11 }}>
            {favorites.length}
          </Text>
        )}
      </Pressable>
    ));

  return (
    <View style={{ flex: 1, backgroundColor: c.bg, flexDirection: "row" }}>
      <StatusBar style="dark" />
      {(sessionState === "offline" || sessionState === "reauth" || sessionState === "logout-retry" || sessionState === "storage-cleanup") && (
        <View style={{ position: "absolute", top: 0, left: 0, right: 0, zIndex: 100, backgroundColor: c.bg, padding: 12 }}>
          <Text accessibilityRole="alert" style={s.text}>
            {sessionState === "reauth" ? "Your session ended. Sign in again." : sessionState === "logout-retry" ? "Sign out could not be confirmed. Open your account to retry." : sessionState === "storage-cleanup" ? "Signed out, but local secure storage could not be cleared. Sign in again to replace it." : "Session unavailable. Check your connection and retry."}
          </Text>
          {sessionState === "offline" && <Button onPress={() => void retrySession()}>Retry session</Button>}
          {sessionState === "reauth" && <Button onPress={() => setDialog("auth")}>Sign in</Button>}
        </View>
      )}
      {desktop && (
        <View
          style={{
            width: 208,
            backgroundColor: "#17382D",
            paddingTop: 34,
            paddingBottom: 24,
            justifyContent: "space-between",
          }}
        >
          <View>
            <View
              style={[
                s.row,
                { gap: 9, paddingHorizontal: 25, marginBottom: 52 },
              ]}
            >
              <House size={27} strokeWidth={1.5} color="#DFE8CB" />
              <Text
                style={{
                  fontFamily: font,
                  color: "#F5F5E9",
                  fontSize: 23,
                  fontWeight: "600",
                  letterSpacing: -1,
                  flexShrink: 1,
                }}
              >
                realtoruch<Text style={{ color: "#B7CA9E" }}>.</Text>
              </Text>
            </View>
            <Text
              style={[
                s.label,
                {
                  color: "#A2BAAC",
                  marginLeft: 28,
                  marginBottom: 15,
                  fontSize: 9,
                },
              ]}
            >
              YOUR NEXT CHAPTER
            </Text>
            <View style={{ gap: 4, paddingHorizontal: 12 }}>{nav()}</View>
          </View>
          <View style={{ paddingHorizontal: 25, gap: 24 }}>
            <View style={{ padding: 18, backgroundColor: "#254638", gap: 12 }}>
              <Sprout size={24} color="#C8D6B0" />
              <Text
                style={{
                  color: "#DCE5CE",
                  fontSize: 15,
                  lineHeight: 21,
                  fontFamily: font,
                }}
              >
                Less searching.{"\n"}More living.
              </Text>
              <Text
                style={{
                  color: "#95AB9B",
                  fontSize: 11,
                  lineHeight: 18,
                  fontFamily: font,
                }}
              >
                One place for a clearer view of the rental market.
              </Text>
            </View>
            <Pressable
              onPress={() => Linking.openURL(API_URL + "/docs")}
              accessibilityRole="link"
              style={[s.row, { gap: 10 }]}
            >
              <Code2 size={16} color="#A6B8A7" />
              <Text style={{ color: "#A6B8A7", fontSize: 11 }}>
                Free public API
              </Text>
              <ArrowUpRight size={12} color="#A6B8A7" />
            </Pressable>
            <View style={{ height: 1, backgroundColor: "#355143" }} />
            <Text style={{ color: "#A2BAAC", fontSize: 10 }}>
              Made for finding home.
            </Text>
          </View>
        </View>
      )}
      <View style={{ flex: 1, minWidth: 0 }}>
        <View
          style={[
            s.row,
            {
              minHeight: 76,
              paddingVertical: 12,
              paddingHorizontal: mobile ? 20 : 36,
              borderBottomWidth: 1,
              borderColor: c.line,
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: 12,
            },
          ]}
        >
          <View style={[s.row, { gap: 10 }]}>
            {!desktop ? (
              <House size={22} color={c.green} />
            ) : (
              <View
                style={{ width: 6, height: 6, backgroundColor: c.orange }}
              />
            )}
            <Text
              style={[
                s.text,
                { fontWeight: "500", fontSize: mobile ? 13 : 12 },
              ]}
            >
              {desktop ? "A clearer way to rent." : "realtoruch."}
            </Text>
          </View>
          <View style={[s.row, { gap: mobile ? 12 : 26 }]}>
            {summary?.demo && (
              <View
                style={{
                  backgroundColor: c.cream,
                  paddingHorizontal: 9,
                  paddingVertical: 5,
                }}
              >
                <Text
                  style={[
                    s.label,
                    { color: "#735B39", fontSize: 9, letterSpacing: 0.7 },
                  ]}
                >
                  DEMO CATALOG
                </Text>
              </View>
            )}
            {!mobile && (
              <Pressable
                accessibilityRole="button"
                onPress={() => openDialog("about")}
              >
                <Text style={[s.muted, { fontSize: 12 }]}>How it works</Text>
              </Pressable>
            )}
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={user ? "Account" : "Sign in"}
              onPress={() => setDialog(user ? "account" : "auth")}
              style={[s.row, { gap: 8 }]}
            >
              <User size={17} color={c.ink} />
              {!mobile && (
                <Text style={[s.text, { fontSize: 12 }]}>
                  {user ? "Account" : "Sign in"}
                </Text>
              )}
            </Pressable>
          </View>
        </View>
        {!desktop && (
          <View
            style={[
              s.row,
              {
                borderBottomWidth: 1,
                borderColor: c.line,
                justifyContent: "space-around",
                flexWrap: "wrap",
                backgroundColor: "white",
              },
            ]}
          >
            {nav(true)}
          </View>
        )}
        <ScrollView
          contentContainerStyle={{
            paddingHorizontal: mobile ? 18 : 36,
            paddingTop: mobile ? 26 : 34,
            paddingBottom: 50,
            gap: 26,
          }}
          keyboardShouldPersistTaps="handled"
        >
          {linkFeedback && (
            <View style={[s.card, { padding: 14, gap: 8, alignItems: "flex-start" }]}>
              <Text accessibilityRole="alert" style={s.text}>{linkFeedback.message}</Text>
              <View style={[s.row, { gap: 8, flexWrap: "wrap" }]}>
                {linkFeedback.retry && <Button onPress={linkFeedback.retry}>Retry link</Button>}
                <Button outline onPress={() => setLinkFeedback(null)}>Dismiss link message</Button>
              </View>
            </View>
          )}
          {tab === "notifications" ? (
            <NotificationInbox
              user={user}
              inbox={inbox}
              onSignIn={() => setDialog("auth")}
              onOpen={(item: RentalNotification) => {
                const generation = sessionGeneration.current;
                return api.detail(item.listing_id)
                  .then((home) => {
                    if (isCurrentAccount(generation, user)) openHome(home);
                  })
                  .catch((e) => {
                    if (isCurrentAccount(generation, user)) setToast(e.message);
                  });
              }}
              onRead={async (id) => {
                const generation = sessionGeneration.current;
                try {
                  await api.readNotification(id);
                  if (isCurrentAccount(generation, user)) await refreshAccount();
                } catch (e) {
                  if (isCurrentAccount(generation, user)) setToast((e as Error).message);
                }
              }}
              onMore={async () => {
                const generation = sessionGeneration.current;
                try {
                  const next = await api.notifications(inbox.page + 1);
                  if (!isCurrentAccount(generation, user)) return;
                  setInbox((previous) => ({
                    ...next,
                    items: [
                      ...previous.items,
                      ...next.items.filter(
                        (item) =>
                          !previous.items.some((old) => old.id === item.id),
                      ),
                    ],
                  }));
                } catch (e) {
                  if (isCurrentAccount(generation, user)) setToast((e as Error).message);
                }
              }}
            />
          ) : tab === "insights" ? (
            <Insights
              city={filters.city}
              districts={summary?.districts || []}
            />
          ) : tab === "searches" ? (
            <View style={{ gap: 24 }}>
              <Text style={s.label}>KEEP AN EYE ON WHAT MATTERS</Text>
              <Text style={s.title}>Your saved searches.</Text>
              <Text style={s.muted}>
                Your saved area and filters run in the background. New homes
                appear in Notifications; existing matches start quietly.
              </Text>
              {!user ? (
                <Button onPress={() => setDialog("auth")}>
                  Sign in to save searches
                </Button>
              ) : !searches.length ? (
                <Text style={s.text}>
                  Find a search you like, then choose “Save search”.
                </Text>
              ) : (
                searches.map((search) => (
                  <View
                    key={search.id}
                    style={[s.card, { padding: 24, gap: 14 }]}
                  >
                    <Text style={[s.title, { fontSize: 20 }]}>
                      {search.name}
                    </Text>
                    <Text style={s.muted}>
                      {search.filters.city} · {search.new_matches} unread
                      matches{search.filters.polygon ? " · Drawn area" : ""}
                    </Text>
                    <View style={[s.row, { gap: 12, flexWrap: "wrap" }]}>
                      <Button
                        onPress={() => {
                          changeFilters(search.filters);
                          setCity(search.filters.city);
                          setQuery(search.filters.q);
                          setTab("discover");
                        }}
                      >
                        View matches
                      </Button>
                      <Button
                        outline
                        onPress={async () => {
                          try {
                            await api.deleteSearch(search.id);
                            await refreshAccount();
                          } catch (e) {
                            setToast((e as Error).message);
                          }
                        }}
                      >
                        Remove
                      </Button>
                    </View>
                  </View>
                ))
              )}
            </View>
          ) : (
            <>
              <View
                style={[
                  s.row,
                  {
                    justifyContent: "space-between",
                    alignItems: "flex-end",
                    gap: 20,
                  },
                ]}
              >
                <View style={{ flex: 1 }}>
                  <Text style={[s.label, { color: c.green }]}>
                    FIND YOUR PLACE, AT YOUR PACE
                  </Text>
                  <Text
                    accessibilityRole="header"
                    style={[
                      s.title,
                      {
                        fontSize: mobile ? 34 : 42,
                        marginTop: 12,
                        letterSpacing: -1.8,
                        lineHeight: mobile ? 39 : 49,
                      },
                    ]}
                  >
                    {tab === "saved"
                      ? "The ones that feel like home."
                      : "Good places. Clear choices."}
                  </Text>
                  <Text style={[s.muted, { marginTop: 12, fontSize: 13 }]}>
                    {tab === "saved"
                      ? "Your favorite homes, including delisted ones. We’ll notify you when a saved home returns at a lower price."
                      : "Rentals from across the web. Duplicates removed. Details made clear."}
                  </Text>
                </View>
                {desktop && tab === "discover" && (
                  <View
                    style={{ alignItems: "flex-end", gap: 9, paddingBottom: 2 }}
                  >
                    <View style={[s.row, { gap: 5 }]}>
                      <ShieldCheck size={15} color={c.green} />
                      <Text
                        style={[s.text, { fontSize: 11, fontWeight: "600" }]}
                      >
                        A little more transparency.
                      </Text>
                    </View>
                    <Text style={[s.muted, { fontSize: 10 }]}>
                      Original sources. Clear fees. Useful signals.
                    </Text>
                  </View>
                )}
              </View>
              {tab === "discover" && (
                <>
                  <View
                    style={[
                      s.card,
                      {
                        padding: mobile ? 12 : 8,
                        flexDirection: mobile ? "column" : "row",
                        gap: mobile ? 12 : 0,
                      },
                    ]}
                  >
                    <View
                      style={[
                        s.row,
                        {
                          paddingHorizontal: 16,
                          gap: 12,
                          width: mobile ? "100%" : 218,
                          borderRightWidth: mobile ? 0 : 1,
                          borderColor: c.line,
                        },
                      ]}
                    >
                      <MapPin size={18} color={c.green} />
                      <View style={{ flex: 1, gap: 4 }}>
                        <Text style={[s.label, { fontSize: 8 }]}>
                          WHERE DO YOU WANT TO LIVE?
                        </Text>
                        <TextInput
                          accessibilityLabel="City"
                          value={city}
                          onChangeText={(value) => {
                            setCity(value);
                            applyText(value, query, true);
                          }}
                          onSubmitEditing={() => applyText(city, query)}
                          style={{
                            fontFamily: font,
                            color: c.ink,
                            fontSize: 14,
                            paddingVertical: 5,
                            minHeight: 30,
                          }}
                          placeholder="City"
                          placeholderTextColor={c.muted}
                        />
                      </View>
                    </View>
                    <View
                      style={[
                        s.row,
                        { flex: 1, minWidth: 0, gap: 12, paddingHorizontal: 18 },
                      ]}
                    >
                      <Search size={18} color={c.muted} />
                      <TextInput
                        accessibilityLabel="Search neighborhood, street or keyword"
                        value={query}
                        onChangeText={(value) => {
                          setQuery(value);
                          applyText(city, value, true);
                        }}
                        onSubmitEditing={() => applyText(city, query)}
                        placeholder="Neighborhood, street, or a little inspiration…"
                        placeholderTextColor={c.muted}
                        style={{
                          flex: 1,
                          minWidth: 0,
                          fontFamily: font,
                          color: c.ink,
                          fontSize: 12,
                          minHeight: 48,
                        }}
                      />
                    </View>
                    <Button onPress={() => applyText(city, query)}>
                      Find a home →
                    </Button>
                  </View>
                  <View
                    style={[
                      s.row,
                      {
                        justifyContent: "space-between",
                        gap: 12,
                        flexWrap: "wrap",
                        marginTop: -12,
                      },
                    ]}
                  >
                    <View
                      style={[
                        s.row,
                        {
                          gap: 8,
                          flexWrap: "wrap",
                          flexShrink: 1,
                          width: mobile ? "100%" : undefined,
                        },
                      ]}
                    >
                      {filters.polygon ? (
                        <Chip
                          label="Drawn area ×"
                          selected
                          onPress={() =>
                            changeFilters({ ...filters, polygon: undefined })
                          }
                        />
                      ) : null}
                      <Chip
                        label="Direct offers"
                        selected={filters.advertiser === "private"}
                        onPress={() =>
                          changeFilters({
                            ...filters,
                            advertiser:
                              filters.advertiser === "private"
                                ? "all"
                                : "private",
                          })
                        }
                      />
                      <Chip
                        label="No commission"
                        selected={filters.no_commission}
                        onPress={() =>
                          changeFilters({
                            ...filters,
                            no_commission: !filters.no_commission,
                          })
                        }
                      />
                      <Chip
                        label="No risk signals"
                        selected={filters.hide_suspicious}
                        onPress={() =>
                          changeFilters({
                            ...filters,
                            hide_suspicious: !filters.hide_suspicious,
                          })
                        }
                      />
                      <Pressable
                        accessibilityRole="button"
                        accessibilityLabel="More filters"
                        onPress={() => openDialog("filters")}
                        style={[
                          s.outline,
                          { gap: 7, minHeight: 38, paddingVertical: 8 },
                        ]}
                      >
                        <SlidersHorizontal size={13} color={c.green} />
                        <Text style={[s.text, { fontSize: 12 }]}>
                          Filters
                          {activeFilterCount > 0
                            ? ` (${activeFilterCount})`
                            : ""}
                        </Text>
                      </Pressable>
                    </View>
                    <Pressable
                      accessibilityRole="button"
                      onPress={() => {
                        setSearchName(`My ${filters.city} shortlist`);
                        openDialog(user ? "save-search" : "auth");
                      }}
                      style={[s.row, { gap: 6, minHeight: 38 }]}
                    >
                      <Bookmark size={14} color={c.green} />
                      <Text style={[s.text, { fontSize: 12, color: c.green }]}>
                        Save search
                      </Text>
                    </Pressable>
                  </View>
                  <SourceStatus
                    key={filters.city}
                    city={filters.city}
                    data={sourceData}
                    loading={sourceLoading}
                    failed={sourceFailed}
                    onRetry={retrySources}
                  />
                  {summary && (
                    <View
                      style={[
                        s.row,
                        { backgroundColor: "#EBEEE4", padding: 15, gap: 14 },
                      ]}
                    >
                      <View
                        style={{
                          width: 31,
                          height: 31,
                          backgroundColor: "#DAE2CE",
                          alignItems: "center",
                          justifyContent: "center",
                        }}
                      >
                        <House size={16} color={c.green} />
                      </View>
                      <Text
                        style={[
                          s.text,
                          { fontSize: 12, flex: 1, lineHeight: 19 },
                        ]}
                      >
                        <Text style={{ fontWeight: "600" }}>
                          {summary.source_listings} adverts. {summary.homes}{" "}
                          homes. One clear view.
                        </Text>
                        {!mobile &&
                          `  We brought ${summary.duplicates_removed} duplicate adverts together, so you don't have to.`}
                      </Text>
                      {!mobile && (
                        <Text
                          style={[s.label, { color: c.green, fontSize: 8 }]}
                        >
                          {summary.demo
                            ? "SAMPLE DATA"
                            : "ACROSS CONNECTED SOURCES"}
                        </Text>
                      )}
                    </View>
                  )}
                </>
              )}
              <View
                style={[
                  s.row,
                  {
                    justifyContent: "space-between",
                    gap: 10,
                    flexWrap: "wrap",
                  },
                ]}
              >
                <View style={[s.row, { gap: 9 }]}>
                  <Text
                    aria-live="polite"
                    style={[s.text, { fontWeight: "600", fontSize: 16, flexShrink: 1 }]}
                  >
                    {tab === "saved"
                      ? `${favorites.length} saved homes`
                      : result
                        ? `${total} homes in ${filters.city || "Poland"}`
                        : `Homes in ${filters.city || "Poland"}`}
                  </Text>
                  {loading && tab === "discover" && (
                    <ActivityIndicator size="small" color={c.green} />
                  )}
                </View>
                {tab === "discover" && (
                  <View style={[s.row, { gap: 14, flexWrap: "wrap" }]}>
                    <Pressable
                      accessibilityRole="button"
                      accessibilityLabel="Change sort order"
                      onPress={() => {
                        const choices = [
                          "newest",
                          "price_asc",
                          "price_desc",
                          "area_desc",
                        ];
                        changeFilters({
                          ...filters,
                          sort: choices[
                            (choices.indexOf(filters.sort) + 1) % choices.length
                          ],
                        });
                      }}
                      style={[s.row, { gap: 5, minHeight: 40 }]}
                    >
                      <ArrowDownUp size={12} color={c.muted} />
                      <Text style={[s.muted, { fontSize: 11 }]}>
                        {
                          {
                            newest: "Newest first",
                            price_asc: "Lowest rent",
                            price_desc: "Highest rent",
                            area_desc: "Largest first",
                          }[filters.sort as "newest"]
                        }
                      </Text>
                    </Pressable>
                    <View
                      style={[s.row, { borderWidth: 1, borderColor: c.line }]}
                    >
                      {(
                        [
                          { mode: "list", Icon: LayoutList },
                          { mode: desktop ? "split" : "map", Icon: MapIcon },
                        ] as const
                      ).map(({ mode, Icon }) => (
                        <Pressable
                          key={mode}
                          onPress={() => setView(mode)}
                          accessibilityRole="button"
                          accessibilityLabel={
                            mode === "list" ? "List view" : "Map view"
                          }
                          accessibilityState={{
                            selected:
                              view === mode ||
                              (mode === "list" && !desktop && view === "split"),
                          }}
                          {...(Platform.OS === "web"
                            ? {
                                "aria-pressed":
                                  view === mode ||
                                  (mode === "list" && !desktop && view === "split"),
                              }
                            : {})}
                          style={{
                            padding: 10,
                            backgroundColor:
                              view === mode ||
                              (mode === "list" && !desktop && view === "split")
                                ? c.pale
                                : "white",
                          }}
                        >
                          <Icon size={15} color={c.green} />
                        </Pressable>
                      ))}
                    </View>
                  </View>
                )}
              </View>
              {tab === "discover" && (failed || (result && !currentPage)) && (
                <View style={[s.card, { padding: 14, gap: 8, alignItems: "flex-start" }]}>
                  {failed && (
                    <Text accessibilityRole="alert" style={s.text}>
                      Could not update homes. Check your connection and retry.
                    </Text>
                  )}
                  {result && (
                    <Text aria-live="polite" style={s.muted}>
                      Showing previous results loaded {resultAge(result.receivedAt)}.
                    </Text>
                  )}
                  {failed && <Button onPress={retrySearch}>Retry search</Button>}
                </View>
              )}
              {tab === "saved" && !user ? (
                <View style={[s.card, { padding: 40, gap: 20 }]}>
                  <Heart size={32} color={c.green} />
                  <Text style={s.title}>Good finds deserve a shortlist.</Text>
                  <Text style={s.muted}>
                    Sign in to keep homes you love across your devices.
                  </Text>
                  <Button onPress={() => setDialog("auth")}>
                    Sign in or create an account
                  </Button>
                </View>
              ) : (
                <View
                  style={{
                    flexDirection:
                      desktop && view === "split" ? "row" : "column",
                    gap: 22,
                    alignItems: "stretch",
                  }}
                >
                  {showList && (
                    <View
                      style={{
                        flex: desktop && showMap ? 1.22 : 1,
                        minWidth: 0,
                        gap: 16,
                      }}
                    >
                      {(tab === "saved" || (!loading && !failed)) && !visibleHomes.length && (
                        <View style={[s.card, { padding: 36, gap: 18 }]}>
                          <Search size={28} color={c.muted} />
                          <Text style={s.title}>
                            {tab === "saved"
                              ? "Your shortlist starts here."
                              : "A little more room to search."}
                          </Text>
                          <Text style={s.muted}>
                            {tab === "saved"
                              ? "Tap the heart on a home to keep it here."
                              : "No homes match these filters. Try a wider price range or another neighborhood."}
                          </Text>
                          <Button
                            outline
                            onPress={() => {
                              changeFilters(DEFAULT_FILTERS);
                              setCity(DEFAULT_FILTERS.city);
                              setQuery("");
                              setTab("discover");
                            }}
                          >
                            Explore all homes
                          </Button>
                        </View>
                      )}
                      {visibleHomes.map((home) => (
                        <ListingCard
                          key={home.id}
                          home={home}
                          selected={home.id === selected}
                          saved={favoriteIds.has(home.id)}
                          compared={comparison.some((h) => h.id === home.id)}
                          seen={(user ? seenIds : guestSeenIds).has(home.id)}
                          onOpen={() => openHome(home)}
                          onSave={() => toggleFavorite(home)}
                          onCompare={() => toggleCompare(home)}
                        />
                      ))}
                      {tab === "discover" && currentPage && total > pageSize && (
                        <View
                          style={[
                            s.row,
                            { justifyContent: "space-between", flexWrap: "wrap", gap: 8 },
                          ]}
                        >
                          <Button
                            outline
                            disabled={page === 1}
                            onPress={() => goToPage(page - 1)}
                          >
                            Previous
                          </Button>
                          <Text style={s.muted}>
                            Page {page} of {Math.ceil(total / pageSize)}
                          </Text>
                          <Button
                            outline
                            disabled={page * pageSize >= total}
                            onPress={() => goToPage(page + 1)}
                          >
                            Next
                          </Button>
                        </View>
                      )}
                    </View>
                  )}
                  {showMap && (
                    <View
                      style={{
                        flex: desktop && showList ? 1 : undefined,
                        minWidth: 0,
                        gap: 14,
                        alignSelf: "stretch",
                      }}
                    >
                      <View
                        style={{
                          height: mobile ? 470 : 570,
                          borderWidth: 1,
                          borderColor: c.line,
                          overflow: "hidden",
                        }}
                      >
                        <PropertyMap
                          homes={homes}
                          selected={selected}
                          onSelect={openHome}
                          city={filters.city}
                          polygon={filters.polygon}
                          onPolygonChange={(polygon) =>
                            changeFilters({ ...filters, polygon })
                          }
                        />
                        <View
                          pointerEvents="none"
                          style={{
                            position: "absolute",
                            bottom: 15,
                            left: 15,
                            backgroundColor: "#FFFFFFF2",
                            paddingVertical: 9,
                            paddingHorizontal: 12,
                          }}
                        >
                          <Text
                            style={[
                              s.text,
                              { fontSize: 10, fontWeight: "600" },
                            ]}
                          >
                            {homes.filter((h) => h.lat !== null).length} homes
                            on this page · approximate locations
                          </Text>
                        </View>
                      </View>
                      <Text style={[s.muted, { fontSize: 10 }]}>
                        Choose a price pin to explore a home.{" "}
                        {summary?.demo
                          ? "Map pins are illustrative sample locations."
                          : "Locations reflect the precision provided by each source."}
                      </Text>
                      <View style={[s.card, { padding: 22, gap: 10 }]}>
                        <Text style={s.label}>THE NEIGHBORHOOD PICTURE</Text>
                        <View
                          style={[s.row, { justifyContent: "space-between" }]}
                        >
                          <Text style={[s.title, { fontSize: 28 }]}>
                            {money(summary?.median_rent_pln ?? null)}
                          </Text>
                          <TrendingUp color={c.green} size={24} />
                        </View>
                        <Text style={s.muted}>
                          Median advertised base rent in{" "}
                          {filters.city || "this market"}.
                        </Text>
                        <Pressable
                          onPress={() => setTab("insights")}
                          accessibilityRole="button"
                          style={[s.row, { gap: 8, marginTop: 5 }]}
                        >
                          <Text
                            style={[
                              s.text,
                              {
                                color: c.green,
                                fontWeight: "600",
                                fontSize: 12,
                              },
                            ]}
                          >
                            Explore rent insights
                          </Text>
                          <ArrowRight size={14} color={c.green} />
                        </Pressable>
                      </View>
                    </View>
                  )}
                </View>
              )}
              <View
                style={[
                  s.row,
                  {
                    gap: 16,
                    paddingTop: 10,
                    borderTopWidth: 1,
                    borderColor: c.line,
                    flexWrap: "wrap",
                  },
                ]}
              >
                <Text style={[s.label, { fontSize: 8 }]}>
                  BUILT TO BRING SOURCES TOGETHER
                </Text>
                {["otodom", "OLX", "gratka.pl", "morizon"].map((name) => (
                  <Text
                    key={name}
                    style={[
                      s.text,
                      {
                        fontWeight: "700",
                        color: c.muted,
                        fontSize: 14,
                        letterSpacing: -0.4,
                      },
                    ]}
                  >
                    {name}
                  </Text>
                ))}
                <Text style={[s.muted, { fontSize: 10 }]}>
                  {summary?.demo
                    ? "Sample catalog · All homes shown are examples"
                    : "Independent aggregator · No portal affiliation"}
                </Text>
              </View>
            </>
          )}
        </ScrollView>
        {comparison.length > 0 && (
          <View
            style={[
              s.row,
              {
                paddingHorizontal: 24,
                paddingVertical: 12,
                justifyContent: "space-between",
                flexWrap: "wrap",
                gap: 14,
                backgroundColor: c.green,
              },
            ]}
          >
            <Text style={{ color: "white", fontSize: 12 }}>
              {comparison.length} {comparison.length === 1 ? "home" : "homes"}{" "}
              to compare
            </Text>
            <View style={[s.row, { gap: 15, flexWrap: "wrap" }]}>
              <Pressable
                accessibilityRole="button"
                onPress={() => setComparison([])}
              >
                <Text style={{ color: "#CBDAC3", fontSize: 12 }}>Clear</Text>
              </Pressable>
              <Button
                outline
                disabled={comparison.length < 2}
                onPress={() => setDialog("compare")}
              >
                Compare homes →
              </Button>
            </View>
          </View>
        )}
        {!!toast && (
          <Pressable
            accessibilityRole="alert"
            onPress={() => setToast("")}
            style={{
              position: "absolute",
              bottom: comparison.length ? 83 : 24,
              left: 22,
              right: 22,
              backgroundColor: "#17382D",
              padding: 16,
              borderWidth: 1,
              borderColor: "#668276",
            }}
          >
            <Text style={{ color: "white", fontSize: 13 }}>{toast}</Text>
          </Pressable>
        )}
      </View>
      {detail && !dialog && (
        <DetailDialog
          home={detail}
          onClose={() => {
            ++detailRequest.current;
            setDetail(null);
          }}
          onSave={() => toggleFavorite(detail)}
          saved={favoriteIds.has(detail.id)}
          onReport={() => openDialog(user ? "report" : "auth")}
          onContact={(advert) => {
            setContact(advert);
            setMarketMode("messages");
            openDialog(user ? "marketplace" : "auth");
          }}
        />
      )}
      {dialog === "marketplace" && (
        <Suspense
          fallback={
            <ActivityIndicator accessibilityLabel="Loading rental desk" />
          }
        >
          <MarketplaceDialog
            mode={marketMode}
            contact={contact}
            onClose={() => {
              setDialog(null);
              setContact(undefined);
              refresh();
              refreshAccount();
            }}
            onOpenHome={(id) => {
              setDialog(null);
              api
                .detail(id)
                .then(openHome)
                .catch((e) => setToast(e.message));
            }}
          />
        </Suspense>
      )}
      {dialog === "account" && (
        <AccountDialog
          onMarketplace={(mode) => {
            setMarketMode(mode);
            setContact(undefined);
            setDialog("marketplace");
          }}
          onClose={() => setDialog(null)}
          onSignOut={async () => {
            let pushWarning = "";
            try {
              await disablePush();
            } catch {
              // A push-provider outage must not prevent revoking the login session.
              pushWarning =
                " Device alert removal could not be confirmed. You can disable alerts in device settings.";
            }
            await api.signOut();
            currentUser.current = null;
            setUser(null);
            setDialog(null);
            setToast("Signed out." + pushWarning);
          }}
          onDeleted={(message) => {
            currentUser.current = null;
            setUser(null);
            setDialog(null);
            setToast(message);
          }}
        />
      )}
      {resetToken && (
        <ResetPasswordDialog
          token={resetToken}
          onClose={() => { links.current?.finishReset(resetToken, false); }}
          onComplete={(message) => {
            const activeLink = links.current?.finishReset(resetToken, true);
            setToken(null);
            currentUser.current = null;
            setUser(null);
            setToast(message);
            if (activeLink) setDialog("auth");
          }}
        />
      )}
      {dialog === "auth" && (
        <AuthDialog
          onClose={() => {
            setDialog(null);
            pendingFavorite.current = null;
            if (!currentUser.current) links.current?.clearPending();
            if (currentUser.current && contact) setDialog("marketplace");
          }}
          onSuccess={async (token, email) => {
            await signedIn(token, email);
          }}
        />
      )}
      {dialog === "filters" && (
        <FilterDialog
          initial={filters}
          districts={summary?.districts || []}
          onApply={changeFilters}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog === "compare" && (
        <CompareDialog homes={comparison} onClose={() => setDialog(null)} />
      )}
      {dialog === "save-search" && (
        <Panel title="Keep this search close." onClose={() => setDialog(null)}>
          <Field
            label="SEARCH NAME"
            value={searchName}
            onChange={setSearchName}
          />
          <Text style={s.muted}>
            Your current filters{filters.polygon ? " and drawn map area" : ""}{" "}
            will be saved. New matches go to your notification inbox. Enable
            email alerts there to receive updates when the app is closed.
          </Text>
          {!!formError && (
            <Text accessibilityRole="alert" style={{ color: "#A3422D" }}>
              {formError}
            </Text>
          )}
          <Button
            disabled={formBusy || !searchName.trim()}
            onPress={submitSearch}
          >
            {formBusy ? "Saving…" : "Save search"}
          </Button>
        </Panel>
      )}
      {dialog === "report" && (
        <Panel
          title="Something worth checking?"
          onClose={() => setDialog(null)}
        >
          <Field
            label="WHAT DID YOU NOTICE?"
            value={reportReason}
            onChange={setReportReason}
            placeholder="Describe the concern (at least 10 characters)"
          />
          <Text style={s.muted}>
            Reports are saved for review. They do not automatically mark an
            advertiser as suspicious.
          </Text>
          {!!formError && (
            <Text accessibilityRole="alert" style={{ color: "#A3422D" }}>
              {formError}
            </Text>
          )}
          <Button
            disabled={formBusy || reportReason.trim().length < 10}
            onPress={submitReport}
          >
            {formBusy ? "Saving…" : "Submit report"}
          </Button>
        </Panel>
      )}
      {dialog === "about" && (
        <Panel
          title="A clearer view of renting."
          onClose={() => setDialog(null)}
        >
          {[
            [
              "01",
              "Bring the sources together",
              "Configured feeds collect listings with their original source links, fees and timestamps. The current catalog is synthetic while source access is arranged.",
            ],
            [
              "02",
              "One home, fewer duplicates",
              "Conservative matching uses the address, area, room count and corroborating contact or image evidence. Each source keeps its own price and status.",
            ],
            [
              "03",
              "Know what deserves a closer look",
              "Repeated contact patterns and conflicting terms become explained signals. They are not accusations or guarantees.",
            ],
            [
              "04",
              "Put price in perspective",
              "Historical charts show observed advertised rents, sample sizes and methodology. Duplicate adverts do not inflate the sample.",
            ],
          ].map(([n, title, body]) => (
            <View key={n} style={{ gap: 8 }}>
              <Text style={[s.label, { color: c.orange }]}>{n}</Text>
              <Text style={[s.text, { fontWeight: "700" }]}>{title}</Text>
              <Text style={s.muted}>{body}</Text>
            </View>
          ))}
          <Button outline onPress={() => Linking.openURL(API_URL + "/docs")}>
            Explore the free public API ↗
          </Button>
        </Panel>
      )}
    </View>
  );
}
