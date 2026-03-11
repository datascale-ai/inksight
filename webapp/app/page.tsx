import Link from "next/link";
import Image from "next/image";
import { cookies } from "next/headers";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { normalizeLocale, withLocalePath } from "@/lib/i18n";
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
  Calendar,
  Mail,
  Globe,
  HelpCircle,
  MessageCircleQuestion,
  Lightbulb,
  PenTool,
  BarChart3,
  Target,
  Plus,
} from "lucide-react";

const coreModes = [
  {
    name: "DAILY",
    label: "每日",
    desc: "语录、书籍推荐、冷知识的综合日报",
    descLines: ["语录、书籍推荐、", "冷知识的综合日报"],
    icon: CloudSun,
  },
  {
    name: "WEATHER",
    label: "天气",
    desc: "实时天气和未来趋势看板",
    descLines: ["实时天气和未来", "趋势看板"],
    icon: CloudSun,
  },
  {
    name: "POETRY",
    label: "诗词",
    desc: "古诗词与简短注解",
    descLines: ["古诗词与简短注解"],
    icon: ScrollText,
  },
  {
    name: "ARTWALL",
    label: "画廊",
    desc: "根据时令生成黑白艺术画",
    descLines: ["根据时令生成", "黑白艺术画"],
    icon: Palette,
  },
  {
    name: "ALMANAC",
    label: "老黄历",
    desc: "农历节气与宜忌",
    descLines: ["农历节气与宜忌"],
    icon: Calendar,
  },
  {
    name: "BRIEFING",
    label: "简报",
    desc: "科技热榜 + AI 洞察简报",
    descLines: ["科技热榜 + AI", "洞察简报"],
    icon: Newspaper,
  },
];

