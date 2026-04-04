import Link from "next/link";
import { BookOpen } from "lucide-react";
import { cookies } from "next/headers";
import { DocsMobileNav } from "./mobile-nav";
import { normalizeLocale, t, withLocalePath } from "@/lib/i18n";

const sidebarSections = [
  {
    titleKey: "docs.section.gettingStarted",
    items: [
      { labelKey: "docs.item.intro", href: "/docs" },
      { labelKey: "docs.item.architecture", href: "/docs/architecture" },
      { labelKey: "docs.item.hardware", href: "/docs/hardware" },
      { labelKey: "docs.item.bom", href: "/docs/bom" },
      { labelKey: "docs.item.assembly", href: "/docs/assembly" },
    ],
  },
  {
    titleKey: "docs.section.usage",
    items: [
      { labelKey: "docs.item.website", href: "/docs/website" },
      { labelKey: "docs.item.flash", href: "/docs/flash" },
      { labelKey: "docs.item.buttonControls", href: "/docs/button-controls" },
      { labelKey: "docs.item.apiKey", href: "/docs/api-key" },
      { labelKey: "docs.item.config", href: "/docs/config" },
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

async function Sidebar() {
  const locale = normalizeLocale((await cookies()).get("ink_locale")?.value);
  return (
    <nav className="space-y-6">
      {sidebarSections.map((section) => (
        <div key={section.titleKey}>
          <h4 className="text-xs font-semibold text-ink-light uppercase tracking-widest mb-2.5 px-3">
            {t(locale, section.titleKey)}
          </h4>
          <ul className="space-y-0.5">
            {section.items.map((item) => (
              <li key={item.href}>
                <Link
                  href={withLocalePath(locale, item.href)}
                  className="block px-3 py-1.5 text-sm text-ink-muted rounded-sm hover:text-ink hover:bg-ink/[0.04] transition-colors"
                >
                  {t(locale, item.labelKey)}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}

export default async function DocsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const locale = normalizeLocale((await cookies()).get("ink_locale")?.value);
  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      {/* Mobile nav trigger */}
      <div className="lg:hidden mb-6">
        <DocsMobileNav />
      </div>

      <div className="flex gap-10">
        {/* Sidebar - desktop only */}
        <aside className="hidden lg:block w-[220px] flex-shrink-0">
          <div className="sticky top-24">
            <div className="flex items-center gap-2 mb-6 px-3">
              <BookOpen size={16} className="text-ink" />
              <span className="text-sm font-semibold text-ink">{t(locale, "docs.center")}</span>
            </div>
            <Sidebar />
          </div>
        </aside>

        {/* Content */}
        <div className="min-w-0 flex-1 max-w-3xl">{children}</div>
      </div>
    </div>
  );
}
