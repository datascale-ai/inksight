export const LOCATION_KEYS = [
  "city",
  "latitude",
  "longitude",
  "timezone",
  "admin1",
  "country",
] as const;

export type LocationKey = (typeof LOCATION_KEYS)[number];

export interface LocationValue {
  city?: string;
  latitude?: number;
  longitude?: number;
  timezone?: string;
  admin1?: string;
  country?: string;
}

export interface LocationOption extends LocationValue {
  city: string;
  display_name: string;
}

const RECENT_LOCATIONS_STORAGE_KEY = "inksight:recent-locations:v2";
const LOCATION_QUERY_CACHE_STORAGE_KEY = "inksight:location-query-cache:v2";
const MAX_RECENT_LOCATIONS = 8;
const MAX_QUERY_CACHE_ITEMS = 24;
const LOCATION_QUERY_CACHE_TTL_MS = 1000 * 60 * 60 * 24 * 7;

export function cleanLocationValue(input?: Partial<LocationValue> | null): LocationValue {
  if (!input) return {};
  const next: LocationValue = {};
  if (typeof input.city === "string" && input.city.trim()) next.city = input.city.trim();
  if (typeof input.latitude === "number" && Number.isFinite(input.latitude)) next.latitude = input.latitude;
  if (typeof input.longitude === "number" && Number.isFinite(input.longitude)) next.longitude = input.longitude;
  if (typeof input.timezone === "string" && input.timezone.trim()) next.timezone = input.timezone.trim();
  if (typeof input.admin1 === "string" && input.admin1.trim()) next.admin1 = input.admin1.trim();
  if (typeof input.country === "string" && input.country.trim()) next.country = input.country.trim();
  return next;
}

export function buildLocationValue(city: string, extra?: Partial<LocationValue> | null): LocationValue {
  return cleanLocationValue({ ...(extra || {}), city });
}

export function extractLocationValue(input?: Record<string, unknown> | null): LocationValue {
  if (!input) return {};
  return cleanLocationValue({
    city: typeof input.city === "string" ? input.city : undefined,
    latitude: typeof input.latitude === "number" ? input.latitude : undefined,
    longitude: typeof input.longitude === "number" ? input.longitude : undefined,
    timezone: typeof input.timezone === "string" ? input.timezone : undefined,
    admin1: typeof input.admin1 === "string" ? input.admin1 : undefined,
    country: typeof input.country === "string" ? input.country : undefined,
  });
}

export function locationsEqual(a?: Partial<LocationValue> | null, b?: Partial<LocationValue> | null): boolean {
  const left = cleanLocationValue(a);
  const right = cleanLocationValue(b);
  return LOCATION_KEYS.every((key) => left[key] === right[key]);
}

export function describeLocation(location?: Partial<LocationValue> | null): string {
  const cleaned = cleanLocationValue(location);
  const city = cleaned.city || "";
  if (!city) return "";
  const parts = [city];
  if (cleaned.admin1) parts.push(cleaned.admin1);
  if (cleaned.country) parts.push(cleaned.country);
  return parts.join(" · ");
}

function normalizeLocationOption(input?: Partial<LocationOption> | null): LocationOption | null {
  if (!input || typeof input.city !== "string") return null;
  const cleaned = cleanLocationValue(input);
  if (!cleaned.city) return null;
  return {
    ...cleaned,
    city: cleaned.city,
    display_name:
      typeof input.display_name === "string" && input.display_name.trim()
        ? input.display_name.trim()
        : describeLocation(cleaned) || cleaned.city,
  };
}

function locationOptionKey(input?: Partial<LocationOption> | null): string {
  const item = normalizeLocationOption(input);
  if (!item) return "";
  const latitude = typeof item.latitude === "number" ? item.latitude.toFixed(4) : "";
  const longitude = typeof item.longitude === "number" ? item.longitude.toFixed(4) : "";
  return [item.city, item.admin1 || "", item.country || "", latitude, longitude].join("|");
}

function safeReadStorage(key: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeWriteStorage(key: string, value: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, value);
  } catch {}
}

