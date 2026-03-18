"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/config/shared";
import { User, LogOut, Loader2, Save, AlertCircle } from "lucide-react";
import { authHeaders, fetchCurrentUser, clearToken, onAuthChanged } from "@/lib/auth";
import { localeFromPathname, withLocalePath } from "@/lib/i18n";

interface ProfileData {
  user_id: number;
  username: string;
  phone: string;
  email: string;
  role: string;
  free_quota_remaining: number;
  llm_config: {
    llm_access_mode?: "preset" | "custom_openai";
    provider: string;
    model: string;
    api_key: string;
    base_url: string;
    image_provider?: string;
    image_model?: string;
    image_api_key?: string;
  } | null;
}

export default function ProfilePage() {
  const router = useRouter();
  const pathname = usePathname();
  const locale = localeFromPathname(pathname || "/");
  const isEn = useMemo(() => locale === "en", [locale]);
  const tr = useCallback((zh: string, en: string) => (isEn ? en : zh), [isEn]);

  const [currentUser, setCurrentUser] = useState<{ user_id: number; username: string } | null | undefined>(undefined);
  const [profileData, setProfileData] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [redeeming, setRedeeming] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: "success" | "error" | "info" } | null>(null);

  // Tab 状态：'platform' 或 'custom'
  const [quotaMode, setQuotaMode] = useState<"platform" | "custom">("platform");

  // 自定义 LLM 配置状态
  const [llmAccessMode, setLlmAccessMode] = useState<"preset" | "custom_openai">("preset");
  const [llmProvider, setLlmProvider] = useState("deepseek");
  const [llmModel, setLlmModel] = useState("");
  const [llmApiKey, setLlmApiKey] = useState("");
  const [llmBaseUrl, setLlmBaseUrl] = useState("");
  const [imageProvider, setImageProvider] = useState("aliyun");
  const [imageModel, setImageModel] = useState("");
  const [imageApiKey, setImageApiKey] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const showToast = useCallback((msg: string, type: "success" | "error" | "info" = "info") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  }, []);

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
    return () => {
      off();
    };
  }, [refreshCurrentUser]);

  const loadProfile = useCallback(async () => {
    if (!currentUser) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const res = await fetch("/api/user/profile", { headers: authHeaders() });
      if (res.status === 401) {
        clearToken();
        setCurrentUser(null);
        router.push(withLocalePath(locale, "/login"));
        return;
      }
      if (!res.ok) {
        showToast(isEn ? "Failed to load profile" : "加载个人信息失败", "error");
        return;
      }
      const data: ProfileData = await res.json();
      setProfileData(data);

      // 如果有 LLM 配置，设置到表单中，并切换到自定义模式
      if (data.llm_config && data.llm_config.api_key) {
        const mode = (data.llm_config.llm_access_mode || "preset") as "preset" | "custom_openai";
        setLlmAccessMode(mode);
        setLlmProvider(data.llm_config.provider || "deepseek");
        setLlmModel(data.llm_config.model || "");
        setLlmApiKey(data.llm_config.api_key || "");
        setLlmBaseUrl(data.llm_config.base_url || "");
        setImageProvider(data.llm_config.image_provider || "aliyun");
        setImageModel(data.llm_config.image_model || "");
        setImageApiKey(data.llm_config.image_api_key || "");
        setQuotaMode("custom");
      }
    } catch {
      showToast(isEn ? "Failed to load profile" : "加载个人信息失败", "error");
    } finally {
      setLoading(false);
    }
  }, [currentUser, locale, router, showToast, isEn]);

  useEffect(() => {
    if (currentUser) {
      loadProfile();
    }
  }, [currentUser, loadProfile]);

  const handleLogout = async () => {
    await fetch("/api/auth/logout", { method: "POST", headers: authHeaders() });
    clearToken();
    setCurrentUser(null);
    router.push(withLocalePath(locale, "/"));
  };

  const handleRedeemInviteCode = async () => {
    if (!inviteCode.trim()) {
      showToast(tr("请输入邀请码", "Please enter invitation code"), "error");
      return;
    }

    setRedeeming(true);
    try {
      const res = await fetch("/api/user/redeem", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ invite_code: inviteCode.trim() }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || tr("邀请码兑换失败", "Failed to redeem invitation code"));
      }

      showToast(data.message || tr("邀请码兑换成功", "Invitation code redeemed successfully"), "success");
      setInviteCode("");
      await loadProfile(); // 重新加载额度信息
    } catch (err) {
      const msg = err instanceof Error ? err.message : tr("邀请码兑换失败", "Failed to redeem invitation code");
      showToast(msg, "error");
    } finally {
      setRedeeming(false);
    }
  };

  // 根据 provider 返回可选文本模型列表
  const getLlmModelOptions = (provider: string): string[] => {
    if (provider === "aliyun") {
      return ["qwen3.5-flash", "deepseek-v3.2", "Moonshot-Kimi-K2-Instruct"];
    }
    // 默认 DeepSeek
    return ["deepseek-chat", "deepseek-reasoner"];
  };

  // 当切换文本 provider 时，如果当前模型不在合法列表中，则自动重置为第一个选项
  useEffect(() => {
    if (llmAccessMode !== "preset") return;
    const opts = getLlmModelOptions(llmProvider);
    if (!opts.includes(llmModel)) {
      setLlmModel(opts[0]);
    }
  }, [llmProvider, llmModel, llmAccessMode]);

  const handleSaveLlmConfig = async () => {
    // 除 base_url 外，其余字段均必填
    const missing: string[] = [];
    if (llmAccessMode === "preset") {
      if (!llmProvider.trim()) missing.push(tr("API 服务商", "API Provider"));
      if (!llmModel.trim()) missing.push(tr("模型名称", "Model Name"));
      if (!llmApiKey.trim()) missing.push(tr("API Key", "API Key"));
    } else {
      if (!llmModel.trim()) missing.push(tr("模型名称", "Model Name"));
      if (!llmApiKey.trim()) missing.push(tr("API Key", "API Key"));
      if (!llmBaseUrl.trim()) missing.push(tr("Base URL", "Base URL"));
    }
    if (!imageProvider.trim()) missing.push(tr("图像 API 服务商", "Image API Provider"));
    if (!imageModel.trim()) missing.push(tr("图像模型名称", "Image Model Name"));
    if (!imageApiKey.trim()) missing.push(tr("图像 API Key", "Image API Key"));
    if (missing.length > 0) {
      showToast(
        llmAccessMode === "preset"
          ? tr(`请填写必填项：${missing.join("、")}（Base URL 可留空）`, `Please fill required fields: ${missing.join(", ")} (Base URL can be empty)`)
          : tr(`请填写必填项：${missing.join("、")}`, `Please fill required fields: ${missing.join(", ")}`),
        "error",
      );
      return;
    }

    setSaving(true);
    try {
      const effectiveProvider = llmAccessMode === "custom_openai" ? "openai_compat" : llmProvider;
      const effectiveBaseUrl = llmAccessMode === "custom_openai" ? llmBaseUrl.trim() : "";
      const res = await fetch("/api/user/profile/llm", {
        method: "PUT",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          llm_access_mode: llmAccessMode,
          provider: effectiveProvider,
          model: llmModel.trim(),
          api_key: llmApiKey.trim(),
          base_url: effectiveBaseUrl,
          image_provider: imageProvider,
          image_model: imageModel.trim(),
          image_api_key: imageApiKey.trim(),
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || tr("保存配置失败", "Failed to save configuration"));
      }

      showToast(tr("配置已保存", "Configuration saved"), "success");
      await loadProfile(); // 重新加载配置
    } catch (err) {
      const msg = err instanceof Error ? err.message : tr("保存配置失败", "Failed to save configuration");
      showToast(msg, "error");
    } finally {
      setSaving(false);
    }
  };

  const resetLlmForm = useCallback(() => {
    setLlmAccessMode("preset");
    setLlmProvider("deepseek");
    setLlmModel("");
    setLlmApiKey("");
    setLlmBaseUrl("");
    setImageProvider("aliyun");
    setImageModel("");
    setImageApiKey("");
  }, []);

  const isLlmConfigValid = useMemo(() => {
    const commonImageOk =
      imageProvider.trim().length > 0 &&
      imageModel.trim().length > 0 &&
      imageApiKey.trim().length > 0;
    if (llmAccessMode === "preset") {
      return (
        llmProvider.trim().length > 0 &&
        llmModel.trim().length > 0 &&
        llmApiKey.trim().length > 0 &&
        commonImageOk
        // base_url 可为空
      );
    }
    // custom_openai: base_url 必填
    return llmModel.trim().length > 0 && llmApiKey.trim().length > 0 && llmBaseUrl.trim().length > 0 && commonImageOk;
  }, [llmProvider, llmModel, llmApiKey, llmBaseUrl, imageProvider, imageModel, imageApiKey, llmAccessMode]);

  const handleDeleteLlmConfig = async () => {
    setDeleting(true);
    try {
      const res = await fetch("/api/user/profile/llm", {
        method: "DELETE",
        headers: authHeaders(),
      });
      const data = await res.json().catch(() => ({} as { error?: string }));
      if (!res.ok) {
        throw new Error(data.error || tr("删除配置失败", "Failed to delete configuration"));
      }
      showToast(tr("配置已删除", "Configuration deleted"), "success");
      resetLlmForm();
      setDeleteConfirmOpen(false);
      await loadProfile(); // 确保服务端状态已清空
    } catch (err) {
      const msg = err instanceof Error ? err.message : tr("删除配置失败", "Failed to delete configuration");
      showToast(msg, "error");
    } finally {
      setDeleting(false);
    }
  };

  if (currentUser === undefined || loading) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-10">
        <div className="flex items-center justify-center py-20 text-ink-light">
          <Loader2 size={24} className="animate-spin mr-2" /> {tr("加载中...", "Loading...")}
        </div>
      </div>
    );
  }

  if (currentUser === null) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-10">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-start gap-2 p-3 rounded-sm border border-amber-200 bg-amber-50 text-sm text-amber-800">
              <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
              <div>
                <p className="font-medium">{tr("请先登录", "Please sign in first")}</p>
                <Link href={withLocalePath(locale, "/login")}>
                  <Button size="sm" className="mt-2">
                    {tr("登录 / 注册", "Sign In / Sign Up")}
                  </Button>
                </Link>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <h1 className="font-serif text-3xl font-bold text-ink mb-8">{tr("个人信息", "Profile")}</h1>

      <div className="space-y-6">
        {/* 账号基本信息卡片 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <User size={18} /> {tr("账号信息", "Account Information")}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-ink-light mb-1">{tr("用户名", "Username")}</p>
                <p className="text-base font-medium text-ink">{profileData?.username || "-"}</p>
              </div>
              <div>
                <p className="text-sm text-ink-light mb-1">{tr("账号角色", "Role")}</p>
                <p className="text-base font-medium text-ink">{profileData?.role === "root" ? "Root" : tr("普通用户", "User")}</p>
              </div>
              {profileData?.phone && (
                <div>
                  <p className="text-sm text-ink-light mb-1">{tr("手机号", "Phone")}</p>
                  <p className="text-base font-medium text-ink">{profileData.phone}</p>
                </div>
              )}
              {profileData?.email && (
                <div>
                  <p className="text-sm text-ink-light mb-1">{tr("邮箱", "Email")}</p>
                  <p className="text-base font-medium text-ink">{profileData.email}</p>
                </div>
              )}
            </div>
            <div className="pt-4 border-t border-ink/10">
              <Button variant="outline" onClick={handleLogout} className="text-ink-light hover:text-ink">
                <LogOut size={14} className="mr-2" />
                {tr("登出", "Logout")}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* AI 算力与模型配置卡片 */}
        <Card>
          <CardHeader>
            <CardTitle>{tr("AI 算力与模型配置", "AI Quota & Model Configuration")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Tab 切换 */}
            <div className="flex gap-2 border-b border-ink/10 pb-2">
              <button
                onClick={() => setQuotaMode("platform")}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  quotaMode === "platform"
                    ? "text-ink border-b-2 border-ink"
                    : "text-ink-light hover:text-ink"
                }`}
              >
                {tr("使用平台免费额度", "Use Platform Free Quota")}
              </button>
              <button
                onClick={() => setQuotaMode("custom")}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  quotaMode === "custom"
                    ? "text-ink border-b-2 border-ink"
                    : "text-ink-light hover:text-ink"
                }`}
              >
                {tr("使用自定义大模型密钥 (BYOK)", "Use Custom LLM API Key (BYOK)")}
              </button>
            </div>

            {/* 平台免费额度模式 */}
            {quotaMode === "platform" && (
              <div className="space-y-4">
                <div className="p-6 rounded-sm border border-ink/20 bg-paper text-center">
                  <p className="text-sm text-ink-light mb-2">{tr("当前剩余免费额度", "Remaining Free Quota")}</p>
                  <p className="text-5xl font-bold text-ink">{profileData?.free_quota_remaining || 0}</p>
                  <p className="text-xs text-ink-light mt-2">{tr("次", "times")}</p>
                </div>
                <div className="space-y-3">
                  <Field label={tr("输入邀请码", "Enter Invitation Code")}>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={inviteCode}
                        onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
                        placeholder={tr("请输入邀请码", "Enter invitation code")}
                        className="flex-1 rounded-sm border border-ink/20 px-3 py-2 text-sm font-mono uppercase"
                        onKeyDown={(e) => {
                          if (e.key === "Enter" && !redeeming) {
                            handleRedeemInviteCode();
                          }
                        }}
                      />
                      <Button onClick={handleRedeemInviteCode} disabled={redeeming || !inviteCode.trim()}>
                        {redeeming ? (
                          <>
                            <Loader2 size={14} className="animate-spin mr-1" />
                            {tr("兑换中...", "Redeeming...")}
                          </>
                        ) : (
                          tr("兑换额度", "Redeem")
                        )}
                      </Button>
                    </div>
                  </Field>
                </div>
              </div>
            )}

            {/* 自定义密钥模式 */}
            {quotaMode === "custom" && (
              <div className="space-y-4">
                <div className="p-3 rounded-sm border border-ink/20 bg-paper-dark">
                  <p className="text-xs text-ink-light">
                    {tr(
                      "💡 在此模式下，设备渲染将不消耗平台的免费额度，使用您自己的 API Key 进行调用。",
                      "💡 In this mode, device rendering will not consume platform free quota, using your own API Key for calls."
                    )}
                </p>
                </div>

                {/* 文本大模型接入模式切换：预设 vs 自定义 OpenAI 格式 */}
                <div className="flex gap-2 border-b border-ink/10 pb-2">
                  <button
                    onClick={() => {
                      setLlmAccessMode("preset");
                      // 回到预设模式时，确保 provider 合法并触发 model 自动回退
                      if (!llmProvider.trim() || llmProvider === "openai_compat") setLlmProvider("deepseek");
                      // 预设模式不使用 base_url，清空避免误提交
                      setLlmBaseUrl("");
                    }}
                    className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                      llmAccessMode === "preset"
                        ? "text-ink border-b-2 border-ink"
                        : "text-ink-light hover:text-ink"
                    }`}
                  >
                    {tr("预设服务商", "Preset")}
                  </button>
                  <button
                    onClick={() => {
                      setLlmAccessMode("custom_openai");
                      setLlmProvider("openai_compat");
                    }}
                    className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                      llmAccessMode === "custom_openai"
                        ? "text-ink border-b-2 border-ink"
                        : "text-ink-light hover:text-ink"
                    }`}
                  >
                    {tr("自定义 OpenAI 格式", "Custom OpenAI")}
                  </button>
                </div>

                {llmAccessMode === "preset" ? (
                  <>
                    <Field label={tr("API 服务商", "API Provider")}>
                      <select
                        value={llmProvider}
                        onChange={(e) => setLlmProvider(e.target.value)}
                        className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
                      >
                        <option value="aliyun">{tr("阿里百炼", "Alibaba Bailian")}</option>
                        <option value="deepseek">DeepSeek</option>
                      </select>
                    </Field>
                    <Field label={tr("模型名称", "Model Name")}>
                      <select
                        value={llmModel}
                        onChange={(e) => setLlmModel(e.target.value)}
                        className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
                      >
                        {llmProvider === "aliyun" ? (
                          <>
                            <option value="qwen3.5-flash">qwen3.5-flash</option>
                            <option value="deepseek-v3.2">deepseek-v3.2</option>
                            <option value="Moonshot-Kimi-K2-Instruct">Moonshot-Kimi-K2-Instruct</option>
                          </>
                        ) : (
                          <>
                            <option value="deepseek-chat">deepseek-chat</option>
                            <option value="deepseek-reasoner">deepseek-reasoner</option>
                          </>
                        )}
                      </select>
                    </Field>
                    <Field label={tr("API Key", "API Key")}>
                      <input
                        type="password"
                        value={llmApiKey}
                        onChange={(e) => setLlmApiKey(e.target.value)}
                        placeholder={tr("请输入您的 API Key", "Enter your API Key")}
                        className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white font-mono"
                        autoComplete="off"
                      />
                    </Field>
                  </>
                ) : (
                  <>
                    <Field label={tr("模型名称", "Model Name")}>
                      <input
                        type="text"
                        value={llmModel}
                        onChange={(e) => setLlmModel(e.target.value)}
                        placeholder={tr("例如：gpt-4o-mini", "e.g. gpt-4o-mini")}
                        className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white font-mono"
                      />
                    </Field>
                    <Field label={tr("API Key", "API Key")}>
                      <input
                        type="password"
                        value={llmApiKey}
                        onChange={(e) => setLlmApiKey(e.target.value)}
                        placeholder={tr("请输入您的 API Key", "Enter your API Key")}
                        className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white font-mono"
                        autoComplete="off"
                      />
                    </Field>
                    <Field label={tr("Base URL（必填）", "Base URL (Required)")}>
                      <input
                        type="text"
                        value={llmBaseUrl}
                        onChange={(e) => setLlmBaseUrl(e.target.value)}
                        placeholder={tr("例如：https://api.openai.com/v1", "e.g. https://api.openai.com/v1")}
                        className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white font-mono"
                      />
                    </Field>
                  </>
                )}
                
                <div className="pt-4 border-t border-ink/10">
                  <p className="text-sm font-medium text-ink mb-3">{tr("图像生成 API 配置", "Image Generation API Configuration")}</p>
                </div>
                
                <Field label={tr("图像 API 服务商", "Image API Provider")}>
                  <input
                    type="text"
                    value={imageProvider}
                    onChange={(e) => setImageProvider(e.target.value)}
                    placeholder={tr("例如 aliyun", "e.g. aliyun")}
                    className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
                  />
                </Field>
                <Field label={tr("图像模型名称", "Image Model Name")}>
                  <select
                    value={imageModel}
                    onChange={(e) => setImageModel(e.target.value)}
                    className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
                  >
                    <option value="">{tr("请选择图像模型", "Select image model")}</option>
                    <option value="qwen-image-plus">qwen-image-plus</option>
                    <option value="qwen-image-2.0">qwen-image-2.0</option>
                    <option value="qwen-image-max">qwen-image-max</option>
                  </select>
                </Field>
                <Field label={tr("图像 API Key", "Image API Key")}>
                  <input
                    type="password"
                    value={imageApiKey}
                    onChange={(e) => setImageApiKey(e.target.value)}
                    placeholder={tr("请输入您的图像 API Key（用于生成图片）", "Enter your Image API Key (for image generation)")}
                    className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white font-mono"
                    autoComplete="off"
                  />
                </Field>
                
                <div className="pt-2">
                  <div className="flex items-center gap-2">
                    <Button
                      onClick={handleSaveLlmConfig}
                      disabled={saving || deleting || !isLlmConfigValid}
                      variant="outline"
                      className="bg-white text-ink border-ink/20 hover:bg-ink hover:text-white hover:border-ink active:bg-ink/90"
                    >
                      {saving ? (
                        <>
                          <Loader2 size={14} className="animate-spin mr-1" />
                          {tr("保存中...", "Saving...")}
                        </>
                      ) : (
                        <>
                          <Save size={14} className="mr-1" />
                          {tr("保存配置", "Save Configuration")}
                        </>
                      )}
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => setDeleteConfirmOpen(true)}
                      disabled={saving || deleting}
                      className="bg-white text-ink border-ink/20 hover:bg-ink hover:text-white hover:border-ink active:bg-ink/90"
                    >
                      {deleting ? (
                        <>
                          <Loader2 size={14} className="animate-spin mr-1" />
                          {tr("删除中...", "Deleting...")}
                        </>
                      ) : (
                        tr("删除配置", "Delete Configuration")
                      )}
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Delete confirm modal */}
      {deleteConfirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" onClick={() => (deleting ? null : setDeleteConfirmOpen(false))} />
          <div className="relative z-10 w-[92vw] max-w-md rounded-sm border border-ink/20 bg-white shadow-lg p-4">
            <div className="text-sm font-medium text-ink mb-2">{tr("确认删除", "Confirm deletion")}</div>
            <div className="text-sm text-ink-light">
              {tr("确定要删除自定义配置吗？删除后将使用平台免费额度。", "Are you sure you want to delete the custom configuration? After deletion, platform free quota will be used.")}
            </div>
            <div className="mt-4 flex items-center justify-end gap-2">
              <Button
                variant="ghost"
                onClick={() => setDeleteConfirmOpen(false)}
                disabled={deleting}
              >
                {tr("取消", "Cancel")}
              </Button>
              <Button
                onClick={handleDeleteLlmConfig}
                disabled={deleting}
                className="bg-red-600 text-white hover:bg-red-700 border border-red-600"
              >
                {deleting ? (
                  <>
                    <Loader2 size={14} className="animate-spin mr-1" />
                    {tr("删除中...", "Deleting...")}
                  </>
                ) : (
                  tr("确认删除", "Delete")
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Toast */}
      {toast && (
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
      )}
    </div>
  );
}
