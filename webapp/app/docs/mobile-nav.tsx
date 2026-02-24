"use client";

import { useState } from "react";
import Link from "next/link";
import { BookOpen, ChevronDown, ChevronUp } from "lucide-react";

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

export function DocsMobileNav() {
  const [open, setOpen] = useState(false);

  return (
    <div className="border border-ink/10 rounded-sm">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-ink"
      >
        <span className="flex items-center gap-2">
          <BookOpen size={15} />
          目录
        </span>
        {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>

      {open && (
        <div className="border-t border-ink/10 px-4 py-3 space-y-4">
          {sidebarSections.map((section) => (
            <div key={section.title}>
              <h4 className="text-xs font-semibold text-ink-light uppercase tracking-widest mb-1.5">
                {section.title}
              </h4>
              <ul className="space-y-0.5">
                {section.items.map((item) => (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className="block py-1 text-sm text-ink-muted hover:text-ink transition-colors"
                      onClick={() => setOpen(false)}
                    >
                      {item.label}
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
