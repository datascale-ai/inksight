"use client";

import { useEffect } from "react";

type ErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function GlobalError({ error, reset }: ErrorProps) {
  useEffect(() => {
    console.error("Global route error", error);
  }, [error]);

  return (
    <html lang="zh-CN">
      <body className="min-h-screen bg-neutral-50 text-neutral-900">
        <main className="mx-auto flex min-h-screen max-w-2xl flex-col items-start justify-center gap-4 px-6">
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-neutral-500">
            InkSight
          </p>
          <h1 className="text-3xl font-semibold">页面加载失败</h1>
          <p className="max-w-xl text-sm leading-6 text-neutral-600">
            出现了未处理错误。可以重试当前路由，或稍后刷新页面。
          </p>
          <button
            type="button"
            onClick={reset}
            className="rounded-full bg-neutral-900 px-5 py-2 text-sm font-medium text-white"
          >
            重试
          </button>
        </main>
      </body>
    </html>
  );
}
