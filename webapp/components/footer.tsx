"use client";

import { usePathname } from "next/navigation";
import { Github } from "lucide-react";
import { localeFromPathname, t } from "@/lib/i18n";

export function Footer() {
  const pathname = usePathname();
  const locale = localeFromPathname(pathname || "/");
  return (
    <footer className="border-t border-ink/10 bg-paper">
      <div className="mx-auto max-w-6xl px-6 py-12">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Brand */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <div className="flex h-7 w-7 items-center justify-center rounded-sm border border-ink bg-ink text-white text-xs font-bold font-serif">
                {locale === "en" ? "I" : "墨"}
              </div>
              <span className="text-base font-semibold text-ink tracking-tight">
                {locale === "en" ? "InkSight" : "墨鱼InkSight"}
              </span>
            </div>
            <p className="text-sm text-ink-light leading-relaxed">
              {t(locale, "footer.desc")}
            </p>
          </div>

          {/* Links */}
          <div>
            <h4 className="text-sm font-semibold text-ink mb-3">{t(locale, "footer.links")}</h4>
            <ul className="space-y-2 text-sm text-ink-light">
              <li>
                <a
                  href="https://github.com/datascale-ai/inksight"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-ink transition-colors inline-flex items-center gap-1.5"
                >
                  <Github size={14} />
                  {t(locale, "footer.githubRepo")}
                </a>
              </li>
              <li>
                <a
                  href="https://github.com/datascale-ai/inksight/blob/main/docs/hardware.md"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-ink transition-colors"
                >
                  {t(locale, "footer.hardwareGuide")}
                </a>
              </li>
              <li>
                <a
                  href="https://github.com/datascale-ai/inksight/blob/main/docs/api.md"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-ink transition-colors"
                >
                  {t(locale, "footer.apiDocs")}
                </a>
              </li>
            </ul>
          </div>

          {/* Tech */}
          <div>
            <h4 className="text-sm font-semibold text-ink mb-3">{t(locale, "footer.techStack")}</h4>
            <ul className="space-y-2 text-sm text-ink-light">
              <li>{t(locale, "footer.tech.item1")}</li>
              <li>{t(locale, "footer.tech.item2")}</li>
              <li>{t(locale, "footer.tech.item3")}</li>
            </ul>
          </div>
        </div>

        <div className="mt-10 pt-6 border-t border-ink/10 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-xs text-ink-light">
            &copy; {new Date().getFullYear()} {locale === "en" ? "InkSight" : "墨鱼InkSight"}. Released under the MIT License.
          </p>
          <p className="text-xs text-ink-light">
            {t(locale, "footer.tagline")}
          </p>
        </div>
      </div>
    </footer>
  );
}
