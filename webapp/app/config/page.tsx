"use client";

import { useEffect, useState, useCallback, Suspense, useMemo, useRef } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import Link from "next/link";
import { DeviceInfo } from "@/components/config/device-info";
import { LocationPicker } from "@/components/config/location-picker";
import { ModeSelector } from "@/components/config/mode-selector";
import { EInkPreviewPanel } from "@/components/config/eink-preview-panel";
import { CalendarReminders } from "@/components/config/calendar-reminders";
import { TimetableEditor, type TimetableData } from "@/components/config/timetable-editor";
import { RefreshStrategyEditor } from "@/components/config/refresh-strategy-editor";
import { Field, StatCard } from "@/components/config/shared";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
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
  Users,
} from "lucide-react";
import { authHeaders, fetchCurrentUser, onAuthChanged } from "@/lib/auth";
import { localeFromPathname, withLocalePath } from "@/lib/i18n";
import {
  buildLocationValue,
  cleanLocationValue,
  describeLocation,
  extractLocationValue,
  locationsEqual,
  type LocationValue,
} from "@/lib/locations";

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

type ModeCatalogItem = {
  mode_id: string;
  category: "core" | "more" | "custom" | string;
  source?: string;
  display_name?: string;
  description?: string;
  settings_schema?: ModeSettingSchemaItem[];
  i18n?: {
    zh?: { name?: string; tip?: string };
    en?: { name?: string; tip?: string };
  };
};

const STRATEGIES: Record<string, string> = {
  random: "从已启用的模式中随机选取",
  cycle: "按顺序循环切换已启用的模式",
  time_slot: "根据时间段显示不同内容模式",
  smart: "根据时间段自动匹配最佳模式",
};

const MODE_LANGUAGE_OPTIONS = [
  { value: "zh", label: "中文", labelEn: "Chinese" },
  { value: "en", label: "English", labelEn: "English" },
] as const;

const TONE_OPTIONS = [
  { value: "positive", label: "积极鼓励" },
  { value: "neutral", label: "中性克制" },
  { value: "deep", label: "深沉内省" },
  { value: "humor", label: "轻松幽默" },
] as const;
const PERSONA_PRESETS = ["鲁迅", "王小波", "JARVIS", "苏格拉底", "村上春树"] as const;

type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

export async function queueImmediateRefreshIfOnline(
  fetchImpl: FetchLike,
  mac: string,
  headers: Record<string, string>,
): Promise<{ onlineNow: boolean | null; lastSeen: string | null; refreshQueued: boolean }> {
  try {
    const stateRes = await fetchImpl(`/api/device/${encodeURIComponent(mac)}/state`, {
      cache: "no-store",
      headers,
    });
    if (!stateRes.ok) {
      return { onlineNow: null, lastSeen: null, refreshQueued: false };
    }
    const stateData = await stateRes.json();
    const onlineNow = Boolean(stateData?.is_online);
    const lastSeen = typeof stateData?.last_seen === "string" && stateData.last_seen ? stateData.last_seen : null;
    if (!onlineNow) {
      return { onlineNow, lastSeen, refreshQueued: false };
    }
    const refreshRes = await fetchImpl(`/api/device/${encodeURIComponent(mac)}/refresh`, {
      method: "POST",
      headers,
    });
    return { onlineNow, lastSeen, refreshQueued: refreshRes.ok };
  } catch {
    return { onlineNow: null, lastSeen: null, refreshQueued: false };
  }
}

function normalizeTone(v: unknown): string {
  if (typeof v !== "string") return "neutral";
  if (v === "positive" || v === "neutral" || v === "deep" || v === "humor") return v;
  const found = TONE_OPTIONS.find((x) => x.label === v);
  return found?.value || "neutral";
}

// Custom mode templates removed (AI-only creation)


const TABS = [
  { id: "modes", label: "模式", icon: Settings },
  { id: "preferences", label: "个性化", icon: Sliders },
  { id: "sharing", label: "共享成员", icon: Users },
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
  latitude?: number;
  longitude?: number;
  timezone?: string;
  admin1?: string;
  country?: string;
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
  mode_overrides?: Record<string, ModeOverride>;
  modeOverrides?: Record<string, ModeOverride>;
  is_focus_listening?: boolean;
  focus_listening?: number;
}

interface ModeOverride {
  city?: string;
  latitude?: number;
  longitude?: number;
  timezone?: string;
  admin1?: string;
  country?: string;
  llm_provider?: string;
  llm_model?: string;
  [key: string]: unknown;
}

interface PendingPreviewConfirm {
  mode: string;
  forceNoCache: boolean;
  forcedModeOverride?: ModeOverride;
  usageSource?: string;
}

type ParamModalType = "quote" | "weather" | "memo" | "countdown" | "habit" | "lifebar" | "calendar" | "timetable";
interface ParamModalState {
  type: ParamModalType;
  mode: string;
  action: "preview" | "apply";
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
  const tr = useCallback((zh: string, en: string) => (isEn ? en : zh), [isEn]);
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
  const [locationMeta, setLocationMeta] = useState<LocationValue>({});
  const [modeLanguage, setModeLanguage] = useState("zh");
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
  const [previewColors, setPreviewColors] = useState(2);
  const [previewNoCacheOnce, setPreviewNoCacheOnce] = useState(false);
  const [previewCacheHit, setPreviewCacheHit] = useState<boolean | null>(null);
  const [previewLlmStatus, setPreviewLlmStatus] = useState<string | null>(null);
  const [previewConfirm, setPreviewConfirm] = useState<PendingPreviewConfirm | null>(null);

  // 自适应图片（MY_ADAPTIVE）本地选图 + 上传（与 /preview 页面一致）
  const adaptiveFileInputRef = useRef<HTMLInputElement | null>(null);
  const [pendingAdaptiveAction, setPendingAdaptiveAction] = useState<null | { action: "preview" | "apply"; mode: string }>(null);
  const [, setAdaptiveUploading] = useState(false);

