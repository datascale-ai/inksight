"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertCircle, ArrowLeft, ArrowRight, Eye, Loader2, RefreshCw, Shuffle } from "lucide-react";
import { localeFromPathname, t } from "@/lib/i18n";

// 模式元数据（从设备配置页面复制）
const MODE_META: Record<string, { name: string; tip: string }> = {
  DAILY: { name: "每日", tip: "语录、书籍推荐、冷知识的综合日报" },
  WEATHER: { name: "天气", tip: "实时天气和未来趋势看板" },
  WORD_OF_THE_DAY: { name: "每日一词", tip: "每日精选一个英语单词，展示其拼写与释义" },
  ZEN: { name: "禅意", tip: "一个大字表达当下心境" },
  BRIEFING: { name: "简报", tip: "科技热榜 + AI 洞察简报" },
  STOIC: { name: "斯多葛", tip: "每日一句哲学箴言" },
  POETRY: { name: "诗词", tip: "古诗词与简短注解" },
  ARTWALL: { name: "画廊", tip: "根据时令生成黑白艺术画" },
  ALMANAC: { name: "老黄历", tip: "农历、节气、宜忌信息" },
  RECIPE: { name: "食谱", tip: "按时段推荐三餐方案" },
  COUNTDOWN: { name: "倒计时", tip: "重要日程倒计时/正计时" },
  MEMO: { name: "便签", tip: "展示自定义便签文字" },
  HABIT: { name: "打卡", tip: "每日习惯完成进度" },
  ROAST: { name: "毒舌", tip: "轻松幽默的吐槽风格内容" },
  FITNESS: { name: "健身", tip: "居家健身动作与建议" },
  LETTER: { name: "慢信", tip: "来自不同时空的一封慢信" },
  THISDAY: { name: "今日历史", tip: "历史上的今天重大事件" },
  RIDDLE: { name: "猜谜", tip: "谜题与脑筋急转弯" },
  QUESTION: { name: "每日一问", tip: "值得思考的开放式问题" },
  BIAS: { name: "认知偏差", tip: "认知偏差与心理效应" },
  STORY: { name: "微故事", tip: "可在 30 秒内读完的微故事" },
  LIFEBAR: { name: "进度条", tip: "年/月/周/人生进度条" },
  CHALLENGE: { name: "微挑战", tip: "每天一个 5 分钟微挑战" },
};

// 英文模式元数据（用于 /en/preview 下显示）
const MODE_META_EN: Record<string, { name: string; tip: string }> = {
  DAILY: { name: "Everyday", tip: "A daily digest: quotes, book picks, and fun facts" },
  WEATHER: { name: "Weather", tip: "Current weather and forecast dashboard" },
  WORD_OF_THE_DAY: { name: "Word of the Day", tip: "One English word with a short explanation" },
  ZEN: { name: "Zen", tip: "A single character to reflect your mood" },
  BRIEFING: { name: "Briefing", tip: "Tech trends + AI insights briefing" },
  STOIC: { name: "Stoic", tip: "A daily stoic quote" },
  POETRY: { name: "Poetry", tip: "Classical poetry with a short note" },
  ARTWALL: { name: "Gallery", tip: "Seasonal black & white generative art" },
  ALMANAC: { name: "Almanac", tip: "Lunar calendar, solar terms, and daily luck" },
  RECIPE: { name: "Recipe", tip: "Meal ideas based on time of day" },
  COUNTDOWN: { name: "Countdown", tip: "Countdown / count-up for important events" },
  MEMO: { name: "Memo", tip: "Show your custom memo text" },
  HABIT: { name: "Habits", tip: "Daily habit progress" },
  ROAST: { name: "Roast", tip: "Lighthearted, sarcastic daily roast" },
  FITNESS: { name: "Fitness", tip: "At-home workout tips" },
  LETTER: { name: "Letter", tip: "A slow letter from another time" },
  THISDAY: { name: "On This Day", tip: "Major events in history today" },
  RIDDLE: { name: "Riddle", tip: "Riddles and brain teasers" },
  QUESTION: { name: "Daily Question", tip: "A thought-provoking open question" },
  BIAS: { name: "Bias", tip: "A cognitive bias or psychological effect" },
  STORY: { name: "Micro Story", tip: "A complete micro fiction in three parts" },
  LIFEBAR: { name: "Life Bar", tip: "Progress bars for year / month / week / life" },
  CHALLENGE: { name: "Challenge", tip: "A 5-minute daily micro challenge" },
};

