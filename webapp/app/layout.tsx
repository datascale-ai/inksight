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

export const metadata: Metadata = {
  title: "InkSight",
  description: "InkSight E-Ink AI desktop companion.",
  keywords: ["InkSight", "墨见", "电子墨水屏", "E-Ink", "ESP32", "LLM", "桌面摆件"],
  manifest: "/manifest.json",
  other: {
    "apple-mobile-web-app-capable": "yes",
    "apple-mobile-web-app-status-bar-style": "black-translucent",
    "mobile-web-app-capable": "yes",
  },
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const locale = normalizeLocale((await cookies()).get("ink_locale")?.value);
  const title = t(locale, "meta.title");
  const description = t(locale, "meta.description");
  const lang = locale === "en" ? "en-US" : "zh-CN";

  return (
    <html lang={lang}>
      <head>
        <title>{title}</title>
        <meta name="description" content={description} />
      </head>
      <body className={`${inter.variable} ${notoSerifSc.variable} antialiased`}>
        <Navbar />
        <main className="min-h-screen">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
