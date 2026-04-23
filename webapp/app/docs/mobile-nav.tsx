"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, ChevronDown, ChevronUp } from "lucide-react";
import { localeFromPathname, t, withLocalePath } from "@/lib/i18n";

const sidebarSections = [
  {
    titleKey: "docs.section.gettingStarted",
    items: [
      { labelKey: "docs.item.intro", href: "/docs" },
      { labelKey: "docs.item.architecture", href: "/docs/architecture" },
      { labelKey: "docs.item.hardware", href: "/docs/hardware" },
      { labelKey: "docs.item.assembly", href: "/docs/assembly" },
    ],
  },
      {
        titleKey: "docs.section.usage",
        items: [
          { labelKey: "docs.item.website", href: "/docs/website" },
          { labelKey: "docs.item.mobileApp", href: "/docs/mobile-app" },
          { labelKey: "docs.item.flash", href: "/docs/flash" },
          { labelKey: "docs.item.buttonControls", href: "/docs/button-controls" },
          { labelKey: "docs.item.apiKey", href: "/docs/api-key" },
          { labelKey: "docs.item.config", href: "/docs/config" },
          { labelKey: "docs.item.voiceMode", href: "/docs/voice-mode" },
        ],
      },
  {
    titleKey: "docs.section.advanced",
    items: [
      { labelKey: "docs.item.deploy", href: "/docs/deploy" },
      { labelKey: "docs.item.pluginDev", href: "/docs/custom-mode-dev" },
      { labelKey: "docs.item.apiReference", href: "/docs/api-reference" },
      { labelKey: "docs.item.faq", href: "/docs/faq" },
    ],
  },
];

export function DocsMobileNav() {
  const pathname = usePathname();
  const locale = localeFromPathname(pathname || "/");
  const [open, setOpen] = useState(false);

  return (
    <div className="border border-ink/10 rounded-sm">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-ink"
      >
        <span className="flex items-center gap-2">
          <BookOpen size={15} />
          {t(locale, "docs.menu")}
        </span>
        {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>

      {open && (
        <div className="border-t border-ink/10 px-4 py-3 space-y-4">
          {sidebarSections.map((section) => (
            <div key={section.titleKey}>
              <h4 className="text-xs font-semibold text-ink-light uppercase tracking-widest mb-1.5">
                {t(locale, section.titleKey)}
              </h4>
              <ul className="space-y-0.5">
                {section.items.map((item) => (
                  <li key={item.href}>
                    <Link
                      href={withLocalePath(locale, item.href)}
                      className="block py-1 text-sm text-ink-muted hover:text-ink transition-colors"
                      onClick={() => setOpen(false)}
                    >
                      {t(locale, item.labelKey)}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
