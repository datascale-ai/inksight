"use client";

import { useEffect, useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import {
  Usb,
  MousePointerClick,
  ListOrdered,
  Zap,
  CheckCircle2,
  AlertCircle,
  Wifi,
  Terminal,
  RefreshCw,
} from "lucide-react";

const steps = [
  {
    icon: Usb,
    title: "连接 USB",
    desc: "使用 USB-C 数据线将 ESP32-C3 开发板连接到电脑",
  },
  {
    icon: MousePointerClick,
    title: "点击连接",
    desc: "点击下方的「连接设备」按钮，浏览器将弹出串口选择窗口",
  },
  {
    icon: ListOrdered,
    title: "选择端口",
    desc: "在弹出窗口中选择你的 ESP32 设备对应的串口",
  },
  {
    icon: Zap,
    title: "开始刷写",
    desc: "固件将自动下载并写入设备，等待进度条完成即可",
  },
];

type FlashStatus =
  | "initializing"
  | "loading_releases"
  | "ready"
  | "connecting"
  | "flashing"
  | "success"
  | "failed";

type FirmwareRelease = {
  version: string;
  tag: string;
  published_at: string | null;
  download_url: string;
  size_bytes: number | null;
  chip_family: string;
  manifest: {
    name: string;
    version: string;
    builds: Array<{
      chipFamily: string;
      parts: Array<{
        path: string;
        offset: number;
      }>;
    }>;
  };
};

const FLASH_STATUS_LABEL: Record<FlashStatus, string> = {
  initializing: "初始化中",
  loading_releases: "加载固件版本中",
  ready: "就绪",
  connecting: "等待串口连接授权",
  flashing: "刷写进行中",
  success: "刷写成功",
  failed: "失败，请重试",
};

export default function FlashPage() {
  const [scriptLoaded, setScriptLoaded] = useState(false);
  const [status, setStatus] = useState<FlashStatus>("initializing");
  const [releases, setReleases] = useState<FirmwareRelease[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<string>("");
  const [manifestUrl, setManifestUrl] = useState<string>("");
  const [releaseError, setReleaseError] = useState<string>("");
  const [manualFirmwareUrl, setManualFirmwareUrl] = useState<string>("");
  const [useManualFirmware, setUseManualFirmware] = useState<boolean>(false);
  const [manualUrlVerified, setManualUrlVerified] = useState<boolean>(false);
  const [manualUrlVerifying, setManualUrlVerifying] = useState<boolean>(false);
  const [manualUrlMessage, setManualUrlMessage] = useState<string>("");
  const [logs, setLogs] = useState<string[]>([
    "[系统] InkSight Web Flasher 已就绪",
    "[提示] 请使用 Chrome 或 Edge 浏览器以获得最佳体验",
    "[提示] 确保已安装 ESP32 USB 驱动程序",
  ]);
  const logEndRef = useRef<HTMLDivElement>(null);
  const installButtonRef = useRef<HTMLElement | null>(null);

  const parseApiJson = async (res: Response) => {
    const contentType = res.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      const text = await res.text();
      const preview = text.slice(0, 80).replace(/\s+/g, " ").trim();
      throw new Error(
        `接口未返回 JSON（HTTP ${res.status}）。请检查 /api/firmware 路由或后端配置。${preview ? ` 响应片段: ${preview}` : ""}`
      );
    }
    return res.json();
  };

  useEffect(() => {
    const script = document.createElement("script");
    script.type = "module";
    script.src =
      "https://unpkg.com/esp-web-tools@10/dist/web/install-button.js?module";
    script.onload = () => {
      setScriptLoaded(true);
      setStatus((prev) => (prev === "loading_releases" ? prev : "ready"));
      setLogs((prev) => [...prev, "[系统] ESP Web Tools 加载完成"]);
    };
    script.onerror = () => {
      setStatus("failed");
      setLogs((prev) => [
        ...prev,
        "[错误] ESP Web Tools 加载失败，请检查网络连接",
      ]);
    };
    document.head.appendChild(script);

    return () => {
      document.head.removeChild(script);
    };
  }, []);

  useEffect(() => {
    const apiBase = process.env.NEXT_PUBLIC_FIRMWARE_API_BASE?.replace(/\/$/, "");
    const endpoint = apiBase
      ? `${apiBase}/api/firmware/releases`
      : "/api/firmware/releases";

    const loadReleases = async () => {
      setStatus("loading_releases");
      setReleaseError("");

      try {
        const res = await fetch(endpoint, { cache: "no-store" });
        const data = await parseApiJson(res);
        if (!res.ok) {
          throw new Error(data?.message || "固件版本接口请求失败");
        }

        const list = (data?.releases || []) as FirmwareRelease[];
        if (!list.length) {
          throw new Error("没有可用的固件版本，请先发布 GitHub Release");
        }

        setReleases(list);
        setSelectedVersion(list[0].version);
        setLogs((prev) => [
          ...prev,
          `[系统] 已加载 ${list.length} 个固件版本，默认选择 v${list[0].version}`,
        ]);
        setStatus(scriptLoaded ? "ready" : "initializing");
      } catch (err) {
        const message = err instanceof Error ? err.message : "加载固件版本失败";
        setReleaseError(message);
        setUseManualFirmware(true);
        setStatus("failed");
        setLogs((prev) => [...prev, `[错误] ${message}`]);
        setLogs((prev) => [...prev, "[提示] 你可以切换到手动 URL 模式继续刷机"]);
      }
    };

    loadReleases();
  }, [scriptLoaded]);

  useEffect(() => {
    if (useManualFirmware) {
      if (!manualFirmwareUrl || !manualUrlVerified) {
        return;
      }
      const manifest = {
        name: "InkSight",
        version: "manual",
        builds: [
          {
            chipFamily: "ESP32-C3",
            parts: [{ path: manualFirmwareUrl, offset: 0 }],
          },
        ],
      };
      const blob = new Blob([JSON.stringify(manifest)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      setManifestUrl(url);
      setLogs((prev) => [...prev, "[系统] 已启用手动固件 URL 刷写模式"]);
      return () => {
        URL.revokeObjectURL(url);
      };
    }

    if (!releases.length || !selectedVersion) {
      return;
    }
    const selected = releases.find((r) => r.version === selectedVersion);
    if (!selected) {
      return;
    }
    const blob = new Blob([JSON.stringify(selected.manifest)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    setManifestUrl(url);
    setLogs((prev) => [...prev, `[系统] 已切换固件版本 v${selected.version}`]);

    return () => {
      URL.revokeObjectURL(url);
    };
  }, [releases, selectedVersion, useManualFirmware, manualFirmwareUrl, manualUrlVerified]);

  useEffect(() => {
    const node = installButtonRef.current;
    if (!node) return;

    const onInstallStart = () => {
      setStatus("flashing");
      setLogs((prev) => [...prev, "[系统] 开始刷写固件，请勿断开 USB 连接"]);
    };
    const onInstallDone = () => {
      setStatus("success");
      setLogs((prev) => [...prev, "[系统] 固件刷写完成，设备即将重启"]);
    };
    const onInstallError = (event: Event) => {
      setStatus("failed");
      const detail = (event as CustomEvent)?.detail;
      const reason = typeof detail === "string" ? detail : "串口连接或刷写失败";
      setLogs((prev) => [...prev, `[错误] ${reason}`]);
    };

    node.addEventListener("state-changed", onInstallStart as EventListener);
    node.addEventListener("install-start", onInstallStart as EventListener);
    node.addEventListener("install-complete", onInstallDone as EventListener);
    node.addEventListener("install-error", onInstallError as EventListener);
    node.addEventListener("error", onInstallError as EventListener);

    return () => {
      node.removeEventListener("state-changed", onInstallStart as EventListener);
      node.removeEventListener("install-start", onInstallStart as EventListener);
      node.removeEventListener("install-complete", onInstallDone as EventListener);
      node.removeEventListener("install-error", onInstallError as EventListener);
      node.removeEventListener("error", onInstallError as EventListener);
    };
  }, [manifestUrl]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const addLog = (msg: string) => {
    setLogs((prev) => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`]);
  };

  const selectedRelease = releases.find((r) => r.version === selectedVersion);
  const sizeMB = selectedRelease?.size_bytes
    ? (selectedRelease.size_bytes / (1024 * 1024)).toFixed(2)
    : null;

  const handleReloadReleases = async () => {
    const apiBase = process.env.NEXT_PUBLIC_FIRMWARE_API_BASE?.replace(/\/$/, "");
    const endpoint = apiBase
      ? `${apiBase}/api/firmware/releases?refresh=true`
      : "/api/firmware/releases?refresh=true";
    setStatus("loading_releases");
    setReleaseError("");
    try {
      const res = await fetch(endpoint, { cache: "no-store" });
      const data = await parseApiJson(res);
      if (!res.ok) {
        throw new Error(data?.message || "刷新固件版本失败");
      }
      const list = (data?.releases || []) as FirmwareRelease[];
      if (!list.length) {
        throw new Error("没有可用固件版本");
      }
      setReleases(list);
      setSelectedVersion(list[0].version);
      setUseManualFirmware(false);
      setStatus(scriptLoaded ? "ready" : "initializing");
      setLogs((prev) => [...prev, "[系统] 已刷新固件版本列表"]);
    } catch (err) {
      const message = err instanceof Error ? err.message : "刷新固件版本失败";
      setReleaseError(message);
      setStatus("failed");
      setLogs((prev) => [...prev, `[错误] ${message}`]);
    }
  };

  const validateManualUrlFormat = (value: string): string | null => {
    if (!value) return "请输入固件 URL";
    let parsed: URL;
    try {
      parsed = new URL(value);
    } catch {
      return "URL 格式不正确";
    }
    if (!["http:", "https:"].includes(parsed.protocol)) {
      return "URL 必须以 http:// 或 https:// 开头";
    }
    if (!parsed.pathname.toLowerCase().endsWith(".bin")) {
      return "URL 必须指向 .bin 固件文件";
    }
    return null;
  };

  const handleVerifyManualUrl = async () => {
    const formatError = validateManualUrlFormat(manualFirmwareUrl);
    if (formatError) {
      setManualUrlVerified(false);
      setManualUrlMessage(formatError);
      setLogs((prev) => [...prev, `[错误] ${formatError}`]);
      return;
    }

    const apiBase = process.env.NEXT_PUBLIC_FIRMWARE_API_BASE?.replace(/\/$/, "");
    const endpoint = apiBase
      ? `${apiBase}/api/firmware/validate-url?url=${encodeURIComponent(manualFirmwareUrl)}`
      : `/api/firmware/validate-url?url=${encodeURIComponent(manualFirmwareUrl)}`;

    setManualUrlVerifying(true);
    setManualUrlMessage("");
    try {
      const res = await fetch(endpoint, { cache: "no-store" });
      const data = await parseApiJson(res);
      if (!res.ok) {
        throw new Error(data?.message || "固件 URL 校验失败");
      }
      setManualUrlVerified(true);
      setManualUrlMessage("链接校验通过，可以开始刷写");
      setLogs((prev) => [...prev, "[系统] 手动固件 URL 校验通过"]);
    } catch (err) {
      const message = err instanceof Error ? err.message : "固件 URL 校验失败";
      setManualUrlVerified(false);
      setManualUrlMessage(message);
      setLogs((prev) => [...prev, `[错误] ${message}`]);
    } finally {
      setManualUrlVerifying(false);
    }
  };

  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      {/* Page Header */}
      <div className="text-center mb-16">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-sm border border-ink/10 bg-paper-dark mb-5">
          <Zap size={24} className="text-ink" />
        </div>
        <h1 className="font-serif text-3xl md:text-4xl font-bold text-ink mb-3">
          在线刷机
        </h1>
        <p className="text-ink-light max-w-lg mx-auto">
          无需安装任何软件，直接在浏览器中为你的 InkSight 设备烧录最新固件。
          <br />
          基于 WebSerial API，支持 Chrome 和 Edge 浏览器。
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
        {/* Left - Steps */}
        <div>
          <h2 className="text-lg font-semibold text-ink mb-6 flex items-center gap-2">
            <ListOrdered size={18} />
            操作步骤
          </h2>
          <div className="space-y-6">
            {steps.map((step, i) => (
              <div key={i} className="flex gap-4 group">
                <div className="flex-shrink-0 flex items-start">
                  <div className="flex items-center justify-center w-10 h-10 rounded-sm border border-ink/10 bg-white group-hover:bg-ink group-hover:text-white transition-colors">
                    <step.icon size={18} />
                  </div>
                </div>
                <div className="pt-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs text-ink-light font-mono">
                      0{i + 1}
                    </span>
                    <h3 className="text-sm font-semibold text-ink">
                      {step.title}
                    </h3>
                  </div>
                  <p className="text-sm text-ink-light leading-relaxed">
                    {step.desc}
                  </p>
                </div>
              </div>
            ))}
          </div>

          {/* Requirements */}
          <div className="mt-8 p-4 rounded-sm border border-ink/10 bg-paper">
            <h3 className="text-sm font-semibold text-ink mb-2 flex items-center gap-2">
              <AlertCircle size={14} />
              注意事项
            </h3>
            <ul className="space-y-1.5 text-sm text-ink-light">
              <li className="flex items-start gap-2">
                <span className="text-ink mt-0.5">·</span>
                需要使用 Chrome 89+ 或 Edge 89+ 浏览器
              </li>
              <li className="flex items-start gap-2">
                <span className="text-ink mt-0.5">·</span>
                确保 USB 数据线支持数据传输（非仅充电线）
              </li>
              <li className="flex items-start gap-2">
                <span className="text-ink mt-0.5">·</span>
                刷写过程中请勿断开设备连接
              </li>
              <li className="flex items-start gap-2">
                <span className="text-ink mt-0.5">·</span>
                刷写完成后设备将自动重启并进入配网模式
              </li>
            </ul>
          </div>
        </div>

        {/* Right - Flasher */}
        <div>
          <h2 className="text-lg font-semibold text-ink mb-6 flex items-center gap-2">
            <Zap size={18} />
            固件烧录
          </h2>

          {/* Flash Card */}
          <div className="rounded-sm border border-ink/10 bg-white p-8 text-center">
            <div className="mb-6">
              <div className="inline-flex items-center gap-2 text-sm text-ink-light mb-2">
                <CheckCircle2 size={14} className="text-green-600" />
                当前状态: {FLASH_STATUS_LABEL[status]}
              </div>
              <p className="text-xs text-ink-light">
                芯片: {selectedRelease?.chip_family ?? "ESP32-C3"} &middot; 固件大小:{" "}
                {sizeMB ? `${sizeMB} MB` : "未知"}
              </p>
            </div>

            <div className="mb-4">
              <label className="block text-xs text-ink-light mb-2 text-left">
                固件来源
              </label>
              <div className="mb-2 grid grid-cols-2 gap-2 text-sm">
                <Button
                  type="button"
                  variant={useManualFirmware ? "outline" : "default"}
                  onClick={() => {
                    setUseManualFirmware(false);
                    setManualUrlMessage("");
                  }}
                >
                  GitHub Releases
                </Button>
                <Button
                  type="button"
                  variant={useManualFirmware ? "default" : "outline"}
                  onClick={() => {
                    setUseManualFirmware(true);
                    setManualUrlVerified(false);
                  }}
                >
                  手动 URL
                </Button>
              </div>

              {useManualFirmware ? (
                <div>
                  <input
                    className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm text-ink bg-white"
                    placeholder="https://.../inksight-firmware-v1.2.3.bin"
                    value={manualFirmwareUrl}
                    onChange={(e) => {
                      setManualFirmwareUrl(e.target.value.trim());
                      setManualUrlVerified(false);
                      setManualUrlMessage("");
                    }}
                  />
                  <div className="mt-2 flex justify-start">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={handleVerifyManualUrl}
                      disabled={!manualFirmwareUrl || manualUrlVerifying}
                    >
                      {manualUrlVerifying ? "校验中..." : "校验链接"}
                    </Button>
                  </div>
                  {manualUrlMessage ? (
                    <p
                      className={`mt-2 text-xs text-left ${
                        manualUrlVerified ? "text-green-700" : "text-red-600"
                      }`}
                    >
                      {manualUrlMessage}
                    </p>
                  ) : null}
                  <p className="mt-2 text-xs text-ink-light text-left">
                    请输入可直接下载的 `.bin` 固件 URL（建议使用 GitHub Releases 资产链接）。
                  </p>
                </div>
              ) : (
              <div className="flex gap-2">
                <select
                  className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm text-ink bg-white"
                  value={selectedVersion}
                  onChange={(e) => setSelectedVersion(e.target.value)}
                  disabled={!releases.length || useManualFirmware}
                >
                  {releases.map((item) => (
                    <option key={item.tag} value={item.version}>
                      v{item.version} ({item.tag})
                    </option>
                  ))}
                </select>
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleReloadReleases}
                  disabled={status === "loading_releases"}
                >
                  <RefreshCw size={14} />
                </Button>
              </div>
              )}
              {releaseError ? (
                <p className="mt-2 text-xs text-red-600 text-left">
                  固件版本加载失败：{releaseError}
                </p>
              ) : null}
              {process.env.NEXT_PUBLIC_FIRMWARE_API_BASE ? null : (
                <p className="mt-2 text-xs text-ink-light text-left">
                  未配置 `NEXT_PUBLIC_FIRMWARE_API_BASE` 时，默认请求当前域名下
                  `/api/firmware/releases`。
                </p>
              )}
            </div>

            {/* ESP Web Install Button */}
            <div className="mb-6">
              {/* @ts-expect-error esp-web-install-button is a custom element */}
              <esp-web-install-button
                ref={installButtonRef}
                manifest={manifestUrl}
              >
                <Button
                  slot="activate"
                  size="lg"
                  className="w-full max-w-xs"
                  onClick={() => {
                    setStatus("connecting");
                    addLog("正在连接设备...");
                  }}
                  disabled={
                    !scriptLoaded ||
                    !manifestUrl ||
                    status === "loading_releases" ||
                    (useManualFirmware && (!manualFirmwareUrl || !manualUrlVerified))
                  }
                >
                  {scriptLoaded && manifestUrl
                    ? useManualFirmware
                      ? "刷写手动固件"
                      : `刷写 v${selectedVersion || "latest"}`
                    : "正在加载工具..."}
                </Button>
                <span slot="unsupported">
                  <div className="p-4 rounded-sm border border-red-200 bg-red-50 text-sm text-red-700">
                    <AlertCircle
                      size={16}
                      className="inline mr-2 align-text-bottom"
                    />
                    你的浏览器不支持 WebSerial API，请使用 Chrome 或 Edge
                    浏览器。
                  </div>
                </span>
                <span slot="not-allowed">
                  <div className="p-4 rounded-sm border border-yellow-200 bg-yellow-50 text-sm text-yellow-700">
                    <AlertCircle
                      size={16}
                      className="inline mr-2 align-text-bottom"
                    />
                    请确保通过 HTTPS 访问此页面。
                  </div>
                </span>
              {/* @ts-expect-error esp-web-install-button is a custom element */}
              </esp-web-install-button>
            </div>

            {/* Post-flash info */}
            <div className="flex items-center justify-center gap-2 text-sm text-ink-light">
              <Wifi size={14} />
              <span>刷写完成后，设备将自动进入 WiFi 配网模式</span>
            </div>
          </div>

          {/* Console Log */}
          <div className="mt-6">
            <h3 className="text-sm font-semibold text-ink mb-3 flex items-center gap-2">
              <Terminal size={14} />
              控制台日志
            </h3>
            <div className="rounded-sm border border-ink/10 bg-ink text-green-400 font-mono text-xs p-4 h-48 overflow-y-auto">
              {logs.map((log, i) => (
                <div key={i} className="py-0.5 leading-relaxed">
                  {log}
                </div>
              ))}
              <div ref={logEndRef} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
