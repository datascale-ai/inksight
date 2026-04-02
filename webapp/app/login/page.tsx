"use client";

import { useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2 } from "lucide-react";
import { setToken } from "@/lib/auth";
import { localeFromPathname } from "@/lib/i18n";

const PHONE_REGION_OPTIONS = [
  { region: "CN", code: "+86", label: "China Mainland", labelZh: "中国大陆" },
  { region: "HK", code: "+852", label: "Hong Kong", labelZh: "中国香港" },
  { region: "TW", code: "+886", label: "Taiwan", labelZh: "中国台湾" },
  { region: "SG", code: "+65", label: "Singapore", labelZh: "新加坡" },
  { region: "JP", code: "+81", label: "Japan", labelZh: "日本" },
  { region: "KR", code: "+82", label: "South Korea", labelZh: "韩国" },
  { region: "US", code: "+1", label: "United States", labelZh: "美国" },
  { region: "CA", code: "+1", label: "Canada", labelZh: "加拿大" },
  { region: "GB", code: "+44", label: "United Kingdom", labelZh: "英国" },
  { region: "DE", code: "+49", label: "Germany", labelZh: "德国" },
  { region: "FR", code: "+33", label: "France", labelZh: "法国" },
  { region: "AU", code: "+61", label: "Australia", labelZh: "澳大利亚" },
  { region: "IN", code: "+91", label: "India", labelZh: "印度" },
] as const;

