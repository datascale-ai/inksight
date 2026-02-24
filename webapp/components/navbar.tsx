"use client";

import { useState } from "react";
import Link from "next/link";
import { Menu, X, Github } from "lucide-react";

const navLinks = [
  { href: "/", label: "首页" },
  { href: "/docs", label: "文档" },
  { href: "/flash", label: "在线刷机" },
  { href: "/store", label: "插件市场" },
];

export function Navbar() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 w-full border-b border-ink/10 bg-white/80 backdrop-blur-md">
      <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-2 group">
          <div className="flex h-8 w-8 items-center justify-center rounded-sm border border-ink bg-ink text-white text-xs font-bold font-serif">
            墨
          </div>
          <span className="text-lg font-semibold text-ink tracking-tight">
            InkSight
          </span>
        </Link>

        {/* Desktop nav */}
        <div className="hidden md:flex items-center gap-8">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
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
                href={link.href}
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
          </div>
        </div>
      )}
    </header>
  );
}
