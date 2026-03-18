"use client";

import { useState } from "react";
import Image from "next/image";
import { ArrowLeft, ChevronDown, Eye, LayoutGrid, Loader2, Plus, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type ModeMeta = Record<string, { name: string; tip: string }>;

type ModeSelectorProps = {
  tr: (zh: string, en: string) => string;
  selectedModes: Set<string>;
  favoritedModes: Set<string>;
  customModes: string[];
  customModeMeta: ModeMeta;
  modeMeta: ModeMeta;
  coreModes: string[];
  extraModes: string[];
  modeTemplates: Record<
    string,
    { label: string; def: Record<string, unknown> & { display_name?: string } }
  >;
  handlePreview: (mode?: string, forceNoCache?: boolean) => void;
  handleModePreview: (mode: string) => void;
  handleModeApply: (mode: string) => void;
  handleModeFavorite: (mode: string) => void;
  setSettingsMode: (mode: string) => void;
  handleDeleteCustomMode: (mode: string) => void;
  editingCustomMode: boolean;
  setEditingCustomMode: (value: boolean) => void;
  editorTab: "ai" | "template";
  setEditorTab: (value: "ai" | "template") => void;
  customDesc: string;
  setCustomDesc: (value: string) => void;
  customModeName: string;
  setCustomModeName: (value: string) => void;
  customJson: string;
  setCustomJson: (value: string) => void;
  customGenerating: boolean;
  customPreviewImg: string | null;
  customPreviewLoading: boolean;
  customApplyToScreenLoading: boolean;
  handleGenerateMode: () => void;
  handleCustomPreview: () => void;
  handleApplyCustomPreviewToScreen: () => void;
  handleSaveCustomMode: () => void;
  mac: string;
};

export function ModeSelector({
  tr,
  selectedModes,
  customModes,
  customModeMeta,
  modeMeta,
  coreModes,
  extraModes,
  modeTemplates,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  handlePreview: _handlePreview,
  handleModePreview,
  handleModeApply,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  handleModeFavorite: _handleModeFavorite,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  setSettingsMode: _setSettingsMode,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  handleDeleteCustomMode: _handleDeleteCustomMode,
  editingCustomMode,
  setEditingCustomMode,
  editorTab,
  setEditorTab,
  customDesc,
  setCustomDesc,
  customModeName,
  setCustomModeName,
  customJson,
  setCustomJson,
  customGenerating,
  customPreviewImg,
  customPreviewLoading,
  customApplyToScreenLoading,
  handleGenerateMode,
  handleCustomPreview,
  handleApplyCustomPreviewToScreen,
  handleSaveCustomMode,
  mac,
}: ModeSelectorProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <LayoutGrid size={18} /> {tr("内容模式", "Content Modes")}
        </CardTitle>
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

        {editingCustomMode ? (
          <div className="mt-6 pt-6 border-t border-ink/10">
            <div className="flex items-center gap-2 mb-4">
              <button
                onClick={() => setEditingCustomMode(false)}
                className="p-1 rounded hover:bg-paper-dark transition-colors"
              >
                <ArrowLeft size={16} className="text-ink-light" />
              </button>
              <span className="text-sm font-medium">
                {tr("创建自定义模式", "Create Custom Mode")}
              </span>
            </div>

            <div className="flex gap-1 mb-4">
              <button
                onClick={() => setEditorTab("ai")}
                className={`px-3 py-1.5 rounded-sm text-xs transition-colors ${
                  editorTab === "ai" ? "bg-ink text-white" : "bg-paper-dark text-ink-light hover:text-ink"
                }`}
              >
                <Sparkles size={12} className="inline mr-1" />
                {tr("AI 生成", "AI Generate")}
              </button>
              <button
                onClick={() => setEditorTab("template")}
                className={`px-3 py-1.5 rounded-sm text-xs transition-colors ${
                  editorTab === "template"
                    ? "bg-ink text-white"
                    : "bg-paper-dark text-ink-light hover:text-ink"
                }`}
              >
                <LayoutGrid size={12} className="inline mr-1" />
                {tr("从模板", "From Template")}
              </button>
            </div>

            {editorTab === "ai" ? (
              <div className="space-y-3 mb-4">
                <textarea
                  value={customDesc}
                  onChange={(e) => setCustomDesc(e.target.value)}
                  rows={3}
                  maxLength={2000}
                  placeholder={tr(
                    "描述你想要的模式，如：每天显示一个英语单词和释义，单词要大号字体居中",
                    "Describe your mode, e.g. show one English word and definition daily with a large centered font",
                  )}
                  className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm resize-y bg-white"
                />
                <Button size="sm" onClick={handleGenerateMode} disabled={customGenerating || !customDesc.trim()}>
                  {customGenerating ? (
                    <>
                      <Loader2 size={14} className="animate-spin mr-1" />{" "}
                      {tr("生成中...", "Generating...")}
                    </>
                  ) : (
                    tr("AI 生成模式", "Generate Mode with AI")
                  )}
                </Button>
              </div>
            ) : (
              <div className="space-y-3 mb-4">
                <select
                  onChange={(e) => {
                    const template = modeTemplates[e.target.value];
                    if (!template) return;
                    setCustomJson(JSON.stringify(template.def, null, 2));
                    setCustomModeName((template.def?.display_name || "").toString());
                  }}
                  defaultValue=""
                  className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
                >
                  <option value="" disabled>
                    {tr("选择模板...", "Select template...")}
                  </option>
                  {Object.entries(modeTemplates).map(([key, template]) => (
                    <option key={key} value={key}>
                      {template.label}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="space-y-3">
              <input
                value={customModeName}
                onChange={(e) => setCustomModeName(e.target.value)}
                placeholder={tr("模式名称（例如：今日英语）", "Mode name (e.g. Daily English)")}
                className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
              />
              <textarea
                value={customJson}
                onChange={(e) => setCustomJson(e.target.value)}
                rows={10}
                spellCheck={false}
                placeholder={tr("模式 JSON 定义", "Mode JSON definition")}
                className="ink-strong-select w-full rounded-sm border border-ink/20 px-3 py-2 text-xs font-mono resize-y bg-ink text-green-400"
              />
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={handleCustomPreview} disabled={!customJson.trim() || customPreviewLoading}>
                  {customPreviewImg ? tr("重新生成预览", "Regenerate Preview") : tr("预览效果", "Preview")}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleApplyCustomPreviewToScreen}
                  disabled={!mac || !customPreviewImg || customPreviewLoading || customApplyToScreenLoading}
                >
                  {customApplyToScreenLoading ? <Loader2 size={14} className="animate-spin mr-1" /> : null}
                  {tr("应用到墨水屏", "Apply to E-Ink")}
                </Button>
                <Button variant="outline" size="sm" onClick={handleSaveCustomMode} disabled={!customJson.trim()}>
                  {tr("保存模式", "Save Mode")}
                </Button>
              </div>
              {(customPreviewLoading || customPreviewImg) && (
                <div className="mt-3 border border-ink/10 rounded-sm p-2 bg-paper flex justify-center">
                  {customPreviewLoading ? (
                    <div className="flex items-center gap-2 text-ink-light text-sm py-8">
                      <Loader2 size={18} className="animate-spin" />{" "}
                      {tr("预览生成中...", "Generating preview...")}
                    </div>
                  ) : (
                    <Image
                      src={customPreviewImg!}
                      alt="Custom preview"
                      width={400}
                      height={300}
                      unoptimized
                      className="max-w-[400px] w-full border border-ink/10"
                    />
                  )}
                </div>
              )}
            </div>
          </div>
        ) : null}
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
