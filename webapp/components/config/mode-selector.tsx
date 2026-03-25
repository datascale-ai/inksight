"use client";

import { useState } from "react";
import { ChevronDown, Eye, LayoutGrid, Plus } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ColorSelect } from "@/components/ui/color-select";

type ModeMeta = Record<string, { name: string; tip: string }>;

type ModeSelectorProps = {
  tr: (zh: string, en: string) => string;
  selectedModes: Set<string>;
  customModes: string[];
  customModeMeta: ModeMeta;
  modeMeta: ModeMeta;
  coreModes: string[];
  extraModes: string[];
  handleModePreview: (mode: string) => void;
  handleModeApply: (mode: string) => void;
  setEditingCustomMode: (value: boolean) => void;
  setCustomDesc: (value: string) => void;
  setCustomModeName: (value: string) => void;
  setCustomJson: (value: string) => void;
  previewColors?: number;
  onColorsChange?: (v: number) => void;
};

export function ModeSelector({
  tr,
  selectedModes,
  customModes,
  customModeMeta,
  modeMeta,
  coreModes,
  extraModes,
  handleModePreview,
  handleModeApply,
  setEditingCustomMode,
  setCustomDesc,
  setCustomModeName,
  setCustomJson,
  previewColors,
  onColorsChange,
}: ModeSelectorProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <CardTitle className="flex items-center gap-2">
            <LayoutGrid size={18} /> {tr("内容模式", "Content Modes")}
          </CardTitle>
          {onColorsChange && previewColors !== undefined && (
            <ColorSelect value={previewColors} onChange={onColorsChange} tr={tr} />
          )}
        </div>
      </CardHeader>
      <CardContent>
        <ModeGrid
          title={tr("核心模式", "Core Modes")}
          modes={coreModes}
          selectedModes={selectedModes}
          onPreview={handleModePreview}
          onApply={handleModeApply}
          modeMeta={modeMeta}
        />
        <ModeGrid
          title={tr("更多模式", "More Modes")}
          modes={extraModes}
          selectedModes={selectedModes}
          onPreview={handleModePreview}
          onApply={handleModeApply}
          modeMeta={modeMeta}
        />
        <ModeGrid
          title={tr("自定义模式", "Custom Modes")}
          modes={customModes}
          selectedModes={selectedModes}
          onPreview={handleModePreview}
          onApply={handleModeApply}
          modeMeta={{ ...modeMeta, ...customModeMeta }}
          tailItem={
            <button
              onClick={() => {
                setEditingCustomMode(true);
                setCustomJson("");
                setCustomDesc("");
                setCustomModeName("");
              }}
              className="rounded-sm border border-dashed border-ink/20 bg-white px-3 py-2 min-h-[64px] flex flex-col items-center justify-center text-ink-light hover:border-ink/40 hover:bg-paper-dark transition-colors"
              title={tr("新建自定义模式", "Create custom mode")}
            >
              <Plus size={18} className="mb-1" />
              <div className="text-[11px]">{tr("新建", "New")}</div>
            </button>
          }
        />
      </CardContent>
    </Card>
  );
}

function ModeGrid({
  title,
  modes,
  selectedModes,
  onPreview,
  onApply,
  modeMeta,
  tailItem,
}: {
  title: string;
  modes: string[];
  selectedModes: Set<string>;
  onPreview: (mode: string) => void;
  onApply: (mode: string) => void;
  modeMeta: ModeMeta;
  tailItem?: React.ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(false);

  if (modes.length === 0) return null;

  return (
    <div className="mb-6">
      <div className="flex items-center justify-between gap-2 mb-3 rounded-sm bg-paper-dark border border-ink/10 px-3 py-2">
        <h4 className="text-base font-semibold text-ink">{title}</h4>
        <button
          onClick={() => setCollapsed((v) => !v)}
          className="text-xs text-ink-light hover:text-ink flex items-center gap-1 transition-colors"
        >
          {collapsed ? "展开" : "收起"}
          <ChevronDown size={14} className={`transition-transform ${collapsed ? "" : "rotate-180"}`} />
        </button>
      </div>

      {collapsed ? null : (
        <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
          {modes.map((mode) => {
            const meta = modeMeta[mode] || { name: mode, tip: "" };
            const isSelected = selectedModes.has(mode);

            return (
              <div key={mode} className="rounded-sm border border-ink/10 bg-white overflow-hidden">
                <button
                  onClick={() => onApply(mode)}
                  className={`w-full px-3 py-2 text-left transition-colors min-h-[64px] flex flex-col justify-center ${
                    isSelected ? "bg-ink text-white" : "hover:bg-paper-dark text-ink"
                  }`}
                  title={meta.tip}
                >
                  <div className="text-sm font-semibold">{meta.name}</div>
                  <div className={`text-[11px] mt-0.5 line-clamp-2 ${isSelected ? "text-white/80" : "text-ink-light"}`}>
                    {meta.tip}
                  </div>
                </button>

                <div className="border-t border-ink/10 grid grid-cols-4">
                  <button
                    onClick={() => onPreview(mode)}
                    className="col-span-2 h-9 px-2 text-[11px] sm:text-xs text-ink hover:bg-ink hover:text-white transition-colors flex items-center justify-center gap-1 whitespace-nowrap"
                    title="预览"
                  >
                    <Eye size={14} />
                  </button>
                  <button
                    onClick={() => onApply(mode)}
                    className="col-span-2 h-9 px-2 text-[11px] sm:text-xs text-ink hover:bg-ink hover:text-white transition-colors flex items-center justify-center gap-1 whitespace-nowrap"
                    title={isSelected ? "移出轮播" : "加入轮播"}
                  >
                    {isSelected ? "-" : "+"}
                  </button>
                </div>
              </div>
            );
          })}
          {tailItem ? tailItem : null}
        </div>
      )}
    </div>
  );
}
