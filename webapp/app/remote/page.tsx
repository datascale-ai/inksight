"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import {
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Heart,
  Loader2,
} from "lucide-react";

const ALL_MODES = [
  "STOIC", "ROAST", "ZEN", "DAILY", "BRIEFING", "ARTWALL",
  "RECIPE", "FITNESS", "POETRY", "COUNTDOWN",
  "ALMANAC", "LETTER", "THISDAY", "RIDDLE", "QUESTION",
  "BIAS", "STORY", "LIFEBAR", "CHALLENGE",
  "WEATHER", "MEMO", "HABIT",
];

const MODE_LABELS: Record<string, string> = {
  STOIC: "斯多葛箴言", ROAST: "精准吐槽", ZEN: "一字禅",
  DAILY: "每日杂学", BRIEFING: "科技简报", ARTWALL: "AI画廊",
  RECIPE: "今日食谱", FITNESS: "健身计划", POETRY: "每日诗词",
  COUNTDOWN: "倒计时", ALMANAC: "老黄历", LETTER: "慢信",
  THISDAY: "今日历史", RIDDLE: "每日一谜", QUESTION: "每日一问",
  BIAS: "认知偏差", STORY: "微故事", LIFEBAR: "人生进度条",
  CHALLENGE: "微挑战",
  WEATHER: "天气看板", MEMO: "便签留言", HABIT: "习惯打卡",
};

