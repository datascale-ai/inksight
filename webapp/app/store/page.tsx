"use client";

import { useState } from "react";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Search,
  Download,
  Copy,
  Check,
  BookOpen,
  Flame,
  CircleDot,
  CloudSun,
  Newspaper,
  Palette,
  UtensilsCrossed,
  Dumbbell,
  ScrollText,
  Timer,
  Bitcoin,
  Clock,
} from "lucide-react";

interface Plugin {
  id: number;
  name: string;
  author: string;
  downloads: string;
  desc: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  config: Record<string, unknown>;
}

const PLUGINS: Plugin[] = [
  {
    id: 1,
    name: "Stoic Philosophy",
    author: "Official",
    downloads: "12k",
    desc: "每日斯多葛哲学语录，庄重内省，适合工作日清晨",
    icon: BookOpen,
    config: {
      mode: "stoic",
      language: "zh-CN",
      tone: "profound",
      refresh_interval: 3600,
    },
  },
  {
    id: 2,
    name: "Crypto Ticker",
    author: "GeekUser",
    downloads: "5k",
    desc: "实时加密货币价格看板，支持 BTC/ETH 等主流币种",
    icon: Bitcoin,
    config: {
      mode: "custom",
      plugin: "crypto-ticker",
      coins: ["BTC", "ETH", "SOL"],
      refresh_interval: 300,
    },
  },
  {
    id: 3,
    name: "Pomodoro",
    author: "Productivity",
    downloads: "3k",
    desc: "番茄工作法倒计时，专注与休息交替进行",
    icon: Clock,
    config: {
      mode: "countdown",
      events: [
        { name: "专注时间", minutes: 25 },
        { name: "短休息", minutes: 5 },
      ],
    },
  },
  {
    id: 4,
    name: "AI Artwall",
    author: "Official",
    downloads: "8k",
    desc: "根据天气和节气生成黑白版画风格的艺术作品",
    icon: Palette,
    config: {
      mode: "artwall",
      style: "woodcut",
      language: "zh-CN",
      refresh_interval: 7200,
    },
  },
  {
    id: 5,
    name: "Daily Recipe",
    author: "FoodLover",
    downloads: "4k",
    desc: "时令食材推荐早中晚三餐方案，荤素搭配",
    icon: UtensilsCrossed,
    config: {
      mode: "recipe",
      language: "zh-CN",
      dietary: "balanced",
      refresh_interval: 21600,
    },
  },
  {
    id: 6,
    name: "Fitness Timer",
    author: "HealthGuru",
    downloads: "2k",
    desc: "简单的居家健身训练计划，动作列表 + 健康提示",
    icon: Dumbbell,
    config: {
      mode: "fitness",
      difficulty: "beginner",
      duration_minutes: 15,
      refresh_interval: 86400,
    },
  },
  {
    id: 7,
    name: "毒舌吐槽",
    author: "Official",
    downloads: "9k",
    desc: "犀利的中文吐槽，用黑色幽默缓解压力",
    icon: Flame,
    config: {
      mode: "roast",
      language: "zh-CN",
      tone: "humorous",
      refresh_interval: 1800,
    },
  },
  {
    id: 8,
    name: "禅意",
    author: "Official",
    downloads: "7k",
    desc: "极简的汉字展示，如「静」「空」，营造宁静氛围",
    icon: CircleDot,
    config: {
      mode: "zen",
      language: "zh-CN",
      refresh_interval: 3600,
    },
  },
  {
    id: 9,
    name: "每日诗词",
    author: "LiteraryFan",
    downloads: "6k",
    desc: "精选古典诗词，感受唐诗宋词之美",
    icon: ScrollText,
    config: {
      mode: "poetry",
      language: "zh-CN",
      era: "classical",
      refresh_interval: 7200,
    },
  },
  {
    id: 10,
    name: "Tech Briefing",
    author: "Official",
    downloads: "10k",
    desc: "Hacker News Top 3 + Product Hunt #1，AI 行业洞察",
    icon: Newspaper,
    config: {
      mode: "briefing",
      sources: ["hackernews", "producthunt"],
      language: "zh-CN",
      refresh_interval: 3600,
    },
  },
  {
    id: 11,
    name: "每日推荐",
    author: "Official",
    downloads: "8k",
    desc: "语录、书籍推荐、冷知识、节气信息的丰富组合",
    icon: CloudSun,
    config: {
      mode: "daily",
      language: "zh-CN",
      refresh_interval: 3600,
    },
  },
  {
    id: 12,
    name: "纪念日倒计时",
    author: "MemoryKeeper",
    downloads: "3k",
    desc: "重要日期倒计时/正计日，纪念日提醒",
    icon: Timer,
    config: {
      mode: "countdown",
      events: [
        { name: "示例事件", date: "2026-12-31" },
      ],
    },
  },
];

