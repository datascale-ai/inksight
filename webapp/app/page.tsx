import Link from "next/link";
import Image from "next/image";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Brain,
  Layers,
  LayoutGrid,
  Cpu,
  Monitor,
  Battery,
  DollarSign,
  BookOpen,
  Flame,
  CloudSun,
  Newspaper,
  Palette,
  UtensilsCrossed,
  Dumbbell,
  ScrollText,
  Timer,
  Sparkles,
  CircleDot,
} from "lucide-react";

const modes = [
  {
    name: "STOIC",
    label: "斯多葛哲学",
    desc: "庄重、内省的哲学语录，适合工作日的清晨",
    icon: BookOpen,
  },
  {
    name: "ROAST",
    label: "毒舌吐槽",
    desc: "犀利的中文吐槽，用黑色幽默缓解压力",
    icon: Flame,
  },
  {
    name: "ZEN",
    label: "禅意",
    desc: "极简的汉字，营造宁静氛围",
    icon: CircleDot,
  },
  {
    name: "DAILY",
    label: "每日推荐",
    desc: "语录、书籍推荐、冷知识、节气信息",
    icon: CloudSun,
  },
  {
    name: "BRIEFING",
    label: "AI 简报",
    desc: "Hacker News Top 3 + Product Hunt #1",
    icon: Newspaper,
  },
  {
    name: "ARTWALL",
    label: "AI 画廊",
    desc: "根据天气/节气生成黑白版画风格艺术",
    icon: Palette,
  },
  {
    name: "RECIPE",
    label: "每日食谱",
    desc: "时令食材推荐早中晚三餐方案",
    icon: UtensilsCrossed,
  },
  {
    name: "FITNESS",
    label: "健身计划",
    desc: "简单的居家健身训练计划与健康提示",
    icon: Dumbbell,
  },
  {
    name: "POETRY",
    label: "每日诗词",
    desc: "精选古典诗词，感受文字之美",
    icon: ScrollText,
  },
  {
    name: "COUNTDOWN",
    label: "倒计时",
    desc: "重要日期倒计时/正计日，纪念日提醒",
    icon: Timer,
  },
];

const specs = [
  {
    icon: Cpu,
    label: "ESP32-C3",
    desc: "RISC-V 架构，WiFi 连接，超低功耗",
  },
  {
    icon: Monitor,
    label: '4.2" E-Paper',
    desc: "400x300 分辨率，类纸质感，不发光",
  },
  {
    icon: Battery,
    label: "续航 6 个月",
    desc: "LiFePO4 电池 + Deep Sleep 模式",
  },
  {
    icon: DollarSign,
    label: "BOM < 220 元",
    desc: "开源硬件，人人都能制作",
  },
];

