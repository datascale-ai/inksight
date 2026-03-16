"use client";

import { useEffect, useState, useCallback, Suspense, useMemo, useRef } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import Link from "next/link";
import { DeviceInfo } from "@/components/config/device-info";
import { ModeSelector } from "@/components/config/mode-selector";
import { RefreshStrategyEditor } from "@/components/config/refresh-strategy-editor";
import { Field, StatCard } from "@/components/config/shared";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Settings,
  Sliders,
  BarChart3,
  RefreshCw,
  Save,
  AlertCircle,
  Loader2,
  Plus,
  Trash2,
  Monitor,
  X,
} from "lucide-react";
import { authHeaders, fetchCurrentUser, onAuthChanged } from "@/lib/auth";
import { localeFromPathname, withLocalePath } from "@/lib/i18n";

interface UserDevice {
  mac: string;
  nickname: string;
  bound_at: string;
  last_seen: string | null;
  role?: string;
  status?: string;
}

interface DeviceMember {
  user_id: number;
  username: string;
  role: string;
  status: string;
  nickname?: string;
  created_at: string;
}

interface AccessRequestItem {
  id: number;
  mac: string;
  requester_user_id: number;
  requester_username: string;
  status: string;
  created_at: string;
}

const MODE_META: Record<string, { name: string; tip: string }> = {
  DAILY: { name: "每日", tip: "语录、书籍推荐、冷知识的综合日报" },
  WEATHER: { name: "天气", tip: "实时天气和未来趋势看板" },
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

const CORE_MODES = ["DAILY", "WEATHER", "POETRY", "ARTWALL", "ALMANAC", "BRIEFING"];
const EXTRA_MODES = Object.keys(MODE_META).filter((m) => !CORE_MODES.includes(m));

const STRATEGIES: Record<string, string> = {
  random: "从已启用的模式中随机选取",
  cycle: "按顺序循环切换已启用的模式",
  time_slot: "根据时间段显示不同内容模式",
  smart: "根据时间段自动匹配最佳模式",
};

const LANGUAGE_OPTIONS = [
  { value: "zh", label: "中文为主" },
  { value: "en", label: "英文为主" },
  { value: "mixed", label: "中英混合" },
] as const;

const TONE_OPTIONS = [
  { value: "positive", label: "积极鼓励" },
  { value: "neutral", label: "中性克制" },
  { value: "deep", label: "深沉内省" },
  { value: "humor", label: "轻松幽默" },
] as const;
const PERSONA_PRESETS = ["鲁迅", "王小波", "JARVIS", "苏格拉底", "村上春树"] as const;

function normalizeLanguage(v: unknown): string {
  if (typeof v !== "string") return "zh";
  if (v === "zh" || v === "en" || v === "mixed") return v;
  const found = LANGUAGE_OPTIONS.find((x) => x.label === v);
  return found?.value || "zh";
}

function normalizeTone(v: unknown): string {
  if (typeof v !== "string") return "neutral";
  if (v === "positive" || v === "neutral" || v === "deep" || v === "humor") return v;
  const found = TONE_OPTIONS.find((x) => x.label === v);
  return found?.value || "neutral";
}

/* eslint-disable @typescript-eslint/no-explicit-any */
const MODE_TEMPLATES: Record<string, { label: string; def: any }> = {
  quote: {
    label: "语录模板",
    def: {
      mode_id: "MY_QUOTE", display_name: "自定义语录", icon: "book", cacheable: true,
      description: "自定义语录模式",
      content: {
        type: "llm_json", prompt_template: "请生成一条有深度的语录，用 JSON 返回 {quote, author}。{context}",
        output_schema: { quote: { type: "string" }, author: { type: "string" } }, temperature: 0.8,
        fallback: { quote: "路漫漫其修远兮", author: "屈原" },
        fallback_pool: [{ quote: "路漫漫其修远兮", author: "屈原" }, { quote: "知者不惑，仁者不忧", author: "孔子" }, { quote: "天行健，君子以自强不息", author: "易经" }],
      },
      layout: { status_bar: { line_width: 1 }, body: [{ type: "centered_text", field: "quote", font: "NotoSerifSC-Light.ttf", font_size: 18, vertical_center: true }], footer: { label: "MY_QUOTE", attribution_template: "— {author}" } },
    },
  },
  list: {
    label: "列表模板",
    def: {
      mode_id: "MY_LIST", display_name: "自定义列表", icon: "list", cacheable: true,
      description: "列表展示模式",
      content: {
        type: "llm_json", prompt_template: "请生成3条科技快讯，JSON 格式 {title, items: [{text}]}。{context}",
        output_schema: { title: { type: "string" }, items: { type: "array", items: { type: "object", properties: { text: { type: "string" } } } } },
        temperature: 0.7, fallback: { title: "今日快讯", items: [{ text: "暂无内容" }] },
      },
      layout: { status_bar: { line_width: 1 }, body: [{ type: "text", field: "title", font_size: 16, align: "center", bold: true }, { type: "spacer", height: 8 }, { type: "list", field: "items", item_template: "{text}", max_items: 5, font_size: 12 }], footer: { label: "MY_LIST" } },
    },
  },
  zen: {
    label: "禅意模板",
    def: {
      mode_id: "MY_ZEN", display_name: "自定义禅", icon: "zen", cacheable: true,
      description: "单字禅意模式",
      content: {
        type: "llm_json", prompt_template: "请给出一个蕴含哲理的汉字，并简短解读。JSON: {word, reading}。{context}",
        output_schema: { word: { type: "string" }, reading: { type: "string" } }, temperature: 0.9,
        fallback: { word: "道", reading: "万物之始" },
      },
      layout: { status_bar: { line_width: 1 }, body: [{ type: "centered_text", field: "word", font: "NotoSerifSC-Bold.ttf", font_size: 80, vertical_center: true }, { type: "centered_text", field: "reading", font_size: 13 }], footer: { label: "MY_ZEN" } },
    },
  },
  sections: {
    label: "综合模板",
    def: {
      mode_id: "MY_DAILY", display_name: "自定义综合", icon: "daily", cacheable: true,
      description: "多栏综合内容",
      content: {
        type: "llm_json", prompt_template: "请生成今日内容：一句话语录、一个推荐、一个小贴士。JSON: {quote, recommend, tip}。{context}",
        output_schema: { quote: { type: "string" }, recommend: { type: "string" }, tip: { type: "string" } }, temperature: 0.8,
        fallback: { quote: "今天是美好的一天", recommend: "推荐阅读", tip: "记得喝水" },
      },
      layout: { status_bar: { line_width: 1 }, body: [{ type: "section", label: "📖 语录", blocks: [{ type: "text", field: "quote", font_size: 13 }] }, { type: "separator", dashed: true }, { type: "section", label: "💡 推荐", blocks: [{ type: "text", field: "recommend", font_size: 12 }] }, { type: "separator", dashed: true }, { type: "section", label: "🌟 小贴士", blocks: [{ type: "text", field: "tip", font_size: 12 }] }], footer: { label: "MY_DAILY" } },
    },
  },
};
/* eslint-enable @typescript-eslint/no-explicit-any */

const TABS = [
  { id: "modes", label: "模式", icon: Settings },
  { id: "preferences", label: "个性化", icon: Sliders },
  { id: "stats", label: "状态", icon: BarChart3 },
] as const;

type TabId = (typeof TABS)[number]["id"];

interface DeviceConfig {
  mac?: string;
  modes?: string[];
  refreshStrategy?: string;
  refreshInterval?: number;
  refresh_strategy?: string;
  refresh_minutes?: number;
  city?: string;
  language?: string;
  contentTone?: string;
  content_tone?: string;
  characterTones?: string[];
  character_tones?: string[];
  llmProvider?: string;
  llmModel?: string;
  llm_provider?: string;
  llm_model?: string;
  imageProvider?: string;
  imageModel?: string;
  image_provider?: string;
  image_model?: string;
  countdownEvents?: { name: string; date: string }[];
  countdown_events?: { name: string; date: string }[];
  memoText?: string;
  memo_text?: string;
  has_api_key?: boolean;
  has_image_api_key?: boolean;
  mode_overrides?: Record<string, ModeOverride>;
  modeOverrides?: Record<string, ModeOverride>;
}

interface ModeOverride {
  city?: string;
  llm_provider?: string;
  llm_model?: string;
  [key: string]: unknown;
}

interface ModeSettingSchemaItem {
  key: string;
  label: string;
  type?: "text" | "textarea" | "number" | "select" | "boolean";
  placeholder?: string;
  default?: unknown;
  min?: number;
  max?: number;
  step?: number;
  description?: string;
  as_json?: boolean;
  options?: Array<{ value: string; label: string } | string>;
}

interface ServerModeItem {
  mode_id: string;
  display_name: string;
  description: string;
  source: string;
  settings_schema?: ModeSettingSchemaItem[];
}

interface DeviceStats {
  total_renders?: number;
  cache_hit_rate?: number;
  last_battery_voltage?: number;
  last_rssi?: number;
  last_refresh?: string;
  error_count?: number;
  mode_frequency?: Record<string, number>;
}

type RuntimeMode = "active" | "interval" | "unknown";

function ConfigPageInner() {
  const pathname = usePathname();
  const locale = localeFromPathname(pathname || "/");
  const isEn = locale === "en";
  const tr = (zh: string, en: string) => (isEn ? en : zh);
  const searchParams = useSearchParams();
  const mac = searchParams.get("mac") || "";
  const preferMac = searchParams.get("prefer_mac") || "";
  const prefillCode = searchParams.get("code") || "";
  const [currentUser, setCurrentUser] = useState<{ user_id: number; username: string } | null | undefined>(undefined);
  const [userDevices, setUserDevices] = useState<UserDevice[]>([]);
  const [devicesLoading, setDevicesLoading] = useState(false);
  const [pairCodeInput, setPairCodeInput] = useState("");
  const [pairingDevice, setPairingDevice] = useState(false);
  const [bindMacInput, setBindMacInput] = useState("");
  const [bindNicknameInput, setBindNicknameInput] = useState("");
  const [deviceMembers, setDeviceMembers] = useState<DeviceMember[]>([]);
  const [pendingRequests, setPendingRequests] = useState<AccessRequestItem[]>([]);
  const [membersLoading, setMembersLoading] = useState(false);
  const [requestsLoading, setRequestsLoading] = useState(false);
  const [shareUsernameInput, setShareUsernameInput] = useState("");
  const [macAccessDenied, setMacAccessDenied] = useState(false);

  const refreshCurrentUser = useCallback(() => {
    fetchCurrentUser()
      .then((d) => setCurrentUser(d ? { user_id: d.user_id, username: d.username } : null))
      .catch(() => setCurrentUser(null));
  }, []);

  useEffect(() => {
    refreshCurrentUser();
  }, [refreshCurrentUser]);

  useEffect(() => {
    const off = onAuthChanged(refreshCurrentUser);
    const onFocus = () => refreshCurrentUser();
    window.addEventListener("focus", onFocus);
    return () => {
      off();
      window.removeEventListener("focus", onFocus);
    };
  }, [refreshCurrentUser]);

  const loadUserDevices = useCallback(async () => {
    setDevicesLoading(true);
    try {
      const res = await fetch("/api/user/devices", { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        setUserDevices(data.devices || []);
      }
    } catch { /* ignore */ }
    finally { setDevicesLoading(false); }
  }, []);

  const loadPendingRequests = useCallback(async () => {
    setRequestsLoading(true);
    try {
      const res = await fetch("/api/user/devices/requests", { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        setPendingRequests(data.requests || []);
      }
    } catch { /* ignore */ }
    finally { setRequestsLoading(false); }
  }, []);

  const loadDeviceMembers = useCallback(async (deviceMac: string) => {
    if (!deviceMac) return;
    setMembersLoading(true);
    try {
      const res = await fetch(`/api/user/devices/${encodeURIComponent(deviceMac)}/members`, {
        headers: authHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setDeviceMembers(data.members || []);
      } else {
        setDeviceMembers([]);
      }
    } catch {
      setDeviceMembers([]);
    } finally {
      setMembersLoading(false);
    }
  }, []);

  useEffect(() => {
    if (currentUser) {
      loadUserDevices();
      loadPendingRequests();
    }
  }, [currentUser, loadPendingRequests, loadUserDevices]);

  useEffect(() => {
    if (mac) return;
    const normalizedCode = prefillCode.trim().toUpperCase();
    if (normalizedCode) {
      setPairCodeInput((prev) => prev || normalizedCode);
    }
    const normalizedMac = preferMac.trim().toUpperCase();
    if (normalizedMac) {
      setBindMacInput((prev) => prev || normalizedMac);
    }
  }, [mac, preferMac, prefillCode]);

  useEffect(() => {
    if (mac || !preferMac || !currentUser || devicesLoading) return;
    const normalizedMac = preferMac.trim().toUpperCase();
    if (!normalizedMac) return;
    const alreadyBound = userDevices.some((item) => item.mac.toUpperCase() === normalizedMac);
    if (alreadyBound) {
      window.location.href = `${withLocalePath(locale, "/config")}?mac=${encodeURIComponent(normalizedMac)}`;
    }
  }, [currentUser, devicesLoading, locale, mac, preferMac, userDevices]);

  const handlePairDevice = async () => {
    const normalized = pairCodeInput.trim().toUpperCase();
    if (!normalized) return;
    setPairingDevice(true);
    try {
      const res = await fetch("/api/claim/consume", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ pair_code: normalized }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        showToast(data.error || "配对失败", "error");
        return;
      }
      setPairCodeInput("");
      if (data.status === "claimed" || data.status === "already_member" || data.status === "active") {
        await loadUserDevices();
        await loadPendingRequests();
        window.location.href = `${withLocalePath(locale, "/config")}?mac=${encodeURIComponent(data.mac)}`;
        return;
      }
      await loadPendingRequests();
      showToast("已提交绑定申请，等待 owner 同意", "info");
    } catch {
      showToast("配对失败", "error");
    } finally {
      setPairingDevice(false);
    }
  };

  const handleBindDevice = async (deviceMac: string, nickname?: string) => {
    try {
      const res = await fetch("/api/user/devices", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ mac: deviceMac, nickname: nickname || "" }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        showToast(data.error || "绑定失败", "error");
        return null;
      }
      setBindMacInput("");
      setBindNicknameInput("");
      await loadUserDevices();
      await loadPendingRequests();
      return data;
    } catch {
      showToast("绑定失败", "error");
      return null;
    }
  };

  const handleUnbindDevice = async (deviceMac: string) => {
    try {
      const res = await fetch(`/api/user/devices/${encodeURIComponent(deviceMac)}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      if (res.ok) await loadUserDevices();
    } catch { /* ignore */ }
  };

  const handleApproveRequest = async (requestId: number) => {
    try {
      const res = await fetch(`/api/user/devices/requests/${requestId}/approve`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: "{}",
      });
      if (res.ok) {
        await loadPendingRequests();
        if (mac) await loadDeviceMembers(mac);
        showToast("已同意绑定请求", "success");
      } else {
        showToast("同意失败", "error");
      }
    } catch {
      showToast("同意失败", "error");
    }
  };

  const handleRejectRequest = async (requestId: number) => {
    try {
      const res = await fetch(`/api/user/devices/requests/${requestId}/reject`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: "{}",
      });
      if (res.ok) {
        await loadPendingRequests();
        showToast("已拒绝绑定请求", "success");
      } else {
        showToast("拒绝失败", "error");
      }
    } catch {
      showToast("拒绝失败", "error");
    }
  };

  const handleShareDevice = async () => {
    if (!mac || !shareUsernameInput.trim()) return;
    try {
      const res = await fetch(`/api/user/devices/${encodeURIComponent(mac)}/share`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ username: shareUsernameInput.trim() }),
      });
      if (!res.ok) throw new Error("share failed");
      setShareUsernameInput("");
      await loadDeviceMembers(mac);
      await loadPendingRequests();
      showToast("分享成功", "success");
    } catch {
      showToast("分享失败", "error");
    }
  };

  const handleRemoveMember = async (targetUserId: number) => {
    if (!mac) return;
    try {
      const res = await fetch(`/api/user/devices/${encodeURIComponent(mac)}/members/${targetUserId}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      if (!res.ok) throw new Error("remove failed");
      await loadDeviceMembers(mac);
      showToast("成员已移除", "success");
    } catch {
      showToast("移除成员失败", "error");
    }
  };

  const [activeTab, setActiveTab] = useState<TabId>("modes");
  const [config, setConfig] = useState<DeviceConfig>({});
  const [selectedModes, setSelectedModes] = useState<Set<string>>(new Set(["STOIC", "ZEN", "DAILY"]));
  const [strategy, setStrategy] = useState("random");
  const [refreshMin, setRefreshMin] = useState(60);
  const [city, setCity] = useState("");
  const [language, setLanguage] = useState("zh");
  const [contentTone, setContentTone] = useState("neutral");
  const [characterTones, setCharacterTones] = useState<string[]>([]);
  const [customPersonaTone, setCustomPersonaTone] = useState("");
  const [modeOverrides, setModeOverrides] = useState<Record<string, ModeOverride>>({});
  const [settingsMode, setSettingsMode] = useState<string | null>(null);
  const [settingsJsonDrafts, setSettingsJsonDrafts] = useState<Record<string, string>>({});
  const [settingsJsonErrors, setSettingsJsonErrors] = useState<Record<string, string>>({});
  const [memoText, setMemoText] = useState("");

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: "success" | "error" | "info" } | null>(null);
  const [stats, setStats] = useState<DeviceStats | null>(null);
  const [previewImg, setPreviewImg] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewStatusText, setPreviewStatusText] = useState("");
  const [previewMode, setPreviewMode] = useState("");
  const [previewNoCacheOnce, setPreviewNoCacheOnce] = useState(false);
  const [previewCacheHit, setPreviewCacheHit] = useState<boolean | null>(null);
  // 邀请码弹窗状态
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteCode, setInviteCode] = useState("");
  const [redeemingInvite, setRedeemingInvite] = useState(false);
  const [pendingPreviewMode, setPendingPreviewMode] = useState<string | null>(null);
  const [currentMode, setCurrentMode] = useState<string>("");
  const [applyToScreenLoading, setApplyToScreenLoading] = useState(false);
  const [favoritedModes, setFavoritedModes] = useState<Set<string>>(new Set());
  const favoritesLoadedMacRef = useRef<string>("");
  const memoSettingsInputRef = useRef<HTMLTextAreaElement | null>(null);
  const previewStreamRef = useRef<EventSource | null>(null);
  const [runtimeMode, setRuntimeMode] = useState<RuntimeMode>("unknown");
  const [isOnline, setIsOnline] = useState(false);
  const [lastSeen, setLastSeen] = useState<string | null>(null);

  const [customDesc, setCustomDesc] = useState("");
  const [customModeName, setCustomModeName] = useState("");
  const [customJson, setCustomJson] = useState("");
  const [customGenerating, setCustomGenerating] = useState(false);
  const [customPreviewImg, setCustomPreviewImg] = useState<string | null>(null);
  const [customPreviewLoading, setCustomPreviewLoading] = useState(false);
  const [customApplyToScreenLoading, setCustomApplyToScreenLoading] = useState(false);
  const [editingCustomMode, setEditingCustomMode] = useState(false);
  const [editorTab, setEditorTab] = useState<"ai" | "template">("ai");

  const [serverModes, setServerModes] = useState<ServerModeItem[]>([]);

  const showToast = useCallback((msg: string, type: "success" | "error" | "info" = "info") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  }, []);

  const nextConfigPath = useMemo(() => {
    const params = new URLSearchParams();
    if (mac) {
      params.set("mac", mac);
    } else {
      if (preferMac) params.set("prefer_mac", preferMac);
      if (prefillCode) params.set("code", prefillCode);
    }
    const query = params.toString();
    return query ? `${withLocalePath(locale, "/config")}?${query}` : withLocalePath(locale, "/config");
  }, [locale, mac, preferMac, prefillCode]);

  useEffect(() => {
    const params = new URLSearchParams();
    if (mac) {
      params.append("mac", mac);
    }
    fetch(`/api/modes?${params.toString()}`, {
      headers: authHeaders(),
    }).then((r) => r.json()).then((d) => {
      if (d.modes) setServerModes(d.modes);
    }).catch(() => {});
  }, [mac]);

  useEffect(() => {
    if (mac && currentUser) {
      loadDeviceMembers(mac);
      loadPendingRequests();
    }
  }, [currentUser, loadDeviceMembers, loadPendingRequests, mac]);

  useEffect(() => {
    setMacAccessDenied(false);
  }, [mac]);

  useEffect(() => {
    if (!mac) return;
    fetch(`/api/device/${encodeURIComponent(mac)}/state`, { headers: authHeaders() })
      .then((r) => {
        if (r.status === 401 || r.status === 403) {
          setMacAccessDenied(true);
          return null;
        }
        return r.ok ? r.json() : null;
      })
      .then(async (d) => {
        if (!d?.last_persona) return;
        setCurrentMode(d.last_persona);
        setPreviewMode(d.last_persona);
      })
      .catch(() => {});
  }, [mac]);

  useEffect(() => {
    if (!mac) return;
    setLoading(true);
    fetch(`/api/config/${encodeURIComponent(mac)}`, { headers: authHeaders() })
      .then((r) => {
        if (r.status === 401 || r.status === 403) {
          setMacAccessDenied(true);
          throw new Error("Forbidden");
        }
        if (!r.ok) throw new Error("No config");
        return r.json();
      })
      .then((cfg: DeviceConfig) => {
        setConfig(cfg);
        if (cfg.modes?.length) setSelectedModes(new Set(cfg.modes.map((m) => m.toUpperCase())));
        if (cfg.refreshStrategy || cfg.refresh_strategy) setStrategy((cfg.refreshStrategy || cfg.refresh_strategy) as string);
        if (cfg.refreshInterval || cfg.refresh_minutes) setRefreshMin((cfg.refreshInterval || cfg.refresh_minutes) as number);
        if (cfg.city) setCity(cfg.city);
        if (cfg.language) setLanguage(normalizeLanguage(cfg.language));
        if (cfg.contentTone || cfg.content_tone) setContentTone(normalizeTone(cfg.contentTone || cfg.content_tone));
        if (cfg.characterTones || cfg.character_tones) setCharacterTones((cfg.characterTones || cfg.character_tones) as string[]);
        if (cfg.mode_overrides) setModeOverrides(cfg.mode_overrides);
        else if (cfg.modeOverrides) setModeOverrides(cfg.modeOverrides);
        const loadedOverrides = ((cfg.mode_overrides || cfg.modeOverrides || {}) as Record<string, ModeOverride>);
        const memoFromOverride = loadedOverrides?.MEMO?.memo_text;
        if (typeof memoFromOverride === "string" && memoFromOverride.trim()) {
          setMemoText(memoFromOverride);
        } else if (cfg.memoText || cfg.memo_text) {
          setMemoText((cfg.memoText || cfg.memo_text) as string);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [mac]);

  const getModeOverride = useCallback((modeId: string) => {
    return modeOverrides[modeId] || {};
  }, [modeOverrides]);

  const sanitizeModeOverride = useCallback((input: ModeOverride) => {
    const cleaned: ModeOverride = {};
    for (const [k, raw] of Object.entries(input)) {
      if (k === "city" || k === "llm_provider" || k === "llm_model") {
        if (typeof raw === "string" && raw.trim()) cleaned[k] = raw.trim();
        continue;
      }
      if (typeof raw === "string") {
        if (raw.trim()) cleaned[k] = raw.trim();
        continue;
      }
      if (typeof raw === "number") {
        if (!Number.isNaN(raw)) cleaned[k] = raw;
        continue;
      }
      if (typeof raw === "boolean") {
        cleaned[k] = raw;
        continue;
      }
      if (Array.isArray(raw)) {
        if (raw.length > 0) cleaned[k] = raw;
        continue;
      }
      if (raw && typeof raw === "object") {
        if (Object.keys(raw).length > 0) cleaned[k] = raw as Record<string, unknown>;
      }
    }
    return cleaned;
  }, []);

  const updateModeOverride = useCallback((modeId: string, patch: Partial<ModeOverride>) => {
    setModeOverrides((prev) => {
      const next = { ...(prev[modeId] || {}), ...patch } as ModeOverride;
      const cleaned = sanitizeModeOverride(next);
      if (!Object.keys(cleaned).length) {
        const copied = { ...prev };
        delete copied[modeId];
        return copied;
      }
      return { ...prev, [modeId]: cleaned };
    });
  }, [sanitizeModeOverride]);

  const clearModeOverride = useCallback((modeId: string) => {
    setModeOverrides((prev) => {
      const copied = { ...prev };
      delete copied[modeId];
      return copied;
    });
    setSettingsJsonDrafts((prev) => {
      const copied = { ...prev };
      Object.keys(copied).forEach((k) => {
        if (k.startsWith(`${modeId}:`)) delete copied[k];
      });
      return copied;
    });
    setSettingsJsonErrors((prev) => {
      const copied = { ...prev };
      Object.keys(copied).forEach((k) => {
        if (k.startsWith(`${modeId}:`)) delete copied[k];
      });
      return copied;
    });
  }, []);

  const modeSchemaMap = useMemo(
    () => Object.fromEntries(serverModes.map((m) => [m.mode_id, m.settings_schema || []])),
    [serverModes]
  );

  const applySettingsDrafts = useCallback((modeId: string) => {
    const schema = modeSchemaMap[modeId] || [];
    for (const item of schema) {
      if (!item.as_json) continue;
      const key = `${modeId}:${item.key}`;
      if (!(key in settingsJsonDrafts)) continue;
      const text = settingsJsonDrafts[key] || "";
      if (!text.trim()) {
        updateModeOverride(modeId, { [item.key]: undefined });
        continue;
      }
      try {
        const parsed = JSON.parse(text);
        updateModeOverride(modeId, { [item.key]: parsed });
      } catch {
        setSettingsJsonErrors((prev) => ({ ...prev, [key]: "JSON 格式错误" }));
        showToast(`${item.label} JSON 格式错误`, "error");
        return false;
      }
    }
    return true;
  }, [modeSchemaMap, settingsJsonDrafts, showToast, updateModeOverride]);

  const handleSave = async () => {
    if (!mac) { showToast("请先完成刷机和配网以获取设备 MAC", "error"); return; }
    if (macAccessDenied) { showToast("你无权配置该设备", "error"); return; }
    setSaving(true);
    try {
      const normalizedModeOverrides = Object.fromEntries(
        Object.entries(modeOverrides)
          .map(([modeId, ov]) => {
            const cleaned = sanitizeModeOverride(ov);
            return [modeId.toUpperCase(), cleaned] as const;
          })
          .filter(([, ov]) => Object.keys(ov).length > 0)
      );
      const body: Record<string, unknown> = {
        mac,
        modes: Array.from(selectedModes),
        refreshStrategy: strategy,
        refreshInterval: refreshMin,
        city,
        language,
        contentTone,
        characterTones: characterTones,
        modeOverrides: normalizedModeOverrides,
        memoText: memoText,
      };
      const res = await fetch("/api/config", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error("Save failed");
      let onlineNow = isOnline;
      try {
        const stateRes = await fetch(`/api/device/${encodeURIComponent(mac)}/state`, { cache: "no-store", headers: authHeaders() });
        if (stateRes.ok) {
          const stateData = await stateRes.json();
          onlineNow = Boolean(stateData?.is_online);
          setIsOnline(onlineNow);
          setLastSeen(typeof stateData?.last_seen === "string" && stateData.last_seen ? stateData.last_seen : null);
        }
      } catch {}
      showToast(
        onlineNow ? "配置已保存" : "配置已保存，设备当前离线，将在设备上线后生效",
        onlineNow ? "success" : "info",
      );
      setPreviewNoCacheOnce(true);
    } catch {
      showToast("保存失败", "error");
    } finally {
      setSaving(false);
    }
  };

  const handlePreview = async (mode?: string, forceNoCache = false, forcedModeOverride?: ModeOverride) => {
    const m = mode || previewMode;
    const consumeNoCacheOnce = previewNoCacheOnce;
    const forceFresh = forceNoCache || consumeNoCacheOnce;
    setPreviewCacheHit(null);
    setPreviewLoading(true);
    setPreviewStatusText(tr("正在生成...", "Generating..."));
    try {
      const params = new URLSearchParams({ persona: m });
      if (mac) params.set("mac", mac);
      const activeModeOverride = sanitizeModeOverride({
        ...(modeOverrides[m] || {}),
        ...(forcedModeOverride || {}),
      });
      if (m === "MEMO" && memoText.trim() && !("memo_text" in activeModeOverride)) {
        activeModeOverride.memo_text = memoText.trim();
      }
      const hasModeOverride = Object.keys(activeModeOverride).length > 0;
      if (hasModeOverride) {
        params.set("mode_override", JSON.stringify(activeModeOverride));
      }
      if (m === "MEMO") {
        const memoCandidate = (
          typeof forcedModeOverride?.memo_text === "string" && forcedModeOverride.memo_text.trim()
            ? forcedModeOverride.memo_text
            : typeof activeModeOverride.memo_text === "string" && activeModeOverride.memo_text.trim()
            ? activeModeOverride.memo_text
            : memoText
        ).trim();
        if (memoCandidate) {
          params.set("memo_text", memoCandidate);
        }
      }
      const modeCity = (modeOverrides[m]?.city || "").trim();
      const globalCity = city.trim();
      const previewCity = modeCity || globalCity;
      const savedGlobalCity = (config.city || "").trim();
      const savedOverrides = (config.mode_overrides || config.modeOverrides || {}) as Record<string, ModeOverride>;
      const savedModeCity = (savedOverrides[m]?.city || "").trim();
      const cityChanged = previewCity.length > 0 && (modeCity ? modeCity !== savedModeCity : globalCity !== savedGlobalCity);
      if (cityChanged) params.set("city_override", previewCity);
      if (forceFresh || cityChanged || hasModeOverride) params.set("no_cache", "1");
      previewStreamRef.current?.close();
      const stream = new EventSource(`/api/preview/stream?${params.toString()}`);
      previewStreamRef.current = stream;

      await new Promise<void>((resolve, reject) => {
        stream.addEventListener("status", (event) => {
          try {
            const data = JSON.parse((event as MessageEvent<string>).data) as { message?: string };
            setPreviewStatusText(data.message || tr("正在生成...", "Generating..."));
          } catch {
            setPreviewStatusText(tr("正在生成...", "Generating..."));
          }
        });

        stream.addEventListener("error", (event) => {
          try {
            const data = JSON.parse((event as MessageEvent<string>).data) as {
              error?: string;
              message?: string;
              requires_invite_code?: boolean;
            };
            // 如果额度耗尽，显示邀请码输入弹窗
            if (data.requires_invite_code) {
              stream.close();
              previewStreamRef.current = null;
              setShowInviteModal(true);
              setPendingPreviewMode(previewMode);
              setPreviewStatusText("");
              setPreviewLoading(false); // 重置加载状态
              resolve(); // 不 reject，而是 resolve，因为这是预期的业务逻辑
              return;
            }
            // 其他错误，正常 reject
            stream.close();
            previewStreamRef.current = null;
            setPreviewLoading(false); // 重置加载状态
            reject(new Error(data.message || "Preview failed"));
          } catch {
            stream.close();
            previewStreamRef.current = null;
            setPreviewLoading(false); // 重置加载状态
            reject(new Error("Preview failed"));
          }
        });

        stream.addEventListener("result", (event) => {
          try {
            const data = JSON.parse((event as MessageEvent<string>).data) as {
              message?: string;
              image_url?: string;
              cache_hit?: boolean;
            };
            console.log("[PREVIEW] Result event received:", { hasImageUrl: !!data.image_url, message: data.message });
            if (!data.image_url) {
              console.error("[PREVIEW] Missing image_url in result event");
              setPreviewLoading(false); // 重置加载状态
              reject(new Error("Preview image missing"));
              return;
            }
            console.log("[PREVIEW] Setting preview image:", data.image_url.substring(0, 50) + "...");
            setPreviewImg(data.image_url);
            setPreviewCacheHit(typeof data.cache_hit === "boolean" ? data.cache_hit : null);
            setPreviewStatusText(data.message || tr("完成", "Done"));
            setPreviewLoading(false); // 重置加载状态
            stream.close();
            previewStreamRef.current = null;
            resolve();
          } catch (error) {
            console.error("[PREVIEW] Error processing result event:", error);
            setPreviewLoading(false); // 重置加载状态
            reject(error);
          }
        });

        stream.onerror = () => {
          stream.close();
          previewStreamRef.current = null;
          setPreviewLoading(false); // 重置加载状态
          reject(new Error("Preview failed"));
        };
      });
    } catch {
      showToast("预览失败", "error");
      setPreviewCacheHit(null);
      setPreviewStatusText("");
    } finally {
      setPreviewLoading(false);
      if (consumeNoCacheOnce) setPreviewNoCacheOnce(false);
    }
  };

  const handleRedeemInviteCode = async () => {
    if (!inviteCode.trim()) {
      showToast(isEn ? "Please enter invitation code" : "请输入邀请码", "error");
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
        throw new Error(data.error || (isEn ? "Failed to redeem invitation code" : "邀请码兑换失败"));
      }

      showToast(data.message || (isEn ? "Invitation code redeemed successfully" : "邀请码兑换成功"), "success");
      setShowInviteModal(false);
      setInviteCode("");
      // 重新尝试预览
      if (pendingPreviewMode) {
        await handlePreview(pendingPreviewMode, true);
        setPendingPreviewMode(null);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : (isEn ? "Failed to redeem invitation code" : "邀请码兑换失败");
      showToast(msg, "error");
    } finally {
      setRedeemingInvite(false);
    }
  };

  const loadStats = useCallback(async () => {
    if (!mac) return;
    try {
      const res = await fetch(`/api/stats/${encodeURIComponent(mac)}`, { headers: authHeaders() });
      if (res.ok) setStats(await res.json());
    } catch {}
  }, [mac]);

  const loadFavorites = useCallback(async (force = false) => {
    if (!mac) return;
    if (!force && favoritesLoadedMacRef.current === mac) return;
    try {
      const res = await fetch(`/api/device/${encodeURIComponent(mac)}/favorites?limit=100`, { headers: authHeaders() });
      if (res.status === 401 || res.status === 403) {
        setMacAccessDenied(true);
        return;
      }
      if (!res.ok) return;
      const data = await res.json();
      const modes = new Set<string>(
        (data.favorites || [])
          .map((item: { mode_id?: string }) => (item.mode_id || "").toUpperCase())
          .filter((modeId: string) => modeId.length > 0),
      );
      setFavoritedModes(modes);
      favoritesLoadedMacRef.current = mac;
    } catch {}
  }, [mac]);

  const loadRuntimeMode = useCallback(async () => {
    if (!mac) return;
    try {
      const res = await fetch(`/api/device/${encodeURIComponent(mac)}/state`, { cache: "no-store", headers: authHeaders() });
      if (res.status === 401 || res.status === 403) {
        setMacAccessDenied(true);
        return;
      }
      if (!res.ok) return;
      const data = await res.json();
      setIsOnline(Boolean(data?.is_online));
      setLastSeen(typeof data?.last_seen === "string" && data.last_seen ? data.last_seen : null);
      const mode = data?.runtime_mode;
      if (mode === "active" || mode === "interval") {
        setRuntimeMode(mode);
      } else {
        setRuntimeMode("interval");
      }
    } catch {
      setIsOnline(false);
      setLastSeen(null);
      setRuntimeMode("interval");
    }
  }, [mac]);

  useEffect(() => {
    if (activeTab === "stats" && mac) loadStats();
  }, [activeTab, mac, loadStats]);

  useEffect(() => {
    if (!mac) return;
    favoritesLoadedMacRef.current = "";
    loadFavorites();
  }, [mac, loadFavorites]);

  useEffect(() => {
    if (!mac) return;
    loadRuntimeMode();
  }, [mac, loadRuntimeMode]);

  useEffect(() => {
    if (!mac || !currentUser) {
      setSettingsMode(null);
    }
  }, [mac, currentUser]);

  useEffect(() => {
    return () => {
      previewStreamRef.current?.close();
      previewStreamRef.current = null;
    };
  }, []);

  const handleGenerateMode = async () => {
    if (!customDesc.trim()) { showToast("请输入模式描述", "error"); return; }
    setCustomGenerating(true);
    try {
      const res = await fetch("/api/modes/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          description: customDesc, 
          provider: "deepseek", 
          model: "deepseek-chat",
          mac: mac || undefined,
        }),
      });

      // 额度不足：后端按 BILLING.md 约定返回 402
      if (res.status === 402) {
        const d = await res.json().catch(() => ({}));
        showToast(
          (d && d.error) || (isEn ? "Your free quota has been exhausted, please redeem an invitation code or configure your own API key in your profile." : "您的免费额度已用完，请输入邀请码或在个人信息中配置自己的 API key。"),
          "error",
        );
        setShowInviteModal(true);
        setCustomGenerating(false);
        return;
      }

      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "生成失败");
      setCustomJson(JSON.stringify(data.mode_def, null, 2));
      setCustomModeName((data.mode_def?.display_name || "").toString());
      showToast("模式生成成功", "success");
    } catch (e) {
      showToast(`生成失败: ${e instanceof Error ? e.message : "未知错误"}`, "error");
    } finally {
      setCustomGenerating(false);
    }
  };

  const handleCustomPreview = async () => {
    if (!customJson.trim()) return;
    setCustomPreviewLoading(true);
    try {
      const def = JSON.parse(customJson);
      if (customModeName.trim()) {
        def.display_name = customModeName.trim();
      }
      const res = await fetch("/api/modes/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode_def: def, mac: mac || undefined }),
      });

      // 额度不足：返回 402
      if (res.status === 402) {
        const d = await res.json().catch(() => ({}));
        showToast(
          (d && d.error) || (isEn ? "Your free quota has been exhausted, please redeem an invitation code or configure your own API key in your profile." : "您的免费额度已用完，请输入邀请码或在个人信息中配置自己的 API key。"),
          "error",
        );
        setShowInviteModal(true);
        setCustomPreviewLoading(false);
        return;
      }

      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.error || "预览失败");
      }
      const blob = await res.blob();
      setCustomPreviewImg(URL.createObjectURL(blob));
    } catch (e) {
      showToast(`预览失败: ${e instanceof Error ? e.message : ""}`, "error");
    } finally {
      setCustomPreviewLoading(false);
    }
  };

  const handleApplyCustomPreviewToScreen = async () => {
    if (!mac || !customPreviewImg) return;
    setCustomApplyToScreenLoading(true);
    try {
      const stateRes = await fetch(`/api/device/${encodeURIComponent(mac)}/state`, { cache: "no-store", headers: authHeaders() });
      if (!stateRes.ok) {
        showToast("无法确认设备状态，已阻止发送", "error");
        return;
      }
      const stateData = await stateRes.json();
      const mode = stateData?.runtime_mode;
      if (mode === "active" || mode === "interval") {
        setRuntimeMode(mode);
      }
      if (mode !== "active") {
        showToast("设备处于间歇状态，不可发送", "error");
        return;
      }

      const previewResponse = await fetch(customPreviewImg);
      if (!previewResponse.ok) throw new Error("preview image unavailable");
      const previewBlob = await previewResponse.blob();

      let modeHint = "CUSTOM_PREVIEW";
      try {
        const def = JSON.parse(customJson);
        if (customModeName.trim()) {
          modeHint = customModeName.trim().toUpperCase().replace(/[^A-Z0-9_]/g, "_");
        } else if (typeof def?.mode_id === "string" && def.mode_id.trim()) {
          modeHint = def.mode_id.trim().toUpperCase();
        }
      } catch {}

      const qs = new URLSearchParams();
      qs.set("mode", modeHint);
      const res = await fetch(`/api/device/${encodeURIComponent(mac)}/apply-preview?${qs.toString()}`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "image/png" }),
        body: previewBlob,
      });
      if (!res.ok) throw new Error("apply-preview failed");
      setCurrentMode(modeHint);
      await loadRuntimeMode();
      showToast("已下发到墨水屏", "success");
    } catch {
      showToast("下发失败", "error");
    } finally {
      setCustomApplyToScreenLoading(false);
    }
  };

  const handleSaveCustomMode = async () => {
    if (!customJson.trim()) return;
    if (!mac) {
      showToast("请先选择设备", "error");
      return;
    }
    try {
      const def = JSON.parse(customJson);
      
      // Ensure mode_id exists - generate from display_name if missing
      if (!def.mode_id || !def.mode_id.trim()) {
        if (customModeName.trim()) {
          def.mode_id = customModeName.trim().toUpperCase().replace(/[^A-Z0-9_]/g, "_");
          // Ensure it starts with a letter
          if (!/^[A-Z]/.test(def.mode_id)) {
            def.mode_id = "CUSTOM_" + def.mode_id;
          }
        } else if (def.display_name) {
          def.mode_id = def.display_name.toUpperCase().replace(/[^A-Z0-9_]/g, "_");
          if (!/^[A-Z]/.test(def.mode_id)) {
            def.mode_id = "CUSTOM_" + def.mode_id;
          }
        } else {
          // Generate a random mode_id if no name is available
          def.mode_id = "CUSTOM_" + Math.random().toString(36).substring(2, 10).toUpperCase();
        }
      }
      
      if (customModeName.trim()) {
        def.display_name = customModeName.trim();
      }
      
      // Add mac to the request body
      def.mac = mac;
      
      const res = await fetch("/api/modes/custom", {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          ...authHeaders(),
        },
        body: JSON.stringify(def),
      });
      
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.error || `保存失败: ${res.status}`);
      }
      
      const data = await res.json();
      if (data.ok || data.status === "ok") {
        showToast(`模式 ${def.mode_id} 已保存`, "success");
        // Refresh modes list with mac parameter
        const params = new URLSearchParams();
        params.append("mac", mac);
        fetch(`/api/modes?${params.toString()}`, { headers: authHeaders() }).then((r) => r.json()).then((d) => { if (d.modes) setServerModes(d.modes); }).catch(() => {});
        setEditingCustomMode(false);
        setCustomJson("");
        setCustomDesc("");
        setCustomModeName("");
        setCustomPreviewImg(null);
      } else {
        throw new Error(data.error || "保存失败");
      }
    } catch (e) {
      showToast(`保存失败: ${e instanceof Error ? e.message : ""}`, "error");
    }
  };

  const toggleMode = (modeId: string) => {
    setSelectedModes((prev) => {
      const next = new Set(prev);
      if (next.has(modeId)) next.delete(modeId);
      else next.add(modeId);
      return next;
    });
  };

  const handleModePreview = (m: string) => {
    setPreviewMode(m);
    handlePreview(m);
  };

  const handleModeApply = async (m: string) => {
    const wasSelected = selectedModes.has(m);
    toggleMode(m);
    showToast(wasSelected ? "已从轮播移除" : "已加入轮播", "success");
  };

  const handlePreviewFromSettings = (addToCarousel: boolean) => {
    if (!settingsMode) return;
    const modeId = settingsMode;
    if (!applySettingsDrafts(modeId)) return;
    let forcedOverride: ModeOverride | undefined;
    if (modeId === "MEMO") {
      const latestMemo = memoSettingsInputRef.current?.value ?? "";
      if (latestMemo.trim()) {
        forcedOverride = { memo_text: latestMemo };
        updateModeOverride(modeId, { memo_text: latestMemo });
        setMemoText(latestMemo);
      }
    }
    if (addToCarousel && !selectedModes.has(modeId)) {
      toggleMode(modeId);
    }
    setSettingsMode(null);
    setPreviewMode(modeId);
    setTimeout(() => {
      handlePreview(modeId, true, forcedOverride);
    }, 0);
    showToast(addToCarousel ? "已加入轮播并刷新预览" : "已刷新预览", "success");
  };

  const handleApplyPreviewToScreen = async () => {
    if (!mac || !previewMode || !previewImg) return;
    setApplyToScreenLoading(true);
    try {
      const stateRes = await fetch(`/api/device/${encodeURIComponent(mac)}/state`, { cache: "no-store", headers: authHeaders() });
      if (!stateRes.ok) {
        showToast("无法确认设备状态，已阻止发送", "error");
        return;
      }
      const stateData = await stateRes.json();
      const mode = stateData?.runtime_mode;
      if (mode === "active" || mode === "interval") {
        setRuntimeMode(mode);
      }
      if (mode !== "active") {
        showToast("设备处于间歇状态，不可发送", "error");
        return;
      }

      const previewResponse = await fetch(previewImg);
      if (!previewResponse.ok) throw new Error("preview image unavailable");
      const previewBlob = await previewResponse.blob();

      const qs = new URLSearchParams();
      qs.set("mode", previewMode);
      const res = await fetch(`/api/device/${encodeURIComponent(mac)}/apply-preview?${qs.toString()}`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "image/png" }),
        body: previewBlob,
      });
      if (!res.ok) throw new Error("apply-preview failed");
      setCurrentMode(previewMode);
      await loadRuntimeMode();
      showToast("已下发到墨水屏", "success");
    } catch {
      showToast("下发失败", "error");
    } finally {
      setApplyToScreenLoading(false);
    }
  };

  const handleModeFavorite = async (m: string) => {
    const wasFavorited = favoritedModes.has(m);
    setFavoritedModes((prev) => {
      const next = new Set(prev);
      if (next.has(m)) next.delete(m); else next.add(m);
      return next;
    });
    if (mac && !wasFavorited) {
      try {
        await fetch(`/api/device/${encodeURIComponent(mac)}/favorite`, {
          method: "POST",
          headers: authHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({ mode: m }),
        });
        await loadFavorites(true);
      } catch {}
    }
    showToast(wasFavorited ? "已取消收藏" : "已收藏", "success");
  };

  const handleAddCustomPersona = () => {
    const v = customPersonaTone.trim();
    if (!v) return;
    setCharacterTones((prev) => (prev.includes(v) ? prev : [...prev, v]));
    setCustomPersonaTone("");
  };

  const handleDeleteCustomMode = async (modeId: string) => {
    const modeName = customModeMeta[modeId]?.name || modeId;
    if (!window.confirm(`确定删除自定义模式「${modeName}」吗？`)) return;
    if (!mac) {
      showToast("请先选择设备", "error");
      return;
    }
    try {
      const params = new URLSearchParams();
      params.append("mac", mac);
      const res = await fetch(`/api/modes/custom/${encodeURIComponent(modeId)}?${params.toString()}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      if (!res.ok) throw new Error("delete failed");
      setServerModes((prev) => prev.filter((m) => m.mode_id !== modeId));
      setSelectedModes((prev) => {
        const next = new Set(prev);
        next.delete(modeId);
        return next;
      });
      setFavoritedModes((prev) => {
        const next = new Set(prev);
        next.delete(modeId);
        return next;
      });
      if (previewMode === modeId) {
        setPreviewMode("");
        setPreviewImg(null);
        setPreviewCacheHit(null);
      }
      if (currentMode === modeId) {
        setCurrentMode("");
      }
      if (settingsMode === modeId) {
        setSettingsMode(null);
      }
      showToast(`已删除模式 ${modeName}`, "success");
    } catch {
      showToast("删除模式失败", "error");
    }
  };

  const customModes = serverModes.filter((m) => m.source === "custom" && m.mode_id !== "VOCAB_DAILY");
  const customModeMeta = Object.fromEntries(serverModes.map((m) => [m.mode_id, { name: m.display_name, tip: m.description }]));
  const activeModeSchema = settingsMode ? (modeSchemaMap[settingsMode] || []) : [];

  const batteryPct = stats?.last_battery_voltage
    ? Math.min(100, Math.max(0, Math.round((stats.last_battery_voltage / 3.3) * 100)))
    : null;
  const currentDeviceMembership = userDevices.find((d) => d.mac.toUpperCase() === mac.toUpperCase()) || null;
  const denyByMembership = Boolean(mac && currentUser && !devicesLoading && !currentDeviceMembership);
  const currentUserRole = currentDeviceMembership?.role || "";
  const statusLabel = !isOnline
    ? tr("离线", "Offline")
    : runtimeMode === "active"
    ? tr("活跃状态", "Active")
    : tr("间歇状态", "Interval");
  const statusClass = !isOnline
    ? "bg-paper-dark text-ink-light border border-ink/10"
    : runtimeMode === "active"
    ? "bg-green-50 text-green-700 border border-green-200"
    : "bg-amber-50 text-amber-700 border border-amber-200";
  const statusIconClass = !isOnline
    ? "text-ink-light"
    : runtimeMode === "active"
    ? "text-green-600"
    : "text-amber-600";
  const tabs = isEn
    ? [
        { id: "modes", label: "Modes", icon: Settings },
        { id: "preferences", label: "Preferences", icon: Sliders },
        { id: "stats", label: "Status", icon: BarChart3 },
      ] as const
    : TABS;

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-serif text-3xl font-bold text-ink mb-2">{tr("设备配置", "Device Configuration")}</h1>
        {currentUser === undefined ? (
          <div className="flex items-center gap-2 text-ink-light text-sm py-4">
            <Loader2 size={16} className="animate-spin" /> {tr("加载中...", "Loading...")}
          </div>
        ) : currentUser === null ? (
          <div className="flex items-start gap-2 p-3 rounded-sm border border-amber-200 bg-amber-50 text-sm text-amber-800">
            <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
            <div>
              <p className="font-medium">{tr("请先登录", "Please sign in first")}</p>
              <p className="text-xs mt-0.5">{mac ? tr("登录后才能配置设备。", "Sign in to configure this device.") : tr("登录后可以管理你的设备列表。", "Sign in to manage your device list.")}</p>
              <Link href={`${withLocalePath(locale, "/login")}?next=${encodeURIComponent(nextConfigPath)}`}>
                <Button size="sm" className="mt-2">{tr("登录 / 注册", "Sign In / Sign Up")}</Button>
              </Link>
            </div>
          </div>
        ) : (macAccessDenied || denyByMembership) ? (
          <div className="flex items-start gap-2 p-3 rounded-sm border border-red-200 bg-red-50 text-sm text-red-800">
            <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
            <div>
              <p className="font-medium">{tr("无权访问该设备", "No permission to access this device")}</p>
              <p className="text-xs mt-0.5">{tr("该设备未绑定到当前账号，或你不是被授权成员。", "This device is not bound to your account, or you are not an authorized member.")}</p>
              <Link href={withLocalePath(locale, "/config")}>
                <Button size="sm" variant="outline" className="mt-2">{tr("返回设备列表", "Back to Device List")}</Button>
              </Link>
            </div>
          </div>
        ) : mac ? (
          <DeviceInfo
            mac={mac}
            currentUserRole={currentUserRole}
            statusIconClass={statusIconClass}
            statusClass={statusClass}
            statusLabel={statusLabel}
            lastSeen={lastSeen}
            isEn={isEn}
            localeConfigPath={withLocalePath(locale, "/config")}
            tr={tr}
          />
        ) : (
          <div className="space-y-4">
            {requestsLoading ? (
              <div className="flex items-center gap-2 text-ink-light text-sm py-2">
                <Loader2 size={16} className="animate-spin" /> {tr("加载待处理请求...", "Loading pending requests...")}
              </div>
            ) : pendingRequests.length > 0 ? (
              <div className="p-3 rounded-sm border border-amber-200 bg-amber-50">
                <p className="text-sm font-medium text-amber-900 mb-2">{tr("待你处理的绑定请求", "Pending binding requests")}</p>
                <div className="space-y-2">
                  {pendingRequests.map((item) => (
                    <div key={item.id} className="flex items-center justify-between gap-3 text-sm">
                      <div>
                        <p className="font-medium text-amber-900">{item.requester_username}</p>
                        <p className="text-xs text-amber-800 font-mono">{item.mac}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button size="sm" variant="outline" onClick={() => handleRejectRequest(item.id)}>{tr("拒绝", "Reject")}</Button>
                        <Button size="sm" onClick={() => handleApproveRequest(item.id)}>{tr("同意", "Approve")}</Button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="p-3 rounded-sm border border-ink/10 bg-paper">
              <p className="text-sm font-medium text-ink mb-2 flex items-center gap-1">
                <Monitor size={14} /> {tr("配对设备", "Pair Device")}
              </p>
              <p className="text-xs text-ink-light mb-3">{tr("在设备配网页查看配对码，输入后即可认领或申请绑定设备。", "Find the pair code in the device portal page, then claim or request binding.")}</p>
              <div className="flex gap-2 flex-wrap items-center">
                <input
                  value={pairCodeInput}
                  onChange={(e) => setPairCodeInput(e.target.value.toUpperCase())}
                  placeholder={tr("配对码", "Pair Code")}
                  className="w-full sm:w-64 rounded-sm border border-ink/20 px-3 py-1.5 text-sm font-mono uppercase tracking-[0.2em]"
                />
                <Button size="sm" variant="outline" onClick={handlePairDevice} disabled={!pairCodeInput.trim() || pairingDevice}>
                  {pairingDevice ? <Loader2 size={14} className="animate-spin mr-1" /> : null}
                  {tr("立即配对", "Pair Now")}
                </Button>
              </div>
            </div>

            <div className="p-3 rounded-sm border border-ink/10 bg-paper">
              <p className="text-sm font-medium text-ink mb-2 flex items-center gap-1">
                <Plus size={14} /> {tr("按 MAC 手动绑定", "Bind by MAC")}
              </p>
              <p className="text-xs text-ink-light mb-3">{tr("请优先使用配对码配对。", "Pair code is recommended first.")}</p>
              <div className="flex gap-2 flex-wrap items-center">
                <input
                  value={bindMacInput}
                  onChange={(e) => setBindMacInput(e.target.value)}
                  placeholder={tr("MAC 地址 (如 AA:BB:CC:DD:EE:FF)", "MAC address (e.g. AA:BB:CC:DD:EE:FF)")}
                  className="w-full sm:w-[360px] rounded-sm border border-ink/20 px-3 py-1.5 text-sm font-mono"
                />
                <input
                  value={bindNicknameInput}
                  onChange={(e) => setBindNicknameInput(e.target.value)}
                  placeholder={tr("别名（可选）", "Nickname (optional)")}
                  className="w-32 rounded-sm border border-ink/20 px-3 py-1.5 text-sm"
                />
                <Button size="sm" variant="outline" onClick={async () => {
                  const targetMac = bindMacInput.trim();
                  if (!targetMac) return;
                  const result = await handleBindDevice(targetMac, bindNicknameInput.trim());
                  if (!result) return;
                  if (result.status === "claimed" || result.status === "active") {
                    showToast("设备已绑定", "success");
                    window.location.href = `${withLocalePath(locale, "/config")}?mac=${encodeURIComponent(targetMac)}`;
                    return;
                  }
                  if (result.status === "pending_approval") {
                    showToast("已提交绑定申请，等待 owner 同意", "info");
                  }
                }}>
                  {tr("绑定", "Bind")}
                </Button>
              </div>
            </div>

            {/* Device list */}
            {devicesLoading ? (
              <div className="flex items-center gap-2 text-ink-light text-sm py-4">
                <Loader2 size={16} className="animate-spin" /> {tr("加载设备列表...", "Loading devices...")}
              </div>
            ) : userDevices.length > 0 ? (
              <div className="space-y-2">
                {userDevices.map((d) => (
                  <div key={d.mac} className="flex items-center justify-between p-3 rounded-sm border border-ink/10 bg-paper hover:border-ink/30 transition-colors">
                    <div className="flex items-center gap-3">
                      <Monitor size={18} className="text-ink-light" />
                      <div>
                        <p className="text-sm font-medium text-ink">
                          {d.nickname || d.mac}
                        </p>
                        {d.nickname && (
                          <p className="text-xs text-ink-light font-mono">{d.mac}</p>
                        )}
                        <p className="text-xs text-ink-light">
                          {tr("权限", "Role")}: {d.role === "owner" ? "Owner" : "Member"}
                        </p>
                        <p className="text-xs text-ink-light">
                          {d.last_seen
                            ? `${tr("上次在线", "Last seen")}: ${new Date(d.last_seen).toLocaleString(isEn ? "en-US" : "zh-CN")}`
                            : tr("尚未上线", "Never online")}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Link href={`${withLocalePath(locale, "/config")}?mac=${encodeURIComponent(d.mac)}`}>
                        <Button size="sm" variant="outline">
                          <Settings size={14} className="mr-1" /> {tr("配置", "Configure")}
                        </Button>
                      </Link>
                      <button
                        onClick={() => handleUnbindDevice(d.mac)}
                        className="p-1.5 text-ink-light hover:text-red-600 transition-colors"
                        title={tr("解绑设备", "Unbind device")}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex items-start gap-2 p-3 rounded-sm border border-amber-200 bg-amber-50 text-sm text-amber-800">
                <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
                <div>
                  <p className="font-medium">{tr("未绑定设备", "No bound devices")}</p>
                  <p className="text-xs mt-0.5">{tr("当前账号下还没有设备。", "There are no devices under this account yet.")}</p>
                </div>
              </div>
            )}

          </div>
        )}
      </div>

      {mac && currentUser && !(macAccessDenied || denyByMembership) && loading && (
        <div className="flex items-center justify-center py-20 text-ink-light">
          <Loader2 size={24} className="animate-spin mr-2" /> {tr("加载配置中...", "Loading configuration...")}
        </div>
      )}

      {mac && currentUser && !(macAccessDenied || denyByMembership) && !loading && (
        <div className="space-y-4">
          {(currentUserRole === "owner" || pendingRequests.some((item) => item.mac === mac)) && (
            <div className="grid gap-4 md:grid-cols-2">
              {currentUserRole === "owner" && (
                <Card>
                  <CardHeader><CardTitle className="text-base">共享成员</CardTitle></CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex gap-2">
                      <input
                        value={shareUsernameInput}
                        onChange={(e) => setShareUsernameInput(e.target.value)}
                        placeholder="输入要共享的用户名"
                        className="flex-1 rounded-sm border border-ink/20 px-3 py-2 text-sm"
                      />
                      <Button variant="outline" size="sm" onClick={handleShareDevice} disabled={!shareUsernameInput.trim()}>
                        分享
                      </Button>
                    </div>
                    {membersLoading ? (
                      <div className="flex items-center gap-2 text-sm text-ink-light">
                        <Loader2 size={14} className="animate-spin" /> 加载成员中...
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {deviceMembers.map((member) => (
                          <div key={member.user_id} className="flex items-center justify-between rounded-sm border border-ink/10 p-2 text-sm">
                            <div>
                              <p className="font-medium text-ink">{member.username}</p>
                              <p className="text-xs text-ink-light">{member.role === "owner" ? "Owner" : "Member"}</p>
                            </div>
                            {member.role !== "owner" && (
                              <Button variant="outline" size="sm" onClick={() => handleRemoveMember(member.user_id)}>
                                移除
                              </Button>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}
              {pendingRequests.some((item) => item.mac === mac) && (
                <Card>
                  <CardHeader><CardTitle className="text-base">待处理绑定请求</CardTitle></CardHeader>
                  <CardContent className="space-y-2">
                    {pendingRequests.filter((item) => item.mac === mac).map((item) => (
                      <div key={item.id} className="flex items-center justify-between gap-2 rounded-sm border border-ink/10 p-2 text-sm">
                        <div>
                          <p className="font-medium text-ink">{item.requester_username}</p>
                          <p className="text-xs text-ink-light">请求绑定此设备</p>
                        </div>
                        <div className="flex items-center gap-2">
                          <Button variant="outline" size="sm" onClick={() => handleRejectRequest(item.id)}>拒绝</Button>
                          <Button size="sm" onClick={() => handleApproveRequest(item.id)}>同意</Button>
                        </div>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              )}
            </div>
          )}

          <div className="flex gap-6">
            {/* Sidebar tabs */}
            <nav className="w-44 flex-shrink-0 hidden md:block">
            <div className="sticky top-24 space-y-1">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-sm text-sm transition-colors ${
                    activeTab === tab.id
                      ? "bg-ink text-white font-medium"
                      : "text-ink-light hover:bg-paper-dark hover:text-ink"
                  }`}
                >
                  <tab.icon size={16} />
                  {tab.label}
                </button>
              ))}
              <div className="pt-4">
                <Button
                  variant="outline"
                  onClick={handleSave}
                  disabled={!mac || saving}
                  className="w-full bg-white text-ink border-ink/20 hover:bg-ink hover:text-white active:bg-ink active:text-white disabled:bg-white disabled:text-ink/50"
                >
                  {saving ? <Loader2 size={14} className="animate-spin mr-1" /> : <Save size={14} className="mr-1" />}
                  {tr("保存到设备", "Save to Device")}
                </Button>
              </div>
            </div>
          </nav>

            {/* Mobile tabs */}
            <div className="md:hidden w-full mb-4 overflow-x-auto">
            <div className="flex gap-1 min-w-max pb-2">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`px-3 py-2 rounded-sm text-xs whitespace-nowrap transition-colors ${
                    activeTab === tab.id ? "bg-ink text-white" : "bg-paper-dark text-ink-light"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
            {/* Modes Tab */}
            {activeTab === "modes" && (
              <div className="space-y-6">
                <ModeSelector
                  tr={tr}
                  selectedModes={selectedModes}
                  favoritedModes={favoritedModes}
                  customModes={customModes.map((cm) => cm.mode_id)}
                  customModeMeta={customModeMeta}
                  modeMeta={MODE_META}
                  coreModes={CORE_MODES}
                  extraModes={EXTRA_MODES}
                  modeTemplates={MODE_TEMPLATES}
                  previewMode={previewMode}
                  previewImg={previewImg}
                  previewLoading={previewLoading}
                  previewStatusText={previewStatusText}
                  previewCacheHit={previewCacheHit}
                  applyToScreenLoading={applyToScreenLoading}
                  handlePreview={handlePreview}
                  handleModePreview={handleModePreview}
                  handleModeApply={handleModeApply}
                  handleModeFavorite={handleModeFavorite}
                  setSettingsMode={setSettingsMode}
                  handleDeleteCustomMode={handleDeleteCustomMode}
                  editingCustomMode={editingCustomMode}
                  setEditingCustomMode={setEditingCustomMode}
                  editorTab={editorTab}
                  setEditorTab={setEditorTab}
                  customDesc={customDesc}
                  setCustomDesc={setCustomDesc}
                  customModeName={customModeName}
                  setCustomModeName={setCustomModeName}
                  customJson={customJson}
                  setCustomJson={setCustomJson}
                  customGenerating={customGenerating}
                  customPreviewImg={customPreviewImg}
                  customPreviewLoading={customPreviewLoading}
                  customApplyToScreenLoading={customApplyToScreenLoading}
                  handleGenerateMode={handleGenerateMode}
                  handleCustomPreview={handleCustomPreview}
                  handleApplyCustomPreviewToScreen={handleApplyCustomPreviewToScreen}
                  handleSaveCustomMode={handleSaveCustomMode}
                  handleApplyPreviewToScreen={handleApplyPreviewToScreen}
                  mac={mac}
                />

              </div>
            )}

            {/* Preferences Tab */}
            {activeTab === "preferences" && (
              <RefreshStrategyEditor
                tr={tr}
                city={city}
                setCity={setCity}
                language={language}
                setLanguage={setLanguage}
                contentTone={contentTone}
                setContentTone={setContentTone}
                characterTones={characterTones}
                setCharacterTones={setCharacterTones}
                customPersonaTone={customPersonaTone}
                setCustomPersonaTone={setCustomPersonaTone}
                handleAddCustomPersona={handleAddCustomPersona}
                strategy={strategy}
                setStrategy={setStrategy}
                refreshMin={refreshMin}
                setRefreshMin={setRefreshMin}
                languageOptions={LANGUAGE_OPTIONS}
                toneOptions={TONE_OPTIONS}
                personaPresets={PERSONA_PRESETS}
                strategies={STRATEGIES}
              />
            )}


            {/* Stats Tab */}
            {activeTab === "stats" && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <BarChart3 size={18} /> {tr("设备状态", "Device Status")}
                    {mac && <Button variant="ghost" size="sm" onClick={loadStats}><RefreshCw size={12} /></Button>}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {!mac && <p className="text-sm text-ink-light">{tr("需要连接设备后才能查看状态", "Connect a device to view status")}</p>}
                  {mac && !stats && <p className="text-sm text-ink-light">{tr("暂无统计数据", "No stats yet")}</p>}
                  {stats && (
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                      <StatCard label={tr("总渲染次数", "Total Renders")} value={stats.total_renders ?? "-"} />
                      <StatCard label={tr("缓存命中率", "Cache Hit Rate")} value={stats.cache_hit_rate != null ? `${Math.round(stats.cache_hit_rate * 100)}%` : "-"} />
                      <StatCard label={tr("电量", "Battery")} value={batteryPct != null ? `${batteryPct}%` : "-"} />
                      <StatCard label={tr("电压", "Voltage")} value={stats.last_battery_voltage ? `${stats.last_battery_voltage.toFixed(2)}V` : "-"} />
                      <StatCard label={tr("WiFi 信号", "WiFi RSSI")} value={stats.last_rssi ? `${stats.last_rssi} dBm` : "-"} />
                      <StatCard label={tr("错误次数", "Error Count")} value={stats.error_count ?? "-"} />
                      {stats.last_refresh && <StatCard label={tr("上次刷新", "Last Refresh")} value={new Date(stats.last_refresh).toLocaleString(isEn ? "en-US" : "zh-CN")} />}
                    </div>
                  )}
                  {stats?.mode_frequency && Object.keys(stats.mode_frequency).length > 0 && (
                    <div className="mt-6">
                      <h4 className="text-sm font-medium mb-3">{tr("模式使用频率", "Mode Frequency")}</h4>
                      <div className="space-y-2">
                        {Object.entries(stats.mode_frequency)
                          .sort(([, a], [, b]) => b - a)
                          .map(([mode, count]) => {
                            const max = Math.max(...Object.values(stats.mode_frequency!));
                            return (
                              <div key={mode} className="flex items-center gap-2 text-sm">
                                <span className="w-20 text-ink-light truncate">{MODE_META[mode]?.name || mode}</span>
                                <div className="flex-1 bg-paper-dark rounded-full h-4 overflow-hidden">
                                  <div className="bg-ink h-full rounded-full" style={{ width: `${(count / max) * 100}%` }} />
                                </div>
                                <span className="w-8 text-right text-ink-light text-xs">{count}</span>
                              </div>
                            );
                          })}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>

          {mac && currentUser && settingsMode && (
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
              <div className="absolute inset-0 bg-black/30" onClick={() => setSettingsMode(null)} />
              <Card className="relative z-10 w-full max-w-md">
                <CardHeader>
                  <CardTitle className="flex items-center justify-between text-base">
                    <span>
                      {tr("模式设置", "Mode Settings")}: {MODE_META[settingsMode]?.name || customModeMeta[settingsMode]?.name || settingsMode}
                    </span>
                    <button className="text-ink-light hover:text-ink" onClick={() => setSettingsMode(null)}>
                      <X size={16} />
                    </button>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <Field label="城市（可选）">
                    <input
                      value={getModeOverride(settingsMode).city || ""}
                      onChange={(e) => updateModeOverride(settingsMode, { city: e.target.value })}
                      placeholder={`留空使用全局默认：${city || "杭州"}`}
                      className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm"
                    />
                  </Field>
                  {activeModeSchema.map((item) => {
                    const key = `${settingsMode}:${item.key}`;
                    const override = getModeOverride(settingsMode);
                    const rawValue = override[item.key] ?? item.default;
                    const valueType = item.type || "text";
                    const options = (item.options || []).map((opt) => typeof opt === "string"
                      ? { value: opt, label: opt }
                      : { value: opt.value, label: opt.label });

                    if (settingsMode === "COUNTDOWN" && item.key === "countdownEvents") {
                      const events = Array.isArray(rawValue)
                        ? rawValue.map((ev) => ({
                            name: typeof ev?.name === "string" ? ev.name : "",
                            date: typeof ev?.date === "string" ? ev.date : "",
                            type: ev?.type === "countup" ? "countup" : "countdown",
                          }))
                        : [];
                      return (
                        <Field key={key} label="倒计时事件">
                          {events.map((ev, i) => (
                            <div key={`${key}:${i}`} className="flex gap-2 mb-2">
                              <input
                                value={ev.name}
                                onChange={(e) => {
                                  const next = [...events];
                                  next[i] = { ...next[i], name: e.target.value };
                                  updateModeOverride(settingsMode, { [item.key]: next });
                                }}
                                placeholder="事件名"
                                className="flex-1 rounded-sm border border-ink/20 px-3 py-1.5 text-sm"
                              />
                              <input
                                type="date"
                                value={ev.date}
                                onChange={(e) => {
                                  const next = [...events];
                                  next[i] = { ...next[i], date: e.target.value };
                                  updateModeOverride(settingsMode, { [item.key]: next });
                                }}
                                className="rounded-sm border border-ink/20 px-3 py-1.5 text-sm"
                              />
                              <select
                                value={ev.type}
                                onChange={(e) => {
                                  const next = [...events];
                                  next[i] = { ...next[i], type: e.target.value === "countup" ? "countup" : "countdown" };
                                  updateModeOverride(settingsMode, { [item.key]: next });
                                }}
                                className="rounded-sm border border-ink/20 px-2 py-1.5 text-sm bg-white"
                              >
                                <option value="countdown">倒计时</option>
                                <option value="countup">正计时</option>
                              </select>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => {
                                  const next = events.filter((_, j) => j !== i);
                                  updateModeOverride(settingsMode, { [item.key]: next });
                                }}
                              >
                                x
                              </Button>
                            </div>
                          ))}
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              const next = [...events, { name: "", date: "", type: "countdown" }];
                              updateModeOverride(settingsMode, { [item.key]: next });
                            }}
                          >
                            + 添加事件
                          </Button>
                        </Field>
                      );
                    }

                    if (item.as_json) {
                      const draft = settingsJsonDrafts[key] ?? (
                        rawValue === undefined ? "" : JSON.stringify(rawValue, null, 2)
                      );
                      return (
                        <Field key={key} label={item.label}>
                          <textarea
                            value={draft}
                            onChange={(e) => {
                              setSettingsJsonDrafts((prev) => ({ ...prev, [key]: e.target.value }));
                            }}
                            onBlur={() => {
                              const text = settingsJsonDrafts[key] ?? "";
                              if (!text.trim()) {
                                updateModeOverride(settingsMode, { [item.key]: undefined });
                                setSettingsJsonErrors((prev) => {
                                  const copied = { ...prev };
                                  delete copied[key];
                                  return copied;
                                });
                                return;
                              }
                              try {
                                const parsed = JSON.parse(text);
                                updateModeOverride(settingsMode, { [item.key]: parsed });
                                setSettingsJsonErrors((prev) => {
                                  const copied = { ...prev };
                                  delete copied[key];
                                  return copied;
                                });
                              } catch {
                                setSettingsJsonErrors((prev) => ({ ...prev, [key]: "JSON 格式错误" }));
                              }
                            }}
                            rows={4}
                            placeholder={item.placeholder}
                            className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm font-mono"
                          />
                          {settingsJsonErrors[key] ? (
                            <p className="mt-1 text-xs text-red-600">{settingsJsonErrors[key]}</p>
                          ) : null}
                        </Field>
                      );
                    }

                    if (valueType === "textarea") {
                      return (
                        <Field key={key} label={item.label}>
                          <textarea
                            ref={settingsMode === "MEMO" && item.key === "memo_text" ? memoSettingsInputRef : undefined}
                            value={typeof rawValue === "string" ? rawValue : ""}
                            onChange={(e) => {
                              const next = e.target.value;
                              updateModeOverride(settingsMode, { [item.key]: next });
                              if (settingsMode === "MEMO" && item.key === "memo_text") {
                                setMemoText(next);
                              }
                            }}
                            rows={3}
                            placeholder={item.placeholder}
                            className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm"
                          />
                        </Field>
                      );
                    }

                    if (valueType === "number") {
                      return (
                        <Field key={key} label={item.label}>
                          <input
                            type="number"
                            value={typeof rawValue === "number" ? rawValue : (item.default as number | undefined) ?? ""}
                            min={item.min}
                            max={item.max}
                            step={item.step}
                            onChange={(e) => {
                              const v = e.target.value;
                              if (!v) {
                                updateModeOverride(settingsMode, { [item.key]: undefined });
                                return;
                              }
                              updateModeOverride(settingsMode, { [item.key]: Number(v) });
                            }}
                            className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm"
                          />
                        </Field>
                      );
                    }

                    if (valueType === "boolean") {
                      const checked = Boolean(rawValue);
                      return (
                        <Field key={key} label={item.label}>
                          <label className="inline-flex items-center gap-2 text-sm text-ink">
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={(e) => updateModeOverride(settingsMode, { [item.key]: e.target.checked })}
                            />
                            启用
                          </label>
                        </Field>
                      );
                    }

                    if (valueType === "select" && options.length > 0) {
                      const current = typeof rawValue === "string" ? rawValue : options[0].value;
                      return (
                        <Field key={key} label={item.label}>
                          <select
                            value={current}
                            onChange={(e) => updateModeOverride(settingsMode, { [item.key]: e.target.value })}
                            className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
                          >
                            {options.map((opt) => (
                              <option key={opt.value} value={opt.value}>{opt.label}</option>
                            ))}
                          </select>
                        </Field>
                      );
                    }

                    return (
                      <Field key={key} label={item.label}>
                        <input
                          value={typeof rawValue === "string" ? rawValue : ""}
                          onChange={(e) => updateModeOverride(settingsMode, { [item.key]: e.target.value })}
                          placeholder={item.placeholder}
                          className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm"
                        />
                      </Field>
                    );
                  })}
                  <div className="flex items-center justify-between">
                    <Button variant="outline" size="sm" onClick={() => clearModeOverride(settingsMode)}>
                      恢复默认
                    </Button>
                    <div className="flex items-center gap-2">
                      <Button variant="outline" size="sm" onClick={() => handlePreviewFromSettings(false)}>
                        预览
                      </Button>
                      <Button
                        variant={settingsMode && selectedModes.has(settingsMode) ? "default" : "outline"}
                        size="sm"
                        className={
                          settingsMode && selectedModes.has(settingsMode)
                            ? "bg-ink text-white border-ink hover:bg-ink hover:text-white"
                            : "bg-white text-ink border-ink/20 hover:bg-ink hover:text-white active:bg-ink active:text-white"
                        }
                        onClick={() => handlePreviewFromSettings(true)}
                      >
                        预览并加入轮播
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
          </div>
        </div>
      )}

      {/* Mobile save button */}
      {mac && (
        <div className="md:hidden fixed bottom-0 left-0 right-0 p-4 bg-white border-t border-ink/10">
          <Button
            variant="outline"
            onClick={handleSave}
            disabled={!mac || saving}
            className="w-full bg-white text-ink border-ink/20 hover:bg-ink hover:text-white active:bg-ink active:text-white disabled:bg-white disabled:text-ink/50"
          >
            {saving ? <Loader2 size={14} className="animate-spin mr-1" /> : <Save size={14} className="mr-1" />}
            保存到设备
          </Button>
        </div>
      )}

      {/* 邀请码输入弹窗 */}
      {showInviteModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <Card className="w-full max-w-md mx-4">
            <CardHeader>
              <CardTitle>{isEn ? "Enter Invitation Code" : "请输入邀请码"}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-ink-light">
                {isEn
                  ? "Your free quota has been exhausted. You can either enter an invitation code to get 10 more free LLM calls, or configure your own API key in your profile settings."
                  : "您的免费额度已用完。您可以输入邀请码获得50次免费LLM调用额度，也可以在个人信息中设置自己的 API key。"}
              </p>
              <div className="p-3 rounded-sm border border-ink/20 bg-paper-dark">
                <p className="text-xs text-ink-light mb-2">
                  {isEn
                    ? "💡 Tip: If you have your own API key, you can configure it in your profile to avoid quota limits."
                    : "💡 提示：如果您有自己的 API key，可以在个人信息中配置，这样就不会受到额度限制了。"}
                </p>
                <Link href={withLocalePath(locale, "/profile")}>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setShowInviteModal(false);
                    }}
                    className="w-full text-xs"
                  >
                    {isEn ? "Go to Profile Settings" : "前往个人信息配置"}
                  </Button>
                </Link>
              </div>
              <div>
                <label className="block text-sm font-medium text-ink mb-1">
                  {isEn ? "Invitation Code" : "邀请码"}
                </label>
                <input
                  type="text"
                  value={inviteCode}
                  onChange={(e) => setInviteCode(e.target.value)}
                  placeholder={isEn ? "Enter invitation code" : "请输入邀请码"}
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
                  {isEn ? "Cancel" : "取消"}
                </Button>
                <Button onClick={handleRedeemInviteCode} disabled={redeemingInvite || !inviteCode.trim()}>
                  {redeemingInvite ? (
                    <>
                      <Loader2 size={16} className="animate-spin mr-2" />
                      {isEn ? "Redeeming..." : "兑换中..."}
                    </>
                  ) : (
                    isEn ? "Redeem" : "兑换"
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      ) : null}

      {/* Toast */}
      {toast && (
        <div className={`fixed top-5 right-5 z-50 px-4 py-3 rounded-sm text-sm font-medium shadow-lg animate-fade-in ${
          toast.type === "success" ? "bg-green-50 text-green-800 border border-green-200"
          : toast.type === "error" ? "bg-red-50 text-red-800 border border-red-200"
          : "bg-amber-50 text-amber-800 border border-amber-200"
        }`}>
          {toast.msg}
        </div>
      )}
    </div>
  );
}

export default function ConfigPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center min-h-screen text-ink-light"><Loader2 size={24} className="animate-spin mr-2" /> 加载中...</div>}>
      <ConfigPageInner />
    </Suspense>
  );
}