  // 参数弹窗（与 /preview 页面保持一致）
  const [paramModal, setParamModal] = useState<ParamModalState | null>(null);
  const [quoteDraft, setQuoteDraft] = useState("");
  const [authorDraft, setAuthorDraft] = useState("");
  const [weatherDraftLocation, setWeatherDraftLocation] = useState<LocationValue>({});
  const [memoDraft, setMemoDraft] = useState("");
  const [countdownName, setCountdownName] = useState(isEn ? "New Year" : "元旦");
  const [countdownDate, setCountdownDate] = useState("2027-01-01");
  const [habitItems, setHabitItems] = useState(
    isEn
      ? [{ name: "Wake up early", done: false }, { name: "Exercise", done: false }, { name: "Read", done: false }]
      : [{ name: "早起", done: false }, { name: "运动", done: false }, { name: "阅读", done: false }],
  );
  const [userAge, setUserAge] = useState(30);
  const [lifeExpectancy, setLifeExpectancy] = useState<100 | 120>(100);
  const [timetableData, setTimetableData] = useState<TimetableData>({
    style: "weekly",
    periods: ["08:00-09:30", "10:00-11:30", "14:00-15:30", "16:00-17:30"],
    courses: isEn
      ? {
          "0-0": "Calculus/A201", "0-2": "Linear Algebra/A201",
          "1-1": "English/B305", "1-3": "PE/Gym",
          "2-0": "Data Struct/C102", "2-2": "Networks/C102",
          "3-1": "Probability/A201", "3-3": "Politics/D405",
          "4-0": "OS/C102",
        }
      : {
          "0-0": "高等数学/A201", "0-2": "线性代数/A201",
          "1-1": "大学英语/B305", "1-3": "体育/操场",
          "2-0": "数据结构/C102", "2-2": "计算机网络/C102",
          "3-1": "概率论/A201", "3-3": "毛概/D405",
          "4-0": "操作系统/C102",
        },
  });
  // 邀请码弹窗状态
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteCode, setInviteCode] = useState("");
  const [redeemingInvite, setRedeemingInvite] = useState(false);
  const [pendingPreviewMode, setPendingPreviewMode] = useState<string | null>(null);
  const [, setCurrentMode] = useState<string>("");
  const [applyToScreenLoading, setApplyToScreenLoading] = useState(false);
  const [, setFavoritedModes] = useState<Set<string>>(new Set());
  const favoritesLoadedMacRef = useRef<string>("");
  const memoSettingsInputRef = useRef<HTMLTextAreaElement | null>(null);
  const previewStreamRef = useRef<EventSource | null>(null);
  const previewObjectUrlRef = useRef<string | null>(null);
  const [runtimeMode, setRuntimeMode] = useState<RuntimeMode>("unknown");
  const [isOnline, setIsOnline] = useState(false);
  const [lastSeen, setLastSeen] = useState<string | null>(null);
  const [isFocusListening, setIsFocusListening] = useState(false);
  const [focusToggleLoading, setFocusToggleLoading] = useState(false);
  const [focusAlertToken, setFocusAlertToken] = useState<string>("");
  const [showFocusTokenModal, setShowFocusTokenModal] = useState(false);

  const [customDesc, setCustomDesc] = useState("");
  const [customModeName, setCustomModeName] = useState("");
  const [customJson, setCustomJson] = useState("");
  const [customGenerating, setCustomGenerating] = useState(false);
  const [customPreviewImg, setCustomPreviewImg] = useState<string | null>(null);
  const [, setCustomPreviewLoading] = useState(false);
  const [editingCustomMode, setEditingCustomMode] = useState(false);
  const [customEditorSource, setCustomEditorSource] = useState<"ai" | "manual" | null>(null);
  const [previewModeLabelOverride, setPreviewModeLabelOverride] = useState<string | null>(null);
  const previewPanelRef = useRef<HTMLDivElement | null>(null);

  const [catalogItems, setCatalogItems] = useState<ModeCatalogItem[]>([]);

  const showToast = useCallback((msg: string, type: "success" | "error" | "info" = "info") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  }, []);

  const currentLocation = useMemo(
    () => buildLocationValue(city, locationMeta),
    [city, locationMeta],
  );
  const defaultWeatherLocation = useMemo(
    () => (currentLocation.city ? cleanLocationValue(currentLocation) : buildLocationValue("杭州")),
    [currentLocation],
  );

  const applyGlobalLocation = useCallback((next: Partial<LocationValue> | null | undefined) => {
    const cleaned = cleanLocationValue(next);
    setCity(cleaned.city || "");
    setLocationMeta(cleaned);
  }, []);

  const replacePreviewImg = useCallback((nextUrl: string | null) => {
    if (previewObjectUrlRef.current) {
      URL.revokeObjectURL(previewObjectUrlRef.current);
      previewObjectUrlRef.current = null;
    }
    if (nextUrl) previewObjectUrlRef.current = nextUrl;
    setPreviewImg(nextUrl);
  }, []);

  const uploadLocalImage = useCallback(async (file: File): Promise<string> => {
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
  }, []);

  useEffect(() => {
    return () => {
      if (previewObjectUrlRef.current) {
        URL.revokeObjectURL(previewObjectUrlRef.current);
        previewObjectUrlRef.current = null;
      }
    };
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

  const refreshCatalog = useCallback(async () => {
    const params = new URLSearchParams();
    if (mac) params.append("mac", mac);
    try {
      const res = await fetch(`/api/modes/catalog?${params.toString()}`, { headers: authHeaders() });
      if (!res.ok) {
        console.error("[CONFIG] Catalog request failed:", res.status, res.statusText);
        return;
      }
      const data = await res.json().catch((err) => {
        console.error("[CONFIG] Failed to parse catalog JSON:", err);
        return {};
      });
      if (data.items && Array.isArray(data.items)) {
        setCatalogItems(data.items);
      } else {
        console.error("[CONFIG] Invalid catalog response:", data);
      }
    } catch (err) {
      console.error("[CONFIG] Failed to load catalog:", err);
    }
  }, [mac]);

  useEffect(() => {
    refreshCatalog();
  }, [refreshCatalog]);

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
        applyGlobalLocation(extractLocationValue(cfg as Record<string, unknown>));
        setModeLanguage((cfg as Record<string, unknown>).modeLanguage as string || (cfg as Record<string, unknown>).mode_language as string || "zh");
        if (cfg.contentTone || cfg.content_tone) setContentTone(normalizeTone(cfg.contentTone || cfg.content_tone));
        if (cfg.characterTones || cfg.character_tones) setCharacterTones((cfg.characterTones || cfg.character_tones) as string[]);
        if (cfg.mode_overrides) setModeOverrides(cfg.mode_overrides);
        else if (cfg.modeOverrides) setModeOverrides(cfg.modeOverrides);
        setIsFocusListening(Boolean(cfg.is_focus_listening ?? Number(cfg.focus_listening || 0) === 1));
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
  }, [applyGlobalLocation, mac]);

  const getModeOverride = useCallback((modeId: string) => {
    return modeOverrides[modeId] || {};
  }, [modeOverrides]);

  const sanitizeModeOverride = useCallback((input: ModeOverride) => {
    const cleaned: ModeOverride = {};
    for (const [k, raw] of Object.entries(input)) {
      if (
        k === "city" ||
        k === "timezone" ||
        k === "admin1" ||
        k === "country" ||
        k === "llm_provider" ||
        k === "llm_model"
      ) {
        if (typeof raw === "string" && raw.trim()) cleaned[k] = raw.trim();
        continue;
      }
      if (k === "latitude" || k === "longitude") {
        if (typeof raw === "number" && Number.isFinite(raw)) cleaned[k] = raw;
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

  const requiresParamModal = useCallback((modeId: string) => {
    const m = (modeId || "").toUpperCase();
    return m === "WEATHER" || m === "MEMO" || m === "MY_QUOTE" || m === "COUNTDOWN" || m === "HABIT" || m === "LIFEBAR" || m === "CALENDAR" || m === "TIMETABLE";
  }, []);

  const openParamModal = useCallback((modeId: string, action: "preview" | "apply") => {
    const m = (modeId || "").toUpperCase();
    if (m === "WEATHER") {
      setWeatherDraftLocation({});
      setParamModal({ type: "weather", mode: m, action });
      return;
    }
    if (m === "MEMO") {
      const existing = (modeOverrides[m]?.memo_text as string) || memoText || "";
      setMemoDraft(existing);
      setParamModal({ type: "memo", mode: m, action });
      return;
    }
    if (m === "MY_QUOTE") {
      setQuoteDraft("");
      setAuthorDraft("");
      setParamModal({ type: "quote", mode: m, action });
      return;
    }
    if (m === "COUNTDOWN") {
      setParamModal({ type: "countdown", mode: m, action });
      return;
    }
    if (m === "HABIT") {
      const savedOv = modeOverrides["HABIT"] || {};
      const savedItems = Array.isArray(savedOv.habitItems) ? (savedOv.habitItems as Array<{ name: string; done?: boolean }>) : null;
      if (savedItems && savedItems.length > 0) {
        setHabitItems(savedItems.map((h) => ({ name: h.name, done: h.done ?? false })));
      }
      setParamModal({ type: "habit", mode: m, action });
      return;
    }
    if (m === "LIFEBAR") {
      setParamModal({ type: "lifebar", mode: m, action });
      return;
    }
    if (m === "CALENDAR") {
      setParamModal({ type: "calendar", mode: m, action });
      return;
    }
    if (m === "TIMETABLE") {
      const existing = (modeOverrides[m] || {}) as Record<string, unknown>;
      if (existing.periods && existing.courses) {
        setTimetableData({
          style: (existing.style as "daily" | "weekly") || "daily",
          periods: existing.periods as string[],
          courses: existing.courses as Record<string, string>,
        });
      }
      setParamModal({ type: "timetable", mode: m, action });
      return;
    }
  }, [memoText, modeOverrides]);

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
    () => Object.fromEntries(catalogItems.map((m) => [m.mode_id.toUpperCase(), m.settings_schema || []])),
    [catalogItems]
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
        ...currentLocation,
        modeLanguage,
        contentTone,
        characterTones: characterTones,
        modeOverrides: normalizedModeOverrides,
        memoText: memoText,
        is_focus_listening: isFocusListening,
      };
      const res = await fetch("/api/config", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error("Save failed");
      let onlineNow = isOnline;
      let refreshQueued = false;
      let latestLastSeen: string | null = lastSeen;
      const syncResult = await queueImmediateRefreshIfOnline(fetch, mac, authHeaders());
      onlineNow = syncResult.onlineNow ?? isOnline;
      refreshQueued = syncResult.refreshQueued;
      latestLastSeen = syncResult.lastSeen;
      if (syncResult.onlineNow !== null) {
        setIsOnline(syncResult.onlineNow);
      }
      setLastSeen(latestLastSeen);
      showToast(
        syncResult.onlineNow === null
          ? "配置已保存，暂时无法确认设备状态"
          : onlineNow
            ? (refreshQueued ? "配置已保存，已通知设备立即刷新" : "配置已保存，设备在线，但立即刷新通知失败")
            : "配置已保存，设备当前离线，将在设备上线后生效",
        syncResult.onlineNow === null || !refreshQueued ? "info" : "success",
      );
      setPreviewNoCacheOnce(true);
    } catch {
      showToast("保存失败", "error");
    } finally {
      setSaving(false);
    }
  };

  const [savingPrefs, setSavingPrefs] = useState(false);
  const handleSavePreferences = async () => {
    if (!mac) { showToast(tr("请先完成刷机和配网以获取设备 MAC", "Please flash and provision to get device MAC"), "error"); return; }
    if (macAccessDenied) { showToast(tr("你无权配置该设备", "No permission"), "error"); return; }
    setSavingPrefs(true);
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
        ...currentLocation,
        modeLanguage,
        contentTone,
        characterTones: characterTones,
        modeOverrides: normalizedModeOverrides,
        memoText: memoText,
        is_focus_listening: isFocusListening,
      };
      const res = await fetch("/api/config", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error("Save failed");
      showToast(tr("配置已保存", "Settings saved"), "success");
      setPreviewNoCacheOnce(true);
    } catch {
      showToast(tr("保存失败", "Save failed"), "error");
    } finally {
      setSavingPrefs(false);
    }
  };

  const handleToggleFocusListening = useCallback(async () => {
    if (!mac) return;
    const next = !isFocusListening;
    setFocusToggleLoading(true);
    try {
      const res = await fetch(
        `/api/config/${encodeURIComponent(mac)}/focus-listening?enabled=${next}`,
        { method: "PATCH", headers: authHeaders() },
      );
      if (!res.ok) {
        const errorText = await res.text().catch(() => "");
        console.error("[FOCUS] Toggle failed:", res.status, errorText);
        throw new Error("focus-toggle-failed");
      }
      const data = (await res.json().catch(() => ({}))) as { alert_token?: string | null };
      setIsFocusListening(next);
      if (next && data?.alert_token) {
        setFocusAlertToken(data.alert_token);
        setShowFocusTokenModal(true);
      }
      showToast(
        next ? "Focus 专注模式就绪，OpenCLAW 守护中" : "专注监听已关闭，设备将按原计划轮播内容",
        "success",
      );
    } catch (err) {
      console.error("[FOCUS] Toggle error:", err);
      showToast("切换专注监听失败，请稍后重试", "error");
    } finally {
      setFocusToggleLoading(false);
    }
  }, [isFocusListening, mac, showToast]);

  const buildPreviewParams = useCallback((mode?: string, forceNoCache = false, forcedModeOverride?: ModeOverride) => {
    const m = mode || previewMode;
    const consumeNoCacheOnce = previewNoCacheOnce;
    const forceFresh = forceNoCache || consumeNoCacheOnce;
    const params = new URLSearchParams({ persona: m });
    if (mac) params.set("mac", mac);
    const modeOverrideSource = sanitizeModeOverride({
      ...(modeOverrides[m] || {}),
      ...(forcedModeOverride || {}),
    });
    const savedOverrides = (config.mode_overrides || config.modeOverrides || {}) as Record<string, ModeOverride>;
    const effectiveLocation = cleanLocationValue(
      modeOverrideSource.city
        ? extractLocationValue(modeOverrideSource as Record<string, unknown>)
        : currentLocation,
    );
    const savedEffectiveLocation = cleanLocationValue(
      savedOverrides[m]?.city
        ? extractLocationValue(savedOverrides[m] as Record<string, unknown>)
        : extractLocationValue(config as Record<string, unknown>),
    );
    const locationChanged = Boolean(effectiveLocation.city) && !locationsEqual(effectiveLocation, savedEffectiveLocation);

    const activeModeOverride = sanitizeModeOverride({
      ...modeOverrideSource,
      ...(locationChanged ? effectiveLocation : {}),
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
    if (locationChanged && effectiveLocation.city) params.set("city_override", effectiveLocation.city);
    if (previewColors > 2) params.set("colors", String(previewColors));
    if (forceFresh || locationChanged || hasModeOverride) params.set("no_cache", "1");
    return { m, params, consumeNoCacheOnce };
  }, [config, currentLocation, mac, memoText, modeOverrides, previewColors, previewMode, previewNoCacheOnce, sanitizeModeOverride]);

  const ownerUsername = useMemo(
    () => deviceMembers.find((member) => member.role === "owner")?.username || "",
    [deviceMembers],
  );

  const formatPreviewUsageText = useCallback((usageSource?: string) => {
    switch (usageSource) {
      case "current_user_api_key":
        return tr("当前使用你的 API key", "Using your API key");
      case "owner_api_key":
        return ownerUsername
          ? tr(`当前使用 owner（${ownerUsername}）的 API key`, `Using ${ownerUsername}'s API key`)
          : tr("当前使用 owner 的 API key", "Using owner's API key");
      case "owner_free_quota":
        return ownerUsername
          ? tr(`当前消耗 owner（${ownerUsername}）的免费额度`, `Using ${ownerUsername}'s free quota`)
          : tr("当前消耗 owner 的免费额度", "Using owner's free quota");
      case "current_user_free_quota":
        return tr("当前消耗你的免费额度", "Using your free quota");
      default:
        return "";
    }
  }, [ownerUsername, tr]);

  const handlePreview = useCallback(async (mode?: string, forceNoCache = false, forcedModeOverride?: ModeOverride, confirmed = false) => {
    const { m, params, consumeNoCacheOnce } = buildPreviewParams(mode, forceNoCache, forcedModeOverride);
    if (!m) return;

    if (mac && !confirmed) {
      try {
        const intentParams = new URLSearchParams(params);
        intentParams.set("intent", "1");
        const intentRes = await fetch(`/api/preview?${intentParams.toString()}`, {
          cache: "no-store",
          headers: authHeaders(),
        });
        if (intentRes.ok) {
          const intentData = (await intentRes.json()) as {
            cache_hit?: boolean;
            usage_source?: string;
            requires_invite_code?: boolean;
            llm_mode_requires_quota?: boolean;
          };
          if (intentData.requires_invite_code) {
            setPreviewConfirm(null);
            setShowInviteModal(true);
            setPendingPreviewMode(m);
            setPreviewStatusText(formatPreviewUsageText(intentData.usage_source));
            return;
          }
          if (!intentData.cache_hit && intentData.llm_mode_requires_quota) {
            setPreviewConfirm({
              mode: m,
              forceNoCache,
              forcedModeOverride,
              usageSource: intentData.usage_source,
            });
            return;
          }
        }
      } catch {}
    }

    setPreviewConfirm(null);
    setPreviewCacheHit(null);
    setPreviewLlmStatus(null);
    setPreviewLoading(true);
    setPreviewStatusText(tr("正在生成...", "Generating..."));
    try {
      previewStreamRef.current?.close();
      const stream = new EventSource(`/api/preview/stream?${params.toString()}`);
      previewStreamRef.current = stream;

      await new Promise<void>((resolve, reject) => {
        let settled = false;
        stream.addEventListener("status", (event) => {
          try {
            const data = JSON.parse((event as MessageEvent<string>).data) as { message?: string };
            setPreviewStatusText(data.message || tr("正在生成...", "Generating..."));
          } catch {
            setPreviewStatusText(tr("正在生成...", "Generating..."));
          }
        });

        stream.addEventListener("error", (event) => {
          if (settled) return;
          try {
            const data = JSON.parse((event as MessageEvent<string>).data) as {
              error?: string;
              message?: string;
              requires_invite_code?: boolean;
              usage_source?: string;
            };
            if (data.requires_invite_code) {
              settled = true;
              stream.close();
              previewStreamRef.current = null;
              setPreviewConfirm(null);
              setShowInviteModal(true);
              setPendingPreviewMode(m);
              setPreviewStatusText(formatPreviewUsageText(data.usage_source));
              setPreviewLoading(false);
              resolve();
              return;
            }
            settled = true;
            stream.close();
            previewStreamRef.current = null;
            setPreviewLoading(false);
            reject(new Error(data.message || "Preview failed"));
          } catch {
            settled = true;
            stream.close();
            previewStreamRef.current = null;
            setPreviewLoading(false);
            reject(new Error("Preview failed"));
          }
        });

        stream.addEventListener("result", async (event) => {
          try {
            const data = JSON.parse((event as MessageEvent<string>).data) as {
              message?: string;
              image_url?: string;
              cache_hit?: boolean;
              preview_status?: string;
              llm_required?: boolean;
              usage_source?: string;
            };
            console.log("[PREVIEW] Result event received:", { hasImageUrl: !!data.image_url, message: data.message });
            if (!data.image_url) {
              settled = true;
              console.error("[PREVIEW] Missing image_url in result event");
              setPreviewLoading(false);
              reject(new Error("Preview image missing"));
              return;
            }
            settled = true;
            const imageResponse = await fetch(data.image_url, { cache: "no-store" });
            if (!imageResponse.ok) {
              setPreviewLoading(false);
              reject(new Error("Preview image unavailable"));
              return;
            }
            const imageBlob = await imageResponse.blob();
            const objectUrl = URL.createObjectURL(imageBlob);
            console.log("[PREVIEW] Setting preview image:", data.image_url.substring(0, 50) + "...");
            replacePreviewImg(objectUrl);
            setPreviewCacheHit(typeof data.cache_hit === "boolean" ? data.cache_hit : null);
            setPreviewStatusText(data.message || tr("完成", "Done"));
            const status = (data.preview_status || "").toLowerCase();
            const llmRequired = data.llm_required;
            if (status === "no_llm_required" || llmRequired === false) {
              setPreviewLlmStatus(null);
            } else if (status === "model_generated") {
              setPreviewLlmStatus(isEn ? "Model call succeeded" : "大模型调用成功");
            } else if (status === "fallback_used") {
              setPreviewLlmStatus(isEn ? "Model call failed, using fallback content" : "大模型调用失败，使用默认内容");
            } else {
              setPreviewLlmStatus(null);
            }
            setPreviewLoading(false); // 重置加载状态
            stream.close();
            previewStreamRef.current = null;
            resolve();
          } catch (error) {
            console.error("[PREVIEW] Error processing result event:", error);
            setPreviewLoading(false);
            reject(error);
          }
        });

        stream.onerror = () => {
          if (settled) return;
          settled = true;
          stream.close();
          previewStreamRef.current = null;
          setPreviewLoading(false);
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
  }, [buildPreviewParams, formatPreviewUsageText, isEn, mac, replacePreviewImg, showToast, tr]);

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
      setCustomEditorSource("ai");
      showToast("模式生成成功", "success");

      // Close modal right after generation, then start preview on the right panel
      const finalName = (customModeName || data.mode_def?.display_name || "").toString().trim();
      setPreviewModeLabelOverride(finalName || null);
      setEditingCustomMode(false);
      requestAnimationFrame(() => {
        previewPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      });

      // show "previewing" on the right panel while preview is being built
      setPreviewLoading(true);
      setPreviewStatusText(isEn ? "Generating preview..." : "模式预览中...");

      await handleCustomPreview(data.mode_def);
    } catch (e) {
      showToast(`生成失败: ${e instanceof Error ? e.message : "未知错误"}`, "error");
    } finally {
      setCustomGenerating(false);
    }
  };

  const handleCustomPreview = async (defOverride?: unknown) => {
    if (!defOverride && !customJson.trim()) return;
    setCustomPreviewLoading(true);
    setPreviewLoading(true);
    if (!previewStatusText) setPreviewStatusText(isEn ? "Generating preview..." : "模式预览中...");
    try {
      const def = defOverride ? (defOverride as Record<string, unknown>) : (JSON.parse(customJson) as Record<string, unknown>);
      if (customModeName.trim()) {
        (def as Record<string, unknown>).display_name = customModeName.trim();
      }
      let modeHint = "CUSTOM_PREVIEW";
      try {
        if (customModeName.trim()) {
          modeHint = customModeName.trim().toUpperCase().replace(/[^A-Z0-9_]/g, "_");
        } else {
          const modeIdRaw = (def as Record<string, unknown>)["mode_id"];
          if (typeof modeIdRaw === "string" && modeIdRaw.trim()) {
            modeHint = modeIdRaw.trim().toUpperCase();
          }
        }
      } catch {}
      const res = await fetch("/api/modes/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode_def: def, mac: mac || undefined, colors: previewColors }),
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
      const objectUrl = URL.createObjectURL(blob);
      if (customPreviewImg) {
        try { URL.revokeObjectURL(customPreviewImg); } catch {}
      }
      setCustomPreviewImg(objectUrl);

      // show custom-mode preview in the right E-Ink panel
      setPreviewMode(modeHint);
      setPreviewCacheHit(null);
      const status = (res.headers.get("x-preview-status") || "").toLowerCase();
      const llmRequiredHeader = (res.headers.get("x-llm-required") || "").toLowerCase();
      if (status === "no_llm_required" || llmRequiredHeader === "0" || llmRequiredHeader === "false") {
        setPreviewLlmStatus(null);
      } else if (status === "model_generated") {
        setPreviewLlmStatus(isEn ? "Model call succeeded" : "大模型调用成功");
      } else if (status === "fallback_used") {
        setPreviewLlmStatus(isEn ? "Model call failed, using fallback content" : "大模型调用失败，使用默认内容");
      } else {
        setPreviewLlmStatus(null);
      }
      replacePreviewImg(objectUrl);
    } catch (e) {
      showToast(`预览失败: ${e instanceof Error ? e.message : ""}`, "error");
    } finally {
      setCustomPreviewLoading(false);
      setPreviewLoading(false);
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
        // Refresh catalog (modes + categories + settings schema)
        refreshCatalog();
        setEditingCustomMode(false);
        setCustomJson("");
        setCustomDesc("");
        setCustomModeName("");
        if (customPreviewImg) {
          try { URL.revokeObjectURL(customPreviewImg); } catch {}
        }
        setCustomPreviewImg(null);
        setCustomEditorSource(null);
      } else {
        throw new Error(data.error || "保存失败");
      }
    } catch (e) {
      showToast(`保存失败: ${e instanceof Error ? e.message : ""}`, "error");
    }
  };

  const toggleMode = useCallback((modeId: string) => {
    setSelectedModes((prev) => {
      const next = new Set(prev);
      if (next.has(modeId)) next.delete(modeId);
      else next.add(modeId);
      return next;
    });
  }, []);

  const handleModePreview = (m: string) => {
    const modeId = (m || "").toUpperCase();
    setPreviewMode(modeId);
    if (modeId === "MY_ADAPTIVE") {
      setPendingAdaptiveAction({ action: "preview", mode: modeId });
      adaptiveFileInputRef.current?.click();
      return;
    }
    if (requiresParamModal(modeId)) {
      openParamModal(modeId, "preview");
      return;
    }
    // Config page preview should bypass cache so it:
    // - reflects latest overrides
    // - triggers quota deduction when applicable (quota is only deducted on cache miss)
    handlePreview(modeId, true);
  };

  const handleModeApply = async (m: string) => {
    const modeId = (m || "").toUpperCase();
    if (modeId === "MY_ADAPTIVE" && !selectedModes.has(modeId)) {
      setPendingAdaptiveAction({ action: "apply", mode: modeId });
      adaptiveFileInputRef.current?.click();
      return;
    }
    if (requiresParamModal(modeId) && !selectedModes.has(modeId)) {
      // only require params when adding to carousel
      openParamModal(modeId, "apply");
      return;
    }
    const wasSelected = selectedModes.has(modeId);
    toggleMode(modeId);
    showToast(wasSelected ? "已从轮播移除" : "已加入轮播", "success");
  };

  const commitModalAction = useCallback(async (modeId: string, action: "preview" | "apply", forcedOverride?: ModeOverride) => {
    setParamModal(null);
    if (forcedOverride && Object.keys(forcedOverride).length > 0) {
      updateModeOverride(modeId, forcedOverride);
      if (modeId === "MEMO" && typeof forcedOverride.memo_text === "string") {
        setMemoText(forcedOverride.memo_text);
      }
      if (modeId === "WEATHER" && typeof forcedOverride.city === "string") {
        // keep global city as-is; weather override is per-mode
      }
    }

    setPreviewMode(modeId);
    await handlePreview(modeId, true, forcedOverride);

    if (action === "apply") {
      if (!selectedModes.has(modeId)) {
        toggleMode(modeId);
        showToast("已加入轮播", "success");
      }
    }
  }, [handlePreview, selectedModes, showToast, toggleMode, updateModeOverride]);

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

  const handleAddCustomPersona = () => {
    const v = customPersonaTone.trim();
    if (!v) return;
    setCharacterTones((prev) => (prev.includes(v) ? prev : [...prev, v]));
    setCustomPersonaTone("");
  };

  const modeMeta = useMemo(() => {
    const map: Record<string, { name: string; tip: string }> = {};
    for (const item of catalogItems) {
      const mid = (item.mode_id || "").toUpperCase();
      if (!mid) continue;
      const lang = isEn ? item.i18n?.en : item.i18n?.zh;
      const name = (lang?.name && String(lang.name)) || (item.display_name && String(item.display_name)) || mid;
      const tip = (lang?.tip && String(lang.tip)) || (item.description && String(item.description)) || "";
      map[mid] = { name, tip };
    }
    return map;
  }, [catalogItems, isEn]);

  const coreModes = useMemo(
    () => catalogItems.filter((m) => m.category === "core").map((m) => m.mode_id.toUpperCase()),
    [catalogItems],
  );
  const extraModes = useMemo(
    () => catalogItems.filter((m) => m.category === "more").map((m) => m.mode_id.toUpperCase()),
    [catalogItems],
  );
  const customModes = useMemo(
    () => catalogItems.filter((m) => m.category === "custom").map((m) => m.mode_id.toUpperCase()),
    [catalogItems],
  );
  const customModeMeta = useMemo(
    () =>
      Object.fromEntries(
        catalogItems
          .filter((m) => m.category === "custom")
          .map((m) => {
            const lang = isEn ? m.i18n?.en : m.i18n?.zh;
            return [
              m.mode_id.toUpperCase(),
              {
                name: (lang?.name && String(lang.name)) || m.display_name || m.mode_id,
                tip: (lang?.tip && String(lang.tip)) || m.description || "",
              },
            ];
          }),
      ),
    [catalogItems, isEn],
  );
  const activeModeSchema = settingsMode ? (modeSchemaMap[settingsMode] || []) : [];

  const batteryPct = stats?.last_battery_voltage
    ? Math.min(100, Math.max(0, Math.round((stats.last_battery_voltage / 3.3) * 100)))
    : null;
  const currentDeviceMembership = userDevices.find((d) => d.mac.toUpperCase() === mac.toUpperCase()) || null;
  const denyByMembership = Boolean(mac && currentUser && !devicesLoading && !currentDeviceMembership);
  const currentUserRole = currentDeviceMembership?.role || "";
  const formatPreviewConfirmText = useCallback((usageSource?: string) => {
    switch (usageSource) {
      case "current_user_api_key":
        return tr("本次预览将使用你的 API key。是否继续？", "This preview will use your API key. Continue?");
      case "owner_api_key":
        return ownerUsername
          ? tr(`本次预览将使用 owner（${ownerUsername}）的 API key。是否继续？`, `This preview will use ${ownerUsername}'s API key. Continue?`)
          : tr("本次预览将使用 owner 的 API key。是否继续？", "This preview will use the owner's API key. Continue?");
      case "owner_free_quota":
        return ownerUsername
          ? tr(`本次预览将消耗 owner（${ownerUsername}）的免费额度。是否继续？`, `This preview will use ${ownerUsername}'s free quota. Continue?`)
          : tr("本次预览将消耗 owner 的免费额度。是否继续？", "This preview will use the owner's free quota. Continue?");
      case "current_user_free_quota":
        return tr("本次预览将消耗你的免费额度。是否继续？", "This preview will use your free quota. Continue?");
      default:
        return tr("当前未命中缓存，将生成新的预览。是否继续？", "No cache hit. A new preview will be generated. Continue?");
    }
  }, [ownerUsername, tr]);
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
        { id: "sharing", label: "Sharing", icon: Users },
        { id: "stats", label: "Status", icon: BarChart3 },
      ] as const
    : TABS;

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
          setAdaptiveUploading(true);
          try {
            const url = await uploadLocalImage(f);
            const pending = pendingAdaptiveAction;
            setPendingAdaptiveAction(null);
            await commitModalAction("MY_ADAPTIVE", pending?.action || "preview", { image_url: url } as ModeOverride);
          } catch (err) {
            const msg = err instanceof Error ? err.message : tr("请选择一张本地图片", "Please choose a local image");
            showToast(msg, "error");
          } finally {
            setAdaptiveUploading(false);
          }
        }}
      />
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
            isFocusListening={isFocusListening}
            onToggleFocus={handleToggleFocusListening}
            focusToggleLoading={focusToggleLoading}
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
                <div className="grid grid-cols-1 lg:grid-cols-[520px_1fr] gap-6 items-start">
                  <ModeSelector
                    tr={tr}
                    selectedModes={selectedModes}
                    customModes={customModes}
                    customModeMeta={customModeMeta}
                    modeMeta={modeMeta}
                    coreModes={coreModes}
                    extraModes={extraModes}
                    handleModePreview={handleModePreview}
                    handleModeApply={handleModeApply}
                    setEditingCustomMode={setEditingCustomMode}
                    setCustomDesc={setCustomDesc}
                    setCustomModeName={setCustomModeName}
                    setCustomJson={setCustomJson}
                    previewColors={previewColors}
                    onColorsChange={setPreviewColors}
                  />

                  <div ref={previewPanelRef}>
                  <EInkPreviewPanel
                    tr={tr}
                    previewModeLabel={
                      previewModeLabelOverride ||
                      (previewMode
                        ? (modeMeta[previewMode]?.name || customModeMeta[previewMode]?.name || previewMode)
                        : tr("请选择模式", "Select a mode"))
                    }
                    previewLoading={previewLoading}
                    previewStatusText={previewStatusText}
                    previewImg={previewImg}
                    previewCacheHit={previewCacheHit}
                    previewLlmStatus={previewLlmStatus}
                    canApplyToScreen={Boolean(mac && previewMode && previewImg)}
                    applyToScreenLoading={applyToScreenLoading}
                    onRegenerate={() => handlePreview(previewMode, true)}
                    onApplyToScreen={handleApplyPreviewToScreen}
                    rightActions={
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleSaveCustomMode}
                        disabled={!(customEditorSource === "ai" && Boolean(customJson.trim()))}
                        className="bg-white text-ink border-ink/20 hover:bg-ink hover:text-white active:bg-ink active:text-white disabled:bg-white disabled:text-ink/50"
                      >
                        {tr("保存模式", "Save Mode")}
                      </Button>
                    }
                  />
                  </div>
                </div>

                <Dialog
                  open={editingCustomMode}
                  onClose={() => {
                    setEditingCustomMode(false);
                  }}
                >
                  <DialogContent className="max-w-2xl">
                    <DialogHeader
                      onClose={() => {
                        setEditingCustomMode(false);
                      }}
                    >
                      <div>
                        <DialogTitle>{tr("创建自定义模式", "Create Custom Mode")}</DialogTitle>
                        <DialogDescription>
                          {tr(
                            "用一句话描述你想要的模式，点击 AI 生成预览，右侧水墨屏会显示效果。",
                            "Describe the mode you want, click AI Generate Preview, and the right E-Ink panel will show the result.",
                          )}
                        </DialogDescription>
                      </div>
                    </DialogHeader>

                    <div className="space-y-3">
                      {customGenerating ? (
                        <div className="rounded-sm border border-ink/10 bg-paper px-3 py-3 text-sm text-ink-light flex items-center gap-2">
                          <Loader2 size={16} className="animate-spin" />
                          {tr("模式生成中...", "Generating mode...")}
                        </div>
                      ) : null}
                      <textarea
                        value={customDesc}
                        onChange={(e) => {
                          setCustomDesc(e.target.value);
                          setCustomEditorSource("manual");
                        }}
                        rows={3}
                        maxLength={2000}
                        placeholder={tr(
                          "描述你想要的模式，如：每天显示一个英语单词和释义，单词要大号字体居中",
                          "Describe your mode, e.g. show one English word and definition daily with a large centered font",
                        )}
                        className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm resize-y bg-white"
                        disabled={customGenerating}
                      />

                      <input
                        value={customModeName}
                        onChange={(e) => {
                          setCustomModeName(e.target.value);
                          setCustomEditorSource((v) => v || "manual");
                        }}
                        placeholder={tr("模式名称（例如：今日英语）", "Mode name (e.g. Daily English)")}
                        className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
                        disabled={customGenerating}
                      />

                      <Button
                        size="sm"
                        onClick={() => {
                          // Keep the dialog open while generating; it will auto-close after generation finishes.
                          void handleGenerateMode();
                        }}
                        disabled={customGenerating || !customDesc.trim()}
                      >
                        {tr("AI 生成预览", "AI Generate Preview")}
                      </Button>

                      {customEditorSource === "ai" ? (
                        <div className="text-[11px] text-ink-light">
                          {tr("AI 生成的模式可在右侧预览后直接保存。", "AI-generated modes can be saved from the right preview panel.")}
                        </div>
                      ) : null}
                    </div>
                  </DialogContent>
                </Dialog>

              </div>
            )}

            {/* Preferences Tab */}
            {activeTab === "preferences" && (
              <div className="space-y-4">
                <RefreshStrategyEditor
                  tr={tr}
                  locale={isEn ? "en" : "zh"}
                  location={currentLocation}
                  setLocation={applyGlobalLocation}
                  modeLanguage={modeLanguage}
                  setModeLanguage={setModeLanguage}
                  modeLanguageOptions={MODE_LANGUAGE_OPTIONS}
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
                  toneOptions={TONE_OPTIONS}
                  personaPresets={PERSONA_PRESETS}
                  strategies={STRATEGIES}
                />
                <Button
                  variant="outline"
                  onClick={handleSavePreferences}
                  disabled={!mac || savingPrefs}
                  className="w-full bg-white text-ink border-ink/20 hover:bg-ink hover:text-white active:bg-ink active:text-white disabled:bg-white disabled:text-ink/50"
                >
                  {savingPrefs ? <Loader2 size={14} className="animate-spin mr-1" /> : <Save size={14} className="mr-1" />}
                  {tr("保存", "Save")}
                </Button>
              </div>
            )}

            {/* Sharing Tab */}
            {activeTab === "sharing" && (
              <div className="space-y-4">
                {currentUserRole === "owner" ? (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-base">{tr("共享成员", "Sharing")}</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div className="flex gap-2 flex-wrap">
                        <input
                          value={shareUsernameInput}
                          onChange={(e) => setShareUsernameInput(e.target.value)}
                          placeholder={tr("输入要共享的用户名", "Enter username to share")}
                          className="flex-1 min-w-[220px] rounded-sm border border-ink/20 px-3 py-2 text-sm"
                        />
                        <Button variant="outline" size="sm" onClick={handleShareDevice} disabled={!shareUsernameInput.trim()}>
                          {tr("分享", "Share")}
                        </Button>
                      </div>
                      {membersLoading ? (
                        <div className="flex items-center gap-2 text-sm text-ink-light">
                          <Loader2 size={14} className="animate-spin" /> {tr("加载成员中...", "Loading members...")}
                        </div>
                      ) : (
                        <div className="space-y-2">
                          {deviceMembers.map((member) => (
                            <div key={member.user_id} className="flex items-center justify-between rounded-sm border border-ink/10 p-2 text-sm">
                              <div>
                                <p className="font-medium text-ink">{member.username}</p>
                                <p className="text-xs text-ink-light">{member.role === "owner" ? "Owner" : "Member"}</p>
                              </div>
                              {member.role !== "owner" ? (
                                <Button variant="outline" size="sm" onClick={() => handleRemoveMember(member.user_id)}>
                                  {tr("移除", "Remove")}
                                </Button>
                              ) : null}
                            </div>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ) : (
                  <div className="p-3 rounded-sm border border-ink/10 bg-paper text-sm text-ink-light">
                    {tr("只有设备 Owner 可以管理共享成员。", "Only the device owner can manage sharing.")}
                  </div>
                )}

                {pendingRequests.some((item) => item.mac === mac) ? (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-base">{tr("待处理绑定请求", "Pending requests")}</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      {pendingRequests.filter((item) => item.mac === mac).map((item) => (
                        <div key={item.id} className="flex items-center justify-between gap-2 rounded-sm border border-ink/10 p-2 text-sm">
                          <div>
                            <p className="font-medium text-ink">{item.requester_username}</p>
                            <p className="text-xs text-ink-light">{tr("请求绑定此设备", "Requested to bind this device")}</p>
                          </div>
                          <div className="flex items-center gap-2">
                            <Button variant="outline" size="sm" onClick={() => handleRejectRequest(item.id)}>
                              {tr("拒绝", "Reject")}
                            </Button>
                            <Button size="sm" onClick={() => handleApproveRequest(item.id)}>
                              {tr("同意", "Approve")}
                            </Button>
                          </div>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                ) : null}
              </div>
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
                      <StatCard label={tr("缓存命中率", "Cache Hit Rate")} value={stats.cache_hit_rate != null ? `${Math.round(stats.cache_hit_rate)}%` : "-"} />
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
                                <span className="w-20 text-ink-light truncate">{modeMeta[mode]?.name || customModeMeta[mode]?.name || mode}</span>
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
                      {tr("模式设置", "Mode Settings")}: {modeMeta[settingsMode]?.name || customModeMeta[settingsMode]?.name || settingsMode}
                    </span>
                    <button className="text-ink-light hover:text-ink" onClick={() => setSettingsMode(null)}>
                      <X size={16} />
                    </button>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <Field label="城市（可选）">
                    <LocationPicker
                      value={extractLocationValue(getModeOverride(settingsMode) as Record<string, unknown>)}
                      onChange={(next) =>
                        updateModeOverride(settingsMode, {
                          city: next.city,
                          latitude: next.latitude,
                          longitude: next.longitude,
                          timezone: next.timezone,
                          admin1: next.admin1,
                          country: next.country,
                        })
                      }
                      locale={isEn ? "en" : "zh"}
                      placeholder={tr("搜索模式专属地点", "Search a mode-specific place")}
                      helperText={tr(
                        `留空则使用全局默认：${describeLocation(currentLocation) || "杭州"}`,
                        `Leave empty to use global default: ${describeLocation(currentLocation) || "Hangzhou"}`,
                      )}
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

      <Dialog
        open={showFocusTokenModal}
        onClose={() => {
          setShowFocusTokenModal(false);
        }}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader
            onClose={() => {
              setShowFocusTokenModal(false);
            }}
          >
            <div>
              <DialogTitle>{tr("设备告警 Token 已生成", "Alert Token Generated")}</DialogTitle>
              <DialogDescription>
                {tr(
                  "将下面的 Token 配置到你的 OpenCLAW（或自建 Agent）里，用于向该设备发送紧急告警。",
                  "Copy this token into your OpenCLAW (or custom agent) to send urgent alerts to this device.",
                )}
              </DialogDescription>
              <div className="mt-2 text-[11px] text-ink-light">
                {tr(
                  "提示：开启专注监听后，设备端通常需要重启/重新进入启动流程，才会开始 10 秒轮询告警并在屏幕显示内容。",
                  "Tip: after enabling Focus Listening, the device usually needs a restart / re-enter startup flow before it starts 10s alert polling and displaying messages.",
                )}
              </div>
            </div>
          </DialogHeader>

          <div className="space-y-3">
            <div className="rounded-sm border border-ink/20 bg-white px-3 py-2 text-xs font-mono break-all">
              {focusAlertToken || tr("（空）", "(empty)")}
            </div>
            <div className="flex items-center justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(focusAlertToken);
                    showToast(tr("已复制 Token", "Token copied"), "success");
                  } catch {
                    showToast(tr("复制失败，请手动选中复制", "Copy failed, please copy manually"), "error");
                  }
                }}
                disabled={!focusAlertToken}
              >
                {tr("复制 Token", "Copy Token")}
              </Button>
              <Button
                type="button"
                onClick={() => {
                  setShowFocusTokenModal(false);
                }}
              >
                {tr("关闭", "Close")}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

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

      {previewConfirm ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <Card className="w-full max-w-md mx-4">
            <CardHeader>
              <CardTitle>{isEn ? "Confirm Preview" : "确认预览"}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm leading-6 text-ink">
                {formatPreviewConfirmText(previewConfirm.usageSource)}
              </p>
              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    setPreviewConfirm(null);
                  }}
                >
                  {isEn ? "Cancel" : "取消"}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    const pending = previewConfirm;
                    setPreviewConfirm(null);
                    if (pending) {
                      handlePreview(pending.mode, pending.forceNoCache, pending.forcedModeOverride, true);
                    }
                  }}
                  className="bg-white text-ink border-ink/20 hover:bg-ink hover:text-white active:bg-ink active:text-white"
                >
                  {isEn ? "Confirm" : "确定"}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      ) : null}

      {/* 邀请码输入弹窗 */}
      {showInviteModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <Card className="w-full max-w-md mx-4">
            <CardHeader>
              <CardTitle>
                {currentUserRole === "member"
                  ? (isEn ? "Free Quota Exhausted" : "免费额度已用完")
                  : (isEn ? "Enter Invitation Code" : "请输入邀请码")}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className={`${currentUserRole === "member" ? "text-base leading-7 text-ink" : "text-sm text-ink-light"}`}>
                {isEn
                  ? (currentUserRole === "member"
                    ? `This device owner's free quota is exhausted. Please contact ${ownerUsername || "the owner"}, or continue with device-free preview.`
                    : "Your free quota has been exhausted. You can enter an invitation code or configure your own API key in your profile.")
                  : (currentUserRole === "member"
                    ? `当前设备 owner${ownerUsername ? `（${ownerUsername}）` : ""} 的免费额度已用完，请联系 owner，或继续在线体验。`
                    : "您的免费额度已用完。您可以输入邀请码获得50次免费LLM调用额度，也可以在个人信息中设置自己的 API key。")}
              </p>
              {currentUserRole === "member" ? (
                <div className="rounded-sm border border-amber-200 bg-amber-50 px-3 py-2">
                  <p className="text-xs leading-5 text-amber-800">
                    {isEn
                      ? "Member free quota only applies to device-free preview, not on-device generation."
                      : "Member 免费额度仅用于无设备预览，不用于设备端生成。"}
                  </p>
                </div>
              ) : (
                <>
                  <div className="p-3 rounded-sm border border-ink/20 bg-paper-dark">
                    <p className="text-xs text-ink-light mb-2">
                      {isEn
                        ? "Tip: If you have your own API key, you can configure it in your profile to avoid quota limits."
                        : "提示：如果您有自己的 API key，可以在个人信息中配置，这样就不会受到额度限制了。"}
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
                </>
              )}
              <div className={`flex gap-2 ${currentUserRole === "member" ? "flex-col-reverse sm:flex-row sm:justify-end" : "justify-end"}`}>
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowInviteModal(false);
                    setInviteCode("");
                    setPendingPreviewMode(null);
                  }}
                  disabled={currentUserRole === "member" ? false : redeemingInvite}
                >
                  {isEn ? "Cancel" : "取消"}
                </Button>
                {currentUserRole === "member" && (
                  <Link href={withLocalePath(locale, "/preview")} className="sm:min-w-[180px]">
                    <Button
                      variant="outline"
                      onClick={() => {
                        setShowInviteModal(false);
                        setInviteCode("");
                        setPendingPreviewMode(null);
                      }}
                      className="w-full bg-white text-ink border-ink/20 hover:bg-ink hover:text-white active:bg-ink active:text-white disabled:bg-white disabled:text-ink/50"
                    >
                      {isEn ? "Continue Online Preview" : "继续在线体验"}
                    </Button>
                  </Link>
                )}
                {currentUserRole !== "member" && (
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
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      ) : null}

      {/* 参数弹窗：与 /preview 页面一致（预览/加入轮播都会触发） */}
      {paramModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" onClick={() => setParamModal(null)} />
          <div className="relative w-[min(520px,calc(100vw-32px))] rounded-sm border border-ink/15 bg-white shadow-xl">
            <div className="px-4 py-3 border-b border-ink/10 flex items-center justify-between">
              <div className="text-sm font-semibold text-ink">
                {paramModal.type === "quote"
                  ? tr("自定义语录", "Custom Quote")
                  : paramModal.type === "weather"
                  ? tr("天气设置", "Weather Settings")
                  : paramModal.type === "memo"
                  ? tr("便签内容", "Memo Content")
                  : paramModal.type === "countdown"
                  ? tr("倒计时设置", "Countdown Settings")
                  : paramModal.type === "habit"
                  ? tr("习惯打卡", "Habit Tracker")
                  : paramModal.type === "calendar"
                  ? tr("日历提醒", "Calendar Reminders")
                  : paramModal.type === "timetable"
                  ? tr("课程表设置", "Timetable Settings")
                  : tr("人生进度条", "Life Progress")}
              </div>
              <button className="text-ink-light hover:text-ink" onClick={() => setParamModal(null)}>
                ✕
              </button>
            </div>
            <div className="px-4 py-4 space-y-3">
              {paramModal.type === "quote" ? (
                <>
                  <div className="text-xs text-ink-light">
                    {tr(
                      "随机生成一条有深度的语录，或粘贴你自己的文字。",
                      "Generate a deep quote randomly, or paste your own text.",
                    )}
                  </div>
                  <textarea
                    value={quoteDraft}
                    onChange={(e) => setQuoteDraft(e.target.value)}
                    placeholder={tr("输入语录内容...", "Type your quote...")}
                    className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm min-h-28 bg-white"
                  />
                  <input
                    value={authorDraft}
                    onChange={(e) => setAuthorDraft(e.target.value)}
                    placeholder={tr("作者（可选）", "Author (optional)")}
                    className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
                  />
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-2">
                    <Button
                      variant="outline"
                      onClick={() => {
                        commitModalAction(paramModal.mode, paramModal.action);
                      }}
                      disabled={previewLoading}
                    >
                      {tr("随机生成", "Random generate")}
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => {
                        const q = quoteDraft.trim();
                        const a = authorDraft.trim();
                        commitModalAction(
                          paramModal.mode,
                          paramModal.action,
                          q ? ({ quote: q, author: a } as ModeOverride) : undefined,
                        );
                      }}
                      disabled={previewLoading}
                    >
                      {tr("使用我的输入", "Use my input")}
                    </Button>
                  </div>
                </>
              ) : paramModal.type === "weather" ? (
                <>
                  <div className="text-xs text-ink-light">
                    {tr(
                      "搜索并选择具体地点查看天气，避免重名城市误匹配。",
                      "Search and choose a specific place to avoid ambiguous city names.",
                    )}
                  </div>
                  <LocationPicker
                    value={weatherDraftLocation}
                    onChange={setWeatherDraftLocation}
                    locale={isEn ? "en" : "zh"}
                    placeholder={tr("输入地点名称（如：上海、巴黎、Singapore）", "Enter a place name (e.g. Shanghai, Paris, Singapore)")}
                    helperText={tr("建议从候选列表中点选具体地点。", "Pick a precise result from the suggestion list.")}
                    className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
                    autoFocus
                  />
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-2">
                    <Button
                      variant="outline"
                      onClick={() => setWeatherDraftLocation(defaultWeatherLocation)}
                      disabled={previewLoading}
                    >
                      {tr("使用默认城市", "Use default city")}
                    </Button>
                    <Button
                      onClick={() => {
                        const nextLocation = cleanLocationValue(weatherDraftLocation);
                        commitModalAction(
                          paramModal.mode,
                          paramModal.action,
                          nextLocation.city ? (nextLocation as ModeOverride) : undefined,
                        );
                      }}
                      disabled={previewLoading}
                      variant="outline"
                    >
                      {tr("预览天气", "Preview weather")}
                    </Button>
                  </div>
                </>
              ) : paramModal.type === "memo" ? (
                <>
                  <div className="text-xs text-ink-light">
                    {tr("输入便签内容，将在墨水屏上显示。", "Enter memo content to display on e-ink screen.")}
                  </div>
                  <textarea
                    value={memoDraft}
                    onChange={(e) => setMemoDraft(e.target.value)}
                    placeholder={tr("输入便签内容...", "Enter memo content...")}
                    className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm min-h-32 bg-white"
                    autoFocus
                  />
                  <div className="flex justify-end pt-2">
                    <Button
                      onClick={() => {
                        const m = memoDraft.trim();
                        commitModalAction(
                          paramModal.mode,
                          paramModal.action,
                          m ? ({ memo_text: m } as ModeOverride) : undefined,
                        );
                      }}
                      disabled={previewLoading}
                      variant="outline"
                    >
                      {tr("预览便签", "Preview memo")}
                    </Button>
                  </div>
                </>
              ) : paramModal.type === "countdown" ? (
                <>
                  <div className="text-xs text-ink-light mb-3">
                    {tr("设置倒计时事件名称和日期", "Set countdown event name and date")}
                  </div>
                  <div className="space-y-3">
                    <div>
                      <label className="block text-xs text-ink mb-1.5">
                        {tr("事件名称", "Event Name")}
                      </label>
                      <input
                        value={countdownName}
                        onChange={(e) => setCountdownName(e.target.value)}
                        placeholder={tr("例如：元旦、生日", "e.g., New Year, Birthday")}
                        className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-ink mb-1.5">
                        {tr("目标日期", "Target Date")}
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
                      onClick={() => commitModalAction(paramModal.mode, paramModal.action)}
                      disabled={previewLoading}
                      variant="outline"
                    >
                      {tr("使用默认", "Use Default")}
                    </Button>
                    <Button
                      onClick={() => {
                        const today = new Date();
                        const target = new Date(countdownDate);
                        const days = Math.ceil((target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
                        commitModalAction(paramModal.mode, paramModal.action, {
                          events: [
                            {
                              name: countdownName || (isEn ? "Countdown" : "倒计时"),
                              date: countdownDate,
                              type: "countdown",
                              days,
                            },
                          ],
                        } as ModeOverride);
                      }}
                      disabled={previewLoading}
                      variant="outline"
                    >
                      {tr("预览倒计时", "Preview Countdown")}
                    </Button>
                  </div>
                </>
              ) : paramModal.type === "habit" ? (
                <>
                  <div className="text-xs text-ink-light mb-3">
                    {tr(
                      "管理你的习惯列表，勾选今日已完成的习惯。用 ✕ 移除不想追踪的习惯。",
                      "Manage your habit list. Check off completed habits today. Use ✕ to remove habits you don't want to track.",
                    )}
                  </div>
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {habitItems.map((item, idx) => (
                      <div key={idx} className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={item.done}
                          onChange={(e) => {
                            const next = [...habitItems];
                            next[idx] = { ...next[idx], done: e.target.checked };
                            setHabitItems(next);
                          }}
                          className="w-4 h-4"
                        />
                        <input
                          value={item.name}
                          onChange={(e) => {
                            const next = [...habitItems];
                            next[idx] = { ...next[idx], name: e.target.value };
                            setHabitItems(next);
                          }}
                          className="flex-1 rounded-sm border border-ink/20 px-3 py-1.5 text-sm bg-white"
                        />
                        <button
                          onClick={() => setHabitItems(habitItems.filter((_, i) => i !== idx))}
                          className="text-ink-light hover:text-red-500 px-2"
                          title={tr("移除此习惯", "Remove this habit")}
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                  </div>
                  <button
                    onClick={() => setHabitItems([...habitItems, { name: "", done: false }])}
                    className="w-full mt-2 px-3 py-2 rounded-sm border border-dashed border-ink/20 text-sm text-ink-light hover:text-ink hover:border-ink/40 transition-colors"
                  >
                    + {tr("添加习惯", "Add Habit")}
                  </button>
                  <div className="grid grid-cols-2 gap-2 pt-3">
                    <Button
                      onClick={() => commitModalAction(paramModal.mode, paramModal.action)}
                      disabled={previewLoading}
                      variant="outline"
                    >
                      {tr("使用默认", "Use Default")}
                    </Button>
                    <Button
                      onClick={() => {
                        const tracked = habitItems.filter((h) => h.name.trim());
                        commitModalAction(paramModal.mode, paramModal.action, {
                          habitItems: tracked.map((h) => ({ name: h.name.trim(), done: h.done })),
                        } as ModeOverride);
                      }}
                      disabled={previewLoading}
                      variant="outline"
                    >
                      {tr("预览打卡", "Preview Habits")}
                    </Button>
                  </div>
                </>
              ) : paramModal.type === "lifebar" ? (
                <>
                  <div className="text-xs text-ink-light mb-3">
                    {tr("设置你的年龄和预期寿命", "Set your age and life expectancy")}
                  </div>
                  <div className="space-y-3">
                    <div>
                      <label className="block text-xs text-ink mb-1.5">
                        {tr("芳龄几何？", "Your Age")}
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
                        {tr("退休金领到？", "Life Expectancy")}
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
                          100 {tr("岁", "years")}
                        </button>
                        <button
                          onClick={() => setLifeExpectancy(120)}
                          className={`flex-1 px-3 py-2 rounded-sm text-sm transition-colors ${
                            lifeExpectancy === 120
                              ? "bg-ink text-white"
                              : "bg-paper-dark text-ink hover:bg-ink/10"
                          }`}
                        >
                          120 {tr("岁", "years")}
                        </button>
                      </div>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2 pt-3">
                    <Button
                      onClick={() => commitModalAction(paramModal.mode, paramModal.action)}
                      disabled={previewLoading}
                      variant="outline"
                    >
                      {tr("使用默认", "Use Default")}
                    </Button>
                    <Button
                      onClick={() => {
                        const lifePct = ((userAge / lifeExpectancy) * 100).toFixed(1);
                        commitModalAction(paramModal.mode, paramModal.action, {
                          age: userAge,
                          life_expect: lifeExpectancy,
                          life_pct: parseFloat(lifePct),
                          life_label: isEn ? "Life" : "人生",
                        } as ModeOverride);
                      }}
                      disabled={previewLoading}
                      variant="outline"
                    >
                      {tr("预览进度", "Preview Progress")}
                    </Button>
                  </div>
                </>
              ) : paramModal.type === "calendar" ? (
                <>
                  <div className="text-xs text-ink-light mb-3">
                    {tr(
                      "为日历中的特定日期添加提醒事项，提醒会显示在日期下方。",
                      "Add reminders for specific dates. They appear below each date in the calendar.",
                    )}
                  </div>
                  <CalendarReminders
                    reminders={
                      (getModeOverride("CALENDAR") as Record<string, unknown>)?.reminders as Record<string, string> ?? {}
                    }
                    onChange={(r) => {
                      updateModeOverride("CALENDAR", {
                        reminders: Object.keys(r).length > 0 ? r : undefined,
                      } as Record<string, unknown>);
                    }}
                    tr={tr}
                  />
                  <div className="grid grid-cols-2 gap-2 pt-3">
                    <Button
                      onClick={() => commitModalAction(paramModal.mode, paramModal.action)}
                      disabled={previewLoading}
                      variant="outline"
                    >
                      {tr("跳过预览", "Skip Preview")}
                    </Button>
                    <Button
                      onClick={() => {
                        const reminders = (getModeOverride("CALENDAR") as Record<string, unknown>)?.reminders as Record<string, string> | undefined;
                        commitModalAction(paramModal.mode, paramModal.action,
                          reminders && Object.keys(reminders).length > 0
                            ? { reminders } as ModeOverride
                            : undefined,
                        );
                      }}
                      disabled={previewLoading}
                      variant="outline"
                    >
                      {tr("预览日历", "Preview Calendar")}
                    </Button>
                  </div>
                </>
              ) : paramModal.type === "timetable" ? (
                <>
                  <div className="text-xs text-ink-light mb-3">
                    {tr(
                      "选择课表类型并编辑课程安排，点击单元格即可修改。",
                      "Choose timetable type and edit courses. Click any cell to modify.",
                    )}
                  </div>
                  <TimetableEditor
                    data={timetableData}
                    onChange={setTimetableData}
                    tr={tr}
                  />
                  <div className="grid grid-cols-2 gap-2 pt-3">
                    <Button
                      onClick={() => commitModalAction(paramModal.mode, paramModal.action)}
                      disabled={previewLoading}
                      variant="outline"
                    >
                      {tr("使用默认", "Use Default")}
                    </Button>
                    <Button
                      onClick={() => {
                        commitModalAction(paramModal.mode, paramModal.action, {
                          style: timetableData.style,
                          periods: timetableData.periods,
                          courses: timetableData.courses,
                        } as ModeOverride);
                      }}
                      disabled={previewLoading}
                      variant="outline"
                    >
                      {tr("预览课程表", "Preview Timetable")}
                    </Button>
                  </div>
                </>
              ) : null}
            </div>
          </div>
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
