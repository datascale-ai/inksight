import AsyncStorage from '@react-native-async-storage/async-storage';
import type { TodayItem, TodayPayload } from '@/features/content/api';

const TODAY_CACHE_KEY = 'inksight.content.today';
const FAVORITES_KEY = 'inksight.content.favorites';
const HISTORY_KEY = 'inksight.content.history';
const TODAY_CACHE_TTL_MS = 30 * 60 * 1000;

type TimedPayload<T> = {
  value: T;
  updated_at: string;
};

export type LocalFavoriteItem = {
  id: string;
  mode_id: string;
  display_name: string;
  summary: string;
  attribution?: string;
  saved_at: string;
};

export type LocalHistoryItem = {
  id: string;
  mode_id: string;
  display_name: string;
  summary: string;
  viewed_at: string;
};

function buildFavoriteId(item: Pick<TodayItem, 'mode_id' | 'summary'>) {
  return `${item.mode_id}:${item.summary}`;
}

export async function getCachedTodayContent(): Promise<TodayPayload | null> {
  const raw = await AsyncStorage.getItem(TODAY_CACHE_KEY);
  if (!raw) {
    return null;
  }
  try {
    const parsed = JSON.parse(raw) as TodayPayload | TimedPayload<TodayPayload>;
    if ('value' in parsed && 'updated_at' in parsed) {
      const age = Date.now() - new Date(parsed.updated_at).getTime();
      if (Number.isFinite(age) && age > TODAY_CACHE_TTL_MS) {
        await AsyncStorage.removeItem(TODAY_CACHE_KEY);
        return null;
      }
      return parsed.value;
    }
    return parsed as TodayPayload;
  } catch {
    await AsyncStorage.removeItem(TODAY_CACHE_KEY);
    return null;
  }
}

export async function setCachedTodayContent(payload: TodayPayload) {
  const timedPayload: TimedPayload<TodayPayload> = {
    value: payload,
    updated_at: new Date().toISOString(),
  };
  await AsyncStorage.setItem(TODAY_CACHE_KEY, JSON.stringify(timedPayload));
}

export async function getLocalFavorites() {
  const raw = await AsyncStorage.getItem(FAVORITES_KEY);
  if (!raw) {
    return [] as LocalFavoriteItem[];
  }
  try {
    return JSON.parse(raw) as LocalFavoriteItem[];
  } catch {
    await AsyncStorage.removeItem(FAVORITES_KEY);
    return [] as LocalFavoriteItem[];
  }
}

export async function isFavoriteTodayItem(item: TodayItem) {
  const favorites = await getLocalFavorites();
  return favorites.some((favorite) => favorite.id === buildFavoriteId(item));
}

export async function toggleLocalFavorite(item: TodayItem) {
  const favorites = await getLocalFavorites();
  const id = buildFavoriteId(item);
  const existing = favorites.find((favorite) => favorite.id === id);

  if (existing) {
    const nextFavorites = favorites.filter((favorite) => favorite.id !== id);
    await AsyncStorage.setItem(FAVORITES_KEY, JSON.stringify(nextFavorites));
    return {
      active: false,
      favorites: nextFavorites,
    };
  }

  const nextFavorite: LocalFavoriteItem = {
    id,
    mode_id: item.mode_id,
    display_name: item.display_name,
    summary: item.summary,
    attribution: typeof item.content?.author === 'string' ? item.content.author : undefined,
    saved_at: new Date().toISOString(),
  };
  const nextFavorites = [nextFavorite, ...favorites].slice(0, 50);
  await AsyncStorage.setItem(FAVORITES_KEY, JSON.stringify(nextFavorites));
  return {
    active: true,
    favorites: nextFavorites,
  };
}

export async function getLocalHistory() {
  const raw = await AsyncStorage.getItem(HISTORY_KEY);
  if (!raw) {
    return [] as LocalHistoryItem[];
  }
  try {
    return JSON.parse(raw) as LocalHistoryItem[];
  } catch {
    await AsyncStorage.removeItem(HISTORY_KEY);
    return [] as LocalHistoryItem[];
  }
}

export async function appendLocalHistory(item: TodayItem) {
  const history = await getLocalHistory();
  const id = buildFavoriteId(item);
  const nextItem: LocalHistoryItem = {
    id,
    mode_id: item.mode_id,
    display_name: item.display_name,
    summary: item.summary,
    viewed_at: new Date().toISOString(),
  };
  const nextHistory = [nextItem, ...history.filter((entry) => entry.id !== id)].slice(0, 50);
  await AsyncStorage.setItem(HISTORY_KEY, JSON.stringify(nextHistory));
  return nextHistory;
}
