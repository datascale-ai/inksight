import type { Metadata } from "next";
import { Inter, Noto_Serif_SC } from "next/font/google";
import { cookies } from "next/headers";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { normalizeLocale, t } from "@/lib/i18n";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

const notoSerifSc = Noto_Serif_SC({
  subsets: ["latin"],
  weight: ["400", "700"],
  variable: "--font-noto-serif-sc",
});

const baseMetadata: Metadata = {
  title: "墨鱼AI墨水屏 | InkSight",
  description: "墨鱼AI墨水屏（InkSight），一款支持在线刷机、模式配置与模式广场的 AI 电子墨水屏桌面伴侣。",
  keywords: ["InkSight", "墨鱼AI墨水屏", "墨鱼", "电子墨水屏", "E-Ink", "ESP32", "LLM", "桌面摆件"],
  manifest: "/manifest.json",
  other: {
    "apple-mobile-web-app-capable": "yes",
    "apple-mobile-web-app-status-bar-style": "black-translucent",
    "mobile-web-app-capable": "yes",
  },
};

export async function generateMetadata(): Promise<Metadata> {
  const locale = normalizeLocale((await cookies()).get("ink_locale")?.value);
  return {
    ...baseMetadata,
    title: t(locale, "meta.title"),
    description: t(locale, "meta.description"),
  };
}

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const locale = normalizeLocale((await cookies()).get("ink_locale")?.value);
  const lang = locale === "en" ? "en-US" : "zh-CN";

  return (
    <html lang={lang}>
      <body className={`${inter.variable} ${notoSerifSc.variable} antialiased`}>
        <Navbar />
        <main className="min-h-screen">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