function RemoteContent() {
  const searchParams = useSearchParams();
  const [mac, setMac] = useState(searchParams.get("mac") || "");
  const [macInput, setMacInput] = useState(mac);
  const [currentMode, setCurrentMode] = useState("");
  const [modes, setModes] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [connected, setConnected] = useState(false);

  const apiBase = typeof window !== "undefined" ? window.location.origin : "";

  useEffect(() => {
    if (!mac) return;
    let cancelled = false;
    async function fetchDeviceState() {
      try {
        const stateRes = await fetch(`${apiBase}/api/device/${mac}/state`);
        if (cancelled) return;
        if (stateRes.ok) {
          const state = await stateRes.json();
          setCurrentMode(state.last_persona || "");
          setConnected(true);
        }

        const configRes = await fetch(`${apiBase}/api/config/${mac}`);
        if (cancelled) return;
        if (configRes.ok) {
          const config = await configRes.json();
          setModes(config.modes || ALL_MODES);
        }
      } catch {
        if (!cancelled) setConnected(false);
      }
    }
    fetchDeviceState();
    return () => { cancelled = true; };
  }, [mac, apiBase]);

  const showFeedback = (msg: string) => {
    setFeedback(msg);
    setTimeout(() => setFeedback(""), 2000);
  };

  const switchMode = async (mode: string) => {
    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/api/device/${mac}/switch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      });
      if (res.ok) {
        setCurrentMode(mode);
        showFeedback(`已切换到 ${MODE_LABELS[mode] || mode}`);
      }
    } catch {
      showFeedback("切换失败");
    }
    setLoading(false);
  };

  const navigateMode = (direction: number) => {
    if (modes.length === 0) return;
    const idx = modes.indexOf(currentMode);
    const nextIdx = idx < 0 ? 0 : (idx + direction + modes.length) % modes.length;
    switchMode(modes[nextIdx]);
  };

  const triggerRefresh = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/api/device/${mac}/refresh`, {
        method: "POST",
      });
      if (res.ok) showFeedback("刷新指令已发送");
    } catch {
      showFeedback("发送失败");
    }
    setLoading(false);
  };

  const triggerFavorite = async () => {
    try {
      const res = await fetch(`${apiBase}/api/device/${mac}/favorite`, {
        method: "POST",
      });
      if (res.ok) showFeedback("已收藏当前内容 ♥");
    } catch {
      showFeedback("收藏失败");
    }
  };

  const connectDevice = () => {
    const trimmed = macInput.trim();
    if (trimmed) {
      setMac(trimmed);
      window.history.replaceState(null, "", `/remote?mac=${encodeURIComponent(trimmed)}`);
    }
  };

  if (!mac) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] px-6">
        <div className="w-14 h-14 bg-black rounded-2xl flex items-center justify-center mb-4">
          <span className="text-white text-xl font-bold font-serif">墨</span>
        </div>
        <h1 className="text-xl font-bold mb-1">InkSight Remote</h1>
        <p className="text-gray-500 text-sm mb-6">输入设备 MAC 地址开始遥控</p>
        <div className="w-full max-w-xs space-y-3">
          <input
            type="text"
            value={macInput}
            onChange={(e) => setMacInput(e.target.value)}
            placeholder="例如: 88:56:A6:7B:C7:0C"
            className="w-full px-4 py-3 text-sm border border-gray-300 rounded-xl bg-white focus:border-black focus:outline-none"
            onKeyDown={(e) => e.key === "Enter" && connectDevice()}
          />
          <button
            onClick={connectDevice}
            className="w-full py-3 text-sm font-semibold text-white bg-black rounded-xl hover:bg-gray-800 transition-colors"
          >
            连接设备
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="px-6 pt-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-lg font-bold">InkSight Remote</h1>
          <p className="text-xs text-gray-400">
            {connected ? (
              <span className="text-green-600">● 已连接</span>
            ) : (
              <span className="text-gray-400">○ 未连接</span>
            )}{" "}
            · {mac.replace(/:/g, "").slice(-6)}
          </p>
        </div>
        <button
          onClick={() => window.location.reload()}
          className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
        >
          <RefreshCw className="w-4 h-4 text-gray-500" />
        </button>
      </div>

      {/* Current mode display */}
      <div className="bg-white rounded-2xl border border-gray-200 p-6 mb-6 text-center">
        <div className="text-xs text-gray-400 mb-2">当前模式</div>
        <div className="text-2xl font-bold mb-1">
          {currentMode || "—"}
        </div>
        <div className="text-sm text-gray-500">
          {MODE_LABELS[currentMode] || ""}
        </div>
      </div>

      {/* Mode navigation */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => navigateMode(-1)}
          className="flex-shrink-0 w-12 h-12 bg-white border border-gray-200 rounded-xl flex items-center justify-center hover:bg-gray-50 active:scale-95 transition-all"
        >
          <ChevronLeft className="w-5 h-5" />
        </button>
        <div className="flex-1 overflow-x-auto">
          <div className="flex gap-2 pb-1">
            {modes.map((mode) => (
              <button
                key={mode}
                onClick={() => switchMode(mode)}
                className={`flex-shrink-0 px-3 py-2 text-xs rounded-lg border transition-all ${
                  mode === currentMode
                    ? "bg-black text-white border-black"
                    : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
                }`}
              >
                {mode}
              </button>
            ))}
          </div>
        </div>
        <button
          onClick={() => navigateMode(1)}
          className="flex-shrink-0 w-12 h-12 bg-white border border-gray-200 rounded-xl flex items-center justify-center hover:bg-gray-50 active:scale-95 transition-all"
        >
          <ChevronRight className="w-5 h-5" />
        </button>
      </div>

      {/* Action buttons */}
      <div className="grid grid-cols-2 gap-3 mb-6">
        <button
          onClick={triggerRefresh}
          disabled={loading}
          className="flex items-center justify-center gap-2 py-4 bg-black text-white rounded-2xl font-semibold text-sm hover:bg-gray-800 active:scale-[0.98] transition-all disabled:opacity-60"
        >
          {loading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <RefreshCw className="w-4 h-4" />
          )}
          立即刷新
        </button>
        <button
          onClick={triggerFavorite}
          className="flex items-center justify-center gap-2 py-4 bg-white border border-gray-200 text-gray-700 rounded-2xl font-semibold text-sm hover:bg-gray-50 active:scale-[0.98] transition-all"
        >
          <Heart className="w-4 h-4" />
          收藏内容
        </button>
      </div>

      {/* Feedback toast */}
      {feedback && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 bg-black text-white px-6 py-3 rounded-xl text-sm font-medium shadow-lg z-50 animate-in fade-in slide-in-from-top-2">
          {feedback}
        </div>
      )}
    </div>
  );
}

export default function RemotePage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center min-h-[60vh]"><p className="text-gray-400 text-sm">加载中...</p></div>}>
      <RemoteContent />
    </Suspense>
  );
}
