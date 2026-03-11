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
  const next = searchParams.get("next") || `/${locale}/config`;
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const [successMsg, setSuccessMsg] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccessMsg("");
    setLoading(true);
    try {
      const endpoint = mode === "register" ? "/api/auth/register" : "/api/auth/login";
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
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
      if (data.token) setToken(data.token);
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
              <label className="block text-sm font-medium text-ink mb-1">{locale === "en" ? "Username" : "用户名"}</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                minLength={2}
                maxLength={30}
                autoComplete="username"
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
