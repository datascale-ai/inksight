import Image from "next/image";
import Link from "next/link";
import { cookies } from "next/headers";
import { Lightbulb, Zap } from "lucide-react";
import { normalizeLocale, withLocalePath } from "@/lib/i18n";

export default async function DocsPage() {
  const locale = normalizeLocale((await cookies()).get("ink_locale")?.value);
  if (locale === "en") {
    return (
      <article className="docs-prose">
        <div className="flex items-center justify-between gap-4 mb-8">
          <h1 className="!mb-0">Quick Start</h1>
          <div className="flex-shrink-0">
            <Image
              src="/images/QQ_EN.jpg"
              alt="QQ Group"
              width={192}
              height={96}
              className="h-24 w-auto object-contain rounded-md border border-ink/10 shadow-sm"
            />
          </div>
        </div>
        <blockquote>
          InkSight is a calm e-ink desk companion. Start with the recommended hardware, flash the firmware, connect Wi-Fi,
          then configure content from the web app.
        </blockquote>
        <p>
          If you want to understand the website before wiring hardware, start with the website guide. It walks through
          the actual product entry points: discover, no-device preview, flashing, device config, and profile settings.
        </p>
        <h2>Suggested Reading Order</h2>
        <ul>
          <li><Link href={withLocalePath(locale, "/docs/website")}>Website Guide</Link></li>
          <li><Link href={withLocalePath(locale, "/docs/hardware")}>Hardware</Link></li>
          <li><Link href={withLocalePath(locale, "/docs/assembly")}>Assembly Guide</Link></li>
          <li><Link href={withLocalePath(locale, "/docs/flash")}>Web Flasher</Link></li>
          <li><Link href={withLocalePath(locale, "/docs/api-key")}>Configure API Key</Link></li>
          <li><Link href={withLocalePath(locale, "/docs/config")}>Device Configuration</Link></li>
          <li><Link href={withLocalePath(locale, "/docs/deploy")}>Local Deployment</Link></li>
        </ul>
        <div className="callout callout-tip">
          <div className="callout-icon">
            <Lightbulb size={16} />
          </div>
          <div>
            <p className="callout-title">Tip</p>
            <p>For a first build, use USB power and the recommended `ESP32-C3 + 4.2-inch e-paper` setup.</p>
          </div>
        </div>
      <div className="callout callout-important">
        <div className="callout-icon">
          <Zap size={16} />
        </div>
        <div>
          <p className="callout-title">Where settings live</p>
          <p>
            In the current version, use <strong>Device Configuration</strong> to manage device display behavior and modes, and <strong>Profile</strong> to manage AI compute resources (including platform free quota and custom LLM API keys).
          </p>
        </div>
      </div>
      </article>
    );
  }

  return (
    <article className="docs-prose">
      <div className="flex items-center justify-between gap-4 mb-8">
        <h1 className="!mb-0">快速开始</h1>
        <div className="flex-shrink-0">
          <Image
            src="/images/QQ.jpg"
            alt="QQ Group"
            width={192}
            height={96}
            className="h-24 w-auto object-contain rounded-md border border-ink/10 shadow-sm"
          />
        </div>
      </div>
      <blockquote>
        InkSight 是一块适合放在桌面的电子墨水信息屏。先准备推荐硬件，完成刷机与配网，再通过 WebApp 配置内容即可。
      </blockquote>
      <p>
        如果你现在更关心“官网能做什么、应该从哪里开始”，建议先读<strong>网站使用指南</strong>。它会按真实入口带你走一遍
        模式广场、无设备体验、在线刷机、设备配置和个人信息页。
      </p>
      <h2>建议阅读顺序</h2>
      <ul>
        <li><Link href={withLocalePath(locale, "/docs/website")}>网站使用指南</Link></li>
        <li><Link href={withLocalePath(locale, "/docs/hardware")}>硬件清单</Link></li>
        <li><Link href={withLocalePath(locale, "/docs/assembly")}>组装指南</Link></li>
        <li><Link href={withLocalePath(locale, "/docs/flash")}>Web 在线刷机</Link></li>
        <li><Link href={withLocalePath(locale, "/docs/api-key")}>配置 API Key</Link></li>
        <li><Link href={withLocalePath(locale, "/docs/config")}>设备配置</Link></li>
        <li><Link href={withLocalePath(locale, "/docs/deploy")}>本地部署</Link></li>
      </ul>
      <div className="callout callout-tip">
        <div className="callout-icon">
          <Lightbulb size={16} />
        </div>
        <div>
          <p className="callout-title">入门建议</p>
          <p>
            第一次搭建建议使用 <strong>ESP32-C3 + 4.2寸 SPI 墨水屏模块</strong>，并优先使用 USB 供电排障。
          </p>
        </div>
      </div>
      <div className="callout callout-important">
        <div className="callout-icon">
          <Zap size={16} />
        </div>
        <div>
          <p className="callout-title">当前产品入口</p>
      <p>
        当前版本中，<strong>设备配置页</strong>用于管理设备的展示行为与模式，<strong>个人信息页</strong>则用于管理 AI 算力（包括平台免费额度和自定义大模型 API Key）。
      </p>
        </div>
      </div>
      <hr />
      <p>
        如果你要本地开发、自托管部署、联调预览或刷机流程，请直接查看{" "}
        <Link href={withLocalePath(locale, "/docs/deploy")}>本地部署</Link>{" "}
        文档。
      </p>
    </article>
  );
}
