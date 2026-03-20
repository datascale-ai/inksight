"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { Menu, X, Github, User, LogOut } from "lucide-react";
import { authHeaders, clearToken, fetchCurrentUser, onAuthChanged } from "@/lib/auth";
import { localeFromPathname, t, withLocalePath } from "@/lib/i18n";

export function Navbar() {
  const router = useRouter();
  const pathname = usePathname();
  const locale = localeFromPathname(pathname || "/");
  const otherLocale = locale === "en" ? "zh" : "en";
  const navLinks = [
    { href: "/", label: t(locale, "nav.home") },
    { href: "/docs", label: t(locale, "nav.docs") },
    { href: "/discover", label: t(locale, "nav.discover") },
    { href: "/flash", label: t(locale, "nav.flash") },
    { href: "/config", label: t(locale, "nav.config") },
    { href: "/preview", label: t(locale, "nav.preview", locale === "zh" ? "无设备体验" : "No-device Demo") },
  ];
  const [mobileOpen, setMobileOpen] = useState(false);
  const [username, setUsername] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);

  const refreshUser = useCallback(() => {
    fetchCurrentUser()
      .then((d) => setUsername(d?.username || null))
      .catch(() => setUsername(null));
  }, []);

  useEffect(() => {
    refreshUser();
  }, [pathname, refreshUser]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setHydrated(true);
  }, []);

  useEffect(() => {
    const off = onAuthChanged(refreshUser);
    const onFocus = () => refreshUser();
    window.addEventListener("focus", onFocus);
    return () => {
      off();
      window.removeEventListener("focus", onFocus);
    };
  }, [refreshUser]);

  const handleLogout = async () => {
    await fetch("/api/auth/logout", { method: "POST", headers: authHeaders() });
    clearToken();
    setUsername(null);
    router.refresh();
  };

  // Avoid hydration mismatch: initial SSR does not have stable auth state
  // (depends on client-side token/cookie). Render a stable placeholder until mounted.
  if (!hydrated) {
    return (
      <header className="sticky top-0 z-40 w-full border-b border-ink/10 bg-white/80 backdrop-blur-md">
        <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6" />
      </header>
    );
  }

  return (
    <header className="sticky top-0 z-40 w-full border-b border-ink/10 bg-white/80 backdrop-blur-md">
      <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <Link href={withLocalePath(locale, "/")} className="flex items-center gap-2 group">
          <div className="flex h-8 w-8 items-center justify-center rounded-sm border border-ink bg-ink text-white text-xs font-bold font-serif">
            {locale === "en" ? "I" : "墨"}
          </div>
          <span className="text-lg font-semibold text-ink tracking-tight">
            {locale === "en" ? "InkSight" : "墨鱼InkSight"}
          </span>
        </Link>

        {/* Desktop nav */}
        <div className="hidden md:flex items-center gap-8">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={withLocalePath(locale, link.href)}
              className="text-sm text-ink-light hover:text-ink transition-colors"
            >
              {link.label}
            </Link>
          ))}
          <a
            href="https://github.com/datascale-ai/inksight"
            target="_blank"
            rel="noopener noreferrer"
            className="text-ink-light hover:text-ink transition-colors"
          >
            <Github size={18} />
          </a>
          {username ? (
            <div className="flex items-center gap-3 text-sm">
              <Link
                href={withLocalePath(locale, "/profile")}
                className="flex items-center gap-1 text-ink-light hover:text-ink transition-colors"
              >
                <User size={14} />
                {username}
              </Link>
              <button onClick={handleLogout} className="text-ink-light hover:text-ink transition-colors" title={t(locale, "nav.logout")}>
                <LogOut size={16} />
              </button>
            </div>
          ) : (
            <Link href={withLocalePath(locale, "/login")} className="text-sm text-ink-light hover:text-ink transition-colors">
              {t(locale, "nav.login")}
            </Link>
          )}
          <Link href={withLocalePath(otherLocale, pathname || "/")} className="text-sm text-ink-light hover:text-ink transition-colors">
            {t(locale, "nav.language")}
          </Link>
        </div>

        {/* Mobile toggle */}
        <button
          className="md:hidden p-2 text-ink"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label="Toggle menu"
        >
          {mobileOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </nav>

      {/* Mobile nav */}
      {mobileOpen && (
        <div className="md:hidden border-t border-ink/10 bg-white">
          <div className="flex flex-col px-6 py-4 space-y-3">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={withLocalePath(locale, link.href)}
                className="text-sm text-ink-light hover:text-ink transition-colors py-1"
                onClick={() => setMobileOpen(false)}
              >
                {link.label}
              </Link>
            ))}
            <a
              href="https://github.com/datascale-ai/inksight"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-sm text-ink-light hover:text-ink transition-colors py-1"
            >
              <Github size={16} />
              GitHub
            </a>
            {username ? (
              <div className="flex items-center justify-between py-1">
                <Link
                  href={withLocalePath(locale, "/profile")}
                  className="flex items-center gap-1 text-sm text-ink-light hover:text-ink transition-colors"
                  onClick={() => setMobileOpen(false)}
                >
                  <User size={14} />
                  {username}
                </Link>
                <button onClick={handleLogout} className="text-sm text-ink-light hover:text-ink">
                  {t(locale, "nav.logout")}
                </button>
              </div>
            ) : (
              <Link
                href={withLocalePath(locale, "/login")}
                className="text-sm text-ink-light hover:text-ink transition-colors py-1"
                onClick={() => setMobileOpen(false)}
              >
                {t(locale, "nav.login")}
              </Link>
            )}
            <Link
              href={withLocalePath(otherLocale, pathname || "/")}
              className="text-sm text-ink-light hover:text-ink transition-colors py-1"
              onClick={() => setMobileOpen(false)}
            >
              {t(locale, "nav.language")}
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}