export default function StorePage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedPlugin, setSelectedPlugin] = useState<Plugin | null>(null);
  const [copied, setCopied] = useState(false);

  const filteredPlugins = PLUGINS.filter(
    (p) =>
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.desc.includes(searchQuery) ||
      p.author.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      {/* Page Header */}
      <div className="text-center mb-12">
        <h1 className="font-serif text-3xl md:text-4xl font-bold text-ink mb-3">
          插件市场
        </h1>
        <p className="text-ink-light max-w-lg mx-auto">
          探索和安装社区贡献的 InkSight 内容插件，一键生成配置
        </p>
      </div>

      {/* Search Bar */}
      <div className="relative max-w-2xl mx-auto mb-12">
        <Search
          size={18}
          className="absolute left-4 top-1/2 -translate-y-1/2 text-ink-light"
        />
        <input
          type="text"
          placeholder="搜索插件..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-11 pr-4 py-3 rounded-sm border border-ink/10 bg-white text-sm text-ink placeholder:text-ink-light/60 focus:outline-none focus:border-ink/30 transition-colors"
        />
      </div>

      {/* Plugin Grid */}
      {filteredPlugins.length === 0 ? (
        <div className="text-center py-20">
          <p className="text-ink-light">没有找到匹配的插件</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredPlugins.map((plugin) => (
            <Card
              key={plugin.id}
              className="flex flex-col group hover:border-ink/20 transition-all duration-200"
            >
              {/* Image placeholder */}
              <div className="h-40 bg-paper-dark border-b border-ink/5 flex items-center justify-center">
                <plugin.icon
                  size={36}
                  className="text-ink/20 group-hover:text-ink/40 transition-colors"
                />
              </div>

              <CardContent className="flex-1 p-5">
                <div className="flex items-start justify-between mb-2">
                  <h3 className="text-base font-semibold text-ink">
                    {plugin.name}
                  </h3>
                </div>
                <p className="text-xs text-ink-light mb-3">
                  by{" "}
                  <span className="text-ink-muted font-medium">
                    @{plugin.author}
                  </span>
                </p>
                <p className="text-sm text-ink-light leading-relaxed line-clamp-2">
                  {plugin.desc}
                </p>
              </CardContent>

              <CardFooter className="p-5 pt-0 flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-xs text-ink-light">
                  <Download size={12} />
                  <span>{plugin.downloads}</span>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setSelectedPlugin(plugin);
                    setCopied(false);
                  }}
                >
                  安装
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}

      {/* Install Dialog */}
      <Dialog
        open={selectedPlugin !== null}
        onClose={() => setSelectedPlugin(null)}
      >
        <DialogContent>
          <DialogHeader onClose={() => setSelectedPlugin(null)}>
            <DialogTitle>安装 {selectedPlugin?.name}</DialogTitle>
            <DialogDescription>
              复制以下 JSON 配置到你的 InkSight 设备配置中
            </DialogDescription>
          </DialogHeader>

          <div className="relative">
            <pre className="rounded-sm border border-ink/10 bg-paper p-4 text-sm font-mono text-ink overflow-x-auto max-h-64 overflow-y-auto">
              {selectedPlugin
                ? JSON.stringify(selectedPlugin.config, null, 2)
                : ""}
            </pre>
            <button
              onClick={() =>
                selectedPlugin &&
                handleCopy(JSON.stringify(selectedPlugin.config, null, 2))
              }
              className="absolute top-3 right-3 p-1.5 rounded-sm border border-ink/10 bg-white hover:bg-paper-dark transition-colors"
              title="复制到剪贴板"
            >
              {copied ? (
                <Check size={14} className="text-green-600" />
              ) : (
                <Copy size={14} className="text-ink-light" />
              )}
            </button>
          </div>

          <div className="mt-4 flex justify-end gap-3">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSelectedPlugin(null)}
            >
              关闭
            </Button>
            <Button
              size="sm"
              onClick={() =>
                selectedPlugin &&
                handleCopy(JSON.stringify(selectedPlugin.config, null, 2))
              }
            >
              {copied ? "已复制" : "复制配置"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
