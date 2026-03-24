"use client";

import Link from "next/link";
import { User, ChevronDown, LogOut } from "lucide-react";
import type { Locale } from "@/lib/i18n";
import { t, withLocalePath } from "@/lib/i18n";
import { useHoverDropdown } from "@/components/ui/use-hover-dropdown";

type UserDropdownProps = {
  locale: Locale;
  username: string;
  onLogout: () => Promise<void>;
};

export function UserDropdown({ locale, username, onLogout }: UserDropdownProps) {
  const { open, openMenu, closeMenu, scheduleClose } = useHoverDropdown({ closeDelayMs: 180 });

  return (
    <div
      className="relative"
      onMouseEnter={openMenu}
      onMouseLeave={scheduleClose}
      onFocusCapture={openMenu}
      onBlurCapture={scheduleClose}
    >
      <button
        type="button"
        className="flex items-center gap-2 rounded-md px-2 py-1 text-sm text-ink-light transition-colors hover:text-ink"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <span className="flex h-6 w-6 items-center justify-center rounded-full border border-ink/20 bg-white text-ink">
          <User size={14} />
        </span>
        <span className="max-w-28 truncate">{username}</span>
        <ChevronDown size={14} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div
          className="absolute right-0 top-[calc(100%+8px)] z-[100] min-w-52 rounded-lg border border-ink/10 bg-white p-2 shadow-lg"
          role="menu"
          onMouseEnter={openMenu}
          onMouseLeave={scheduleClose}
        >
          <div className="px-2 py-2 text-sm text-ink">
            <p className="text-xs text-ink-light">{t(locale, "nav.userMenu.identityLabel")}</p>
            <p className="mt-1 font-medium">{username}</p>
          </div>

          <div className="my-1 h-px bg-ink/10" />

          <div className="py-1">
            <Link
              href={withLocalePath(locale, "/profile")}
              className="flex items-center gap-2 rounded-md px-2 py-2 text-sm text-ink-light transition-colors hover:bg-gray-50 hover:text-ink"
              role="menuitem"
              onClick={closeMenu}
            >
              <User size={14} />
              {t(locale, "nav.userMenu.profile")}
            </Link>
          </div>

          <div className="my-1 h-px bg-ink/10" />

          <button
            type="button"
            className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-sm text-red-600 transition-colors hover:bg-red-50 hover:text-red-700"
            role="menuitem"
            onClick={onLogout}
          >
            <LogOut size={14} />
            {t(locale, "nav.userMenu.logout")}
          </button>
        </div>
      )}
    </div>
  );
}
