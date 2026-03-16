"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertCircle, Eye, Loader2, Sparkles, LayoutGrid } from "lucide-react";
import { localeFromPathname, t, withLocalePath } from "@/lib/i18n";
import { authHeaders, fetchCurrentUser } from "@/lib/auth";

// 模式元数据（从设备配置页面复制）
const MODE_META: Record<string, { name: string; tip: string }> = {
  DAILY: { name: "每日", tip: "语录、书籍推荐、冷知识的综合日报" },
  WEATHER: { name: "天气", tip: "实时天气和未来趋势看板" },
  WORD_OF_THE_DAY: { name: "每日一词", tip: "每日精选一个英语单词，展示其拼写与释义" },
  ZEN: { name: "禅意", tip: "一个大字表达当下心境" },
  BRIEFING: { name: "简报", tip: "科技热榜 + AI 洞察简报" },
  MY_QUOTE: { name: "自定义语录", tip: "可在预览弹窗中随机生成，或输入你自己的语录内容" },
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
  MY_QUOTE: { name: "Custom Quote", tip: "Supports custom input or random generation" },
  MY_ADAPTIVE: { name: "Adaptive Photo", tip: "Upload a local photo and auto-fit it to the 4.2\" e-ink screen" },
  ADAPTIVE_PHOTO: { name: "Adaptive Photo", tip: "Auto-fit photo mode for the e-ink screen" },
  PHOTO: { name: "Photo", tip: "Photo mode" },
  MY_PHOTO: { name: "Custom Photo", tip: "Your own photo mode (JSON-defined)" },
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
const EXTRA_MODES = Object.keys(MODE_META).filter((m) => !CORE_MODES.includes(m) && m !== "MY_QUOTE");

// 自定义模式模板（与配置页使用的模板保持一致的最小子集）
type ModeTemplateDef = {
  mode_id: string;
  display_name: string;
  cacheable?: boolean;
  content?: Record<string, unknown>;
  layout?: Record<string, unknown>;
};

const MODE_TEMPLATES: Record<string, { label: string; def: ModeTemplateDef }> = {
  STOIC: {
    label: "Stoic Quote (JSON)",
    def: {
      mode_id: "STOIC_CUSTOM",
      display_name: "Stoic Quote",
      cacheable: true,
      content: {
        type: "llm_json",
        prompt_template:
          "生成一条斯多葛风格的简短语录（不超过50字），并给出作者和一句话解释，返回 JSON。",
        output_schema: {
          quote: { type: "string", default: "阻碍行动的障碍，本身就是行动的路。" },
          author: { type: "string", default: "马可·奥勒留" },
          explanation: { type: "string", default: "面对阻碍时，转而把它当作前进的道路本身。" },
        },
      },
      layout: {
        body: [
          { type: "text", field: "quote", variant: "large" },
          { type: "text", field: "author", variant: "small" },
          { type: "text", field: "explanation", variant: "small" },
        ],
      },
    },
  },
};

interface ServerModeItem {
  mode_id: string;
  display_name: string;
  description: string;
  source: string;
}

function ModeSection({
  title,
  modes,
  currentMode,
  onPreview,
  collapsible,
  customMeta,
  locale,
}: {
  title: string;
  modes: string[];
  currentMode: string;
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
            const isCurrent = currentMode === m;
            return (
              <div key={m} className="rounded-sm border border-ink/10 bg-white overflow-hidden">
                <button
                  onClick={() => onPreview(m)}
                  className={`w-full px-3 py-2 text-left transition-colors min-h-[64px] flex flex-col justify-center ${
                    isCurrent ? "bg-ink text-white" : "hover:bg-paper-dark text-ink"
                  }`}
                  title={meta.tip}
                >
                  <div className="text-sm font-semibold">{meta.name}</div>
                  <div className={`text-[11px] mt-0.5 line-clamp-2 ${isCurrent ? "text-white/80" : "text-ink-light"}`}>
                    {meta.tip}
                  </div>
                </button>
                <div className="border-t border-ink/10">
                  <button
                    onClick={() => onPreview(m)}
                    className="w-full h-9 px-2 text-[11px] sm:text-xs text-ink hover:bg-ink hover:text-white transition-colors flex items-center justify-center gap-1 whitespace-nowrap"
                  >
                    <Eye size={14} />
                    {t(localeFromPathname(`/${locale}`), "preview.action.preview", locale === "zh" ? "预览" : "Preview")}
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
  const router = useRouter();
  const pathname = usePathname();
  const locale = localeFromPathname(pathname || "/");

  const [authChecked, setAuthChecked] = useState(false);
  const [userLlmApiKey, setUserLlmApiKey] = useState<string>("");

  const [serverModes, setServerModes] = useState<ServerModeItem[]>([]);
  const [modesError, setModesError] = useState<string | null>(null);
  const [previewMode, setPreviewMode] = useState("DAILY");

  const [city, setCity] = useState("杭州");
  const [memoText, setMemoText] = useState(t(locale, "preview.memo.default", "写点什么吧…"));

  const [previewLoading, setPreviewLoading] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [toast, setToast] = useState<{ msg: string; type: "success" | "error" | "info" } | null>(null);

  // 当前预览对应的大模型调用状态提示（无 / 成功 / 失败使用兜底等）
  const [previewLlmStatus, setPreviewLlmStatus] = useState<string | null>(null);

  const [previewImageUrl, setPreviewImageUrl] = useState<string | null>(null);
  const lastObjectUrlRef = useRef<string | null>(null);
  const toastTimerRef = useRef<number | null>(null);

  const [modal, setModal] = useState<null | { type: "quote" | "weather" | "memo" | "countdown" | "habit" | "lifebar"; modeId: string }>(null);
  const [imageUploadLoading, setImageUploadLoading] = useState(false);
  const [quoteDraft, setQuoteDraft] = useState("");
  const [authorDraft, setAuthorDraft] = useState("");
  const [cityDraft, setCityDraft] = useState("");
  const [memoDraft, setMemoDraft] = useState("");
  
  // 倒计时状态
  const [countdownName, setCountdownName] = useState("元旦");
  const [countdownDate, setCountdownDate] = useState("2027-01-01");
  
  // 打卡状态
  const [habitItems, setHabitItems] = useState([
    { name: "早起", done: false },
    { name: "运动", done: false },
    { name: "阅读", done: false },
  ]);
  
  // 人生进度条状态
  const [userAge, setUserAge] = useState(30);
  const [lifeExpectancy, setLifeExpectancy] = useState<100 | 120>(100);
  
  const [showCustomModeModal, setShowCustomModeModal] = useState(false);
  const [customDesc, setCustomDesc] = useState("");
  const [customModeName, setCustomModeName] = useState("");
  const [customJson, setCustomJson] = useState("");
  const [customGenerating, setCustomGenerating] = useState(false);
  const [customEditorTab, setCustomEditorTab] = useState<"ai" | "template">("ai");

  const adaptiveFileInputRef = useRef<HTMLInputElement | null>(null);

  const uploadLocalImage = async (file: File): Promise<string> => {
    const fd = new FormData();
    fd.append("file", file);
    const up = await fetch("/api/uploads", { method: "POST", body: fd });
    if (!up.ok) {
      const err = await up.text().catch(() => "");
      throw new Error(err || `upload failed: ${up.status}`);
    }
    const data = (await up.json()) as { url?: string };
    if (!data.url) throw new Error("upload failed: missing url");
    return data.url;
  };

  // 进入无设备体验前必须登录
  useEffect(() => {
    fetchCurrentUser()
      .then((u) => {
        if (!u) {
          router.replace(withLocalePath(locale, "/login"));
          return;
        }
        setAuthChecked(true);
      })
      .catch(() => {
        router.replace(withLocalePath(locale, "/login"));
      });
  }, [locale, router]);

  // 从本机缓存读取用户 API Key（由配置页写入）
  useEffect(() => {
    if (typeof window === "undefined") return;
    const k = localStorage.getItem("ink_user_llm_api_key") || "";
    if (k.trim()) setUserLlmApiKey(k.trim());
  }, []);
  // 邀请码弹窗状态
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteCode, setInviteCode] = useState("");
  const [redeemingInvite, setRedeemingInvite] = useState(false);
  const [pendingPreviewMode, setPendingPreviewMode] = useState<string | null>(null);

  const showToast = (msg: string, type: "success" | "error" | "info" = "info") => {
    setToast({ msg, type });
    if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current);
    toastTimerRef.current = window.setTimeout(() => setToast(null), 2500);
  };

  const customModes = useMemo(
    () => serverModes.filter((m) => m.source === "custom" && m.mode_id !== "WORD_OF_THE_DAY"),
    [serverModes],
  );
  const customModeMeta = useMemo(
    () => Object.fromEntries(serverModes.map((m) => [m.mode_id, { name: m.display_name, tip: m.description }])),
    [serverModes],
  );

  const previewModeName =
    (locale === "en" ? MODE_META_EN[previewMode]?.name : MODE_META[previewMode]?.name) ||
    customModeMeta[previewMode]?.name ||
    previewMode ||
    t(locale, "preview.unknown_mode", "Unknown");
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const previewModeTip =
    (locale === "en" ? MODE_META_EN[previewMode]?.tip : MODE_META[previewMode]?.tip) ||
    customModeMeta[previewMode]?.tip ||
    "";

  const handlePreview = async (modeId?: string, override?: Record<string, unknown>) => {
    const targetMode = modeId || previewMode;
    if (!targetMode) return;
    if (!authChecked) return;

    // 检查是否需要弹窗
    if (!override) {
      if (targetMode === "WEATHER") {
        setModal({ type: "weather", modeId: targetMode });
        setCityDraft(city);
        return;
      }
      if (targetMode === "MEMO") {
        setModal({ type: "memo", modeId: targetMode });
        setMemoDraft(memoText);
        return;
      }
      if (targetMode === "MY_QUOTE") {
        setModal({ type: "quote", modeId: targetMode });
        return;
      }
      if (targetMode === "COUNTDOWN") {
        setModal({ type: "countdown", modeId: targetMode });
        return;
      }
      if (targetMode === "HABIT") {
        setModal({ type: "habit", modeId: targetMode });
        return;
      }
      if (targetMode === "LIFEBAR") {
        setModal({ type: "lifebar", modeId: targetMode });
        return;
      }
    }

    // 普通模式预览时，清除上次 LLM 状态提示
    setPreviewLlmStatus(null);

    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const params = new URLSearchParams();
      params.set("persona", targetMode);
      
      // 处理城市覆盖：优先使用 override 中的 city，否则使用全局 city
      const cityOverride = override?.city ? String(override.city) : city.trim();
      if (cityOverride) {
        params.set("city_override", cityOverride);
      }
      
      // 处理便签文本：优先使用 override 中的 memo_text
      if (targetMode === "MEMO") {
        const memoOverride = override?.memo_text ? String(override.memo_text) : memoText;
        params.set("memo_text", memoOverride);
      }
      
      if (override && Object.keys(override).length > 0) {
        params.set("mode_override", JSON.stringify(override));
      }

      const res = await fetch(`/api/preview?${params.toString()}`, {
        headers: authHeaders(userLlmApiKey ? { "x-inksight-llm-api-key": userLlmApiKey } : undefined),
      });
      if (res.status === 402) {
        // 额度耗尽，显示邀请码输入弹窗
        const data = await res.json().catch(() => ({}));
        if (data.requires_invite_code) {
          setPendingPreviewMode(targetMode);
          setShowInviteModal(true);
          setPreviewLoading(false);
          return;
        }
      }
      if (!res.ok) {
        const errText = await res.text().catch(() => "Unknown error");
        throw new Error(`${t(locale, "preview.error.preview_failed", "Preview failed")}: HTTP ${res.status} ${errText.substring(0, 120)}`);
      }

      const statusHeader = res.headers.get("x-preview-status");
      const llmRequired = res.headers.get("x-llm-required");
      
      if (statusHeader === "no_llm_required" || llmRequired === "0") {
        setPreviewLlmStatus(
          locale === "zh" ? "该模式无需调用大模型" : "This mode does not require LLM",
        );
      } else if (statusHeader === "model_generated") {
        setPreviewLlmStatus(
          locale === "zh" ? "大模型调用成功" : "Model call succeeded",
        );
      } else if (statusHeader === "fallback_used") {
        setPreviewLlmStatus(
          locale === "zh"
            ? "大模型调用失败，使用默认内容"
            : "Model call failed, using fallback content",
        );
      } else {
        setPreviewLlmStatus(null);
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

  const handleRedeemInviteCode = async () => {
    if (!inviteCode.trim()) {
      showToast(locale === "en" ? "Please enter invitation code" : "请输入邀请码", "error");
      return;
    }

    setRedeemingInvite(true);
    try {
      const res = await fetch("/api/auth/redeem-invite-code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ invite_code: inviteCode.trim() }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || (locale === "en" ? "Failed to redeem invitation code" : "邀请码兑换失败"));
      }

      showToast(data.message || (locale === "en" ? "Invitation code redeemed successfully" : "邀请码兑换成功"), "success");
      setShowInviteModal(false);
      setInviteCode("");
      // 重新尝试预览
      if (pendingPreviewMode) {
        await handlePreview(pendingPreviewMode);
        setPendingPreviewMode(null);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : (locale === "en" ? "Failed to redeem invitation code" : "邀请码兑换失败");
      showToast(msg, "error");
    } finally {
      setRedeemingInvite(false);
    }
  };

  const applyModeAndPreview = async (modeId: string) => {
    // Custom flows
    if (modeId === "MY_ADAPTIVE") {
      setPreviewMode(modeId);
      adaptiveFileInputRef.current?.click();
      return;
    }
    if (modeId === "MY_QUOTE") {
      setPreviewMode(modeId);
      setQuoteDraft("");
      setAuthorDraft("");
      setModal({ type: "quote", modeId });
      return;
    }
    if (modeId === "WEATHER") {
      setPreviewMode(modeId);
      setCityDraft(city); // 使用当前城市作为默认值
      setModal({ type: "weather", modeId });
      return;
    }
    if (modeId === "MEMO") {
      setPreviewMode(modeId);
      setMemoDraft(memoText); // 使用当前便签内容作为默认值
      setModal({ type: "memo", modeId });
      return;
    }

    setPreviewMode(modeId);
    await handlePreview(modeId);
  };

  const handleGenerateCustomMode = async () => {
    if (!customDesc.trim()) {
      showToast(
        locale === "zh" ? "请输入模式描述" : "Please enter a description for the mode",
        "error",
      );
      return;
    }
    setCustomGenerating(true);
    try {
      const res = await fetch("/api/modes/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description: customDesc }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "Generate failed");
      setCustomJson(JSON.stringify(data.mode_def, null, 2));
      setCustomModeName((data.mode_def?.display_name || "").toString());
      showToast(
        locale === "zh" ? "模式生成成功" : "Mode generated successfully",
        "success",
      );
    } catch (e) {
      showToast(
        (locale === "zh" ? "生成失败: " : "Generate failed: ") +
          (e instanceof Error ? e.message : "Unknown error"),
        "error",
      );
    } finally {
      setCustomGenerating(false);
    }
  };

  const handleCustomModePreview = async () => {
    if (!customJson.trim()) return;
    setPreviewLoading(true);
    setPreviewError(null);
    setPreviewLlmStatus(null);
    setShowCustomModeModal(false);
    try {
      const def = JSON.parse(customJson);
      const nameFromInput = customModeName.trim();
      const nameFromDef =
        (typeof def.display_name === "string" && def.display_name.trim()) ||
        (typeof def.mode_id === "string" && def.mode_id.trim()) ||
        "";
      const res = await fetch("/api/modes/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode_def: def }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.error || "Preview failed");
      }
      const statusHeader = res.headers.get("x-preview-status");
      const llmRequired = res.headers.get("x-llm-required");
      
      if (statusHeader === "no_llm_required" || llmRequired === "0") {
        setPreviewLlmStatus(
          locale === "zh" ? "该模式无需调用大模型" : "This mode does not require LLM",
        );
      } else if (statusHeader === "model_generated") {
        setPreviewLlmStatus(
          locale === "zh" ? "大模型调用成功" : "Model call succeeded",
        );
      } else if (statusHeader === "fallback_used") {
        setPreviewLlmStatus(
          locale === "zh"
            ? "大模型调用失败，使用默认内容"
            : "Model call failed, using fallback content",
        );
      } else {
        setPreviewLlmStatus(null);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      if (lastObjectUrlRef.current) URL.revokeObjectURL(lastObjectUrlRef.current);
      lastObjectUrlRef.current = url;
      setPreviewImageUrl(url);
      showToast(
        t(locale, "preview.toast.updated", "Preview updated"),
        "success",
      );
    } catch (e) {
      const msg =
        (locale === "zh" ? "预览失败: " : "Preview failed: ") +
        (e instanceof Error ? e.message : "Unknown error");
      setPreviewError(msg);
      showToast(msg, "error");
    } finally {
      setPreviewLoading(false);
    }
  };

  const reset = () => {
    setCity("杭州");
    setMemoText(t(locale, "preview.memo.default", "写点什么吧…"));
    setPreviewMode("DAILY");
    setPreviewError(null);
    showToast(t(locale, "preview.toast.reset", "Reset to defaults"), "info");
  };

  useEffect(() => {
    setModesError(null);
    if (!authChecked) return;
    fetch("/api/modes", { headers: authHeaders() })
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
  }, [authChecked, locale]);

  useEffect(() => {
    if (!authChecked) return;
    handlePreview().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authChecked]);

  useEffect(() => {
    return () => {
      if (lastObjectUrlRef.current) URL.revokeObjectURL(lastObjectUrlRef.current);
      if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current);
    };
  }, []);

  useEffect(() => {
    // no-op: playlist removed
  }, [previewMode]);

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      {/* Hidden file picker for MY_ADAPTIVE (local upload only) */}
      <input
        ref={adaptiveFileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={async (e) => {
          const f = e.target.files?.[0] || null;
          e.currentTarget.value = "";
          if (!f) return;
          setImageUploadLoading(true);
          try {
            const url = await uploadLocalImage(f);
            await handlePreview("MY_ADAPTIVE", { image_url: url });
          } catch (err) {
            const msg = err instanceof Error ? err.message : t(locale, "preview.modal.image.need_file", "Please choose a local image");
            showToast(msg, "error");
          } finally {
            setImageUploadLoading(false);
          }
        }}
      />
      <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-serif text-3xl font-bold text-ink mb-1">{t(locale, "preview.title", "No-device Demo")}</h1>
          <p className="text-ink-light text-sm">{t(locale, "preview.subtitle", "Try modes and preview without a device.")}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[520px_1fr] gap-6 items-start">
        <div className="space-y-6">
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

              <ModeSection
                title={t(locale, "preview.section.core", "Core modes")}
                modes={CORE_MODES}
                currentMode={previewMode}
                onPreview={applyModeAndPreview}
                collapsible
                locale={locale}
              />

              <ModeSection
                title={t(locale, "preview.section.more", "More modes")}
                modes={EXTRA_MODES}
                currentMode={previewMode}
                onPreview={applyModeAndPreview}
                collapsible
                locale={locale}
              />

              {customModes.length ? (
                <ModeSection
                  title={t(locale, "preview.section.custom", "Custom modes")}
                  modes={customModes.map((m) => m.mode_id)}
                  currentMode={previewMode}
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
                  <div className="flex flex-col items-center gap-2 w-full">
                    <div className="relative w-full max-w-md aspect-[4/3] bg-white border border-ink/20 rounded-sm overflow-hidden">
                      <Image
                        src={previewImageUrl}
                        alt={t(locale, "preview.display.alt", "InkSight preview")}
                        fill
                        className="object-contain"
                        unoptimized
                      />
                    </div>
                    {previewLlmStatus ? (
                      <p className="text-[11px] text-ink-light text-center px-4">
                        {previewLlmStatus}
                      </p>
                    ) : null}
                  </div>
                ) : previewMode === null ? (
                  <div className="flex items-center justify-center w-full">
                    <div className="text-center">
                      <Eye size={32} className="mx-auto text-ink-light mb-3" />
                      <p className="text-sm text-ink-light">{t(locale, "preview.select_mode", locale === "zh" ? "请选择模式" : "Please select a mode")}</p>
                    </div>
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

      {modal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" onClick={() => setModal(null)} />
          <div className="relative w-[min(520px,calc(100vw-32px))] rounded-sm border border-ink/15 bg-white shadow-xl">
            <div className="px-4 py-3 border-b border-ink/10 flex items-center justify-between">
              <div className="text-sm font-semibold text-ink">
                {modal.type === "quote"
                  ? t(locale, "preview.modal.quote.title", locale === "zh" ? "自定义语录" : "Custom Quote")
                  : modal.type === "weather"
                  ? locale === "zh" ? "天气设置" : "Weather Settings"
                  : modal.type === "memo"
                  ? locale === "zh" ? "便签内容" : "Memo Content"
                  : modal.type === "countdown"
                  ? locale === "zh" ? "倒计时设置" : "Countdown Settings"
                  : modal.type === "habit"
                  ? locale === "zh" ? "习惯打卡" : "Habit Tracker"
                  : locale === "zh" ? "人生进度条" : "Life Progress"}
              </div>
              <button className="text-ink-light hover:text-ink" onClick={() => setModal(null)}>
                ✕
              </button>
            </div>
            <div className="px-4 py-4 space-y-3">
              {modal.type === "quote" ? (
                <>
                  <div className="text-xs text-ink-light">
                    {t(locale, "preview.modal.quote.hint", "Generate a deep quote randomly, or paste your own text.")}
                  </div>
                  <textarea
                    value={quoteDraft}
                    onChange={(e) => setQuoteDraft(e.target.value)}
                    placeholder={t(locale, "preview.modal.quote.placeholder", "Type your quote...")}
                    className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm min-h-28 bg-white"
                  />
                  <input
                    value={authorDraft}
                    onChange={(e) => setAuthorDraft(e.target.value)}
                    placeholder={t(locale, "preview.modal.quote.author_placeholder", "Author (optional)")}
                    className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
                  />
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-2">
                    <Button
                      onClick={async () => {
                        setModal(null);
                        // random generate via LLM (no override)
                        await handlePreview(modal.modeId);
                      }}
                      disabled={previewLoading}
                    >
                      {t(locale, "preview.modal.quote.random", locale === "zh" ? "随机生成" : "Random generate")}
                    </Button>
                    <Button
                      variant="outline"
                      onClick={async () => {
                        const q = quoteDraft.trim();
                        const a = authorDraft.trim();
                        setModal(null);
                        await handlePreview(modal.modeId, q ? { quote: q, author: a } : {});
                      }}
                      disabled={previewLoading}
                    >
                      {t(locale, "preview.modal.quote.use_input", locale === "zh" ? "使用我的输入" : "Use my input")}
                    </Button>
                  </div>
                </>
              ) : modal.type === "weather" ? (
                <>
                  <div className="text-xs text-ink-light">
                    {locale === "zh" 
                      ? "输入城市名称查看天气。如果大模型调用失败，将显示默认城市天气。" 
                      : "Enter city name to view weather. If LLM call fails, default city weather will be shown."}
                  </div>
                  <input
                    value={cityDraft}
                    onChange={(e) => setCityDraft(e.target.value)}
                    placeholder={locale === "zh" ? "输入城市名称（如：北京、上海）" : "Enter city name (e.g., Beijing, Shanghai)"}
                    className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
                    autoFocus
                  />
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-2">
                    <Button
                      onClick={async () => {
                        setModal(null);
                        // 使用默认城市
                        await handlePreview(modal.modeId);
                      }}
                      disabled={previewLoading}
                      variant="outline"
                    >
                      {locale === "zh" ? "使用默认城市" : "Use default city"}
                    </Button>
                    <Button
                      onClick={async () => {
                        const c = cityDraft.trim();
                        setModal(null);
                        if (c) {
                          await handlePreview(modal.modeId, { city: c });
                        } else {
                          await handlePreview(modal.modeId);
                        }
                      }}
                      disabled={previewLoading}
                    >
                      {locale === "zh" ? "预览天气" : "Preview weather"}
                    </Button>
                  </div>
                </>
              ) : modal.type === "memo" ? (
                <>
                  <div className="text-xs text-ink-light">
                    {locale === "zh" 
                      ? "输入便签内容，将在墨水屏上显示。" 
                      : "Enter memo content to display on e-ink screen."}
                  </div>
                  <textarea
                    value={memoDraft}
                    onChange={(e) => setMemoDraft(e.target.value)}
                    placeholder={locale === "zh" ? "输入便签内容..." : "Enter memo content..."}
                    className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm min-h-32 bg-white"
                    autoFocus
                  />
                  <div className="flex justify-end pt-2">
                    <Button
                      onClick={async () => {
                        const m = memoDraft.trim();
                        setModal(null);
                        if (m) {
                          await handlePreview(modal.modeId, { memo_text: m });
                        } else {
                          await handlePreview(modal.modeId);
                        }
                      }}
                      disabled={previewLoading}
                    >
                      {locale === "zh" ? "预览便签" : "Preview memo"}
                    </Button>
                  </div>
                </>
              ) : modal.type === "countdown" ? (
                <>
                  <div className="text-xs text-ink-light mb-3">
                    {locale === "zh" 
                      ? "设置倒计时事件名称和日期" 
                      : "Set countdown event name and date"}
                  </div>
                  <div className="space-y-3">
                    <div>
                      <label className="block text-xs text-ink mb-1.5">
                        {locale === "zh" ? "事件名称" : "Event Name"}
                      </label>
                      <input
                        value={countdownName}
                        onChange={(e) => setCountdownName(e.target.value)}
                        placeholder={locale === "zh" ? "例如：元旦、生日" : "e.g., New Year, Birthday"}
                        className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-ink mb-1.5">
                        {locale === "zh" ? "目标日期" : "Target Date"}
                      </label>
                      <input
                        type="date"
                        value={countdownDate}
                        onChange={(e) => setCountdownDate(e.target.value)}
                        className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2 pt-3">
                    <Button
                      onClick={async () => {
                        setModal(null);
                        await handlePreview(modal.modeId);
                      }}
                      disabled={previewLoading}
                      variant="outline"
                    >
                      {locale === "zh" ? "使用默认" : "Use Default"}
                    </Button>
                    <Button
                      onClick={async () => {
                        setModal(null);
                        const today = new Date();
                        const target = new Date(countdownDate);
                        const days = Math.ceil((target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
                        await handlePreview(modal.modeId, {
                          events: [{
                            name: countdownName || "倒计时",
                            date: countdownDate,
                            type: "countdown",
                            days: days
                          }]
                        });
                      }}
                      disabled={previewLoading}
                    >
                      {locale === "zh" ? "预览倒计时" : "Preview Countdown"}
                    </Button>
                  </div>
                </>
              ) : modal.type === "habit" ? (
                <>
                  <div className="text-xs text-ink-light mb-3">
                    {locale === "zh" 
                      ? "设置你的习惯并勾选完成情况" 
                      : "Set your habits and check completion"}
                  </div>
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {habitItems.map((item, idx) => (
                      <div key={idx} className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={item.done}
                          onChange={(e) => {
                            const newItems = [...habitItems];
                            newItems[idx].done = e.target.checked;
                            setHabitItems(newItems);
                          }}
                          className="w-4 h-4"
                        />
                        <input
                          value={item.name}
                          onChange={(e) => {
                            const newItems = [...habitItems];
                            newItems[idx].name = e.target.value;
                            setHabitItems(newItems);
                          }}
                          placeholder={locale === "zh" ? "习惯名称" : "Habit name"}
                          className="flex-1 rounded-sm border border-ink/20 px-3 py-1.5 text-sm bg-white"
                        />
                        <button
                          onClick={() => {
                            const newItems = habitItems.filter((_, i) => i !== idx);
                            setHabitItems(newItems);
                          }}
                          className="text-ink-light hover:text-red-500 px-2"
                          title={locale === "zh" ? "删除" : "Delete"}
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                  </div>
                  <button
                    onClick={() => {
                      setHabitItems([...habitItems, { name: "", done: false }]);
                    }}
                    className="w-full mt-2 px-3 py-2 rounded-sm border border-dashed border-ink/20 text-sm text-ink-light hover:text-ink hover:border-ink/40 transition-colors"
                  >
                    + {locale === "zh" ? "添加习惯" : "Add Habit"}
                  </button>
                  <div className="grid grid-cols-2 gap-2 pt-3">
                    <Button
                      onClick={async () => {
                        setModal(null);
                        await handlePreview(modal.modeId);
                      }}
                      disabled={previewLoading}
                      variant="outline"
                    >
                      {locale === "zh" ? "使用默认" : "Use Default"}
                    </Button>
                    <Button
                      onClick={async () => {
                        setModal(null);
                        const lines = habitItems.map(h => `${h.name} ${h.done ? '✓' : '✗'}`);
                        const summary = lines.join('\n');
                        await handlePreview(modal.modeId, {
                          habits: habitItems,
                          summary: summary
                        });
                      }}
                      disabled={previewLoading}
                    >
                      {locale === "zh" ? "预览打卡" : "Preview Habits"}
                    </Button>
                  </div>
                </>
              ) : modal.type === "lifebar" ? (
                <>
                  <div className="text-xs text-ink-light mb-3">
                    {locale === "zh" 
                      ? "设置你的年龄和预期寿命" 
                      : "Set your age and life expectancy"}
                  </div>
                  <div className="space-y-3">
                    <div>
                      <label className="block text-xs text-ink mb-1.5">
                        {locale === "zh" ? "芳龄几何？" : "Your Age"}
                      </label>
                      <input
                        type="number"
                        value={userAge}
                        onChange={(e) => setUserAge(parseInt(e.target.value) || 0)}
                        min="0"
                        max="120"
                        className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-ink mb-1.5">
                        {locale === "zh" ? "退休金领到？" : "Life Expectancy"}
                      </label>
                      <div className="flex gap-2">
                        <button
                          onClick={() => setLifeExpectancy(100)}
                          className={`flex-1 px-3 py-2 rounded-sm text-sm transition-colors ${
                            lifeExpectancy === 100
                              ? "bg-ink text-white"
                              : "bg-paper-dark text-ink hover:bg-ink/10"
                          }`}
                        >
                          100 {locale === "zh" ? "岁" : "years"}
                        </button>
                        <button
                          onClick={() => setLifeExpectancy(120)}
                          className={`flex-1 px-3 py-2 rounded-sm text-sm transition-colors ${
                            lifeExpectancy === 120
                              ? "bg-ink text-white"
                              : "bg-paper-dark text-ink hover:bg-ink/10"
                          }`}
                        >
                          120 {locale === "zh" ? "岁" : "years"}
                        </button>
                      </div>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2 pt-3">
                    <Button
                      onClick={async () => {
                        setModal(null);
                        await handlePreview(modal.modeId);
                      }}
                      disabled={previewLoading}
                      variant="outline"
                    >
                      {locale === "zh" ? "使用默认" : "Use Default"}
                    </Button>
                    <Button
                      onClick={async () => {
                        setModal(null);
                        const lifePct = ((userAge / lifeExpectancy) * 100).toFixed(1);
                        await handlePreview(modal.modeId, {
                          age: userAge,
                          life_expect: lifeExpectancy,
                          life_pct: parseFloat(lifePct),
                          life_label: locale === "zh" ? "人生" : "Life"
                        });
                      }}
                      disabled={previewLoading}
                    >
                      {locale === "zh" ? "预览进度" : "Preview Progress"}
                    </Button>
                  </div>
                </>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
      {showCustomModeModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setShowCustomModeModal(false)}
          />
          <div className="relative w-[min(720px,calc(100vw-32px))] max-h-[min(640px,calc(100vh-80px))] rounded-sm border border-ink/15 bg-white shadow-xl flex flex-col">
            <div className="px-4 py-3 border-b border-ink/10 flex items-center justify-between">
              <div className="text-sm font-semibold text-ink">
                {locale === "zh" ? "创建自定义模式" : "Create Custom Mode"}
              </div>
              <button
                className="text-ink-light hover:text-ink"
                onClick={() => setShowCustomModeModal(false)}
              >
                ✕
              </button>
            </div>
            <div className="px-4 py-4 space-y-4 overflow-auto">
              <div className="flex gap-1 mb-3">
                <button
                  type="button"
                  onClick={() => setCustomEditorTab("ai")}
                  className={`px-3 py-1.5 rounded-sm text-xs flex items-center gap-1 transition-colors ${
                    customEditorTab === "ai"
                      ? "bg-ink text-white"
                      : "bg-paper-dark text-ink-light hover:text-ink"
                  }`}
                >
                  <Sparkles size={12} />
                  {locale === "zh" ? "AI 生成" : "AI Generate"}
                </button>
                <button
                  type="button"
                  onClick={() => setCustomEditorTab("template")}
                  className={`px-3 py-1.5 rounded-sm text-xs flex items-center gap-1 transition-colors ${
                    customEditorTab === "template"
                      ? "bg-ink text-white"
                      : "bg-paper-dark text-ink-light hover:text-ink"
                  }`}
                >
                  <LayoutGrid size={12} />
                  {locale === "zh" ? "从模板" : "From Template"}
                </button>
              </div>

              {customEditorTab === "ai" ? (
                <div className="space-y-3">
                  <textarea
                    value={customDesc}
                    onChange={(e) => setCustomDesc(e.target.value)}
                    rows={3}
                    maxLength={2000}
                    placeholder={
                      locale === "zh"
                        ? "描述你想要的模式，如：每天显示一个英语单词和释义，单词要大号字体居中"
                        : "Describe your mode, e.g. show one English word and definition daily with a large centered font"
                    }
                    className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm resize-y"
                  />
                  <Button
                    size="sm"
                    onClick={handleGenerateCustomMode}
                    disabled={customGenerating || !customDesc.trim()}
                  >
                    {customGenerating ? (
                      <>
                        <Loader2 size={14} className="animate-spin mr-1" />
                        {locale === "zh" ? "生成中..." : "Generating..."}
                      </>
                    ) : (
                      locale === "zh" ? "AI 生成模式" : "Generate Mode with AI"
                    )}
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  <select
                    onChange={(e) => {
                      const template = MODE_TEMPLATES[e.target.value];
                      if (!template) return;
                      setCustomJson(JSON.stringify(template.def, null, 2));
                      setCustomModeName((template.def?.display_name || "").toString());
                    }}
                    defaultValue=""
                    className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
                  >
                    <option value="" disabled>
                      {locale === "zh" ? "选择模板..." : "Select template..."}
                    </option>
                    {Object.entries(MODE_TEMPLATES).map(([key, template]) => (
                      <option key={key} value={key}>
                        {template.label}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="space-y-3 mt-1">
                <input
                  value={customModeName}
                  onChange={(e) => setCustomModeName(e.target.value)}
                  placeholder={
                    locale === "zh"
                      ? "模式名称（例如：今日英语）"
                      : "Mode name (e.g. Daily English)"
                  }
                  className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
                />
                <textarea
                  value={customJson}
                  onChange={(e) => setCustomJson(e.target.value)}
                  rows={12}
                  spellCheck={false}
                  placeholder={
                    locale === "zh"
                      ? "模式 JSON 定义"
                      : "Mode JSON definition"
                  }
                  className="w-full rounded-sm border border-ink/20 px-3 py-2 text-xs font-mono resize-y bg-ink text-green-400"
                />
                <div className="flex gap-2 justify-end">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleCustomModePreview}
                    disabled={!customJson.trim() || previewLoading}
                  >
                    {locale === "zh" ? "预览到右侧水墨屏" : "Preview on E-ink display"}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : null}
      {/* 邀请码输入弹窗 */}
      {showInviteModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <Card className="w-full max-w-md mx-4">
            <CardHeader>
              <CardTitle>{locale === "en" ? "Enter Invitation Code" : "请输入邀请码"}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-ink-light">
                {locale === "en"
                  ? "Your free quota has been exhausted. You can either enter an invitation code to get 5 more free LLM calls, or configure your own API key in device settings."
                  : "您的免费额度已用完。您可以输入邀请码获得50次免费LLM调用额度，也可以在设备配置中设置自己的 API key。"}
              </p>
              <div className="p-3 rounded-sm border border-ink/20 bg-paper-dark">
                <p className="text-xs text-ink-light mb-2">
                  {locale === "en"
                    ? "💡 Tip: If you have your own API key, you can configure it in your profile to avoid quota limits."
                    : "💡 提示：如果您有自己的 API key，可以在个人信息中配置，这样就不会受到额度限制了。"}
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setShowInviteModal(false);
                    router.push(withLocalePath(localeFromPathname(pathname || "/"), "/profile"));
                  }}
                  className="w-full text-xs"
                >
                  {locale === "en" ? "Go to Profile Settings" : "前往个人信息配置"}
                </Button>
              </div>
              <div>
                <label className="block text-sm font-medium text-ink mb-1">
                  {locale === "en" ? "Invitation Code" : "邀请码"}
                </label>
                <input
                  type="text"
                  value={inviteCode}
                  onChange={(e) => setInviteCode(e.target.value)}
                  placeholder={locale === "en" ? "Enter invitation code" : "请输入邀请码"}
                  className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm"
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !redeemingInvite) {
                      handleRedeemInviteCode();
                    }
                  }}
                />
              </div>
              <div className="flex gap-2 justify-end">
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowInviteModal(false);
                    setInviteCode("");
                    setPendingPreviewMode(null);
                  }}
                  disabled={redeemingInvite}
                >
                  {locale === "en" ? "Cancel" : "取消"}
                </Button>
                <Button onClick={handleRedeemInviteCode} disabled={redeemingInvite || !inviteCode.trim()}>
                  {redeemingInvite ? (
                    <>
                      <Loader2 size={16} className="animate-spin mr-2" />
                      {locale === "en" ? "Redeeming..." : "兑换中..."}
                    </>
                  ) : (
                    locale === "en" ? "Redeem" : "兑换"
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      ) : null}
    </div>
  );
}