const CORE_MODES = ["DAILY", "WEATHER", "POETRY", "ARTWALL", "ALMANAC", "BRIEFING"];
const EXTRA_MODES = Object.keys(MODE_META).filter((m) => !CORE_MODES.includes(m));

type RotateStrategy = "cycle" | "random";

interface ServerModeItem {
  mode_id: string;
  display_name: string;
  description: string;
  source: string;
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="flex items-end justify-between gap-2">
        <label className="block text-sm font-medium text-ink mb-1.5">{label}</label>
        {hint ? <span className="text-xs text-ink-light mb-1.5">{hint}</span> : null}
      </div>
      {children}
    </div>
  );
}

function ModeSection({
  title,
  modes,
  selected,
  current,
  onToggle,
  onPreview,
  collapsible,
  customMeta,
  locale,
}: {
  title: string;
  modes: string[];
  selected: Set<string>;
  current: string;
  onToggle: (m: string) => void;
  onPreview: (m: string) => void;
  collapsible?: boolean;
  customMeta?: Record<string, { name: string; tip: string }>;
  locale: string;
}) {
  const [collapsed, setCollapsed] = useState(false);
  if (!modes.length) return null;

  return (
    <div className="mb-6">
      <div className="flex items-center justify-between gap-2 mb-3 rounded-sm bg-paper-dark border border-ink/10 px-3 py-2">
        <h4 className="text-base font-semibold text-ink">{title}</h4>
        {collapsible ? (
          <button
            onClick={() => setCollapsed((v) => !v)}
            className="text-xs text-ink-light hover:text-ink flex items-center gap-1 transition-colors"
          >
            {collapsed ? "展开" : "收起"}
          </button>
        ) : null}
      </div>
      {collapsed ? null : (
        <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
          {modes.map((m) => {
            const meta =
              (locale === "en" ? MODE_META_EN[m] : MODE_META[m]) ||
              customMeta?.[m] ||
              MODE_META[m] ||
              { name: m, tip: "" };
            const isSelected = selected.has(m);
            const isCurrent = current === m;
            return (
              <div key={m} className="rounded-sm border border-ink/10 bg-white overflow-hidden">
                <button
                  onClick={() => onToggle(m)}
                  className={`w-full px-3 py-2 text-left transition-colors ${
                    isCurrent ? "bg-ink text-white" : "hover:bg-paper-dark text-ink"
                  }`}
                  title={meta.tip}
                >
                  <div className="text-sm font-semibold">{meta.name}</div>
                  <div className={`text-[11px] mt-0.5 ${isCurrent ? "text-white/80" : "text-ink-light"}`}>
                    {isSelected
                      ? t(localeFromPathname(`/${locale}`), "preview.mode.in_playlist", locale === "zh" ? "已加入轮播" : "In playlist")
                      : t(localeFromPathname(`/${locale}`), "preview.mode.not_in_playlist", locale === "zh" ? "未加入轮播" : "Not in playlist")}
                  </div>
                </button>
                <div className="grid grid-cols-2 border-t border-ink/10">
                  <button
                    onClick={() => onPreview(m)}
                    className="px-2 py-2 text-[11px] sm:text-xs text-ink hover:bg-ink hover:text-white transition-colors flex items-center justify-center gap-1 whitespace-nowrap"
                  >
                    <Eye size={14} />
                    {t(localeFromPathname(`/${locale}`), "preview.action.preview", locale === "zh" ? "预览" : "Preview")}
                  </button>
                  <button
                    onClick={() => onToggle(m)}
                    className="px-2 py-2 text-[11px] sm:text-xs text-ink hover:bg-ink hover:text-white transition-colors whitespace-nowrap"
                  >
                    {isSelected
                      ? t(localeFromPathname(`/${locale}`), "preview.action.remove", locale === "zh" ? "移出" : "Remove")
                      : t(localeFromPathname(`/${locale}`), "preview.action.add", locale === "zh" ? "加入" : "Add")}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function ExperiencePage() {
  const pathname = usePathname();
  const locale = localeFromPathname(pathname || "/");

  const [serverModes, setServerModes] = useState<ServerModeItem[]>([]);
  const [modesError, setModesError] = useState<string | null>(null);

  const [selectedModes, setSelectedModes] = useState<Set<string>>(new Set(["DAILY", "WEATHER", "POETRY"]));
  const [previewMode, setPreviewMode] = useState("DAILY");

  const [city, setCity] = useState("杭州");
  const [strategy, setStrategy] = useState<RotateStrategy>("cycle");
  const [memoText, setMemoText] = useState(t(locale, "preview.memo.default", "写点什么吧…"));

  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [toast, setToast] = useState<{ msg: string; type: "success" | "error" | "info" } | null>(null);

  const [previewImageUrl, setPreviewImageUrl] = useState<string | null>(null);
  const lastObjectUrlRef = useRef<string | null>(null);
  const toastTimerRef = useRef<number | null>(null);

  const showToast = (msg: string, type: "success" | "error" | "info" = "info") => {
    setToast({ msg, type });
    if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current);
    toastTimerRef.current = window.setTimeout(() => setToast(null), 2500);
  };

  const selectedModeList = useMemo(() => Array.from(selectedModes), [selectedModes]);

  const customModes = useMemo(
    () => serverModes.filter((m) => m.source === "custom"),
    [serverModes],
  );
  const customModeMeta = useMemo(
    () => Object.fromEntries(serverModes.map((m) => [m.mode_id, { name: m.display_name, tip: m.description }])),
    [serverModes],
  );

  const allModeIds = useMemo(() => {
    const ids = [...CORE_MODES, ...EXTRA_MODES, ...customModes.map((m) => m.mode_id)];
    return Array.from(new Set(ids));
  }, [customModes]);

  const previewModeName =
    (locale === "en" ? MODE_META_EN[previewMode]?.name : MODE_META[previewMode]?.name) ||
    customModeMeta[previewMode]?.name ||
    previewMode ||
    t(locale, "preview.unknown_mode", "Unknown");
  const previewModeTip =
    (locale === "en" ? MODE_META_EN[previewMode]?.tip : MODE_META[previewMode]?.tip) ||
    customModeMeta[previewMode]?.tip ||
    "";

  const toggleMode = (modeId: string) => {
    setSelectedModes((prev) => {
      const next = new Set(prev);
      if (next.has(modeId)) next.delete(modeId);
      else next.add(modeId);
      return next;
    });
  };

  const pickNextMode = (dir: 1 | -1) => {
    const list = selectedModeList.length ? selectedModeList : CORE_MODES;
    const idx = Math.max(0, list.indexOf(previewMode));
    return list[(idx + dir + list.length) % list.length] || previewMode;
  };
  const pickRandomMode = () => {
    const list = selectedModeList.length ? selectedModeList : CORE_MODES;
    const filtered = list.filter((m) => m !== previewMode);
    const pool = filtered.length ? filtered : list;
    return pool[Math.floor(Math.random() * pool.length)] || previewMode;
  };

  const handlePreview = async (modeId?: string) => {
    const targetMode = modeId || previewMode;
    if (!targetMode) return;

    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const params = new URLSearchParams();
      params.set("persona", targetMode);
      if (city.trim()) params.set("city_override", city.trim());
      if (targetMode === "MEMO") params.set("memo_text", memoText);

      const res = await fetch(`/api/preview?${params.toString()}`);
      if (!res.ok) {
        const errText = await res.text().catch(() => "Unknown error");
        throw new Error(`${t(locale, "preview.error.preview_failed", "Preview failed")}: HTTP ${res.status} ${errText.substring(0, 120)}`);
      }

      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      if (lastObjectUrlRef.current) URL.revokeObjectURL(lastObjectUrlRef.current);
      lastObjectUrlRef.current = objectUrl;
      setPreviewImageUrl(objectUrl);
      showToast(t(locale, "preview.toast.updated", "Preview updated"), "success");
    } catch (err) {
      const msg = err instanceof Error ? err.message : t(locale, "preview.error.preview_failed", "Preview failed");
      setPreviewError(msg);
      showToast(msg, "error");
    } finally {
      setPreviewLoading(false);
    }
  };

  const applyModeAndPreview = async (modeId: string) => {
    setPreviewMode(modeId);
    await handlePreview(modeId);
  };

  const handleRotate = async (action: "prev" | "next" | "smart") => {
    const next =
      action === "prev"
        ? pickNextMode(-1)
        : action === "next"
          ? pickNextMode(1)
          : strategy === "random"
            ? pickRandomMode()
            : pickNextMode(1);
    await applyModeAndPreview(next);
  };

  const reset = () => {
    setCity("杭州");
    setStrategy("cycle");
    setMemoText(t(locale, "preview.memo.default", "写点什么吧…"));
    setSelectedModes(new Set(["DAILY", "WEATHER", "POETRY"]));
    setPreviewMode("DAILY");
    setPreviewError(null);
    showToast(t(locale, "preview.toast.reset", "Reset to defaults"), "info");
  };

  useEffect(() => {
    setModesError(null);
    fetch("/api/modes")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => {
        if (d.modes) setServerModes(d.modes);
        else setModesError(t(locale, "preview.error.no_modes", "No modes data"));
      })
      .catch(() => {
        setModesError(t(locale, "preview.error.modes_unreachable", "Cannot load modes. Make sure backend is running."));
        setServerModes([]);
      });
  }, []);

  useEffect(() => {
    handlePreview().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    return () => {
      if (lastObjectUrlRef.current) URL.revokeObjectURL(lastObjectUrlRef.current);
      if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current);
    };
  }, []);

  useEffect(() => {
    if (selectedModes.size === 0) return;
    if (!selectedModes.has(previewMode)) {
      const first = Array.from(selectedModes)[0];
      if (first) setPreviewMode(first);
    }
  }, [selectedModes, previewMode]);

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-serif text-3xl font-bold text-ink mb-1">{t(locale, "preview.title", "No-device Demo")}</h1>
          <p className="text-ink-light text-sm">{t(locale, "preview.subtitle", "Try modes and preview without a device.")}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={reset}>{t(locale, "preview.action.reset", "Reset")}</Button>
          <Button onClick={() => handlePreview()} disabled={previewLoading}>
            {previewLoading ? <Loader2 size={16} className="animate-spin mr-2" /> : <RefreshCw size={16} className="mr-2" />}
            {t(locale, "preview.action.refresh", "Refresh")}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[520px_1fr] gap-6 items-start">
        <div className="space-y-6">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <Eye size={18} /> {t(locale, "preview.panel.console", "Console")}
                </span>
                <span className="text-xs text-ink-light">
                  {t(locale, "preview.summary.currentLabel", "Current:")} {previewModeName} · {t(locale, "preview.summary.playlistLabel", "Playlist:")}{" "}
                  {selectedModes.size}
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-4 space-y-4">
              {previewModeTip ? <div className="text-xs text-ink-light">{previewModeTip}</div> : null}

              <div className="grid grid-cols-3 gap-2">
                <Button variant="outline" onClick={() => handleRotate("prev")} disabled={previewLoading}>
                  <ArrowLeft size={16} className="mr-1" />
                  {t(locale, "preview.action.prev", "Prev")}
                </Button>
                <Button variant="outline" onClick={() => handleRotate("next")} disabled={previewLoading}>
                  {t(locale, "preview.action.next", "Next")}
                  <ArrowRight size={16} className="ml-1" />
                </Button>
                <Button variant="outline" onClick={() => handleRotate("smart")} disabled={previewLoading}>
                  <Shuffle size={16} className="mr-1" />
                  {strategy === "random" ? t(locale, "preview.strategy.random", "Random") : t(locale, "preview.strategy.cycle", "Cycle")}
                </Button>
              </div>

              <Field label={t(locale, "preview.field.strategy", "Rotation")}>
                <select
                  value={strategy}
                  onChange={(e) => setStrategy(e.target.value as RotateStrategy)}
                  className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
                >
                  <option value="cycle">{t(locale, "preview.strategy.cycle", "Cycle")}</option>
                  <option value="random">{t(locale, "preview.strategy.random", "Random")}</option>
                </select>
              </Field>

              <Field label={t(locale, "preview.field.city", "City")} hint={t(locale, "preview.hint.city", "Affects Weather etc.")}>
                <div className="flex gap-2">
                  <input
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    placeholder={t(locale, "preview.city.placeholder", "e.g. Shenzhen, Beijing, Shanghai")}
                    className="flex-1 rounded-sm border border-ink/20 px-3 py-2 text-sm"
                  />
                  <Button variant="outline" onClick={() => handlePreview()} disabled={previewLoading}>
                    {t(locale, "preview.action.apply", "Apply")}
                  </Button>
                </div>
              </Field>

              {previewMode === "MEMO" ? (
                <Field label={t(locale, "preview.field.memo", "Memo")} hint={t(locale, "preview.hint.memo", "Only for MEMO mode")}>
                  <textarea
                    value={memoText}
                    onChange={(e) => setMemoText(e.target.value)}
                    className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm min-h-24"
                  />
                  <div className="pt-2">
                    <Button onClick={() => handlePreview("MEMO")} disabled={previewLoading} className="w-full">
                      {previewLoading ? <Loader2 size={16} className="animate-spin mr-2" /> : <Eye size={16} className="mr-2" />}
                      {t(locale, "preview.action.update_memo", "Update memo preview")}
                    </Button>
                  </div>
                </Field>
              ) : null}

              {previewError ? (
                <div className="p-3 rounded-sm border border-red-200 bg-red-50 text-red-800 text-sm">
                  <AlertCircle size={16} className="inline mr-2" />
                  {previewError}
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t(locale, "preview.panel.modes", "Modes")}</CardTitle>
            </CardHeader>
            <CardContent>
              {modesError ? (
                <div className="mb-4 p-3 rounded-sm border border-amber-200 bg-amber-50 text-amber-800 text-sm">
                  <AlertCircle size={16} className="inline mr-2" />
                  {modesError}
                </div>
              ) : null}

              <div className="flex gap-2 mb-4">
                <Button
                  variant="outline"
                  onClick={() => {
                    setSelectedModes(new Set(allModeIds));
                    showToast(t(locale, "preview.toast.select_all", "Selected all modes"), "success");
                  }}
                >
                  {t(locale, "preview.action.select_all", "Select all")}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    setSelectedModes(new Set());
                    showToast(t(locale, "preview.toast.clear", "Cleared playlist"), "info");
                  }}
                >
                  {t(locale, "preview.action.clear", "Clear")}
                </Button>
              </div>

              <ModeSection
                title={t(locale, "preview.section.core", "Core modes")}
                modes={CORE_MODES}
                selected={selectedModes}
                current={previewMode}
                onToggle={toggleMode}
                onPreview={applyModeAndPreview}
                collapsible
                locale={locale}
              />

              <ModeSection
                title={t(locale, "preview.section.more", "More modes")}
                modes={EXTRA_MODES}
                selected={selectedModes}
                current={previewMode}
                onToggle={toggleMode}
                onPreview={applyModeAndPreview}
                collapsible
                locale={locale}
              />

              {customModes.length ? (
                <ModeSection
                  title={t(locale, "preview.section.custom", "Custom modes")}
                  modes={customModes.map((m) => m.mode_id)}
                  selected={selectedModes}
                  current={previewMode}
                  onToggle={toggleMode}
                  onPreview={applyModeAndPreview}
                  collapsible
                  customMeta={customModeMeta}
                  locale={locale}
                />
              ) : null}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-baseline justify-between gap-3 flex-wrap">
                <span className="text-base font-semibold text-ink">{t(locale, "preview.panel.display", "E-Ink Preview")}</span>
                <span className="text-base font-semibold text-ink">
                  {t(locale, "preview.summary.current_mode", "Mode")}: {previewModeName}
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="h-[calc(100vh-220px)] flex flex-col p-0">
              <div className="border border-ink/10 rounded-sm bg-paper flex flex-col items-center justify-center flex-1 w-full">
                {previewLoading ? (
                  <div className="flex items-center justify-center w-full">
                    <div className="text-center">
                      <Loader2 size={32} className="animate-spin mx-auto text-ink-light mb-3" />
                      <p className="text-sm text-ink-light">{t(locale, "preview.state.generating", "Generating preview...")}</p>
                    </div>
                  </div>
                ) : previewImageUrl ? (
                  <div className="relative w-full max-w-md aspect-[4/3] bg-white border border-ink/20 rounded-sm overflow-hidden">
                    <img
                      src={previewImageUrl}
                      alt={t(locale, "preview.display.alt", "InkSight preview")}
                      className="absolute inset-0 w-full h-full object-contain"
                    />
                  </div>
                ) : (
                  <div className="flex items-center justify-center w-full">
                    <div className="text-center">
                      <Eye size={32} className="mx-auto text-ink-light mb-3" />
                      <p className="text-sm text-ink-light">{t(locale, "preview.state.empty_title", "No preview yet")}</p>
                      <p className="text-xs text-ink-light mt-1">{t(locale, "preview.state.empty_hint", "Click Refresh to generate.")}</p>
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {toast ? (
        <div
          className={`fixed top-5 right-5 z-50 px-4 py-3 rounded-sm text-sm font-medium shadow-lg animate-fade-in ${
            toast.type === "success"
              ? "bg-green-50 text-green-800 border border-green-200"
              : toast.type === "error"
                ? "bg-red-50 text-red-800 border border-red-200"
                : "bg-amber-50 text-amber-800 border border-amber-200"
          }`}
        >
          {toast.msg}
        </div>
      ) : null}
    </div>
  );
}