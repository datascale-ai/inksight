import { NextRequest, NextResponse } from "next/server";
import { DEFAULT_LOCALE, isLocale, normalizeLocale } from "@/lib/i18n";

const LOCALE_COOKIE = "ink_locale";

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
  if (isBypassPath(pathname)) return NextResponse.next();

  const seg = pathname.split("/").filter(Boolean)[0] || "";
  if (isLocale(seg)) {
    const res = NextResponse.next();
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
