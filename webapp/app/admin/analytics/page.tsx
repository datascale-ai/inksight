"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import Link from "next/link";
import { BarChart3, Cpu, Loader2, MonitorSmartphone, Users, WandSparkles } from "lucide-react";
import { authHeaders } from "@/lib/auth";

type CountRow = { day: string; count?: number; active_users?: number };
type EventRow = { event_name: string; count: number };
type ModeRow = { mode: string; count: number };

type AnalyticsOverview = {
  users: {
    total: number;
    today_new: number;
    new_7d: number;
    new_30d: number;
    with_device: number;
    dau: number;
    wau: number;
    mau: number;
    device_active_24h: number;
  };
  devices: {
    bound: number;
    active_today: number;
    active_7d: number;
    heartbeats_today: number;
  };
  rendering: {
    today: number;
    last_7d: number;
    avg_ms_today: number;
    errors_today: number;
    fallback_today: number;
  };
  content: {
    custom_modes: number;
    shared_modes: number;
    users_with_llm_config: number;
  };
  series: {
    new_users: CountRow[];
    active_devices: CountRow[];
    renders: CountRow[];
    activity_events: CountRow[];
  };
  top: {
    events: EventRow[];
    modes: ModeRow[];
  };
};

function fmt(value: number | null | undefined) {
  return Number(value || 0).toLocaleString();
}

function MetricCard({
  title,
  value,
  note,
  icon,
}: {
  title: string;
  value: number;
  note: string;
  icon: ReactNode;
}) {
  return (
    <div className="rounded-[2rem] border border-stone-200 bg-white/80 p-6 shadow-[0_24px_80px_rgba(66,48,25,0.08)]">
      <div className="flex items-center justify-between gap-4">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-stone-500">{title}</p>
        <div className="rounded-full bg-[#e7f0df] p-2 text-[#365f46]">{icon}</div>
      </div>
      <p className="mt-5 text-4xl font-semibold tracking-[-0.06em] text-stone-950">{fmt(value)}</p>
      <p className="mt-2 text-sm text-stone-500">{note}</p>
    </div>
  );
}

function MiniBars({ rows, valueKey = "count" }: { rows: CountRow[]; valueKey?: "count" | "active_users" }) {
  const ordered = [...rows].reverse();
  const max = Math.max(...ordered.map((row) => Number(row[valueKey] || 0)), 1);
  return (
    <div className="mt-5 flex h-36 items-end gap-2">
      {ordered.map((row) => {
        const value = Number(row[valueKey] || 0);
        return (
          <div key={row.day} className="group flex flex-1 flex-col items-center gap-2">
            <div
              className="w-full rounded-t-full bg-gradient-to-t from-[#315c48] to-[#aecf94]"
              style={{ height: `${Math.max(8, (value / max) * 120)}px` }}
              title={`${row.day}: ${value}`}
            />
            <span className="text-[10px] text-stone-400">{row.day.slice(5)}</span>
          </div>
        );
      })}
    </div>
  );
}

