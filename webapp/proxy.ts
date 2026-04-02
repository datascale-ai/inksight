import { NextRequest, NextResponse } from "next/server";
import { DEFAULT_LOCALE, isLocale, normalizeLocale } from "@/lib/i18n";

const LOCALE_COOKIE = "ink_locale";
const DEFAULT_ALLOWED_HOSTS = new Set([
  "www.inksight.site",
  "inksight.site",
  "localhost",
  "127.0.0.1",
  "::1",
]);

function normalizeHost(raw: string | null): string {
  const value = (raw || "").split(",")[0]?.trim().toLowerCase() || "";
  if (!value) return "";
  if (value.startsWith("[")) {
    const end = value.indexOf("]");
    return end >= 0 ? value.slice(1, end) : value;
  }
  const colonCount = value.split(":").length - 1;
  if (colonCount === 1) return value.split(":")[0] || "";
  return value;
}

function allowedHosts(): Set<string> {
  const hosts = new Set(DEFAULT_ALLOWED_HOSTS);
  const extra = process.env.INKSIGHT_ALLOWED_WEB_HOSTS || "";
  for (const part of extra.split(",")) {
    const host = normalizeHost(part);
    if (host) hosts.add(host);
  }
  return hosts;
}

function requestHost(req: NextRequest): string {
  return normalizeHost(
    req.headers.get("x-forwarded-host")
      || req.headers.get("host")
      || req.nextUrl.host,
  );
}

function isBypassPath(pathname: string): boolean {
  return (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api") ||
    pathname.startsWith("/images") ||
    pathname.startsWith("/favicon") ||
    pathname.startsWith("/manifest")
  );
}

export function proxy(req: NextRequest) {
  const { pathname, search } = req.nextUrl;
  if (!allowedHosts().has(requestHost(req))) {
    return new NextResponse("Not Found", { status: 404 });
  }
  if (isBypassPath(pathname)) return NextResponse.next();

  const seg = pathname.split("/").filter(Boolean)[0] || "";
  if (isLocale(seg)) {
    const requestHeaders = new Headers(req.headers);
    requestHeaders.set("x-ink-locale", seg);
    const res = NextResponse.next({ request: { headers: requestHeaders } });
    res.cookies.set(LOCALE_COOKIE, seg, { path: "/" });
    return res;
  }

  const cookieLocale = normalizeLocale(req.cookies.get(LOCALE_COOKIE)?.value);
  const locale = isLocale(cookieLocale) ? cookieLocale : DEFAULT_LOCALE;
  const url = req.nextUrl.clone();
  url.pathname = pathname === "/" ? `/${locale}` : `/${locale}${pathname}`;
  url.search = search;
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/((?!.*\\..*).*)"],
};
