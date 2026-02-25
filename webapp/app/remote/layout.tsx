"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, History, Settings } from "lucide-react";

const tabs = [
  { href: "/remote", label: "遥控器", icon: Home },
  { href: "/remote/history", label: "时光机", icon: History },
  { href: "/config", label: "设置", icon: Settings, external: true },
];

export default function RemoteLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div className="flex flex-col min-h-screen bg-[#fafaf7]">
      <div className="flex-1 overflow-y-auto pb-20">{children}</div>

      <nav className="fixed bottom-0 inset-x-0 bg-white border-t border-gray-200 z-50">
        <div className="flex justify-around items-center h-16 max-w-md mx-auto">
          {tabs.map((tab) => {
            const isActive =
              tab.href === "/remote"
                ? pathname === "/remote"
                : pathname.startsWith(tab.href);
            const Icon = tab.icon;

            if (tab.external) {
              return (
                <a
                  key={tab.href}
                  href={tab.href}
                  className={`flex flex-col items-center gap-0.5 px-4 py-2 text-xs transition-colors ${
                    isActive
                      ? "text-black font-semibold"
                      : "text-gray-400 hover:text-gray-600"
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  <span>{tab.label}</span>
                </a>
              );
            }

            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={`flex flex-col items-center gap-0.5 px-4 py-2 text-xs transition-colors ${
                  isActive
                    ? "text-black font-semibold"
                    : "text-gray-400 hover:text-gray-600"
                }`}
              >
                <Icon className="w-5 h-5" />
                <span>{tab.label}</span>
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