function dedupeLocationOptions(items: Array<Partial<LocationOption> | null | undefined>, limit = MAX_RECENT_LOCATIONS): LocationOption[] {
  const deduped: LocationOption[] = [];
  const seen = new Set<string>();
  const seenLabels = new Set<string>();
  for (const item of items) {
    const normalized = normalizeLocationOption(item);
    if (!normalized) continue;
    const labelKey = (normalized.display_name || describeLocation(normalized) || normalized.city)
      .trim()
      .toLowerCase();
    if (labelKey && seenLabels.has(labelKey)) continue;
    const key = locationOptionKey(normalized);
    if (!key || seen.has(key)) continue;
    if (labelKey) seenLabels.add(labelKey);
    seen.add(key);
    deduped.push(normalized);
    if (deduped.length >= limit) break;
  }
  return deduped;
}

export function getStoredRecentLocations(): LocationOption[] {
  const raw = safeReadStorage(RECENT_LOCATIONS_STORAGE_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return dedupeLocationOptions(parsed, MAX_RECENT_LOCATIONS);
  } catch {
    return [];
  }
}

export function saveRecentLocation(option?: Partial<LocationOption> | null): LocationOption[] {
  const next = dedupeLocationOptions([option, ...getStoredRecentLocations()], MAX_RECENT_LOCATIONS);
  safeWriteStorage(RECENT_LOCATIONS_STORAGE_KEY, JSON.stringify(next));
  return next;
}

interface StoredLocationQueryCacheItem {
  updatedAt: number;
  items: LocationOption[];
}

type StoredLocationQueryCache = Record<string, StoredLocationQueryCacheItem>;

function normalizeQuery(query: string): string {
  return query.trim().toLowerCase();
}

function readLocationQueryCache(): StoredLocationQueryCache {
  const raw = safeReadStorage(LOCATION_QUERY_CACHE_STORAGE_KEY);
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return {};
    const now = Date.now();
    const entries = Object.entries(parsed as Record<string, unknown>);
    const next: StoredLocationQueryCache = {};
    for (const [key, value] of entries) {
      if (!value || typeof value !== "object") continue;
      const updatedAt = typeof (value as { updatedAt?: unknown }).updatedAt === "number"
        ? (value as { updatedAt: number }).updatedAt
        : 0;
      if (!updatedAt || now - updatedAt > LOCATION_QUERY_CACHE_TTL_MS) continue;
      const rawItems = Array.isArray((value as { items?: unknown[] }).items)
        ? (value as { items: unknown[] }).items
        : [];
      const items = dedupeLocationOptions(rawItems as Array<Partial<LocationOption>>, 10);
      if (!items.length) continue;
      next[key] = { updatedAt, items };
    }
    return next;
  } catch {
    return {};
  }
}

function writeLocationQueryCache(cache: StoredLocationQueryCache): void {
  const entries = Object.entries(cache)
    .sort((left, right) => right[1].updatedAt - left[1].updatedAt)
    .slice(0, MAX_QUERY_CACHE_ITEMS);
  safeWriteStorage(LOCATION_QUERY_CACHE_STORAGE_KEY, JSON.stringify(Object.fromEntries(entries)));
}

export function getCachedLocationResults(query: string): LocationOption[] | null {
  const normalizedQuery = normalizeQuery(query);
  if (!normalizedQuery) return null;
  const cache = readLocationQueryCache();
  const entry = cache[normalizedQuery];
  return entry?.items?.length ? entry.items : null;
}

export function cacheLocationResults(query: string, items: Array<Partial<LocationOption> | null | undefined>): LocationOption[] {
  const normalizedQuery = normalizeQuery(query);
  const cleanedItems = dedupeLocationOptions(items, 10);
  if (!normalizedQuery || !cleanedItems.length) return cleanedItems;
  const cache = readLocationQueryCache();
  cache[normalizedQuery] = {
    updatedAt: Date.now(),
    items: cleanedItems,
  };
  writeLocationQueryCache(cache);
  return cleanedItems;
}

export function mergeLocationOptions(
  primary: Array<Partial<LocationOption> | null | undefined>,
  secondary: Array<Partial<LocationOption> | null | undefined>,
  limit = 8,
): LocationOption[] {
  return dedupeLocationOptions([...primary, ...secondary], limit);
}
