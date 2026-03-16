"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  Usb,
  MousePointerClick,
  ListOrdered,
  Zap,
  CheckCircle2,
  AlertCircle,
  Terminal,
  RefreshCw,
  X,
} from "lucide-react";
import { fetchCurrentUser, onAuthChanged } from "@/lib/auth";
import { localeFromPathname, withLocalePath } from "@/lib/i18n";
import { buildReleaseKey, buildReleaseLabel, getPreferredBuild, type FirmwareReleaseOption } from "./release-options";

declare global {
  interface Navigator {
    serial?: {
      requestPort(options?: object): Promise<unknown>;
    };
  }
}

const steps = [
  {
    icon: Usb,
    title: "连接 USB",
    desc: "使用 USB-C 数据线将 ESP32-C3 开发板连接到电脑",
  },
  {
    icon: MousePointerClick,
    title: "点击刷写",
    desc: "点击下方的「刷写固件」按钮，浏览器将弹出串口选择窗口",
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

type FirmwareRelease = FirmwareReleaseOption & {
  version: string;
  tag: string;
  published_at: string | null;
  download_url: string;
  size_bytes: number | null;
  chip_family: string;
  asset_name: string;
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
  const pathname = usePathname();
  const locale = localeFromPathname(pathname || "/");
  const isEn = locale === "en";
  const stepsLocalized = isEn
    ? [
        { icon: Usb, title: "Connect USB", desc: "Connect your ESP32-C3 board using a USB-C data cable." },
        { icon: MousePointerClick, title: "Click Flash", desc: 'Click "Flash Firmware" and allow serial port access.' },
        { icon: ListOrdered, title: "Select Port", desc: "Select the serial port corresponding to your ESP32 device." },
        { icon: Zap, title: "Start Flashing", desc: "Firmware will be downloaded and written automatically." },
      ]
    : steps;
  const flashStatusLabel = isEn
    ? {
        initializing: "Initializing",
        loading_releases: "Loading releases",
        ready: "Ready",
        connecting: "Waiting serial permission",
        flashing: "Flashing",
        success: "Success",
        failed: "Failed, retry",
      }
    : FLASH_STATUS_LABEL;
  const [status, setStatus] = useState<FlashStatus>("initializing");
  const [releases, setReleases] = useState<FirmwareRelease[]>([]);
  const [selectedReleaseKey, setSelectedReleaseKey] = useState<string>("");
  const [releaseError, setReleaseError] = useState<string>("");
  const [manualFirmwareUrl, setManualFirmwareUrl] = useState<string>("");
  const [useManualFirmware, setUseManualFirmware] = useState<boolean>(false);
  const [manualUrlVerified, setManualUrlVerified] = useState<boolean>(false);
  const [manualUrlVerifying, setManualUrlVerifying] = useState<boolean>(false);
  const [manualUrlMessage, setManualUrlMessage] = useState<string>("");
  const [flashProgress, setFlashProgress] = useState<number>(0);
  const [serialSupported, setSerialSupported] = useState<boolean | null>(null);
  const [logs, setLogs] = useState<string[]>([
    isEn ? "[system] InkSight Web Flasher ready" : "[系统] InkSight Web Flasher 已就绪",
    isEn ? "[tip] Use Chrome or Edge for best compatibility" : "[提示] 请使用 Chrome 或 Edge 浏览器以获得最佳体验",
    isEn ? "[tip] Ensure ESP32 USB driver is installed" : "[提示] 确保已安装 ESP32 USB 驱动程序",
  ]);
  const [showPostFlashGuide, setShowPostFlashGuide] = useState(false);
  const [authState, setAuthState] = useState<"checking" | "logged_in" | "guest">("checking");
  const [skipLoginGate, setSkipLoginGate] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);
  const transportRef = useRef<InstanceType<typeof import("esptool-js").Transport> | null>(null);

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
    setSerialSupported(!!navigator.serial);
  }, []);

  const refreshAuthState = useCallback(() => {
    fetchCurrentUser()
      .then((user) => {
        setAuthState(user ? "logged_in" : "guest");
      })
      .catch(() => setAuthState("guest"));
  }, []);

  useEffect(() => {
    refreshAuthState();
  }, [refreshAuthState]);

  useEffect(() => {
    const off = onAuthChanged(refreshAuthState);
    const onFocus = () => refreshAuthState();
    window.addEventListener("focus", onFocus);
    return () => {
      off();
      window.removeEventListener("focus", onFocus);
    };
  }, [refreshAuthState]);

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
        setSelectedReleaseKey(buildReleaseKey(list[0]));
        setLogs((prev) => [
          ...prev,
          `[系统] 已加载 ${list.length} 个固件版本，默认选择 ${buildReleaseLabel(list[0])}`,
        ]);
        setStatus("ready");
      } catch (err) {
        const message = err instanceof Error ? err.message : "加载固件版本失败";
        setReleaseError(message);
        setUseManualFirmware(true);
        setStatus("ready");
        setLogs((prev) => [...prev, `[错误] ${message}`]);
        setLogs((prev) => [...prev, "[提示] 你可以切换到手动 URL 模式继续刷机"]);
      }
    };

    loadReleases();
  }, []);

  useEffect(() => {
    const el = logEndRef.current;
    if (el?.parentElement) {
      el.parentElement.scrollTop = el.parentElement.scrollHeight;
    }
  }, [logs]);

  const addLog = useCallback((msg: string) => {
    setLogs((prev) => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`]);
  }, []);

  const selectedRelease = releases.find((r) => buildReleaseKey(r) === selectedReleaseKey);
  const loginHref = `${withLocalePath(locale, "/login")}?next=${encodeURIComponent(withLocalePath(locale, "/flash"))}`;
  const [actualChip, setActualChip] = useState<string | null>(null);
  const [actualSizeMB, setActualSizeMB] = useState<string | null>(null);
  const sizeMB = actualSizeMB
    ?? (selectedRelease?.size_bytes
      ? (selectedRelease.size_bytes / (1024 * 1024)).toFixed(2)
      : null);

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
      setSelectedReleaseKey(buildReleaseKey(list[0]));
      setUseManualFirmware(false);
      setStatus("ready");
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
      if (data.content_length) {
        setActualSizeMB((Number(data.content_length) / (1024 * 1024)).toFixed(2));
      }
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

  const getFirmwareUrl = (): string | null => {
    if (useManualFirmware) {
      if (!manualFirmwareUrl || !manualUrlVerified) return null;
      return `${window.location.origin}/api/firmware/download?url=${encodeURIComponent(manualFirmwareUrl)}`;
    }
    const selected = releases.find((r) => buildReleaseKey(r) === selectedReleaseKey);
    if (!selected) return null;
    const build = getPreferredBuild(selected);
    if (!build || !build.parts.length) return null;
    const rawUrl = build.parts[0].path;
    return `${window.location.origin}/api/firmware/download?url=${encodeURIComponent(rawUrl)}`;
  };

  const handleFlash = async () => {
    if (!navigator.serial) {
      addLog("浏览器不支持 WebSerial API，请使用 Chrome 或 Edge");
      setStatus("failed");
      return;
    }

    const firmwareUrl = getFirmwareUrl();
    if (!firmwareUrl) {
      addLog("无法确定固件下载地址");
      setStatus("failed");
      return;
    }

    setStatus("connecting");
    setActualChip(null);
    setActualSizeMB(null);
    addLog("正在请求串口权限...");

    let port: unknown;
    try {
      port = await navigator.serial.requestPort();
    } catch {
      addLog("用户取消了串口选择或无可用串口");
      setStatus("ready");
      return;
    }

    addLog("串口已选择，正在连接设备...");

    try {
      const { ESPLoader, Transport } = await import("esptool-js");

      const transport = new Transport(port as ConstructorParameters<typeof Transport>[0], true);
      transportRef.current = transport;

      const loaderTerminal = {
        clean() { /* no-op */ },
        writeLine(data: string) { addLog(data); },
        write(data: string) {
          if (data.trim()) addLog(data.trim());
        },
      };

      const esploader = new ESPLoader({
        transport,
        baudrate: 115200,
        romBaudrate: 115200,
        terminal: loaderTerminal,
      });

      const chip = await esploader.main();
      setActualChip(chip);
      addLog(`已连接: ${chip}`);

      addLog("正在下载固件...");
      const fwResp = await fetch(firmwareUrl);
      if (!fwResp.ok) {
        throw new Error(`固件下载失败: HTTP ${fwResp.status}`);
      }
      const fwBuffer = await fwResp.arrayBuffer();
      const fwData = new Uint8Array(fwBuffer);
      const fwBinaryStr = Array.from(fwData, (b) => String.fromCharCode(b)).join("");
      setActualSizeMB((fwData.length / (1024 * 1024)).toFixed(2));
      addLog(`固件下载完成: ${(fwData.length / 1024).toFixed(0)} KB`);

      setStatus("flashing");
      setFlashProgress(0);
      addLog("开始刷写固件，请勿断开 USB 连接...");

      const header = Array.from(fwData.slice(0, 16), b => b.toString(16).padStart(2, "0")).join(" ");
      addLog(`固件头部: ${header}`);

      await esploader.writeFlash({
        fileArray: [{ data: fwBinaryStr, address: 0x0 }],
        flashSize: "keep",
        flashMode: "keep",
        flashFreq: "keep",
        eraseAll: false,
        compress: true,
        reportProgress: (_fileIndex: number, written: number, total: number) => {
          const pct = Math.round((written / total) * 100);
          setFlashProgress(pct);
        },
      });

      addLog("固件写入完成，正在重启设备...");
      try {
        await transport.setRTS(true);
        await new Promise((r) => setTimeout(r, 100));
        await transport.setRTS(false);
        await new Promise((r) => setTimeout(r, 50));
      } catch { /* RTS toggle may fail on some adapters */ }

      try {
        await transport.disconnect();
      } catch { /* port may already be closed */ }
      transportRef.current = null;

      setStatus("success");
      setShowPostFlashGuide(true);
      addLog("刷写成功！设备已重启，请按引导完成配网。");
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      addLog(`刷写失败: ${msg}`);
      setStatus("failed");
      try {
        if (transportRef.current) {
          await transportRef.current.disconnect();
          transportRef.current = null;
        }
      } catch { /* ignore */ }
    }
  };

  const canFlash =
    status === "ready" || status === "failed" || status === "success"
      ? useManualFirmware
        ? manualFirmwareUrl && manualUrlVerified
        : !!selectedReleaseKey
      : false;
  const loginGateActive = authState === "guest" && !skipLoginGate;
  const canStartFlash = canFlash && authState !== "checking" && !loginGateActive;

  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      <div className="text-center mb-16">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-sm border border-ink/10 bg-paper-dark mb-5">
          <Zap size={24} className="text-ink" />
        </div>
        <h1 className="font-serif text-3xl md:text-4xl font-bold text-ink mb-3">
          {isEn ? "Web Flasher" : "在线刷机"}
        </h1>
        <p className="text-ink-light max-w-lg mx-auto">
          {isEn
            ? "No extra software required. Flash the latest firmware directly in your browser."
            : "无需安装任何软件，直接在浏览器中为你的 InkSight 设备烧录最新固件。"}
          <br />
          {isEn ? "Powered by WebSerial API, works with Chrome and Edge." : "基于 WebSerial API，支持 Chrome 和 Edge 浏览器。"}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
        {/* Left - Steps */}
        <div>
          <h2 className="text-lg font-semibold text-ink mb-6 flex items-center gap-2">
            <ListOrdered size={18} />
            {isEn ? "Steps" : "操作步骤"}
          </h2>
          <div className="space-y-6">
            {stepsLocalized.map((step, i) => (
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

          <div className="mt-8 p-4 rounded-sm border border-ink/10 bg-paper">
            <h3 className="text-sm font-semibold text-ink mb-2 flex items-center gap-2">
              <AlertCircle size={14} />
              {isEn ? "Notes" : "注意事项"}
            </h3>
            <ul className="space-y-1.5 text-sm text-ink-light">
              <li className="flex items-start gap-2">
                <span className="text-ink mt-0.5">·</span>
                {isEn ? "Use Chrome 89+ or Edge 89+" : "需要使用 Chrome 89+ 或 Edge 89+ 浏览器"}
              </li>
              <li className="flex items-start gap-2">
                <span className="text-ink mt-0.5">·</span>
                {isEn ? "Use a USB cable that supports data transfer" : "确保 USB 数据线支持数据传输（非仅充电线）"}
              </li>
              <li className="flex items-start gap-2">
                <span className="text-ink mt-0.5">·</span>
                {isEn ? "Do not unplug device while flashing" : "刷写过程中请勿断开设备连接"}
              </li>
              <li className="flex items-start gap-2">
                <span className="text-ink mt-0.5">·</span>
                {isEn ? "Device reboots and enters provisioning mode after flashing" : "刷写完成后设备将自动重启并进入配网模式"}
              </li>
            </ul>
          </div>
        </div>

        {/* Right - Flasher */}
        <div>
          <h2 className="text-lg font-semibold text-ink mb-6 flex items-center gap-2">
            <Zap size={18} />
            {isEn ? "Firmware Flash" : "固件烧录"}
          </h2>

          <div className="rounded-sm border border-ink/10 bg-white p-8 text-center">
            <div className="mb-6">
              <div className="inline-flex items-center gap-2 text-sm text-ink-light mb-2">
                <CheckCircle2 size={14} className={status === "success" ? "text-green-600" : status === "failed" ? "text-red-500" : status === "flashing" ? "text-amber-500 animate-pulse" : "text-ink-light"} />
                {isEn ? "Status" : "当前状态"}: {flashStatusLabel[status]}
                {status === "flashing" ? ` ${flashProgress}%` : ""}
              </div>
              <p className="text-xs text-ink-light">
                {isEn ? "Chip" : "芯片"}: {actualChip ?? selectedRelease?.chip_family ?? "ESP32-C3"} &middot; {isEn ? "Size" : "固件大小"}:{" "}
                {sizeMB ? `${sizeMB} MB` : isEn ? "Unknown" : "未知"}
              </p>
            </div>

            <div className="mb-4">
              <label className="block text-xs text-ink-light mb-2 text-left">
                {isEn ? "Source" : "固件来源"}
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
                  {isEn ? "Manual URL" : "手动 URL"}
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
                      {manualUrlVerifying ? (isEn ? "Verifying..." : "校验中...") : (isEn ? "Verify URL" : "校验链接")}
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
                    {isEn ? "Enter a direct downloadable .bin firmware URL (GitHub Releases asset link recommended)." : "请输入可直接下载的 `.bin` 固件 URL（建议使用 GitHub Releases 资产链接）。"}
                  </p>
                </div>
              ) : (
              <div className="flex gap-2">
                <select
                  className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm text-ink bg-white"
                  value={selectedReleaseKey}
                  onChange={(e) => setSelectedReleaseKey(e.target.value)}
                  disabled={!releases.length || useManualFirmware}
                >
                  {releases.map((item) => (
                    <option key={buildReleaseKey(item)} value={buildReleaseKey(item)}>
                      {buildReleaseLabel(item)}
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
              {!useManualFirmware && releaseError ? (
                <p className="mt-2 text-xs text-red-600 text-left">
                  {isEn ? "Failed to load firmware versions" : "固件版本加载失败"}: {releaseError}
                </p>
              ) : null}
              {!process.env.NEXT_PUBLIC_FIRMWARE_API_BASE && !useManualFirmware ? (
                <p className="mt-2 text-xs text-ink-light text-left">
                  {isEn
                    ? "NEXT_PUBLIC_FIRMWARE_API_BASE not set. Releases list uses /api/firmware/releases on current site."
                    : "未配置 NEXT_PUBLIC_FIRMWARE_API_BASE 环境变量：GitHub Releases 列表会走当前站点的 /api/firmware/releases。"}
                </p>
              ) : null}
            </div>

            {/* Flash button */}
            <div className="mb-6">
              {authState === "checking" ? (
                <div className="mb-3 p-3 rounded-sm border border-ink/10 bg-paper text-sm text-ink-light">
                  {isEn ? "Checking auth status..." : "正在检查登录状态..."}
                </div>
              ) : authState === "guest" && !skipLoginGate ? (
                <div className="mb-3 p-3 rounded-sm border border-amber-200 bg-amber-50 text-left">
                  <p className="text-sm text-amber-800">{isEn ? "Sign in first for a smoother flow" : "建议先登录，再开始刷机"}</p>
                  <p className="mt-1 text-xs text-amber-700">
                    {isEn ? "After sign in: flash -> provisioning -> online configuration." : "登录后可更顺畅完成 刷机 -&gt; 配网 -&gt; 在线配置。"}
                  </p>
                  <div className="mt-3 flex gap-2">
                    <Button
                      size="sm"
                      onClick={() => {
                        window.location.href = loginHref;
                      }}
                    >
                      {isEn ? "Sign in and continue" : "登录后继续"}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setSkipLoginGate(true);
                        addLog(isEn ? "Continue flashing without sign in" : "已选择跳过登录，继续刷机");
                      }}
                    >
                      {isEn ? "Skip sign in" : "跳过登录，直接刷机"}
                    </Button>
                  </div>
                </div>
              ) : authState === "logged_in" ? (
                <div className="mb-3 p-3 rounded-sm border border-green-200 bg-green-50 text-sm text-green-700">
                  {isEn ? "Signed in. You can continue to online config after flashing." : "已登录，可直接完成刷机后的在线配置流程。"}
                </div>
              ) : null}

              {serialSupported === false ? (
                <div className="p-4 rounded-sm border border-red-200 bg-red-50 text-sm text-red-700">
                  <AlertCircle size={16} className="inline mr-2 align-text-bottom" />
                  {isEn ? "Your browser does not support WebSerial API. Please use Chrome or Edge." : "你的浏览器不支持 WebSerial API，请使用 Chrome 或 Edge 浏览器。"}
                </div>
              ) : (
                <Button
                  variant="outline"
                  size="lg"
                  className="w-full max-w-xs bg-white text-ink border-ink/20 hover:bg-ink hover:text-white active:bg-ink active:text-white disabled:bg-white disabled:text-ink/50"
                  type="button"
                  onClick={handleFlash}
                  disabled={!canStartFlash || status === "connecting" || status === "flashing"}
                >
                  {status === "connecting"
                    ? (isEn ? "Connecting..." : "正在连接...")
                    : status === "flashing"
                    ? (isEn ? `Flashing ${flashProgress}%` : `刷写中 ${flashProgress}%`)
                    : (isEn ? "Flash Firmware" : "刷写固件")}
                </Button>
              )}

              {status === "flashing" && (
                <div className="mt-3 w-full max-w-xs mx-auto">
                  <div className="h-2 bg-ink/10 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-ink transition-all duration-300 rounded-full"
                      style={{ width: `${flashProgress}%` }}
                    />
                  </div>
                  <p className="text-xs text-ink-light mt-1">{flashProgress}%</p>
                </div>
              )}
            </div>

            {/* Post-flash info */}
            {status === "success" ? (
              <div className="mt-4 rounded-sm border border-green-200 bg-green-50 p-5 text-left">
                <h3 className="text-sm font-semibold text-green-800 mb-3 flex items-center gap-2">
                  <CheckCircle2 size={16} />
                  {isEn ? "Flashed Successfully - Next: Provisioning" : "刷写成功 — 下一步配网"}
                </h3>
                <ol className="space-y-2 text-sm text-green-700 list-decimal list-inside">
                  <li>断开 USB，给设备上电</li>
                  <li>在手机/电脑 WiFi 列表中找到 <code className="bg-white px-1.5 py-0.5 rounded text-xs font-mono">InkSight-XXXX</code> 热点并连接</li>
                  <li>浏览器会自动弹出配网页面（如未弹出，手动访问 <code className="bg-white px-1.5 py-0.5 rounded text-xs font-mono">192.168.4.1</code>）</li>
                  <li>在配网页面输入 WiFi 和服务器地址后保存</li>
                  <li>保存成功后，配网页面底部会显示<strong>「打开配置页面」</strong>链接（已带设备标识），点击即可进行个性化配置</li>
                </ol>
                {status === "success" ? (
                  <div className="mt-4">
                    <Button size="sm" onClick={() => window.open(withLocalePath(locale, "/config"), "_blank")}>
                      {isEn ? "Open Configuration Page" : "前往配置页面"}
                    </Button>
                    <p className="mt-2 text-xs text-green-600">{isEn ? "Configuration page will detect device online status automatically." : "配置页面会自动检测设备上线"}</p>
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>

          {/* Console Log */}
          <div className="mt-6">
            <h3 className="text-sm font-semibold text-ink mb-3 flex items-center gap-2">
              <Terminal size={14} />
              {isEn ? "Console Logs" : "控制台日志"}
            </h3>
            <div className="ink-strong-select rounded-sm border border-ink/10 bg-ink text-green-400 font-mono text-xs p-4 h-48 overflow-y-auto">
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

      {/* Post-flash guide dialog */}
      {showPostFlashGuide && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setShowPostFlashGuide(false)} />
          <div className="relative z-10 w-full max-w-md mx-4 animate-fade-in">
            <div className="rounded-sm border border-ink/10 bg-white p-6 shadow-lg">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-2">
                  <CheckCircle2 size={20} className="text-green-600" />
                  <h2 className="text-lg font-semibold text-ink">{isEn ? "Flash Completed" : "刷写成功"}</h2>
                </div>
                <button onClick={() => setShowPostFlashGuide(false)} className="p-1 text-ink-light hover:text-ink">
                  <X size={18} />
                </button>
              </div>
              <p className="text-sm text-ink-light mb-4">{isEn ? "Firmware flashed successfully. Follow the steps below to finish provisioning:" : "固件已烧录成功，请按以下步骤完成配网："}</p>
              <ol className="space-y-3 text-sm text-ink">
                <li className="flex gap-3">
                  <span className="flex-shrink-0 w-6 h-6 rounded-full bg-ink text-white text-xs flex items-center justify-center font-medium">1</span>
                  <span>断开 USB 数据线，给设备上电</span>
                </li>
                <li className="flex gap-3">
                  <span className="flex-shrink-0 w-6 h-6 rounded-full bg-ink text-white text-xs flex items-center justify-center font-medium">2</span>
                  <span>在 WiFi 列表中找到 <code className="bg-paper-dark px-1.5 py-0.5 rounded text-xs font-mono">InkSight-XXXX</code> 热点并连接</span>
                </li>
                <li className="flex gap-3">
                  <span className="flex-shrink-0 w-6 h-6 rounded-full bg-ink text-white text-xs flex items-center justify-center font-medium">3</span>
                  <span>浏览器自动弹出配网页面，若未弹出则手动访问 <code className="bg-paper-dark px-1.5 py-0.5 rounded text-xs font-mono">192.168.4.1</code></span>
                </li>
                <li className="flex gap-3">
                  <span className="flex-shrink-0 w-6 h-6 rounded-full bg-ink text-white text-xs flex items-center justify-center font-medium">4</span>
                  <span>输入家庭 WiFi 和服务器地址，保存后设备自动重启联网</span>
                </li>
                <li className="flex gap-3">
                  <span className="flex-shrink-0 w-6 h-6 rounded-full bg-ink text-white text-xs flex items-center justify-center font-medium">5</span>
                  <span>保存成功后，配网页面底部会显示<strong>「打开配置页面」</strong>链接，点击即可进行个性化配置</span>
                </li>
              </ol>
              <div className="mt-4">
                <Button size="sm" onClick={() => window.open("/config", "_blank")}>
                  前往配置页面
                </Button>
                <p className="mt-2 text-xs text-ink-light">配置页面会自动检测设备上线</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