function LoginForm() {
  const router = useRouter();
  const pathname = usePathname();
  const locale = localeFromPathname(pathname || "/");
  const searchParams = useSearchParams();
  // Support both 'next' (internal route) and 'redirect_url' (external URL)
  // Get redirect_url - useSearchParams should auto-decode, but ensure it's decoded
  const redirectUrlParam = searchParams.get("redirect_url");
  // Decode if needed (handle cases where it might still be encoded)
  let redirectUrl: string | null = null;
  if (redirectUrlParam) {
    try {
      // Try to decode, if it fails it's already decoded
      redirectUrl = decodeURIComponent(redirectUrlParam);
    } catch {
      redirectUrl = redirectUrlParam;
    }
  }
  const next = searchParams.get("next") || `/${locale}/config`;
  const [mode, setMode] = useState<"login" | "register" | "reset">("login");
  const [resetStep, setResetStep] = useState<"email" | "verify">("email");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [phoneRegion, setPhoneRegion] = useState<(typeof PHONE_REGION_OPTIONS)[number]["region"]>("CN");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [verifyCode, setVerifyCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  const [successMsg, setSuccessMsg] = useState("");

  const startCooldown = () => {
    setCooldown(60);
    const timer = setInterval(() => {
      setCooldown((prev) => { if (prev <= 1) { clearInterval(timer); return 0; } return prev - 1; });
    }, 1000);
  };

  const handleResetSendCode = async () => {
    setError("");
    if (!email.trim()) {
      setError(locale === "en" ? "Email is required" : "请输入邮箱");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch("/api/auth/reset-password/send-code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || (locale === "en" ? "Failed to send code" : "发送验证码失败"));
        return;
      }
      setResetStep("verify");
      startCooldown();
    } catch {
      setError(locale === "en" ? "Network error" : "网络错误");
    } finally {
      setLoading(false);
    }
  };

  const handleResetVerify = async () => {
    setError("");
    if (!verifyCode.trim()) {
      setError(locale === "en" ? "Enter verification code" : "请输入验证码");
      return;
    }
    if (password.length < 4) {
      setError(locale === "en" ? "Password must be at least 4 characters" : "密码至少 4 位");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch("/api/auth/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), code: verifyCode.trim(), password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || (locale === "en" ? "Reset failed" : "重置失败"));
        return;
      }
      setSuccessMsg(locale === "en" ? "Password reset successful, please sign in" : "密码重置成功，请登录");
      setMode("login");
      setResetStep("email");
      setPassword("");
      setEmail("");
      setVerifyCode("");
    } catch {
      setError(locale === "en" ? "Network error" : "网络错误");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (mode === "reset") {
      if (resetStep === "email") return handleResetSendCode();
      return handleResetVerify();
    }
    setError("");
    setSuccessMsg("");
    setLoading(true);
    try {
      if (mode === "register" && !email.trim()) {
        setError(locale === "en" ? "Email is required" : "邮箱为必填项");
        setLoading(false);
        return;
      }

      const endpoint = mode === "register" ? "/api/auth/register" : "/api/auth/login";
      const payload: Record<string, string> = { username, password };
      if (mode === "register" && phone.trim()) {
        payload.phone = phone.trim();
        payload.phone_region = phoneRegion;
      }
      if (mode === "register" && email.trim()) payload.email = email.trim();
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || (locale === "en" ? "Operation failed" : "操作失败"));
        return;
      }
      if (mode === "register") {
        setSuccessMsg(locale === "en" ? "Registration successful, please sign in" : "注册成功，请登录");
        setMode("login");
        setPassword("");
        setPhoneRegion("CN");
        setPhone("");
        setEmail("");
        return;
      }
      if (data.token) {
        setToken(data.token);
        const maxAge = 30 * 24 * 60 * 60;
        document.cookie = `ink_session=${data.token}; path=/; max-age=${maxAge}; SameSite=Lax`;
      }
      
      if (redirectUrl) {
        const trimmedUrl = redirectUrl.trim();
        if (trimmedUrl.startsWith("http://") || trimmedUrl.startsWith("https://")) {
          try {
            const urlObj = new URL(trimmedUrl);
            urlObj.searchParams.set("_token", data.token);
            window.location.href = urlObj.toString();
          } catch {
            window.location.href = trimmedUrl;
          }
          return;
        }
      }
      router.push(next);
      router.refresh();
    } catch {
      setError(locale === "en" ? "Network error" : "网络错误");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-sm px-6 py-20">
      <Card>
        <CardHeader>
          <CardTitle className="text-center font-serif text-2xl">
            {mode === "login"
              ? (locale === "en" ? "Sign In" : "登录")
              : mode === "register"
                ? (locale === "en" ? "Sign Up" : "注册")
                : (locale === "en" ? "Reset Password" : "重置密码")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {mode !== "reset" && (
              <>
                <div>
                  <label className="block text-sm font-medium text-ink mb-1">
                    {locale === "en" ? "Username" : "用户名"}
                  </label>
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    required
                    minLength={2}
                    maxLength={30}
                    autoComplete="username"
                    placeholder={
                      locale === "en"
                        ? "Choose a display name"
                        : "用于显示的昵称（非手机号/邮箱）"
                    }
                    className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-ink mb-1">{locale === "en" ? "Password" : "密码"}</label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={4}
                    autoComplete={mode === "login" ? "current-password" : "new-password"}
                    className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm"
                  />
                </div>
              </>
            )}
            {mode === "register" && (
              <div className="grid grid-cols-1 gap-3">
                <div>
                  <label className="block text-sm font-medium text-ink mb-1">
                    {locale === "en" ? "Email" : "邮箱"} <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    autoComplete="email"
                    placeholder={locale === "en" ? "Required, used for account recovery" : "必填，用于找回账号"}
                    className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-ink mb-1">
                    {locale === "en" ? "Phone" : "手机号"}
                    <span className="text-ink-light text-xs ml-1">({locale === "en" ? "optional" : "选填"})</span>
                  </label>
                  <div className="flex w-full flex-col gap-2">
                    <select
                      value={phoneRegion}
                      onChange={(e) => setPhoneRegion(e.target.value as (typeof PHONE_REGION_OPTIONS)[number]["region"])}
                      className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm"
                    >
                      {PHONE_REGION_OPTIONS.map((option) => (
                        <option key={`${option.region}-${option.code}`} value={option.region}>
                          {option.code} {locale === "en" ? option.label : option.labelZh}
                        </option>
                      ))}
                    </select>
                    <input
                      type="tel"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      autoComplete="tel"
                      placeholder={locale === "en" ? "Local phone number" : "本地手机号"}
                      className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm"
                    />
                  </div>
                </div>
              </div>
            )}
            {mode === "reset" && (
              <div className="grid grid-cols-1 gap-3">
                <div>
                  <label className="block text-sm font-medium text-ink mb-1">
                    {locale === "en" ? "Email" : "注册邮箱"}
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    autoComplete="email"
                    disabled={resetStep === "verify"}
                    placeholder={locale === "en" ? "Enter your registered email" : "输入注册时使用的邮箱"}
                    className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm disabled:opacity-50"
                  />
                </div>
                {resetStep === "verify" && (
                  <>
                    <div>
                      <label className="block text-sm font-medium text-ink mb-1">
                        {locale === "en" ? "Verification Code" : "验证码"}
                      </label>
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={verifyCode}
                          onChange={(e) => setVerifyCode(e.target.value)}
                          maxLength={6}
                          placeholder="000000"
                          className="flex-1 rounded-sm border border-ink/20 px-3 py-2 text-sm tracking-widest"
                        />
                        <button
                          type="button"
                          disabled={cooldown > 0 || loading}
                          onClick={handleResetSendCode}
                          className="shrink-0 rounded-sm border border-ink/20 px-3 py-2 text-xs disabled:opacity-50"
                        >
                          {cooldown > 0
                            ? `${cooldown}s`
                            : (locale === "en" ? "Resend" : "重新发送")}
                        </button>
                      </div>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-ink mb-1">
                        {locale === "en" ? "New Password" : "新密码"}
                      </label>
                      <input
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        minLength={4}
                        autoComplete="new-password"
                        className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm"
                      />
                    </div>
                  </>
                )}
              </div>
            )}
            {successMsg && (
              <p className="text-sm text-green-600">{successMsg}</p>
            )}
            {error && (
              <p className="text-sm text-red-600">{error}</p>
            )}
            <Button type="submit" disabled={loading} className="w-full">
              {loading && <Loader2 size={14} className="animate-spin mr-1" />}
              {mode === "login"
                ? (locale === "en" ? "Sign In" : "登录")
                : mode === "register"
                  ? (locale === "en" ? "Sign Up" : "注册")
                  : resetStep === "email"
                    ? (locale === "en" ? "Send Verification Code" : "发送验证码")
                    : (locale === "en" ? "Reset Password" : "重置密码")}
            </Button>
          </form>
          <div className="mt-4 text-center text-sm text-ink-light">
            {mode === "login" ? (
              <div className="space-y-2">
                <div>
                  {locale === "en" ? "No account?" : "没有账号？"}{" "}
                  <button onClick={() => { setMode("register"); setError(""); setSuccessMsg(""); }} className="text-ink underline">
                    {locale === "en" ? "Sign up" : "注册"}
                  </button>
                </div>
                <div>
                  <button onClick={() => { setMode("reset"); setResetStep("email"); setError(""); setSuccessMsg(""); setPassword(""); setEmail(""); setVerifyCode(""); }} className="text-ink underline">
                    {locale === "en" ? "Forgot password?" : "忘记密码？"}
                  </button>
                </div>
              </div>
            ) : (
              <span>
                {mode === "register"
                  ? (locale === "en" ? "Already have an account?" : "已有账号？")
                  : (locale === "en" ? "Remembered your password?" : "想起密码了？")}{" "}
                <button onClick={() => { setMode("login"); setError(""); setSuccessMsg(""); }} className="text-ink underline">
                  {locale === "en" ? "Sign in" : "登录"}
                </button>
              </span>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
