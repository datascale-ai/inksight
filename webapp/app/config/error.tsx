"use client";

import { useEffect } from "react";

type ErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function ConfigError({ error, reset }: ErrorProps) {
  useEffect(() => {
    console.error("Config page error", error);
  }, [error]);

  return (
    <div className="mx-auto flex min-h-[60vh] max-w-3xl flex-col justify-center gap-4 px-6 py-16">
      <p className="text-sm font-medium uppercase tracking-[0.2em] text-neutral-500">
        Config
      </p>
      <h2 className="text-3xl font-semibold text-neutral-900">配置页暂时不可用</h2>
      <p className="max-w-2xl text-sm leading-6 text-neutral-600">
        配置数据加载或渲染时发生异常。可以直接重试当前路由，避免整站白屏。
      </p>
      <div>
        <button
          type="button"
          onClick={reset}
          className="rounded-full bg-neutral-900 px-5 py-2 text-sm font-medium text-white"
        >
          重新加载配置页
        </button>
      </div>
    </div>
  );
}
