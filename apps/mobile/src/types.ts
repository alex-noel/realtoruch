export type Source = {
  name: string;
  url: string;
  rent_pln: number;
  fees_pln: number | null;
  commission_pln: number | null;
  advertiser_type: string;
  status: string;
  last_checked: string;
  match_reason: string;
};
export type Listing = {
  id: string;
  title: string;
  description: string;
  city: string;
  district: string;
  region: string;
  address: string;
  lat: number | null;
  lon: number | null;
  area_m2: number;
  rooms: number;
  floor: number | null;
  rent_pln: number;
  fees_pln: number | null;
  deposit_pln: number | null;
  commission_pln: number | null;
  total_monthly_pln: number | null;
  advertiser_type: string;
  property_type: string;
  status: string;
  images: string[];
  amenities: string[];
  is_demo: boolean;
  first_seen: string;
  last_seen: string;
  risk_score: number;
  risk_flags: {
    code: string;
    label: string;
    detail: string;
    severity: string;
  }[];
  sources: Source[];
  history?: {
    at: string;
    rent_pln: number;
    fees_pln: number | null;
    status: string;
  }[];
};
export type Filters = {
  city: string;
  q: string;
  district: string;
  min_price?: number;
  max_price?: number;
  min_area?: number;
  max_area?: number;
  rooms?: number;
  advertiser: string;
  no_commission: boolean;
  hide_suspicious: boolean;
  property_type: string;
  amenity: string;
  sort: string;
};
export type SearchResult = {
  items: Listing[];
  total: number;
  page: number;
  page_size: number;
  engine: string;
  degraded?: boolean;
};
export type Summary = {
  homes: number;
  source_listings: number;
  duplicates_removed: number;
  private_homes: number;
  median_rent_pln: number | null;
  demo: boolean;
  districts: string[];
  cities: string[];
};
export type History = {
  points: {
    month: string;
    median_rent_pln: number;
    median_per_m2: number;
    sample_size: number;
    is_demo: boolean;
  }[];
  methodology: string;
};
export type SavedSearch = {
  id: string;
  name: string;
  filters: Filters;
  new_matches: number;
};
export const DEFAULT_FILTERS: Filters = {
  city: "Warszawa",
  q: "",
  district: "",
  advertiser: "all",
  no_commission: false,
  hide_suspicious: false,
  property_type: "all",
  amenity: "",
  sort: "newest",
};
