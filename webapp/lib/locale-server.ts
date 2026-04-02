import { cookies, headers } from "next/headers";
import { isLocale, normalizeLocale, type Locale } from "@/lib/i18n";

/** Set by webapp/proxy.ts when the URL starts with /en or /zh */
export const INK_LOCALE_HEADER = "x-ink-locale";

/**
 * Locale for Server Components: URL prefix wins (same as client Navbar), then cookie.
 * Fixes mismatch when pathname is /en/docs but ink_locale cookie is missing or stale.
 */
export async function localeForRequest(): Promise<Locale> {
  const h = await headers();
  const fromHeader = h.get(INK_LOCALE_HEADER);
  if (fromHeader && isLocale(fromHeader)) return fromHeader;
  return normalizeLocale((await cookies()).get("ink_locale")?.value);
}
