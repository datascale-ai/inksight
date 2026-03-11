"use client";

import { useState } from "react";
import Image from "next/image";
import { ArrowLeft, ChevronDown, Eye, Heart, LayoutGrid, Loader2, Plus, Settings, Sparkles, Trash2 } from "lucide-react";
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
  previewMode: string;
  previewImg: string | null;
  previewLoading: boolean;
  previewStatusText: string;
  previewCacheHit: boolean | null;
  applyToScreenLoading: boolean;
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
  handleApplyPreviewToScreen: () => void;
  mac: string;
};

export function ModeSelector({
  tr,
  selectedModes,
  favoritedModes,
  customModes,
  customModeMeta,
  modeMeta,
  coreModes,
  extraModes,
  modeTemplates,
  previewMode,
  previewImg,
  previewLoading,
  previewStatusText,
  previewCacheHit,
  applyToScreenLoading,
  handlePreview,
  handleModePreview,
  handleModeApply,
  handleModeFavorite,
  setSettingsMode,
  handleDeleteCustomMode,
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
  handleApplyPreviewToScreen,
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
          favoritedModes={favoritedModes}
          onPreview={handleModePreview}
          onApply={handleModeApply}
          onFavorite={handleModeFavorite}
          onSettings={setSettingsMode}
          modeMeta={modeMeta}
        />
        <ModeGrid
          title={tr("更多模式", "More Modes")}
          modes={extraModes}
          selectedModes={selectedModes}
          favoritedModes={favoritedModes}
          onPreview={handleModePreview}
          onApply={handleModeApply}
          onFavorite={handleModeFavorite}
          onSettings={setSettingsMode}
          modeMeta={modeMeta}
          collapsible
        />
        <ModeGrid
          title={tr("自定义模式", "Custom Modes")}
          modes={customModes}
          selectedModes={selectedModes}
          favoritedModes={favoritedModes}
          onPreview={handleModePreview}
          onApply={handleModeApply}
          onFavorite={handleModeFavorite}
          onSettings={setSettingsMode}
          onDelete={handleDeleteCustomMode}
          modeMeta={{ ...modeMeta, ...customModeMeta }}
        />
        <div className="mb-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-1.5">
            <div className="relative flex">
              <button
                onClick={() => {
                  setEditingCustomMode(true);
                  setCustomJson("");
                  setCustomDesc("");
                  setCustomModeName("");
                }}
                className="flex-1 aspect-square rounded-lg border border-dashed border-ink/20 p-1.5 flex flex-col items-center justify-center transition-all hover:border-ink/40 hover:bg-paper-dark bg-white text-ink-light"
              >
                <Plus size={18} className="mb-0.5" />
                <div className="text-[10px] leading-tight">{tr("新建", "New")}</div>
              </button>
            </div>
          </div>
        </div>

        {editingCustomMode ? (
          <div className="mt-4 pt-4 border-t border-ink/10">
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
                  className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm resize-y"
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
                rows={14}
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
                      {previewStatusText || tr("预览生成中...", "Generating preview...")}
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
        ) : (
          <>
            <p className="text-xs text-ink-light mt-3">
              {tr("已选", "Selected")} {selectedModes.size} {tr("个模式", "modes")}
            </p>
            <div className="mt-6 pt-6 border-t border-ink/10">
              <div className="flex items-center gap-2 mb-3">
                <Eye size={16} className="text-ink-light" />
                <span className="text-sm font-medium">
                  {tr("预览", "Preview")}
                  {previewMode
                    ? `: ${modeMeta[previewMode]?.name || customModeMeta[previewMode]?.name || previewMode}`
                    : ""}
                </span>
                {previewLoading && <Loader2 size={14} className="animate-spin text-ink-light" />}
              </div>
              <div className="mb-3">
                {previewImg && !previewLoading && previewCacheHit === true && (
                  <div className="mb-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-sm px-2 py-1.5">
                    {tr(
                      "当前预览为历史缓存。如需查看最新效果，请点击“重新生成预览”。",
                      'Current preview is from cache. Click "Regenerate Preview" to fetch latest output.',
                    )}
                  </div>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handlePreview(undefined, true)}
                  disabled={!previewMode || previewLoading}
                  className="bg-white text-ink border-ink/20 hover:bg-ink hover:text-white active:bg-ink active:text-white disabled:bg-white disabled:text-ink/50 mr-2"
                >
                  {tr("重新生成预览", "Regenerate Preview")}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleApplyPreviewToScreen}
                  disabled={!mac || !previewMode || !previewImg || previewLoading || applyToScreenLoading}
                  className="bg-white text-ink border-ink/20 hover:bg-ink hover:text-white active:bg-ink active:text-white disabled:bg-white disabled:text-ink/50"
                >
                  {applyToScreenLoading ? <Loader2 size={14} className="animate-spin mr-1" /> : null}
                  {tr("应用到墨水屏", "Apply to E-Ink")}
                </Button>
              </div>
              {previewLoading ? (
                <div className="border border-ink/10 rounded-sm p-3 bg-paper flex justify-center">
                  <div className="flex items-center gap-2 text-ink-light text-sm py-8">
                    <Loader2 size={18} className="animate-spin" />{" "}
                    {previewStatusText || tr("预览生成中...", "Generating preview...")}
                  </div>
                </div>
              ) : previewImg ? (
                <div className="border border-ink/10 rounded-sm p-3 bg-paper flex justify-center">
                  <Image
                    src={previewImg}
                    alt="Preview"
                    width={400}
                    height={300}
                    unoptimized
                    className="max-w-[400px] w-full border border-ink/10"
                  />
                </div>
              ) : (
                <div className="text-sm text-ink-light text-center py-8">
                  {tr("点击任意模式的「预览」查看效果", "Click Preview on any mode to view output")}
                </div>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function ModeGrid({
  title,
  modes,
  selectedModes,
  favoritedModes,
  onPreview,
  onApply,
  onFavorite,
  onSettings,
  onDelete,
  modeMeta,
  collapsible,
}: {
  title: string;
  modes: string[];
  selectedModes: Set<string>;
  favoritedModes: Set<string>;
  onPreview: (mode: string) => void;
  onApply: (mode: string) => void;
  onFavorite: (mode: string) => void;
  onSettings: (mode: string) => void;
  onDelete?: (mode: string) => void;
  modeMeta: ModeMeta;
  collapsible?: boolean;
}) {
  const [collapsed, setCollapsed] = useState(Boolean(collapsible));
  const [openMode, setOpenMode] = useState<string | null>(null);

  if (modes.length === 0) return null;

  return (
    <div className="mb-4">
      <div className="flex items-center gap-2 mb-2">
        <h4 className="text-sm font-medium text-ink-light">{title}</h4>
        {collapsible && (
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="text-xs text-ink-light hover:text-ink flex items-center gap-1 transition-colors"
          >
            {collapsed ? "展开" : "收起"}
            <ChevronDown size={14} className={`transition-transform ${collapsed ? "" : "rotate-180"}`} />
          </button>
        )}
      </div>
      {!collapsed && (
        <div className="grid grid-cols-4 sm:grid-cols-6 gap-1.5">
          {modes.map((mode) => {
            const meta = modeMeta[mode] || { name: mode, tip: "" };
            const isSelected = selectedModes.has(mode);
            const isFavorited = favoritedModes.has(mode);
            const isOpen = openMode === mode;
            const menuItems = [
              { key: "preview", label: "预览", icon: Eye, onClick: () => onPreview(mode) },
              {
                key: "apply",
                label: isSelected ? "移出轮播" : "加入轮播",
                icon: Plus,
                onClick: () => onApply(mode),
              },
              {
                key: "favorite",
                label: isFavorited ? "取消收藏" : "收藏",
                icon: Heart,
                onClick: () => onFavorite(mode),
                iconClass: isFavorited ? "fill-current text-ink/70" : "text-ink/50",
              },
              { key: "settings", label: "设置", icon: Settings, onClick: () => onSettings(mode) },
              ...(onDelete
                ? [{ key: "delete", label: "删除", icon: Trash2, onClick: () => onDelete(mode) }]
                : []),
            ];

            return (
              <div key={mode} className="relative flex">
                <div className="flex-1 aspect-square relative">
                  <button
                    onClick={() => setOpenMode(isOpen ? null : mode)}
                    className={`w-full h-full rounded-lg border-r-0 rounded-r-none border p-1.5 flex flex-col justify-center transition-all ${
                      isSelected
                        ? "bg-ink text-white border-ink"
                        : "bg-white text-ink border-ink/10 hover:border-ink/30"
                    }`}
                  >
                    <div className="font-semibold text-sm leading-tight text-center">{meta.name}</div>
                  </button>
                  {isOpen && (
                    <>
                      <div className="fixed inset-0 z-10" onClick={() => setOpenMode(null)} />
                      <div className="absolute inset-0 z-20 bg-white border border-ink/15 rounded-lg shadow-lg flex flex-col justify-center py-0.5">
                        {menuItems.map((item) => {
                          const Icon = item.icon;
                          return (
                            <button
                              key={item.key}
                              onClick={() => {
                                item.onClick();
                                setOpenMode(null);
                              }}
                              className="flex-1 px-1 py-0.5 text-[10px] leading-none text-ink hover:bg-paper-dark rounded-sm flex items-center justify-center gap-1 whitespace-nowrap"
                            >
                              <Icon size={10} className={`shrink-0 ${item.iconClass || "text-ink/50"}`} />
                              {item.label}
                            </button>
                          );
                        })}
                      </div>
                    </>
                  )}
                </div>
                <div className="flex flex-col items-center justify-center gap-0 px-0.5 rounded-r-lg border border-l-0 transition-all bg-white border-ink/10">
                  <button onClick={() => onPreview(mode)} className="p-0.5 rounded transition-colors hover:bg-ink/10">
                    <Eye size={10} className="text-ink/35" />
                  </button>
                  <button onClick={() => onApply(mode)} className="p-0.5 rounded transition-colors hover:bg-ink/10">
                    <Plus size={10} className={isSelected ? "text-ink" : "text-ink/20"} />
                  </button>
                  <button onClick={() => onFavorite(mode)} className="p-0.5 rounded transition-colors hover:bg-ink/10">
                    <Heart size={10} className={`${isFavorited ? "fill-current text-ink" : "text-ink/20"}`} />
                  </button>
                  <button onClick={() => onSettings(mode)} className="p-0.5 rounded transition-colors hover:bg-ink/10">
                    <Settings size={10} className="text-ink/35" />
                  </button>
                  {onDelete && (
                    <button onClick={() => onDelete(mode)} className="p-0.5 rounded transition-colors hover:bg-ink/10">
                      <Trash2 size={10} className="text-ink/35" />
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
