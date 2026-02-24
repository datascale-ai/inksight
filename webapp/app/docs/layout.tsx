import Link from "next/link";
import { BookOpen } from "lucide-react";
import { DocsMobileNav } from "./mobile-nav";

const sidebarSections = [
  {
    title: "入门",
    items: [
      { label: "项目介绍", href: "/docs" },
      { label: "硬件清单", href: "/docs/hardware" },
      { label: "组装指南", href: "/docs/assembly" },
    ],
  },
  {
    title: "使用",
    items: [
      { label: "Web 在线刷机", href: "/docs/flash" },
      { label: "配置 API Key", href: "/docs/api-key" },
      { label: "Web 配置后台", href: "/docs/config" },
    ],
  },
  {
    title: "进阶",
    items: [
      { label: "插件开发", href: "/docs/plugin-dev" },
      { label: "API 参考", href: "/docs/api-reference" },
      { label: "常见问题", href: "/docs/faq" },
    ],
  },
];

function Sidebar() {
  return (
    <nav className="space-y-6">
      {sidebarSections.map((section) => (
        <div key={section.title}>
          <h4 className="text-xs font-semibold text-ink-light uppercase tracking-widest mb-2.5 px-3">
            {section.title}
          </h4>
          <ul className="space-y-0.5">
            {section.items.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className="block px-3 py-1.5 text-sm text-ink-muted rounded-sm hover:text-ink hover:bg-ink/[0.04] transition-colors"
                >
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}

export default function DocsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
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
              <span className="text-sm font-semibold text-ink">文档中心</span>
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
