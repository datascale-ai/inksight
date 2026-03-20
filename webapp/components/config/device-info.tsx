"use client";

import Link from "next/link";
import { CheckCircle2 } from "lucide-react";

export function DeviceInfo({
  mac,
  currentUserRole,
  statusIconClass,
  statusClass,
  statusLabel,
  lastSeen,
  isEn,
  localeConfigPath,
  tr,
}: {
  mac: string;
  currentUserRole: string;
  statusIconClass: string;
  statusClass: string;
  statusLabel: string;
  lastSeen: string | null;
  isEn: boolean;
  localeConfigPath: string;
  tr: (zh: string, en: string) => string;
}) {
  return (
    <div className="space-y-1">
      <p className="text-ink-light text-sm flex items-center gap-2 flex-wrap">
        <CheckCircle2 size={14} className={statusIconClass} />
        {tr("设备 MAC", "Device MAC")}:
        <code className="bg-paper-dark px-2 py-0.5 rounded text-xs">{mac}</code>
        {currentUserRole && (
          <span className="inline-flex items-center rounded px-2 py-0.5 text-xs bg-paper-dark text-ink">
            {currentUserRole === "owner" ? "Owner" : "Member"}
          </span>
        )}
        <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs ${statusClass}`}>
          {statusLabel}
        </span>
        {lastSeen && (
          <span className="text-xs text-ink-light">
            {tr("上次在线", "Last seen")}:{" "}
            {new Date(lastSeen).toLocaleString(isEn ? "en-US" : "zh-CN")}
          </span>
        )}
        <Link href={localeConfigPath} className="text-xs text-ink-light hover:text-ink underline">
          {tr("返回设备列表", "Back to Device List")}
        </Link>
      </p>
      {currentUserRole === "member" && (
        <p className="text-xs text-amber-700">
          {tr("Member 免费额度仅用于无设备预览，不用于设备端生成。", "Member free quota only applies to device-free preview, not on-device generation.")}
        </p>
      )}
    </div>
  );
}