function Ranking({ rows, nameKey }: { rows: Array<EventRow | ModeRow>; nameKey: "event_name" | "mode" }) {
  if (!rows.length) return <p className="mt-4 text-sm text-stone-500">暂无数据，部署后会逐步积累。</p>;
  const max = Math.max(...rows.map((row) => row.count), 1);
  return (
    <div className="mt-5 space-y-3">
      {rows.map((row) => {
        const label = nameKey === "event_name" ? (row as EventRow).event_name : (row as ModeRow).mode;
        return (
          <div key={label}>
            <div className="mb-1 flex items-center justify-between text-sm">
              <span className="font-medium text-stone-700">{label}</span>
              <span className="text-stone-500">{fmt(row.count)}</span>
            </div>
            <div className="h-2 rounded-full bg-stone-100">
              <div className="h-2 rounded-full bg-[#315c48]" style={{ width: `${Math.max(3, (row.count / max) * 100)}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function AdminAnalyticsPage() {
  const [data, setData] = useState<AnalyticsOverview | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const res = await fetch("/api/admin/analytics/overview", {
          cache: "no-store",
          headers: authHeaders(),
        });
        if (res.status === 401) throw new Error("请先登录 root 账号。");
        if (res.status === 403) throw new Error("当前账号没有 root 权限。");
        if (!res.ok) throw new Error(`加载失败：HTTP ${res.status}`);
        const payload = (await res.json()) as AnalyticsOverview;
        if (!cancelled) setData(payload);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "加载失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_8%_0%,#e3efda_0,#fffaf0_34%,#f4eadb_100%)] px-4 py-10 text-stone-950">
      <section className="mx-auto max-w-7xl">
        <div className="mb-8 flex flex-col justify-between gap-5 md:flex-row md:items-end">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.22em] text-[#457052]">InkSight Admin</p>
            <h1 className="mt-3 text-5xl font-semibold tracking-[-0.07em] md:text-7xl">运营看板</h1>
            <p className="mt-4 max-w-2xl text-stone-600">
              统计注册、活跃用户、设备在线、渲染量、页面访问和内容创作。DAU/WAU/MAU 从新埋点启用后开始累积。
            </p>
          </div>
          <Link className="rounded-full border border-stone-300 bg-white/70 px-5 py-3 text-sm font-semibold text-stone-700" href="/profile">
            返回个人中心
          </Link>
        </div>

        {loading ? (
          <div className="flex min-h-96 items-center justify-center rounded-[2rem] bg-white/70">
            <Loader2 className="h-8 w-8 animate-spin text-[#315c48]" />
          </div>
        ) : error ? (
          <div className="rounded-[2rem] border border-red-200 bg-red-50 p-8 text-red-700">{error}</div>
        ) : data ? (
          <div className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <MetricCard title="注册用户" value={data.users.total} note={`今日 +${fmt(data.users.today_new)} / 7日 +${fmt(data.users.new_7d)}`} icon={<Users className="h-5 w-5" />} />
              <MetricCard title="活跃用户" value={data.users.dau} note={`WAU ${fmt(data.users.wau)} / MAU ${fmt(data.users.mau)}`} icon={<BarChart3 className="h-5 w-5" />} />
              <MetricCard title="活跃设备" value={data.devices.active_today} note={`7日 ${fmt(data.devices.active_7d)} / 绑定 ${fmt(data.devices.bound)}`} icon={<MonitorSmartphone className="h-5 w-5" />} />
              <MetricCard title="今日渲染" value={data.rendering.today} note={`7日 ${fmt(data.rendering.last_7d)} / 均值 ${fmt(data.rendering.avg_ms_today)}ms`} icon={<Cpu className="h-5 w-5" />} />
            </div>

            <div className="grid gap-6 xl:grid-cols-3">
              <div className="rounded-[2rem] border border-stone-200 bg-white/80 p-6 xl:col-span-2">
                <p className="text-xs font-bold uppercase tracking-[0.18em] text-stone-500">14 日新增用户</p>
                <MiniBars rows={data.series.new_users} />
              </div>
              <div className="rounded-[2rem] border border-stone-200 bg-white/80 p-6">
                <p className="text-xs font-bold uppercase tracking-[0.18em] text-stone-500">内容创作</p>
                <div className="mt-6 grid grid-cols-3 gap-3 text-center">
                  <div><p className="text-3xl font-semibold">{fmt(data.content.custom_modes)}</p><p className="text-xs text-stone-500">自定义</p></div>
                  <div><p className="text-3xl font-semibold">{fmt(data.content.shared_modes)}</p><p className="text-xs text-stone-500">共享</p></div>
                  <div><p className="text-3xl font-semibold">{fmt(data.content.users_with_llm_config)}</p><p className="text-xs text-stone-500">BYOK</p></div>
                </div>
                <p className="mt-5 rounded-2xl bg-stone-100 p-4 text-sm text-stone-600">
                  设备反推活跃用户 24h：{fmt(data.users.device_active_24h)}。这可和 DAU 对比，判断“只设备在线但未网页登录”的用户规模。
                </p>
              </div>
            </div>

            <div className="grid gap-6 xl:grid-cols-2">
              <div className="rounded-[2rem] border border-stone-200 bg-white/80 p-6">
                <p className="text-xs font-bold uppercase tracking-[0.18em] text-stone-500">7 日热门模式</p>
                <Ranking rows={data.top.modes} nameKey="mode" />
              </div>
              <div className="rounded-[2rem] border border-stone-200 bg-white/80 p-6">
                <p className="text-xs font-bold uppercase tracking-[0.18em] text-stone-500">7 日用户事件</p>
                <Ranking rows={data.top.events} nameKey="event_name" />
              </div>
            </div>

            <div className="grid gap-6 xl:grid-cols-2">
              <div className="rounded-[2rem] border border-stone-200 bg-white/80 p-6">
                <p className="text-xs font-bold uppercase tracking-[0.18em] text-stone-500">14 日活跃设备</p>
                <MiniBars rows={data.series.active_devices} />
              </div>
              <div className="rounded-[2rem] border border-stone-200 bg-white/80 p-6">
                <p className="text-xs font-bold uppercase tracking-[0.18em] text-stone-500">14 日渲染量</p>
                <MiniBars rows={data.series.renders} />
              </div>
            </div>

            <div className="rounded-[2rem] border border-stone-200 bg-white/80 p-6">
              <div className="flex items-center gap-2 text-stone-500">
                <WandSparkles className="h-4 w-4" />
                <p className="text-xs font-bold uppercase tracking-[0.18em]">统计口径</p>
              </div>
              <p className="mt-4 text-sm leading-6 text-stone-600">
                注册数来自 users；DAU/WAU/MAU 来自 user_activity_events；设备活跃来自心跳和渲染日志；渲染量来自 render_logs。
                页面访问事件从本版本部署后开始写入，历史官网访问仍建议用 Nginx 独立 access log 回溯。
              </p>
            </div>
          </div>
        ) : null}
      </section>
    </main>
  );
}
