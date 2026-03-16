"use client";

import { useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2 } from "lucide-react";
import { setToken } from "@/lib/auth";
import { localeFromPathname } from "@/lib/i18n";

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
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const [successMsg, setSuccessMsg] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccessMsg("");
    setLoading(true);
    try {
      // 基础前端校验：注册时强制要求手机号/邮箱（邀请码可选）
      if (mode === "register") {
        if (!phone.trim() && !email.trim()) {
          setError(locale === "en" ? "Please enter phone or email" : "手机号或邮箱至少填写一个");
          setLoading(false);
          return;
        }
      }

      const endpoint = mode === "register" ? "/api/auth/register" : "/api/auth/login";
      const payload: Record<string, string> = { username, password };
      if (mode === "register" && phone.trim()) payload.phone = phone.trim();
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
        return;
      }
      if (data.token) {
        setToken(data.token);
        // Set ink_session cookie for frontend domain (localhost:3000)
        const maxAge = 30 * 24 * 60 * 60; // 30 days (same as backend JWT_EXPIRE_DAYS)
        document.cookie = `ink_session=${data.token}; path=/; max-age=${maxAge}; SameSite=Lax`;
        console.log("[LOGIN] Set ink_session cookie for frontend");
      }
      
      // Handle redirect: if redirect_url exists (external URL), use window.location.href
      // Otherwise, use Next.js router for internal routes
      if (redirectUrl) {
        // Check if it's an external URL (starts with http:// or https://)
        const trimmedUrl = redirectUrl.trim();
        if (trimmedUrl.startsWith("http://") || trimmedUrl.startsWith("https://")) {
          // External URL (cross-port/cross-domain) - append token to URL for backend to set cookie
          // Backend will detect the token parameter, set the cookie, and redirect to the original URL
          try {
            const urlObj = new URL(trimmedUrl);
            urlObj.searchParams.set("_token", data.token);
            const redirectWithToken = urlObj.toString();
            
            // Redirect to backend with token parameter
            window.location.href = redirectWithToken;
          } catch (e) {
            console.warn("[LOGIN] Failed to parse redirect URL:", e);
            // Fallback: redirect without token
            window.location.href = trimmedUrl;
          }
          return;
        }
      }
      // Internal route - use Next.js router (only if no redirectUrl or redirectUrl is not external)
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
            {mode === "login" ? (locale === "en" ? "Sign In" : "登录") : (locale === "en" ? "Sign Up" : "注册")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
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
                autoComplete={mode === "register" ? "new-password" : "current-password"}
                className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm"
              />
            </div>
            {mode === "register" && (
              <div className="grid grid-cols-1 gap-3">
                <div>
                  <label className="block text-sm font-medium text-ink mb-1">
                    {locale === "en" ? "Phone" : "手机号"}
                  </label>
                  <input
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    autoComplete="tel"
                    placeholder={
                      locale === "en"
                        ? "Required: at least phone or email"
                        : "与邮箱至少填一项，用于找回账号"
                    }
                    className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-ink mb-1">
                    {locale === "en" ? "Email" : "邮箱"}
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    autoComplete="email"
                    placeholder={
                      locale === "en"
                        ? "Required: at least phone or email"
                        : "与手机号至少填一项，用于找回账号"
                    }
                    className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm"
                  />
                </div>
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
              {mode === "login" ? (locale === "en" ? "Sign In" : "登录") : (locale === "en" ? "Sign Up" : "注册")}
            </Button>
          </form>
          <div className="mt-4 text-center text-sm text-ink-light">
            {mode === "login" ? (
              <span>
                {locale === "en" ? "No account?" : "没有账号？"}{" "}
                <button onClick={() => { setMode("register"); setError(""); }} className="text-ink underline">
                  {locale === "en" ? "Sign up" : "注册"}
                </button>
              </span>
            ) : (
              <span>
                {locale === "en" ? "Already have an account?" : "已有账号？"}{" "}
                <button onClick={() => { setMode("login"); setError(""); }} className="text-ink underline">
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
