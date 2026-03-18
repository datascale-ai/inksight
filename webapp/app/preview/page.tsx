"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { LocationPicker } from "@/components/config/location-picker";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertCircle, Eye, Loader2, Plus } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { localeFromPathname, t, withLocalePath } from "@/lib/i18n";
import { cleanLocationValue, type LocationValue } from "@/lib/locations";
import { authHeaders, fetchCurrentUser } from "@/lib/auth";

type ModeCatalogItem = {
  mode_id: string;
  category: "core" | "more" | "custom" | string;
  source?: string;
  display_name?: string;
  description?: string;
  i18n?: {
    zh?: { name?: string; tip?: string };
    en?: { name?: string; tip?: string };
  };
};

function ModeSection({
  title,
  modes,
  currentMode,
  onPreview,
  collapsible,
  customMeta,
  tailItem,
  locale,
}: {
  title: string;
  modes: string[];
  currentMode: string;
  onPreview: (m: string) => void;
  collapsible?: boolean;
  customMeta?: Record<string, { name: string; tip: string }>;
  tailItem?: React.ReactNode;
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
            const meta = customMeta?.[m] || { name: m, tip: "" };
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
          {tailItem ? tailItem : null}
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

  const [catalogItems, setCatalogItems] = useState<ModeCatalogItem[]>([]);
  const [modesError, setModesError] = useState<string | null>(null);
  // do not preselect any mode
  const [previewMode, setPreviewMode] = useState("");
  const [previewModeNameOverride, setPreviewModeNameOverride] = useState<string | null>(null);

  const [city] = useState("杭州");
  const [memoText] = useState(t(locale, "preview.memo.default", "写点什么吧…"));

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
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [_imageUploadLoading, setImageUploadLoading] = useState(false);
  const [quoteDraft, setQuoteDraft] = useState("");
  const [authorDraft, setAuthorDraft] = useState("");
  const [weatherDraftLocation, setWeatherDraftLocation] = useState<LocationValue>({ city: "杭州" });
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

  const modeMeta = useMemo(() => {
    const map: Record<string, { name: string; tip: string }> = {};
    for (const item of catalogItems) {
      const mid = (item.mode_id || "").toUpperCase();
      if (!mid) continue;
      const lang = locale === "en" ? item.i18n?.en : item.i18n?.zh;
      const name =
        (lang?.name && String(lang.name)) ||
        (item.display_name && String(item.display_name)) ||
        mid;
      const tip =
        (lang?.tip && String(lang.tip)) ||
        (item.description && String(item.description)) ||
        "";
      map[mid] = { name, tip };
    }
    return map;
  }, [catalogItems, locale]);

  const coreModes = useMemo(
    () => catalogItems.filter((m) => m.category === "core").map((m) => m.mode_id.toUpperCase()),
    [catalogItems],
  );
  const moreModes = useMemo(
    () =>
      catalogItems
        .filter((m) => m.category === "more")
        .map((m) => m.mode_id.toUpperCase()),
    [catalogItems],
  );
  const customModes = useMemo(
    () =>
      catalogItems
        .filter((m) => m.category === "custom")
        .map((m) => m.mode_id.toUpperCase()),
    [catalogItems],
  );

  const previewModeName =
    previewModeNameOverride ||
    modeMeta[previewMode]?.name ||
    previewMode ||
    t(locale, "preview.unknown_mode", "Unknown");
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const previewModeTip =
    modeMeta[previewMode]?.tip ||
    "";

  const handlePreview = async (modeId?: string, override?: Record<string, unknown> | LocationValue) => {
    const targetMode = modeId || previewMode;
    if (!targetMode) return;
    if (!authChecked) return;

    // 检查是否需要弹窗
    if (!override) {
      if (targetMode === "WEATHER") {
        setModal({ type: "weather", modeId: targetMode });
        setWeatherDraftLocation({});
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
        const memoOverrideValue =
          override && "memo_text" in override ? override.memo_text : undefined;
        const memoOverride = memoOverrideValue ? String(memoOverrideValue) : memoText;
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
        setPreviewLlmStatus(null);
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
      setWeatherDraftLocation({});
      setModal({ type: "weather", modeId });
      return;
    }
    if (modeId === "MEMO") {
      setPreviewMode(modeId);
      setMemoDraft(memoText); // 使用当前便签内容作为默认值
      setModal({ type: "memo", modeId });
      return;
    }

    setPreviewModeNameOverride(null);
    setPreviewMode(modeId);
    await handlePreview(modeId);
  };

  const handleCustomModePreview = async (defOverride?: unknown) => {
    if (!defOverride && !customJson.trim()) return;
    setPreviewLoading(true);
    setPreviewError(null);
    setPreviewLlmStatus(null);
    try {
      const def = defOverride ? (defOverride as Record<string, unknown>) : (JSON.parse(customJson) as Record<string, unknown>);
      const nameFromInput = customModeName.trim();
      const displayNameRaw = (def as Record<string, unknown>)["display_name"];
      const modeIdRaw = (def as Record<string, unknown>)["mode_id"];
      const nameFromDef =
        (typeof displayNameRaw === "string" && displayNameRaw.trim()) ||
        (typeof modeIdRaw === "string" && modeIdRaw.trim()) ||
        "";
      const displayName = nameFromInput || nameFromDef || (locale === "zh" ? "自定义模式" : "Custom Mode");
      setPreviewModeNameOverride(displayName);
      setPreviewMode(displayName.toUpperCase().replace(/[^A-Z0-9_]/g, "_"));
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
        setPreviewLlmStatus(null);
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

  const handleGenerateCustomModeAndPreview = async () => {
    if (!customDesc.trim()) {
      showToast(locale === "zh" ? "请输入模式描述" : "Please enter a description for the mode", "error");
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
      if (!customModeName.trim()) {
        setCustomModeName((data.mode_def?.display_name || "").toString());
      }
      // generation complete -> close dialog -> preview on main panel
      setShowCustomModeModal(false);
      await handleCustomModePreview(data.mode_def);
    } catch (e) {
      showToast(
        (locale === "zh" ? "生成失败: " : "Generate failed: ") + (e instanceof Error ? e.message : "Unknown error"),
        "error",
      );
    } finally {
      setCustomGenerating(false);
    }
  };
  // (removed) reset(): unused

  useEffect(() => {
    setModesError(null);
    if (!authChecked) return;
    fetch("/api/modes/catalog", { headers: authHeaders() })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => {
        if (d.items && Array.isArray(d.items)) {
          setCatalogItems(d.items);
        } else {
          console.error("[PREVIEW] Invalid catalog response:", d);
          setModesError(t(locale, "preview.error.no_modes", "No modes data"));
        }
      })
      .catch((err) => {
        console.error("[PREVIEW] Failed to load catalog:", err);
        setModesError(t(locale, "preview.error.modes_unreachable", "Cannot load modes. Make sure backend is running."));
        setCatalogItems([]);
      });
  }, [authChecked, locale]);

  useEffect(() => {
    if (!authChecked) return;
    // no auto-preview on enter; user must pick a mode
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
                modes={coreModes}
                currentMode={previewMode}
                onPreview={applyModeAndPreview}
                collapsible
                customMeta={modeMeta}
                locale={locale}
              />

              <ModeSection
                title={t(locale, "preview.section.more", "More modes")}
                modes={moreModes}
                currentMode={previewMode}
                onPreview={applyModeAndPreview}
                collapsible
                customMeta={modeMeta}
                locale={locale}
              />

              {customModes.length ? (
                <ModeSection
                  title={t(locale, "preview.section.custom", "Custom modes")}
                  modes={customModes}
                  currentMode={previewMode}
                  onPreview={applyModeAndPreview}
                  collapsible
                  customMeta={modeMeta}
                  tailItem={
                    <button
                      onClick={() => {
                        setShowCustomModeModal(true);
                        setCustomDesc("");
                        setCustomModeName("");
                        setCustomJson("");
                        setCustomGenerating(false);
                      }}
                      className="rounded-sm border border-dashed border-ink/20 bg-white px-3 py-2 min-h-[64px] flex flex-col items-center justify-center text-ink-light hover:border-ink/40 hover:bg-paper-dark transition-colors"
                      title={locale === "zh" ? "新建自定义模式" : "Create custom mode"}
                    >
                      <Plus size={18} className="mb-1" />
                      <div className="text-[11px]">{locale === "zh" ? "新建" : "New"}</div>
                    </button>
                  }
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
            <CardContent className="h-[calc(80vh-220px)] flex flex-col p-0">
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
                ) : !previewMode ? (
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
                      ? "搜索并选择具体地点查看天气，避免重名地点。"
                      : "Search and choose a specific place to avoid ambiguous names."}
                  </div>
                  <LocationPicker
                    value={weatherDraftLocation}
                    onChange={setWeatherDraftLocation}
                    locale={locale === "zh" ? "zh" : "en"}
                    placeholder={locale === "zh" ? "输入地点名称（如：上海、巴黎、Singapore）" : "Enter a place name (e.g. Shanghai, Paris, Singapore)"}
                    helperText={locale === "zh" ? "建议从候选列表中点选。" : "Pick a result from the suggestion list."}
                    className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
                    autoFocus
                  />
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-2">
                    <Button
                      onClick={async () => {
                        setWeatherDraftLocation({ city: "杭州" });
                      }}
                      disabled={previewLoading}
                      variant="outline"
                    >
                      {locale === "zh" ? "使用默认城市" : "Use default city"}
                    </Button>
                    <Button
                      onClick={async () => {
                        const nextLocation = cleanLocationValue(weatherDraftLocation);
                        setModal(null);
                        if (nextLocation.city) {
                          await handlePreview(modal.modeId, nextLocation);
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
      <Dialog open={showCustomModeModal} onClose={() => setShowCustomModeModal(false)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader onClose={() => setShowCustomModeModal(false)}>
            <div>
              <DialogTitle>{locale === "zh" ? "创建自定义模式" : "Create Custom Mode"}</DialogTitle>
              <DialogDescription>
                {locale === "zh"
                  ? "用一句话描述你想要的模式，点击 AI 生成预览即可。"
                  : "Describe the mode you want, then click AI Generate Preview."}
              </DialogDescription>
            </div>
          </DialogHeader>

          <div className="space-y-3">
            {customGenerating ? (
              <div className="rounded-sm border border-ink/10 bg-paper px-3 py-3 text-sm text-ink-light flex items-center gap-2">
                <Loader2 size={16} className="animate-spin" />
                {locale === "zh" ? "模式生成中..." : "Generating mode..."}
              </div>
            ) : null}

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
              className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm resize-y bg-white"
              disabled={customGenerating}
            />

            <input
              value={customModeName}
              onChange={(e) => setCustomModeName(e.target.value)}
              placeholder={locale === "zh" ? "模式名称（例如：今日英语）" : "Mode name (e.g. Daily English)"}
              className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
              disabled={customGenerating}
            />

            <Button
              size="sm"
              onClick={() => void handleGenerateCustomModeAndPreview()}
              disabled={customGenerating || !customDesc.trim()}
            >
              {locale === "zh" ? "AI 生成预览" : "AI Generate Preview"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
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
