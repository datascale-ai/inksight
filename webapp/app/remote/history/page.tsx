"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Star, Filter } from "lucide-react";

interface HistoryItem {
  id: number;
  mode_id: string;
  content: Record<string, unknown>;
  is_favorite: boolean;
  time: string;
}

interface FavoriteItem {
  id: number;
  mode_id: string;
  content: Record<string, unknown>;
  time: string;
}

const MODE_LABELS: Record<string, string> = {
  STOIC: "斯多葛箴言", ROAST: "精准吐槽", ZEN: "一字禅",
  DAILY: "每日杂学", BRIEFING: "科技简报", ARTWALL: "AI画廊",
  RECIPE: "今日食谱", FITNESS: "健身计划", POETRY: "每日诗词",
  COUNTDOWN: "倒计时", ALMANAC: "老黄历", LETTER: "慢信",
  THISDAY: "今日历史", RIDDLE: "每日一谜", QUESTION: "每日一问",
  BIAS: "认知偏差", STORY: "微故事", LIFEBAR: "人生进度条",
  CHALLENGE: "微挑战",
};

function getContentPreview(content: Record<string, unknown>): string {
  const keys = ["quote", "question", "challenge", "body", "word",
    "opening", "event_title", "name_cn", "title", "greeting"];
  for (const key of keys) {
    if (content[key] && typeof content[key] === "string") {
      return (content[key] as string).substring(0, 100);
    }
  }
  const vals = Object.values(content);
  if (vals.length > 0 && typeof vals[0] === "string") {
    return (vals[0] as string).substring(0, 100);
  }
  return "";
}

function HistoryContent() {
  const searchParams = useSearchParams();
  const mac = searchParams.get("mac") || "";
  const [tab, setTab] = useState<"history" | "favorites">("history");
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [favorites, setFavorites] = useState<FavoriteItem[]>([]);
  const [modeFilter, setModeFilter] = useState("");
  const [loading, setLoading] = useState(false);

  const apiBase = typeof window !== "undefined" ? window.location.origin : "";

  useEffect(() => {
    if (!mac) return;
    let cancelled = false;
    async function fetchData() {
      setLoading(true);
      try {
        if (tab === "history") {
          let url = `${apiBase}/api/device/${mac}/history?limit=50`;
          if (modeFilter) url += `&mode=${modeFilter}`;
          const res = await fetch(url);
          if (!cancelled && res.ok) {
            const data = await res.json();
            setHistory(data.history || []);
          }
        } else {
          const res = await fetch(`${apiBase}/api/device/${mac}/favorites?limit=50`);
          if (!cancelled && res.ok) {
            const data = await res.json();
            setFavorites(data.favorites || []);
          }
        }
      } catch { /* ignore */ }
      if (!cancelled) setLoading(false);
    }
    fetchData();
    return () => { cancelled = true; };
  }, [tab, mac, modeFilter, apiBase]);

  if (!mac) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <p className="text-gray-400 text-sm">请先在遥控器页面连接设备</p>
      </div>
    );
  }

  const groupByDate = (items: { time: string }[]) => {
    const groups: Record<string, typeof items> = {};
    items.forEach((item) => {
      const date = item.time.split("T")[0];
      if (!groups[date]) groups[date] = [];
      groups[date].push(item);
    });
    return groups;
  };

  return (
    <div className="px-6 pt-6">
      <h1 className="text-lg font-bold mb-4">内容时光机</h1>

      {/* Tab bar */}
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setTab("history")}
          className={`flex-1 py-2.5 text-sm font-medium rounded-xl transition-colors ${
            tab === "history"
              ? "bg-black text-white"
              : "bg-white text-gray-500 border border-gray-200"
          }`}
        >
          全部记录
        </button>
        <button
          onClick={() => setTab("favorites")}
          className={`flex-1 py-2.5 text-sm font-medium rounded-xl transition-colors ${
            tab === "favorites"
              ? "bg-black text-white"
              : "bg-white text-gray-500 border border-gray-200"
          }`}
        >
          <Star className="w-3.5 h-3.5 inline mr-1" />
          收藏
        </button>
      </div>

      {/* Mode filter (history only) */}
      {tab === "history" && (
        <div className="flex items-center gap-2 mb-4">
          <Filter className="w-4 h-4 text-gray-400" />
          <select
            value={modeFilter}
            onChange={(e) => setModeFilter(e.target.value)}
            className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:border-black"
          >
            <option value="">全部模式</option>
            {Object.keys(MODE_LABELS).map((m) => (
              <option key={m} value={m}>
                {m} {MODE_LABELS[m]}
              </option>
            ))}
          </select>
        </div>
      )}

      {loading && (
        <div className="text-center py-8 text-sm text-gray-400">加载中...</div>
      )}

      {/* History list */}
      {tab === "history" && !loading && (
        <div>
          {history.length === 0 ? (
            <div className="text-center py-12 text-sm text-gray-400">
              暂无内容记录
            </div>
          ) : (
            Object.entries(groupByDate(history)).map(([date, items]) => (
              <div key={date} className="mb-6">
                <div className="text-xs text-gray-400 font-medium mb-2">
                  {date}
                </div>
                <div className="space-y-2">
                  {(items as HistoryItem[]).map((item) => (
                    <div
                      key={item.id}
                      className="bg-white border border-gray-200 rounded-xl p-4"
                    >
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs font-semibold bg-gray-100 text-gray-700 px-2 py-0.5 rounded">
                          {item.mode_id}
                        </span>
                        <div className="flex items-center gap-2">
                          {item.is_favorite && (
                            <Star className="w-3.5 h-3.5 text-yellow-500 fill-yellow-500" />
                          )}
                          <span className="text-xs text-gray-400">
                            {item.time.split("T")[1]?.substring(0, 5)}
                          </span>
                        </div>
                      </div>
                      <p className="text-sm text-gray-600 line-clamp-2">
                        {getContentPreview(item.content)}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Favorites grid */}
      {tab === "favorites" && !loading && (
        <div>
          {favorites.length === 0 ? (
            <div className="text-center py-12 text-sm text-gray-400">
              <Star className="w-8 h-8 mx-auto mb-2 text-gray-300" />
              暂无收藏
              <br />
              <span className="text-xs">三击设备按钮或点击遥控器的收藏按钮</span>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3">
              {favorites.map((item) => (
                <div
                  key={item.id}
                  className="bg-white border border-gray-200 rounded-xl p-4"
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-semibold bg-yellow-50 text-yellow-700 px-2 py-0.5 rounded">
                      <Star className="w-3 h-3 inline mr-0.5 fill-yellow-500 text-yellow-500" />
                      {item.mode_id}
                    </span>
                    <span className="text-xs text-gray-400">
                      {item.time.split("T")[0]}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600 line-clamp-3">
                    {getContentPreview(item.content)}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function HistoryPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center min-h-[60vh]"><p className="text-gray-400 text-sm">加载中...</p></div>}>
      <HistoryContent />
    </Suspense>
  );
}
