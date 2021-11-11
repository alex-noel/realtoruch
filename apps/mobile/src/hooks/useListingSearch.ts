import { useCallback, useLayoutEffect, useState } from "react";
import { api, queryString } from "../api";
import type { Filters, SearchResult, Sources, Summary } from "../types";

export const SEARCH_DEBOUNCE_MS = 250;
const LISTING_STATE_BATCH_SIZE = 100;

export function normalizeCity(value: string) {
  const city = value.trim();
  const folded = city
    .toLowerCase()
    .replace(/ł/g, "l")
    .normalize("NFKD")
    .replace(/[^\x00-\x7F]/g, "")
    .trim();
  if (folded === "krakow") return "Kraków";
  if (folded === "warszawa") return "Warszawa";
  return city;
}

function normalizeFilters(filters: Filters): Filters {
  return {
    ...filters,
    city: normalizeCity(filters.city),
    q: filters.q.trim(),
    district: filters.district.trim(),
    amenity: filters.amenity.trim(),
  };
}

function queryKey(filters: Filters) {
  return queryString(
    Object.fromEntries(
      Object.entries(filters).sort(([a], [b]) => a.localeCompare(b)),
    ),
  );
}

// A generation also protects against transports that finish after being aborted.
export function createLatestRequest() {
  let generation = 0;
  let controller: AbortController | undefined;
  let timer: ReturnType<typeof setTimeout> | undefined;

  function cancel() {
    generation++;
    clearTimeout(timer);
    controller?.abort();
    controller = undefined;
  }

  function run<T>(
    delay: number,
    load: (signal: AbortSignal | undefined) => Promise<T>,
    success: (value: T) => void,
    failure: () => void,
  ) {
    cancel();
    const expected = generation;
    controller =
      typeof AbortController === "undefined"
        ? undefined
        : new AbortController();
    const signal = controller?.signal;
    async function start() {
      try {
        const value = await load(signal);
        if (generation === expected) success(value);
      } catch {
        if (generation === expected) failure();
      }
    }
    if (delay) timer = setTimeout(start, delay);
    else void start();
    return cancel;
  }

  return { run, cancel };
}

export async function loadSeenIds(ids: string[], signal?: AbortSignal) {
  const unique = [...new Set(ids)];
  const seen: string[] = [];
  for (
    let start = 0;
    start < unique.length && !signal?.aborted;
    start += LISTING_STATE_BATCH_SIZE
  ) {
    const batch = unique.slice(start, start + LISTING_STATE_BATCH_SIZE);
    const state = await api.listingState(batch, signal);
    seen.push(...state.seen_ids);
  }
  return seen;
}

type SearchRequest = { filters: Filters; page: number; wait: number };
type CityRequest = { city: string; wait: number };
type Snapshot = {
  request: SearchRequest;
  data: SearchResult;
  receivedAt: number;
};
type SearchCompletion = {
  request: SearchRequest;
  snapshot: Snapshot | null;
  failed: boolean;
};

export function useListingSearch(initial: Filters) {
  const [desired, setDesired] = useState(() => {
    const filters = normalizeFilters(initial);
    return {
      search: { filters, page: 1, wait: 0 },
      city: { city: filters.city, wait: 0 },
    };
  });
  const { search, city } = desired;
  const [searchCompletion, setSearchCompletion] = useState<SearchCompletion>();
  const [sourceCompletion, setSourceCompletion] = useState<{
    request: CityRequest;
    data: Sources | null;
  }>();
  const [summaryCompletion, setSummaryCompletion] = useState<{
    city: string;
    data: Summary | null;
  }>();
  const [listingRequests] = useState(createLatestRequest);
  const [sourceRequests] = useState(createLatestRequest);
  const [summaryRequests] = useState(createLatestRequest);

  useLayoutEffect(
    () =>
      listingRequests.run(
        search.wait,
        (signal) => api.search(search.filters, search.page, signal),
        (data) =>
          setSearchCompletion({
            request: search,
            snapshot: { request: search, data, receivedAt: Date.now() },
            failed: false,
          }),
        () =>
          setSearchCompletion((previous) => ({
            request: search,
            snapshot: previous?.snapshot ?? null,
            failed: true,
          })),
      ),
    [listingRequests, search],
  );

  useLayoutEffect(() => {
    const cancelSources = sourceRequests.run(
      city.wait,
      (signal) => api.sources(city.city, signal),
      (data) => setSourceCompletion({ request: city, data }),
      () => setSourceCompletion({ request: city, data: null }),
    );
    const cancelSummary = summaryRequests.run(
      city.wait,
      (signal) => api.summary(city.city, signal),
      (data) => setSummaryCompletion({ city: city.city, data }),
      () => setSummaryCompletion({ city: city.city, data: null }),
    );
    return () => {
      cancelSources();
      cancelSummary();
    };
  }, [city, sourceRequests, summaryRequests]);

  const changeFilters = useCallback((value: Filters, debounce = false) => {
    const filters = normalizeFilters(value);
    const wait = debounce ? SEARCH_DEBOUNCE_MS : 0;
    setDesired((current) => {
      if (debounce && queryKey(filters) === queryKey(current.search.filters))
        return current;
      const changeCity = filters.city !== current.city.city;
      return {
        search: { filters, page: 1, wait },
        city: changeCity ? { city: filters.city, wait } : current.city,
      };
    });
  }, []);

  const goToPage = useCallback((page: number) => {
    setDesired((current) => ({
      ...current,
      search: { ...current.search, page, wait: 0 },
    }));
  }, []);

  const retrySearch = useCallback(() => {
    setDesired((current) => ({
      ...current,
      search: { ...current.search, wait: 0 },
    }));
  }, []);

  const retrySources = useCallback(() => {
    setDesired((current) => ({
      ...current,
      city: { ...current.city, wait: 0 },
    }));
  }, []);

  const refresh = useCallback(() => {
    setDesired((current) => ({
      search: { ...current.search },
      city: { ...current.city },
    }));
  }, []);

  const snapshot = searchCompletion?.snapshot;
  const result =
    snapshot?.request.filters.city === search.filters.city ? snapshot : null;
  const currentPage =
    result?.request.page === search.page &&
    queryKey(result.request.filters) === queryKey(search.filters);
  return {
    filters: search.filters,
    page: search.page,
    result,
    currentPage,
    loading: searchCompletion?.request !== search,
    failed: searchCompletion?.request === search && searchCompletion.failed,
    sourceData:
      sourceCompletion?.request.city === city.city
        ? sourceCompletion.data
        : null,
    sourceLoading: sourceCompletion?.request !== city,
    sourceFailed: sourceCompletion?.request === city && !sourceCompletion.data,
    summary:
      summaryCompletion?.city === city.city ? summaryCompletion.data : null,
    changeFilters,
    goToPage,
    retrySearch,
    retrySources,
    refresh,
  };
}

export function resultAge(receivedAt: number, now = Date.now()) {
  const minutes = Math.max(0, Math.floor((now - receivedAt) / 60_000));
  if (minutes === 0) return "less than a minute ago";
  if (minutes === 1) return "1 minute ago";
  return `${minutes} minutes ago`;
}