export default function Home() {
  return (
    <>
      {/* Hero Section */}
      <section className="relative overflow-hidden">
        <div className="mx-auto max-w-6xl px-6 py-24 md:py-32">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-12 items-center">
            {/* Text */}
            <div className="animate-slide-up">
              <p className="text-sm text-ink-light tracking-widest uppercase mb-4">
                Open Source &middot; ESP32-C3 &middot; E-Ink
              </p>
              <h1 className="font-serif text-4xl md:text-5xl lg:text-6xl font-bold text-ink leading-tight mb-6">
                InkSight
                <br />
                <span className="text-ink-muted">桌面上的斯多葛哲学家</span>
              </h1>
              <p className="text-lg text-ink-light leading-relaxed mb-8 max-w-lg">
                一款极简主义的智能电子墨水屏桌面摆件，通过 LLM
                生成有温度的「慢信息」。10 种内容模式，从哲学语录到 AI
                简报，为你的桌面带来有温度的智能陪伴。
              </p>
              <div className="flex flex-col sm:flex-row gap-3">
                <Link href="/flash">
                  <Button size="lg">开始制作 (DIY Guide)</Button>
                </Link>
                <Link href="/store">
                  <Button variant="outline" size="lg">
                    在线体验 (Live Demo)
                  </Button>
                </Link>
              </div>
            </div>

            {/* Product Image */}
            <div className="flex items-center justify-center animate-fade-in">
              <div className="relative w-full max-w-md aspect-[4/3] rounded-sm border border-ink/10 overflow-hidden">
                <Image
                  src="/images/intro.jpg"
                  alt="InkSight 展示图"
                  fill
                  className="object-cover"
                  priority
                />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="border-t border-ink/10 bg-paper">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <div className="text-center mb-14">
            <h2 className="font-serif text-3xl font-bold text-ink mb-3">
              核心特性
            </h2>
            <p className="text-ink-light">
              硬件 + 软件 + AI，三位一体的桌面智能体验
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              {
                icon: Brain,
                title: "AI 驱动",
                desc: "接入 DeepSeek / 通义千问 / Kimi，根据天气、时间、节气实时生成个性化内容。",
              },
              {
                icon: Layers,
                title: "电子墨水",
                desc: "4.2 英寸 E-Paper 显示屏，类纸质感，不发光，专注不打扰，单次充电续航 6 个月。",
              },
              {
                icon: LayoutGrid,
                title: "无限扩展",
                desc: "支持 10 种内容模式和 4 种刷新策略，从哲学语录到股票行情，满足一切需求。",
              },
            ].map((feature) => (
              <Card key={feature.title} className="p-8 text-center group hover:border-ink/20 transition-colors">
                <CardContent className="p-0">
                  <div className="inline-flex items-center justify-center w-12 h-12 rounded-sm border border-ink/10 mb-5 group-hover:border-ink/30 transition-colors">
                    <feature.icon size={22} className="text-ink" />
                  </div>
                  <h3 className="text-lg font-semibold text-ink mb-2">
                    {feature.title}
                  </h3>
                  <p className="text-sm text-ink-light leading-relaxed">
                    {feature.desc}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Showcase Section - 10 Modes */}
      <section className="border-t border-ink/10">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <div className="text-center mb-14">
            <h2 className="font-serif text-3xl font-bold text-ink mb-3">
              10 种内容模式
            </h2>
            <p className="text-ink-light">
              从哲学思辨到烟火日常，总有一款属于你的「慢信息」
            </p>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-4">
            {modes.map((mode) => (
              <Card
                key={mode.name}
                className="group p-5 hover:border-ink/20 transition-all duration-200 hover:-translate-y-0.5"
              >
                <CardContent className="p-0 text-center">
                  <div className="inline-flex items-center justify-center w-10 h-10 rounded-sm bg-paper-dark mb-3 group-hover:bg-ink group-hover:text-white transition-colors">
                    <mode.icon size={18} />
                  </div>
                  <h4 className="text-xs font-semibold text-ink tracking-wider uppercase mb-1">
                    {mode.name}
                  </h4>
                  <p className="text-sm font-medium text-ink mb-1">
                    {mode.label}
                  </p>
                  <p className="text-xs text-ink-light leading-snug line-clamp-2">
                    {mode.desc}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Tech Specs Section */}
      <section className="border-t border-ink/10 bg-ink text-white">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <div className="text-center mb-14">
            <h2 className="font-serif text-3xl font-bold mb-3">
              硬件参数
            </h2>
            <p className="text-white/60">
              总 BOM 成本约 220 元以内，人人都能拥有
            </p>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {specs.map((spec) => (
              <div key={spec.label} className="text-center p-6">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-sm border border-white/20 mb-4">
                  <spec.icon size={22} className="text-white/80" />
                </div>
                <h4 className="text-base font-semibold mb-1">{spec.label}</h4>
                <p className="text-sm text-white/50">{spec.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="border-t border-ink/10">
        <div className="mx-auto max-w-6xl px-6 py-20 text-center">
          <Sparkles size={28} className="mx-auto text-ink-light mb-4" />
          <h2 className="font-serif text-3xl font-bold text-ink mb-4">
            开始你的 InkSight 之旅
          </h2>
          <p className="text-ink-light mb-8 max-w-md mx-auto">
            无需编程基础，通过浏览器即可完成固件烧录。
            <br />
            只需一块 ESP32 和一块墨水屏。
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link href="/flash">
              <Button size="lg">在线刷机</Button>
            </Link>
            <a
              href="https://github.com/datascale-ai/inksight"
              target="_blank"
              rel="noopener noreferrer"
            >
              <Button variant="outline" size="lg">
                查看源码
              </Button>
            </a>
          </div>
        </div>
      </section>
    </>
  );
}