const moreModes = [
  {
    name: "STOIC",
    label: "斯多葛",
    desc: "每日一句哲学箴言",
    icon: BookOpen,
  },
  {
    name: "ZEN",
    label: "禅意",
    desc: "一个大字表达当下心境",
    icon: CircleDot,
  },
  {
    name: "RECIPE",
    label: "食谱",
    desc: "按时段推荐三餐方案",
    icon: UtensilsCrossed,
  },
  {
    name: "COUNTDOWN",
    label: "倒计时",
    desc: "重要日程倒计时/正计时",
    icon: Timer,
  },
  {
    name: "MEMO",
    label: "便签",
    desc: "展示自定义便签文字",
    icon: ScrollText,
  },
  {
    name: "HABIT",
    label: "打卡",
    desc: "每日习惯完成进度",
    icon: Target,
  },
  {
    name: "ROAST",
    label: "毒舌",
    desc: "轻松幽默的吐槽风格内容",
    icon: Flame,
  },
  {
    name: "FITNESS",
    label: "健身",
    desc: "居家健身动作与建议",
    icon: Dumbbell,
  },
  {
    name: "LETTER",
    label: "慢信",
    desc: "来自不同时空的一封慢信",
    icon: Mail,
  },
  {
    name: "THISDAY",
    label: "今日历史",
    desc: "历史上的今天重大事件",
    icon: Globe,
  },
  {
    name: "RIDDLE",
    label: "每日一谜",
    desc: "谜语、脑筋急转弯、趣味知识题",
    icon: HelpCircle,
  },
  {
    name: "QUESTION",
    label: "每日一问",
    desc: "一个值得思考的开放式问题",
    icon: MessageCircleQuestion,
  },
  {
    name: "BIAS",
    label: "认知偏差",
    desc: "每天认识一个认知偏差或心理学效应",
    icon: Lightbulb,
  },
  {
    name: "STORY",
    label: "微故事",
    desc: "一个完整的三段式微型小说",
    icon: PenTool,
  },
  {
    name: "LIFEBAR",
    label: "人生进度条",
    desc: "年/月/周/人生的进度可视化",
    icon: BarChart3,
  },
  {
    name: "CHALLENGE",
    label: "微挑战",
    desc: "每天一个5分钟可完成的小挑战",
    icon: Target,
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

const modeTextEn: Record<string, { label: string; desc: string; descLines?: string[] }> = {
  DAILY: { label: "Daily", desc: "Quotes, book picks and curious facts", descLines: ["Quotes, book picks", "and curious facts"] },
  WEATHER: { label: "Weather", desc: "Live weather and trend board", descLines: ["Live weather and", "trend board"] },
  POETRY: { label: "Poetry", desc: "Classical poems with short notes", descLines: ["Classical poems", "with short notes"] },
  ARTWALL: { label: "Gallery", desc: "Seasonal black-and-white artwork", descLines: ["Seasonal B/W", "artwork"] },
  ALMANAC: { label: "Almanac", desc: "Lunar calendar and daily dos", descLines: ["Lunar calendar", "and daily dos"] },
  BRIEFING: { label: "Briefing", desc: "Tech hot topics + AI insights", descLines: ["Tech topics + AI", "insight brief"] },
  STOIC: { label: "Stoic", desc: "A daily philosophical quote" },
  ZEN: { label: "Zen", desc: "One large character for your mood" },
  RECIPE: { label: "Recipe", desc: "Meal ideas by time of day" },
  COUNTDOWN: { label: "Countdown", desc: "Countdown or count-up for events" },
  MEMO: { label: "Memo", desc: "Display your custom note text" },
  HABIT: { label: "Habit", desc: "Daily habit completion progress" },
  ROAST: { label: "Roast", desc: "Light, humorous roasting style" },
  FITNESS: { label: "Fitness", desc: "Home workout tips and moves" },
  LETTER: { label: "Letter", desc: "A slow letter across time" },
  THISDAY: { label: "On This Day", desc: "Historic events of today" },
  RIDDLE: { label: "Riddle", desc: "Riddles and brain teasers" },
  QUESTION: { label: "Question", desc: "One open-ended question each day" },
  BIAS: { label: "Bias", desc: "A cognitive bias per day" },
  STORY: { label: "Story", desc: "A complete micro-story in three acts" },
  LIFEBAR: { label: "Life Bar", desc: "Progress view for year/month/week/life" },
  CHALLENGE: { label: "Challenge", desc: "A 5-minute daily micro challenge" },
};

export default async function Home() {
  const locale = normalizeLocale((await cookies()).get("ink_locale")?.value);
  const isEn = locale === "en";
  const coreModesLocalized = coreModes.map((mode) => ({
    ...mode,
    label: isEn ? (modeTextEn[mode.name]?.label || mode.label) : mode.label,
    desc: isEn ? (modeTextEn[mode.name]?.desc || mode.desc) : mode.desc,
    descLines: isEn ? (modeTextEn[mode.name]?.descLines || mode.descLines) : mode.descLines,
  }));
  const moreModesLocalized = moreModes.map((mode) => ({
    ...mode,
    label: isEn ? (modeTextEn[mode.name]?.label || mode.label) : mode.label,
  }));
  const specsLocalized = isEn
    ? [
        { icon: Cpu, label: "ESP32-C3", desc: "RISC-V architecture, WiFi, low power" },
        { icon: Monitor, label: '4.2" E-Paper', desc: "400x300 resolution, paper-like and glare-free" },
        { icon: Battery, label: "6-Month Battery", desc: "LiFePO4 battery + Deep Sleep mode" },
        { icon: DollarSign, label: "BOM < CNY 220", desc: "Open hardware for everyone" },
      ]
    : specs;

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
                {isEn ? "InkSight E-Ink" : "InkSight 墨水屏"}
                <br />
                <span className="text-ink-muted text-3xl md:text-4xl lg:text-5xl">
                  {isEn ? "Your Multi-Scenario AI Companion on Desk" : "桌面上的多场景AI搭档"}
                </span>
              </h1>
              <p className="text-lg text-ink-light leading-relaxed mb-8 max-w-lg">
                {isEn
                  ? "A minimalist smart E-Ink desktop device. InkSight uses LLMs to generate warm, slow information for your daily desk flow."
                  : "一款极简主义的智能电子墨水屏桌面摆件，通过 LLM 生成有温度的「慢信息」。数十种内容模式，从每日推荐到 AI 简报，为你的桌面带来有温度的智能陪伴。"}
              </p>
              <div className="flex flex-col sm:flex-row gap-3">
                <Link href={withLocalePath(locale, "/flash")}>
                  <Button
                    variant="outline"
                    size="lg"
                    className="bg-white text-ink border-ink/20 hover:bg-ink hover:text-white active:bg-ink active:text-white"
                  >
                    {isEn ? "Build Yours" : "开始制作"}
                  </Button>
                </Link>
              </div>
            </div>

            {/* Product Image */}
            <div className="flex items-center justify-center animate-fade-in">
              <div className="relative w-full max-w-md aspect-[4/3] rounded-sm border border-ink/10 overflow-hidden">
                <Image
                  src="/images/intro.jpg"
                  alt={isEn ? "InkSight product preview" : "InkSight 展示图"}
                  fill
                  className="object-cover"
                  priority
                  unoptimized
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
              {isEn ? "Core Features" : "核心特性"}
            </h2>
            <p className="text-ink-light">
              {isEn ? "Hardware + software + AI, one integrated desk experience" : "硬件 + 软件 + AI，三位一体的桌面智能体验"}
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              {
                icon: Brain,
                title: isEn ? "AI Powered" : "AI 驱动",
                desc: isEn ? "Connect DeepSeek / Qwen / Kimi to generate contextual content in real time." : "接入 DeepSeek / 通义千问 / Kimi，根据天气、时间、节气实时生成个性化内容。",
              },
              {
                icon: Layers,
                title: isEn ? "E-Ink Experience" : "电子墨水",
                desc: isEn ? '4.2" E-Paper display with paper-like feeling, glare-free and distraction-free.' : "4.2 英寸 E-Paper 显示屏，类纸质感，不发光，专注不打扰，单次充电续航 6 个月。",
              },
              {
                icon: LayoutGrid,
                title: isEn ? "Highly Extensible" : "无限扩展",
                desc: isEn ? "Multiple content modes and refresh strategies, from philosophy to market snapshots." : "支持 10 种内容模式和 4 种刷新策略，从哲学语录到股票行情，满足一切需求。",
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

      {/* Showcase Section */}
      <section className="border-t border-ink/10">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <div className="text-center mb-14">
            <h2 className="font-serif text-3xl font-bold text-ink mb-3">
              {isEn ? "Rich Content Modes" : "多种内容模式"}
            </h2>
            <p className="text-ink-light">
              {isEn ? "From philosophy to daily life, there is always a slow-information mode for you." : "从哲学思辨到烟火日常，总有一款属于你的「慢信息」，支持自定义模式，支持 AI 生成模式。"}
            </p>
          </div>

          <div className="mb-6 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-4">
            {coreModesLocalized.map((mode) => (
              <div key={mode.name} className="aspect-square">
                <Card className="group h-full p-3 md:p-4 hover:border-ink/20 transition-all duration-200 hover:-translate-y-0.5">
                  <CardContent className="h-full p-0 text-center flex flex-col items-center">
                    <div>
                      <div className="inline-flex items-center justify-center w-9 h-9 md:w-10 md:h-10 rounded-sm bg-paper-dark mb-2.5 group-hover:bg-ink group-hover:text-white transition-colors">
                        <mode.icon size={16} />
                      </div>
                      <h4 className="text-[10px] md:text-[11px] font-semibold text-ink tracking-wider uppercase mb-1">
                        {mode.name}
                      </h4>
                      <p className="font-serif text-sm md:text-base font-medium text-ink mb-1 line-clamp-1">
                        {mode.label}
                      </p>
                    </div>
                    {Array.isArray(mode.descLines) && mode.descLines.length > 0 ? (
                      <div className="mt-auto w-full text-[10px] md:text-[11px] text-ink-light leading-4 text-center">
                        {mode.descLines.map((line) => (
                          <span key={`${mode.name}-${line}`} className="block w-full text-center break-keep">
                            {line}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="mt-auto w-full text-[10px] md:text-[11px] text-ink-light leading-4 whitespace-normal break-keep text-center">
                        {mode.desc}
                      </p>
                    )}
                  </CardContent>
                </Card>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-10 gap-4">
            {moreModesLocalized.slice(0, 8).map((mode) => (
              <div key={mode.name} className="aspect-square">
                <Card className="group h-full p-3 md:p-4 hover:border-ink/20 transition-all duration-200 hover:-translate-y-0.5">
                  <CardContent className="h-full p-0 text-center flex flex-col items-center">
                    <div className="inline-flex items-center justify-center w-9 h-9 rounded-sm bg-paper-dark mb-2.5 group-hover:bg-ink group-hover:text-white transition-colors">
                      <mode.icon size={16} />
                    </div>
                    <h4 className="text-[9px] md:text-[10px] font-semibold text-ink tracking-wider uppercase mb-1">
                      {mode.name}
                    </h4>
                    <p className="font-serif text-xs md:text-sm font-medium text-ink mb-1 leading-4 min-h-4 whitespace-nowrap">
                      {mode.label}
                    </p>
                  </CardContent>
                </Card>
              </div>
            ))}

            <div className="aspect-square md:aspect-auto md:row-span-2 md:col-span-2 md:col-start-9 md:row-start-1">
              <Card className="group h-full p-3 md:p-4 border-dashed hover:border-ink/30 transition-all duration-200 hover:-translate-y-0.5">
                <CardContent className="h-full p-0 text-center flex flex-col items-center justify-center">
                  <div className="inline-flex items-center justify-center w-10 h-10 md:w-12 md:h-12 rounded-sm border border-ink/20 mb-2.5 group-hover:bg-ink group-hover:text-white group-hover:border-ink transition-colors">
                    <Plus size={18} />
                  </div>
                  <h4 className="text-[10px] md:text-xs font-semibold text-ink tracking-wider uppercase mb-1">
                    CUSTOM
                  </h4>
                  <p className="font-serif text-sm md:text-base font-medium text-ink mb-1">
                    {isEn ? "Custom Mode" : "自定义模式"}
                  </p>
                  <p className="text-[clamp(10px,0.9vw,12px)] text-ink-light leading-[1.35] whitespace-normal break-words text-balance">
                    {isEn ? "Define your own content" : "更多内容，由你定义"}
                  </p>
                </CardContent>
              </Card>
            </div>

            {moreModesLocalized.slice(8).map((mode) => (
              <div key={mode.name} className="aspect-square">
                <Card className="group h-full p-3 md:p-4 hover:border-ink/20 transition-all duration-200 hover:-translate-y-0.5">
                  <CardContent className="h-full p-0 text-center flex flex-col items-center">
                    <div className="inline-flex items-center justify-center w-9 h-9 rounded-sm bg-paper-dark mb-2.5 group-hover:bg-ink group-hover:text-white transition-colors">
                      <mode.icon size={16} />
                    </div>
                    <h4 className="text-[9px] md:text-[10px] font-semibold text-ink tracking-wider uppercase mb-1">
                      {mode.name}
                    </h4>
                    <p className="font-serif text-xs md:text-sm font-medium text-ink mb-1 leading-4 min-h-4 whitespace-nowrap">
                      {mode.label}
                    </p>
                  </CardContent>
                </Card>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Tech Specs Section */}
      <section className="border-t border-ink/10 bg-ink text-white">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <div className="text-center mb-14">
            <h2 className="font-serif text-3xl font-bold mb-3">
              {isEn ? "Hardware Specs" : "硬件参数"}
            </h2>
            <p className="text-white/60">
              {isEn ? "Approx. BOM cost under CNY 220" : "总 BOM 成本约 220 元以内，人人都能拥有"}
            </p>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {specsLocalized.map((spec) => (
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
            {isEn ? "Start Your InkSight Journey" : "开始你的 InkSight 之旅"}
          </h2>
          <p className="text-ink-light mb-8 max-w-md mx-auto">
            {isEn ? "No coding required. Flash firmware directly in browser with an ESP32 and E-Ink panel." : "无需编程基础，通过浏览器即可完成固件烧录。"}
            {!isEn && (
              <>
                <br />
                只需一块 ESP32 和一块墨水屏。
              </>
            )}
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link href={withLocalePath(locale, "/flash")}>
              <Button size="lg">{isEn ? "Web Flasher" : "在线刷机"}</Button>
            </Link>
            <Link href={withLocalePath(locale, "/config")}>
              <Button variant="outline" size="lg">
                {isEn ? "Device Config" : "设备配置"}
              </Button>
            </Link>
            <a
              href="https://github.com/datascale-ai/inksight"
              target="_blank"
              rel="noopener noreferrer"
            >
              <Button variant="outline" size="lg">
                {isEn ? "View Source" : "查看源码"}
              </Button>
            </a>
          </div>
        </div>
      </section>
    </>
  );
}
