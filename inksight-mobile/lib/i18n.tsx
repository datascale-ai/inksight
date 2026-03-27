import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { getLocales } from 'expo-localization';
import { getStoredLocale, setStoredLocale } from '@/lib/storage';

type Locale = 'zh' | 'en';
type MessageDict = Record<string, string>;

export type I18nContextValue = {
  locale: Locale;
  ready: boolean;
  t: (key: string, vars?: Record<string, string | number | null | undefined>) => string;
  setLocale: (locale: Locale) => Promise<void>;
};

const zhMessages = require('@/messages/zh.json') as MessageDict;
const enMessages = require('@/messages/en.json') as MessageDict;

const dictionaries: Record<Locale, MessageDict> = {
  zh: zhMessages,
  en: enMessages,
};

const I18nContext = createContext<I18nContextValue | null>(null);

function resolveDefaultLocale(): Locale {
  const locale = getLocales()[0]?.languageCode?.toLowerCase();
  return locale === 'en' ? 'en' : 'zh';
}

function interpolate(template: string, vars?: Record<string, string | number | null | undefined>) {
  if (!vars) {
    return template;
  }
  return template.replace(/\{([^}]+)\}/g, (_match, key: string) => {
    const value = vars[key];
    return value == null ? '' : String(value);
  });
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>('zh');
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const localePromise = getStoredLocale();
    const timeoutMs = 4000;
    const timeout = new Promise<null>((resolve) => {
      setTimeout(() => resolve(null), timeoutMs);
    });
    Promise.race([localePromise, timeout])
      .then((stored) => {
        if (cancelled) {
          return;
        }
        if (stored === 'en' || stored === 'zh') {
          setLocaleState(stored);
        } else {
          setLocaleState(resolveDefaultLocale());
        }
        setReady(true);
      })
      .catch(() => {
        if (!cancelled) {
          setLocaleState(resolveDefaultLocale());
          setReady(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const value = useMemo<I18nContextValue>(
    () => ({
      locale,
      ready,
      t: (key, vars) => {
        const dictionary = dictionaries[locale] || dictionaries.zh;
        const fallback = dictionaries.en[key] || dictionaries.zh[key] || key;
        const template = dictionary[key] || fallback;
        return interpolate(template, vars);
      },
      setLocale: async (nextLocale) => {
        setLocaleState(nextLocale);
        await setStoredLocale(nextLocale);
      },
    }),
    [locale, ready],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error('useI18n must be used within I18nProvider');
  }
  return ctx;
}

/**
 * Translate with fallback: calls `t(key)` and returns `fallback` if the result
 * equals the raw key (i.e., the key is missing from the dictionary).
 * Usage: Alert.alert(tf(t, 'key', 'Default Title'), ...)
 */
export function tf(
  t: (key: string, vars?: Record<string, string | number | null | undefined>) => string,
  key: string,
  fallback: string,
  vars?: Record<string, string | number | null | undefined>,
) {
  const result = t(key, vars);
  return result === key ? fallback : result;
}
