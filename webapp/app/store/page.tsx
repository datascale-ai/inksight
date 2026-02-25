"use client";

import { useState, useEffect, useCallback } from "react";
import { Search } from "lucide-react";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface Plugin {
  mode_id: string;
  display_name: string;
  description: string;
  author: string;
  category: string;
  preview_url?: string;
  definition_url: string;
  downloads?: number;
}

export default function StorePage() {
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [filtered, setFiltered] = useState<Plugin[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [installing, setInstalling] = useState<string | null>(null);
  const [installed, setInstalled] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetchPlugins();
  }, []);

  useEffect(() => {
    if (!search.trim()) {
      setFiltered(plugins);
    } else {
      const q = search.toLowerCase();
      setFiltered(
        plugins.filter(
          (p) =>
            p.display_name.toLowerCase().includes(q) ||
            p.description.toLowerCase().includes(q) ||
            p.category.toLowerCase().includes(q)
        )
      );
    }
  }, [search, plugins]);

  async function fetchPlugins() {
    setLoading(true);
    setError("");
    try {
      const resp = await fetch("/api/store");
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setPlugins(data.plugins || []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load plugins");
      setPlugins([]);
    } finally {
      setLoading(false);
    }
  }

  const installPlugin = useCallback(async (plugin: Plugin) => {
    setInstalling(plugin.mode_id);
    try {
      const defResp = await fetch(
        `/api/store/plugin?url=${encodeURIComponent(plugin.definition_url)}`
      );
      if (!defResp.ok) throw new Error("Failed to fetch plugin definition");
      const modeDef = await defResp.json();

      const apiBase = process.env.NEXT_PUBLIC_API_BASE || "";
      const installResp = await fetch(`${apiBase}/api/modes/custom`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(modeDef),
      });
      if (!installResp.ok) throw new Error("Install failed");

      setInstalled((prev) => new Set([...prev, plugin.mode_id]));
    } catch (e: unknown) {
      alert(`安装失败: ${e instanceof Error ? e.message : "Unknown error"}`);
    } finally {
      setInstalling(null);
    }
  }, []);

  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      {/* Page Header */}
      <div className="text-center mb-12">
        <h1 className="font-serif text-3xl md:text-4xl font-bold text-ink mb-3">
          插件商店
        </h1>
        <p className="text-ink-light max-w-lg mx-auto">
          发现和安装社区贡献的内容模式
        </p>
      </div>

      {/* Search Bar */}
      <div className="relative max-w-2xl mx-auto mb-12">
        <Search
          size={18}
          className="absolute left-4 top-1/2 -translate-y-1/2 text-ink-light"
        />
        <input
          type="text"
          placeholder="搜索插件..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-11 pr-4 py-3 rounded-sm border border-ink/10 bg-white text-sm text-ink placeholder:text-ink-light/60 focus:outline-none focus:border-ink/30 transition-colors"
        />
      </div>

      {loading && (
        <div className="text-center py-20 text-ink-light">
          <div className="animate-spin w-8 h-8 border-2 border-ink border-t-transparent rounded-full mx-auto mb-4" />
          加载插件中...
        </div>
      )}

      {error && (
        <div className="text-center py-20">
          <p className="text-red-500 mb-4">{error}</p>
          <Button onClick={fetchPlugins} size="sm">
            重试
          </Button>
        </div>
      )}

      {!loading && !error && filtered.length === 0 && (
        <div className="text-center py-20 text-ink-light">
          {search ? "没有找到匹配的插件" : "暂无可用插件"}
        </div>
      )}

      {!loading && !error && filtered.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {filtered.map((plugin) => (
            <Card
              key={plugin.mode_id}
              className="flex flex-col group hover:border-ink/20 transition-all duration-200"
            >
              {plugin.preview_url ? (
                <div className="h-40 bg-paper-dark border-b border-ink/5 flex items-center justify-center overflow-hidden">
                  <img
                    src={plugin.preview_url}
                    alt={plugin.display_name}
                    className="w-full h-full object-cover"
                  />
                </div>
              ) : (
                <div className="h-40 bg-paper-dark border-b border-ink/5 flex items-center justify-center">
                  <span className="text-ink/20 text-4xl font-serif">墨</span>
                </div>
              )}
              <CardContent className="flex-1 p-5">
                <div className="flex items-start justify-between gap-2 mb-2">
                  <h3 className="text-base font-semibold text-ink">
                    {plugin.display_name}
                  </h3>
                  <span className="text-[10px] px-2 py-0.5 rounded-sm bg-paper-dark text-ink-light shrink-0">
                    {plugin.category}
                  </span>
                </div>
                <p className="text-xs text-ink-light mb-3 line-clamp-2">
                  {plugin.description}
                </p>
                <p className="text-xs text-ink-light">
                  by{" "}
                  <span className="text-ink-muted font-medium">
                    @{plugin.author}
                  </span>
                </p>
              </CardContent>
              <CardFooter className="p-5 pt-0 flex items-center justify-between">
                {plugin.downloads != null && (
                  <span className="text-xs text-ink-light">
                    {plugin.downloads >= 1000
                      ? `${(plugin.downloads / 1000).toFixed(1)}k`
                      : plugin.downloads}{" "}
                    下载
                  </span>
                )}
                <div className={plugin.downloads != null ? "" : "ml-auto"}>
                  <Button
                    size="sm"
                    variant={installed.has(plugin.mode_id) ? "ghost" : "default"}
                    disabled={
                      installing === plugin.mode_id ||
                      installed.has(plugin.mode_id)
                    }
                    onClick={() => installPlugin(plugin)}
                    className={
                      installed.has(plugin.mode_id)
                        ? "text-green-600 hover:text-green-600 cursor-default"
                        : ""
                    }
                  >
                    {installed.has(plugin.mode_id)
                      ? "已安装 ✓"
                      : installing === plugin.mode_id
                        ? "安装中..."
                        : "安装"}
                  </Button>
                </div>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
