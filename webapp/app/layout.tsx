import type { Metadata } from "next";
import { Inter, Noto_Serif_SC } from "next/font/google";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
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
  title: "InkSight 墨见 — 桌面上的斯多葛哲学家",
  description:
    "一款极简主义的智能电子墨水屏桌面摆件，通过 LLM 生成有温度的慢信息。支持 10 种内容模式，ESP32-C3 驱动，BOM 成本不到 $30。",
  keywords: ["InkSight", "墨见", "电子墨水屏", "E-Ink", "ESP32", "LLM", "桌面摆件"],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className={`${inter.variable} ${notoSerifSc.variable} antialiased`}>
        <Navbar />
        <main className="min-h-screen">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
