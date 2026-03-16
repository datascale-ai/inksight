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
    provider: string;
    model: string;
    api_key: string;
    base_url: string;
    image_provider?: string;
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
  const [llmProvider, setLlmProvider] = useState("deepseek");
  const [llmModel, setLlmModel] = useState("");
  const [llmApiKey, setLlmApiKey] = useState("");
  const [llmBaseUrl, setLlmBaseUrl] = useState("");
  const [imageProvider, setImageProvider] = useState("aliyun");
  const [imageApiKey, setImageApiKey] = useState("");
  const [inviteCode, setInviteCode] = useState("");

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
    const onFocus = () => refreshCurrentUser();
    window.addEventListener("focus", onFocus);
    return () => {
      off();
      window.removeEventListener("focus", onFocus);
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
        setLlmProvider(data.llm_config.provider || "deepseek");
        setLlmModel(data.llm_config.model || "");
        setLlmApiKey(data.llm_config.api_key || "");
        setLlmBaseUrl(data.llm_config.base_url || "");
        setImageProvider(data.llm_config.image_provider || "aliyun");
        setImageApiKey(data.llm_config.image_api_key || "");
        setQuotaMode("custom");
      } else {
        setQuotaMode("platform");
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

  const handleSaveLlmConfig = async () => {
    setSaving(true);
    try {
      const res = await fetch("/api/user/profile/llm", {
        method: "PUT",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          provider: llmProvider,
          model: llmModel.trim(),
          api_key: llmApiKey.trim(),
          base_url: llmBaseUrl.trim(),
          image_provider: imageProvider,
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
                <Field label={tr("API 服务商", "API Provider")}>
                  <input
                    type="text"
                    value={llmProvider}
                    onChange={(e) => setLlmProvider(e.target.value)}
                    placeholder={tr("例如 deepseek、aliyun、moonshot", "e.g. deepseek, aliyun, moonshot")}
                    className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
                  />
                </Field>
                <Field label={tr("模型名称", "Model Name")}>
                  <input
                    type="text"
                    value={llmModel}
                    onChange={(e) => setLlmModel(e.target.value)}
                    placeholder={tr("例如 deepseek-chat、qwen-max", "e.g. deepseek-chat, qwen-max")}
                    className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
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
                <Field label={tr("Base URL (可选)", "Base URL (Optional)")}>
                  <input
                    type="text"
                    value={llmBaseUrl}
                    onChange={(e) => setLlmBaseUrl(e.target.value)}
                    placeholder={tr("留空使用默认地址", "Leave empty to use default")}
                    className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
                  />
                </Field>
                
                <div className="pt-4 border-t border-ink/10">
                  <p className="text-sm font-medium text-ink mb-3">{tr("图像生成 API 配置", "Image Generation API Configuration")}</p>
                </div>
                
                <Field label={tr("图像 API 服务商", "Image API Provider")}>
                  <select
                    value={imageProvider}
                    onChange={(e) => setImageProvider(e.target.value)}
                    className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
                  >
                    <option value="aliyun">{tr("阿里百炼", "Alibaba Bailian")}</option>
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
                  <Button onClick={handleSaveLlmConfig} disabled={saving} className="bg-ink text-white hover:bg-ink/90">
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
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

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
