import en from "@/messages/en.json";
import zh from "@/messages/zh.json";

export const SUPPORTED_LOCALES = ["zh", "en"] as const;
export type Locale = (typeof SUPPORTED_LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "zh";

type DictValue = string | Dict;
type Dict = { [key: string]: DictValue };

const messages: Record<Locale, Dict> = {
  zh: zh as Dict,
  en: en as Dict,
};

export function isLocale(value: string): value is Locale {
  return SUPPORTED_LOCALES.includes(value as Locale);
}

export function normalizeLocale(input?: string | null): Locale {
  if (!input) return DEFAULT_LOCALE;
  const value = input.toLowerCase();
  if (value.startsWith("en")) return "en";
  if (value.startsWith("zh")) return "zh";
  return DEFAULT_LOCALE;
}

export function localeFromPathname(pathname: string): Locale {
  const seg = pathname.split("/").filter(Boolean)[0];
  if (seg && isLocale(seg)) return seg;
  return DEFAULT_LOCALE;
}

export function stripLocalePrefix(pathname: string): string {
  const segments = pathname.split("/").filter(Boolean);
  if (segments.length > 0 && isLocale(segments[0])) {
    const rest = segments.slice(1).join("/");
    return rest ? `/${rest}` : "/";
  }
  return pathname || "/";
}

export function withLocalePath(locale: Locale, pathname: string): string {
  const normalized = stripLocalePrefix(pathname);
  if (normalized === "/") return `/${locale}`;
  return `/${locale}${normalized}`;
}

function resolvePath(dict: Dict, key: string): string | undefined {
  const parts = key.split(".");
  let current: DictValue | undefined = dict;
  for (const part of parts) {
    if (!current || typeof current === "string" || !(part in current)) return undefined;
    current = (current as Record<string, DictValue>)[part];
  }
  return typeof current === "string" ? current : undefined;
}

export function t(locale: Locale, key: string, fallback?: string): string {
  const directPrimary = messages[locale][key];
  if (typeof directPrimary === "string") return directPrimary;
  const primary = resolvePath(messages[locale], key);
  if (primary) return primary;
  const directDefault = messages[DEFAULT_LOCALE][key];
  if (typeof directDefault === "string") return directDefault;
  const defaultValue = resolvePath(messages[DEFAULT_LOCALE], key);
  if (defaultValue) return defaultValue;
  return fallback || key;
}
